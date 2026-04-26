"""LangGraph-driven multi-agent simulation loop.

This module adds an event-driven interaction layer on top of an existing
persona-generation pipeline. Each agent sees:

- the global scenario
- its own JSON profile
- only the log entries authored by directly connected agents

The graph cycles until ``tick >= max_ticks``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - optional at import time for example-only usage
    ChatOpenAI = None  # type: ignore[assignment]


ActionType = Literal["talk_to_agent", "post_public", "do_nothing"]


class AgentAction(BaseModel):
    """Structured action returned by the per-agent reasoning layer."""

    author_id: str = Field(description="The agent id authoring this action.")
    action_type: ActionType = Field(
        description="One of: talk_to_agent, post_public, do_nothing."
    )
    content: str = Field(
        default="",
        description="The outward message content. Leave blank only for do_nothing.",
    )
    target_agent_id: str | None = Field(
        default=None,
        description="Required when action_type is talk_to_agent.",
    )
    rationale: str = Field(
        default="",
        description="Brief internal reason for taking the action.",
    )


class SimulationState(TypedDict):
    """Global simulation state carried by LangGraph."""

    scenario: str
    agents: dict[str, dict[str, Any]]
    global_message_log: list[BaseMessage]
    tick: int
    max_ticks: int
    pending_actions: list[dict[str, Any]]
    scenario_initialized: bool


class AgentDecisionEngine(Protocol):
    """Swappable decision layer for agent reasoning."""

    def decide(
        self,
        *,
        agent_id: str,
        agent_profile: dict[str, Any],
        scenario: str,
        visible_messages: list[BaseMessage],
        tick: int,
    ) -> AgentAction:
        ...


def _connections_for_agent(agent_profile: dict[str, Any]) -> list[str]:
    """Extract adjacency from common JSON layouts."""

    raw = (
        agent_profile.get("connections")
        or agent_profile.get("edges")
        or agent_profile.get("neighbors")
        or []
    )
    connections: list[str] = []

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                connections.append(item)
            elif isinstance(item, dict):
                target = item.get("target_agent_id") or item.get("target") or item.get("id")
                if isinstance(target, str):
                    connections.append(target)
    elif isinstance(raw, dict):
        connections.extend(str(key) for key, enabled in raw.items() if enabled)

    return connections


def _visible_messages_for_agent(
    agent_id: str,
    agents: dict[str, dict[str, Any]],
    message_log: list[BaseMessage],
) -> list[BaseMessage]:
    """Return only log entries authored by directly connected agents."""

    profile = agents[agent_id]
    direct_neighbors = set(_connections_for_agent(profile))
    visible: list[BaseMessage] = []

    for message in message_log:
        author = message.name or message.additional_kwargs.get("author_id")
        if author in direct_neighbors:
            visible.append(message)

    return visible


def _serialize_messages_for_prompt(messages: list[BaseMessage]) -> str:
    if not messages:
        return "[]"

    payload: list[dict[str, Any]] = []
    for message in messages:
        payload.append(
            {
                "author_id": message.name or message.additional_kwargs.get("author_id"),
                "tick": message.additional_kwargs.get("tick"),
                "action_type": message.additional_kwargs.get("action_type"),
                "target_agent_id": message.additional_kwargs.get("target_agent_id"),
                "content": message.content,
            }
        )
    return json.dumps(payload, indent=2, ensure_ascii=True)


@dataclass
class LangChainAgentDecisionEngine:
    """LLM-backed agent decision layer using LangChain-compatible models."""

    llm: Any

    def __post_init__(self) -> None:
        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are simulating one person in a social propagation model. "
                        "You must decide one outward action for the current tick. "
                        "Use only the provided scenario, profile, and visible neighbor messages. "
                        "Do not invent hidden observations. "
                        "Return a structured action."
                    ),
                ),
                (
                    "human",
                    (
                        "Tick: {tick}\n"
                        "Scenario:\n{scenario}\n\n"
                        "Agent ID: {agent_id}\n"
                        "Agent profile JSON:\n{agent_profile_json}\n\n"
                        "Visible neighbor-authored log entries:\n{visible_messages_json}\n\n"
                        "Rules:\n"
                        "- If you talk to someone, choose only from your explicit connections.\n"
                        "- If you have no reason to speak, choose do_nothing.\n"
                        "- Keep public posts concise.\n"
                    ),
                ),
            ]
        )
        if hasattr(self.llm, "with_structured_output"):
            self._structured_llm = self.llm.with_structured_output(AgentAction)
        else:  # pragma: no cover - intended for alternate adapters
            self._structured_llm = None

    def decide(
        self,
        *,
        agent_id: str,
        agent_profile: dict[str, Any],
        scenario: str,
        visible_messages: list[BaseMessage],
        tick: int,
    ) -> AgentAction:
        prompt_value = self._prompt.invoke(
            {
                "tick": tick,
                "scenario": scenario,
                "agent_id": agent_id,
                "agent_profile_json": json.dumps(agent_profile, indent=2, ensure_ascii=True),
                "visible_messages_json": _serialize_messages_for_prompt(visible_messages),
            }
        )

        if self._structured_llm is None:  # pragma: no cover
            raw = self.llm.invoke(prompt_value.to_messages())
            text = getattr(raw, "content", raw)
            return AgentAction.model_validate_json(text)

        result = self._structured_llm.invoke(prompt_value.to_messages())
        action = result if isinstance(result, AgentAction) else AgentAction.model_validate(result)

        if not action.author_id:
            action.author_id = agent_id
        if action.action_type == "talk_to_agent" and not action.target_agent_id:
            raise ValueError(f"Agent {agent_id} selected talk_to_agent without target_agent_id.")

        return action


@dataclass
class RuleBasedDemoDecisionEngine:
    """Local deterministic engine for the runnable example."""

    def decide(
        self,
        *,
        agent_id: str,
        agent_profile: dict[str, Any],
        scenario: str,
        visible_messages: list[BaseMessage],
        tick: int,
    ) -> AgentAction:
        visible_authors = [message.name or "" for message in visible_messages]
        visible_text = " ".join(str(message.content) for message in visible_messages).lower()
        connections = _connections_for_agent(agent_profile)

        if tick == 0:
            if agent_id == "A":
                return AgentAction(
                    author_id="A",
                    action_type="post_public",
                    content=f"I just saw this scenario: {scenario[:90]}",
                    rationale="Seed the rumor into the network.",
                )
            if agent_id == "B":
                return AgentAction(
                    author_id="B",
                    action_type="talk_to_agent",
                    target_agent_id="C",
                    content="Have you heard this claim? Someone in my network is pushing it.",
                    rationale="Relay the new information to a direct connection.",
                )
            return AgentAction(
                author_id=agent_id,
                action_type="do_nothing",
                content="",
                rationale="No visible signal yet from direct contacts.",
            )

        if agent_id == "A" and "B" in visible_authors:
            return AgentAction(
                author_id="A",
                action_type="talk_to_agent",
                target_agent_id="B",
                content="What are people saying back to you?",
                rationale="Follow up through the only shared bridge.",
            )

        if agent_id == "C" and "B" in visible_authors and "heard this claim" in visible_text:
            return AgentAction(
                author_id="C",
                action_type="talk_to_agent",
                target_agent_id="B",
                content="I had not seen that directly. Who is spreading it?",
                rationale="React only to B because C cannot directly observe A.",
            )

        return AgentAction(
            author_id=agent_id,
            action_type="do_nothing",
            content="",
            rationale="No new neighbor message changed my stance this tick.",
        )


def environment_setup_node(state: SimulationState) -> dict[str, Any]:
    """Inject the initial scenario into the environment once."""

    if state.get("scenario_initialized"):
        return {}

    setup_message = SystemMessage(
        content=state["scenario"],
        name="environment",
        additional_kwargs={
            "author_id": "environment",
            "tick": state["tick"],
            "action_type": "scenario_injection",
        },
    )
    updated_log = list(state["global_message_log"])
    updated_log.append(setup_message)
    return {
        "global_message_log": updated_log,
        "scenario_initialized": True,
        "pending_actions": [],
    }


def make_agent_step_node(decision_engine: AgentDecisionEngine):
    """Create the core per-agent decision node."""

    def agent_step_node(state: SimulationState) -> dict[str, Any]:
        pending_actions: list[dict[str, Any]] = []

        for agent_id, agent_profile in sorted(state["agents"].items()):
            visible_messages = _visible_messages_for_agent(
                agent_id,
                state["agents"],
                state["global_message_log"],
            )
            action = decision_engine.decide(
                agent_id=agent_id,
                agent_profile=agent_profile,
                scenario=state["scenario"],
                visible_messages=visible_messages,
                tick=state["tick"],
            )
            pending_actions.append(action.model_dump())

        return {"pending_actions": pending_actions}

    return agent_step_node


def environment_routing_node(state: SimulationState) -> dict[str, Any]:
    """Commit agent actions into the global environment log."""

    next_log = list(state["global_message_log"])
    for action_dict in state.get("pending_actions", []):
        action = AgentAction.model_validate(action_dict)
        content = action.content.strip()
        if action.action_type == "do_nothing" and not content:
            content = "[no outward action]"

        next_log.append(
            AIMessage(
                content=content,
                name=action.author_id,
                additional_kwargs={
                    "author_id": action.author_id,
                    "tick": state["tick"],
                    "action_type": action.action_type,
                    "target_agent_id": action.target_agent_id,
                    "rationale": action.rationale,
                },
            )
        )

    return {
        "global_message_log": next_log,
        "tick": state["tick"] + 1,
        "pending_actions": [],
    }


def _should_continue(state: SimulationState) -> Literal["agent_step_node", "__end__"]:
    return "agent_step_node" if state["tick"] < state["max_ticks"] else "__end__"


def build_simulation_graph(decision_engine: AgentDecisionEngine):
    """Build and compile the LangGraph simulation."""

    graph = StateGraph(SimulationState)
    graph.add_node("environment_setup_node", environment_setup_node)
    graph.add_node("agent_step_node", make_agent_step_node(decision_engine))
    graph.add_node("environment_routing_node", environment_routing_node)

    graph.add_edge(START, "environment_setup_node")
    graph.add_edge("environment_setup_node", "agent_step_node")
    graph.add_edge("agent_step_node", "environment_routing_node")
    graph.add_conditional_edges(
        "environment_routing_node",
        _should_continue,
        {
            "agent_step_node": "agent_step_node",
            "__end__": END,
        },
    )

    return graph.compile()


def make_chat_openai_decision_engine(
    *,
    model: str = "gpt-4o-mini",
    temperature: float = 0.2,
    **kwargs: Any,
) -> LangChainAgentDecisionEngine:
    """Convenience constructor for production use."""

    if ChatOpenAI is None:  # pragma: no cover
        raise ImportError(
            "langchain_openai is not installed. Add it to the environment before "
            "constructing a ChatOpenAI-backed decision engine."
        )
    llm = ChatOpenAI(model=model, temperature=temperature, **kwargs)
    return LangChainAgentDecisionEngine(llm=llm)


def _demo_agents() -> dict[str, dict[str, Any]]:
    return {
        "A": {
            "id": "A",
            "name": "Agent A",
            "demographics": {"age": 29, "role": "teacher"},
            "psychology": {"openness": 0.61, "neuroticism": 0.42},
            "location": {"city": "Los Angeles", "lat": 34.0522, "lng": -118.2437},
            "connections": ["B"],
        },
        "B": {
            "id": "B",
            "name": "Agent B",
            "demographics": {"age": 41, "role": "nurse"},
            "psychology": {"openness": 0.53, "neuroticism": 0.58},
            "location": {"city": "Los Angeles", "lat": 34.0470, "lng": -118.2500},
            "connections": ["A", "C"],
        },
        "C": {
            "id": "C",
            "name": "Agent C",
            "demographics": {"age": 35, "role": "mechanic"},
            "psychology": {"openness": 0.34, "neuroticism": 0.44},
            "location": {"city": "Los Angeles", "lat": 34.0395, "lng": -118.2580},
            "connections": ["B"],
        },
    }


def _print_demo_summary(final_state: SimulationState) -> None:
    print("\n=== FINAL GLOBAL MESSAGE LOG ===")
    for message in final_state["global_message_log"]:
        author = message.name or message.additional_kwargs.get("author_id")
        tick = message.additional_kwargs.get("tick")
        action_type = message.additional_kwargs.get("action_type")
        target = message.additional_kwargs.get("target_agent_id")
        target_suffix = f" -> {target}" if target else ""
        print(f"[tick={tick}] {author} [{action_type}{target_suffix}]: {message.content}")

    print("\n=== LOCAL OBSERVATION WINDOWS ===")
    for agent_id in sorted(final_state["agents"]):
        visible = _visible_messages_for_agent(
            agent_id,
            final_state["agents"],
            final_state["global_message_log"],
        )
        seen_authors = [message.name or "unknown" for message in visible]
        print(f"{agent_id} can see authors: {seen_authors}")

    print(
        "\nNotice: Agent C only reacts to Agent B's relay. "
        "C never directly observes A because there is no A-C edge."
    )


if __name__ == "__main__":
    demo_state: SimulationState = {
        "scenario": (
            "A neighborhood Facebook post claims city hall quietly approved a controversial "
            "policy and urges residents to share it before it gets deleted."
        ),
        "agents": _demo_agents(),
        "global_message_log": [],
        "tick": 0,
        "max_ticks": 3,
        "pending_actions": [],
        "scenario_initialized": False,
    }

    demo_graph = build_simulation_graph(RuleBasedDemoDecisionEngine())
    final = demo_graph.invoke(demo_state)
    _print_demo_summary(final)

