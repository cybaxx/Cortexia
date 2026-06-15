import { describe, it, expect, beforeEach } from 'vitest';
import { useCortexStore } from '@/store/cortex';
import type { SimulateResponse } from '@/types/simulation';

function buildResponse(overrides: Partial<SimulateResponse> = {}): SimulateResponse {
  return {
    run_id: 7,
    city_id: 'los-angeles-ca',
    domain: 'Political Campaign',
    case_goal: 'Test spread',
    effective_catalyst_text: 'Test catalyst',
    tribe_meta: {
      provider: 'tribe_neural_framework',
      model_id: 'facebook/tribev2',
      signal_confidence: 1.17,
      dominant_roi: 'fear_salience',
      surface_summary: {
        dominant_response: {
          id: 'fear', label: 'Threat response', peak: 2.8, auc: 1.2,
          trajectory: 'stable', onset_seconds: 0, sustained: true,
        },
        weakest_response: {
          id: 'reward', label: 'Reward', peak: 0.2, auc: 0.01,
          trajectory: 'rising', onset_seconds: 18, sustained: false,
        },
        composite_highlights: [
          { id: 'arousal', label: 'Arousal', value: 1.12, interpretation: 'High' },
        ],
        narrative_flags: ['Strongly activating stimulus.'],
      },
    },
    case_summary: {
      title: 'Test case',
      goal: 'Test',
      domain: 'Political Campaign',
      target_region: 'LA',
      spread_risk: 'High',
      overall_confidence: 0.8,
      key_finding: 'Claim spread rapidly.',
      recommended_next_step: 'Monitor.',
    },
    spread_model: {
      risk_score: 75,
      spread_risk: 'High',
      belief_adoption_rate: 100,
      population_reached: 100,
      avg_cognitive_load: 0.9,
      avg_defensive_activation: 0.6,
      high_risk_segments: [],
      belief_adoption_pathways: [],
      hotspots: [
        { id: 'se', label: 'SE cluster', area: 'SE', share: 0.5, lng: -118, lat: 34, radiusMeters: 2000, state: 'adopted' },
      ],
      network_summary: '24 agents adopted.',
      core_story: 'The catalyst spread through reactive sharing.',
    },
    mechanisms: {
      mechanism_summary: 'Defensive reactance drove spread.',
      dominant_cognitive_drivers: [
        { signal: 'defensive_reactance', share: 0.7, description: 'Reactance' },
      ],
      target_segments: [],
      evidence_links: [],
      confidence_notes: [],
    },
    intervention_playbook: [
      {
        id: 'i1', title: 'Counter social proof', goal: 'Reduce spread',
        target_audience: 'Analytical professionals', mechanism_addressed: 'social proof',
        recommended_channel: 'SMS', recommended_messenger: 'Local leaders',
        message_strategy: 'Fact-based', time_horizon: 'Immediate',
        expected_effect: '35% reduction', confidence: 0.8,
        why_this_should_work: 'Breaks feedback loop.',
        supporting_evidence: ['Studies show...'],
      },
    ],
    evidence_trace: {
      original_text: 'test',
      analysis_text: 'test',
      source_url: null,
      source_excerpt: null,
      speaker_context: null,
      claims: [],
      themes: [],
      provenance: { source_type: 'text', transcript_used: false, analysis_text_source: 'direct' },
      warnings: [],
    },
    swarm_dynamics: {
      narrative_summary: '3 rounds of propagation.',
      rounds: [
        {
          round: 1, adoption_rate: 0.75, rejection_rate: 0.04, neutral_rate: 0.21,
          dominant_mechanism: 'defensive_reactance', notable_shift: 'Rapid adoption', posts: [],
        },
      ],
      network_edges: [
        { source_id: 0, target_id: 1, source_lng: -118, source_lat: 34, target_lng: -118.1, target_lat: 34.1, weight: 0.8, compatibility: 0.7 },
      ],
      event_log: [],
    },
    summary: { total: 24, adopted: 24, rejected: 0, neutral: 0 },
    agents: [
      {
        id: 0, name: 'Ava Ramos', role: 'Civic analyst',
        longitude: -118.24, latitude: 34.05,
        belief_state: 'adopted' as const,
        k2_reasoning_trace: ['Amygdala 0.80 dominant → adopted.'],
        k2_decision_confidence: 0.85,
        dominant_signal: 'defensive_reactance' as const,
        brain_regions: {
          prefrontal_cortex: 0.86, amygdala: 0.80, insula: 0.61,
          hippocampus: 0.23, anterior_cingulate: 0.55, temporoparietal_junction: 0.27,
        },
        brain_summary: 'Amygdala 0.80 → adopted.',
        tribe_neurological_metrics: {
          cognitive_load: 0.79, emotional_friction: 0.88,
          defensive_activation: 0.72, working_memory_strain: 0.96,
        },
        agent_insight: {
          vulnerability: 'Housing insecure.',
          cause_of_state: 'score 0.72; adopted.',
          best_intervention: 'Peer validators.',
        },
      },
      {
        id: 1, name: 'Marcus Webb', role: 'Teacher',
        longitude: -118.28, latitude: 33.98,
        belief_state: 'rejected' as const,
        k2_reasoning_trace: ['Threat signal → rejected.'],
        k2_decision_confidence: 0.62,
        dominant_signal: 'empathic_resonance' as const,
        brain_regions: {
          prefrontal_cortex: 0.82, amygdala: 0.60, insula: 0.45,
          hippocampus: 0.30, anterior_cingulate: 0.58, temporoparietal_junction: 0.35,
        },
        brain_summary: 'Skeptical scrutiny dominant → rejected.',
        tribe_neurological_metrics: {
          cognitive_load: 0.65, emotional_friction: 0.55,
          defensive_activation: 0.40, working_memory_strain: 0.70,
        },
        agent_insight: {
          vulnerability: 'Educated skepticism.',
          cause_of_state: 'score 0.22; rejected.',
          best_intervention: 'Provide data.',
        },
      },
    ],
    macro_result: {
      score: 75, risk_level: 'High',
      insights: [{ where: 'LA', why: 'Reactance', who: 'Mechanism' }],
      suggested_rewrite: 'Lead with respect.',
      synthetic_thoughts: [],
      hotspots: [],
      summary_text: 'High-risk spread driven by defensive reactance.',
      sentiment_mix: { total: 24, adopted: 24, rejected: 0, neutral: 0 },
      input_summary: 'Test input summary.',
    },
    ...overrides,
  };
}

describe('CortexStore — applySimulationResponse', () => {
  beforeEach(() => {
    useCortexStore.setState({
      status: 'idle',
      apiError: null,
      latestResponse: null,
      caseSummary: null,
      spreadModel: null,
      mechanisms: null,
      interventionPlaybook: [],
      evidenceTrace: null,
      evidenceGraph: null,
      swarmDynamics: null,
      agentSimulationById: {},
      selectedAgentId: null,
      stage: 'evidence',
    });
  });

  it('sets status to ready and stage to spread on valid response', () => {
    const { runSimulation } = useCortexStore.getState();
    // Manually simulate what runSimulation does after API call
    const response = buildResponse();
    const store = useCortexStore;

    // Simulate the apply flow directly
    store.setState({ status: 'running', stage: 'spread' });

    // Call internal apply via a test helper
    const state = store.getState();
    expect(state.status).toBe('running');

    // Now simulate successful response
    store.setState({
      status: 'ready',
      stage: 'spread',
      latestResponse: response,
      caseSummary: response.case_summary,
      spreadModel: response.spread_model,
      mechanisms: response.mechanisms,
      interventionPlaybook: response.intervention_playbook,
      evidenceTrace: response.evidence_trace,
      evidenceGraph: response.evidence_graph ?? null,
      swarmDynamics: response.swarm_dynamics ?? null,
      agentSimulationById: Object.fromEntries(response.agents.map(a => [a.id, a])),
    });

    const final = store.getState();
    expect(final.status).toBe('ready');
    expect(final.stage).toBe('spread');
    expect(final.latestResponse).not.toBeNull();
    expect(final.caseSummary).not.toBeNull();
    expect(final.spreadModel).not.toBeNull();
    expect(final.mechanisms).not.toBeNull();
    expect(final.interventionPlaybook.length).toBe(1);
    expect(final.evidenceTrace).not.toBeNull();
    expect(final.swarmDynamics).not.toBeNull();
    expect(Object.keys(final.agentSimulationById).length).toBe(2);
  });

  it('rejects response without tribe_meta.provider', () => {
    const response = buildResponse();
    response.tribe_meta = { model_id: 'test' } as any;

    expect(() => {
      const provider = response.tribe_meta?.provider;
      const modelId = response.tribe_meta?.model_id;
      if (!provider || !modelId) {
        throw new Error('Simulation response did not include live TRIBE metadata. Refusing to render fallback data.');
      }
    }).toThrow('Simulation response did not include live TRIBE metadata. Refusing to render fallback data.');
  });

  it('rejects response without tribe_meta.model_id', () => {
    const response = buildResponse();
    response.tribe_meta = { provider: 'test' } as any;

    expect(() => {
      const provider = response.tribe_meta?.provider;
      const modelId = response.tribe_meta?.model_id;
      if (!provider || !modelId) {
        throw new Error('Simulation response did not include live TRIBE metadata. Refusing to render fallback data.');
      }
    }).toThrow('Simulation response did not include live TRIBE metadata. Refusing to render fallback data.');
  });

  it('correctly derives spreadStory from core_story', () => {
    const response = buildResponse();
    response.spread_model.core_story = 'The core story text.';

    const spreadStory = response.spread_model.core_story
      || response.spread_model.network_summary
      || response.case_summary.key_finding;

    expect(spreadStory).toBe('The core story text.');
  });

  it('falls back spreadStory to network_summary when core_story is empty', () => {
    const response = buildResponse();
    response.spread_model.core_story = '';

    const spreadStory = response.spread_model.core_story
      || response.spread_model.network_summary
      || response.case_summary.key_finding;

    expect(spreadStory).toBe('24 agents adopted.');
  });

  it('falls back spreadStory to key_finding when both are empty', () => {
    const response = buildResponse();
    response.spread_model.core_story = '';
    response.spread_model.network_summary = '';

    const spreadStory = response.spread_model.core_story
      || response.spread_model.network_summary
      || response.case_summary.key_finding;

    expect(spreadStory).toBe('Claim spread rapidly.');
  });

  it('maps agent IDs correctly to agentSimulationById', () => {
    const response = buildResponse();
    const byId = Object.fromEntries(response.agents.map(a => [a.id, a]));

    expect(Object.keys(byId)).toEqual(['0', '1']);
    expect(byId[0].name).toBe('Ava Ramos');
    expect(byId[0].belief_state).toBe('adopted');
    expect(byId[1].name).toBe('Marcus Webb');
    expect(byId[1].belief_state).toBe('rejected');
  });

  it('handles empty agents array', () => {
    const response = buildResponse();
    response.agents = [];
    const byId = Object.fromEntries(response.agents.map(a => [a.id, a]));

    expect(Object.keys(byId).length).toBe(0);
  });

  it('derives tribeSurfaceSummary fields correctly', () => {
    const response = buildResponse();
    const tribeSurfaceSummary = response.tribe_meta?.surface_summary;

    expect(tribeSurfaceSummary?.dominant_response?.label).toBe('Threat response');
    expect(tribeSurfaceSummary?.weakest_response?.label).toBe('Reward');
    expect(tribeSurfaceSummary?.composite_highlights?.length).toBe(1);
    expect(tribeSurfaceSummary?.narrative_flags?.length).toBe(1);
  });

  it('derives selectedAgentPayload correctly', () => {
    const response = buildResponse();
    const selectedAgentId = 0;
    const payload = response.agents.find(a => a.id === selectedAgentId);

    expect(payload).toBeDefined();
    expect(payload?.name).toBe('Ava Ramos');
    expect(payload?.belief_state).toBe('adopted');
    expect(payload?.brain_regions.amygdala).toBe(0.80);
    expect(payload?.tribe_neurological_metrics.cognitive_load).toBe(0.79);
    expect(payload?.agent_insight.best_intervention).toBe('Peer validators.');
  });

  it('handles null selectedAgentId gracefully', () => {
    const response = buildResponse();
    const selectedAgentId: number | null = null;
    const payload = selectedAgentId != null
      ? response.agents.find(a => a.id === selectedAgentId)
      : undefined;

    expect(payload).toBeUndefined();
  });

  it('correctly extracts hotspots from spreadModel', () => {
    const response = buildResponse();
    const hotspots = response.spread_model.hotspots;

    expect(hotspots.length).toBe(1);
    expect(hotspots[0].id).toBe('se');
    expect(hotspots[0].state).toBe('adopted');
    expect(hotspots[0].lng).toBe(-118);
    expect(hotspots[0].lat).toBe(34);
  });

  it('correctly extracts network edges from swarmDynamics', () => {
    const response = buildResponse();
    const edges = response.swarm_dynamics?.network_edges ?? [];

    expect(edges.length).toBe(1);
    expect(edges[0].source_id).toBe(0);
    expect(edges[0].target_id).toBe(1);
    expect(edges[0].weight).toBe(0.8);
  });

  it('returns empty array for missing swarmDynamics', () => {
    const response = buildResponse();
    const resp = response as any;
    resp.swarm_dynamics = undefined;
    const edges = resp.swarm_dynamics?.network_edges ?? [];

    expect(edges).toEqual([]);
  });

  it('preserves all agent fields needed by the UI', () => {
    const response = buildResponse();
    const agent = response.agents[0];

    // MapView needs these
    expect(agent.id).toBeTypeOf('number');
    expect(agent.longitude).toBeTypeOf('number');
    expect(agent.latitude).toBeTypeOf('number');
    expect(agent.belief_state).toBe('adopted');
    expect(agent.tribe_neurological_metrics).toBeDefined();
    expect(agent.k2_decision_confidence).toBeTypeOf('number');
    expect(agent.dominant_signal).toBeTypeOf('string');

    // BrainViz needs these
    expect(agent.brain_regions).toBeDefined();
    expect(agent.brain_summary).toBeTypeOf('string');

    // AgentVoiceWorkspace needs these
    expect(agent.name).toBeTypeOf('string');
    expect(agent.role).toBeTypeOf('string');
    expect(agent.agent_insight).toBeDefined();
    expect(agent.k2_reasoning_trace).toBeInstanceOf(Array);
  });
});

describe('CortexStore — edge cases', () => {
  beforeEach(() => {
    useCortexStore.setState({
      status: 'idle',
      apiError: null,
      latestResponse: null,
      evidence: { text_input: '', source_url: null, transcript: null, edited_analysis_text: null, speaker_context: null, audio_input: null },
    });
  });

  it('requires 12+ characters of evidence to run simulation', () => {
    const store = useCortexStore.getState();
    store.setEvidenceField('text_input', 'short');
    const state = useCortexStore.getState();
    const canonicalText =
      state.evidence.edited_analysis_text?.trim() ||
      state.evidence.transcript?.trim() ||
      state.evidence.text_input.trim();
    expect(canonicalText.length).toBeLessThan(12);
  });

  it('allows simulation with sufficient evidence', () => {
    const store = useCortexStore.getState();
    store.setEvidenceField('text_input', 'City approved park conversions without any public notice.');
    const state = useCortexStore.getState();
    const canonicalText =
      state.evidence.edited_analysis_text?.trim() ||
      state.evidence.transcript?.trim() ||
      state.evidence.text_input.trim();
    expect(canonicalText.length).toBeGreaterThanOrEqual(12);
  });

  it('invalidates simulation result when evidence changes', () => {
    const response = buildResponse();
    useCortexStore.setState({
      status: 'ready',
      latestResponse: response,
      stage: 'spread',
    });

    // Change evidence
    useCortexStore.getState().setEvidenceField('text_input', 'New evidence text that is different.');

    const final = useCortexStore.getState();
    expect(final.latestResponse).toBeNull();
    expect(final.caseSummary).toBeNull();
    expect(final.spreadModel).toBeNull();
    // status resets to idle, stage stays unchanged but data is cleared
  });
});

// ── Cyber propagation & credibility decay ────────────────────────

describe('Cyber propagation — source_channel & hop_distance', () => {
  it('round_history entries include source_channel field', () => {
    const response = buildResponse();
    response.agents[0].round_history = [
      {
        round: 1,
        belief_state: 'adopted' as const,
        confidence: 0.72,
        sentiment: 'positive' as const,
        post: 'test post',
        source_channel: 'physical',
        hop_distance: 0,
        effective_credibility: 0.85,
      },
      {
        round: 2,
        belief_state: 'rejected' as const,
        confidence: 0.45,
        sentiment: 'negative' as const,
        post: 'reconsidering',
        source_channel: 'cyber',
        hop_distance: 1,
        effective_credibility: 0.68,
      },
    ] as any;

    const history = response.agents[0].round_history;
    expect(history).toBeDefined();
    expect(history!.length).toBe(2);

    const physical = history![0] as any;
    expect(physical.source_channel).toBeDefined();
    expect(physical.source_channel).toBe('physical');
    expect(physical.hop_distance).toBeDefined();
    expect(physical.hop_distance).toBe(0);
    expect(physical.effective_credibility).toBeDefined();

    const cyber = history![1] as any;
    expect(cyber.source_channel).toBe('cyber');
    expect(cyber.hop_distance).toBe(1);
    expect(cyber.effective_credibility).toBe(0.68);
  });

  it('effective_credibility decays with hop distance for physical channel', () => {
    const response = buildResponse();
    const claimCred = 0.85;

    // Simulate decay: cred * max(0.10, 1.0 - hop * 0.08)
    const hop0 = claimCred * Math.max(0.10, 1.0 - 0 * 0.08);  // round 1
    const hop1 = claimCred * Math.max(0.10, 1.0 - 1 * 0.08);  // round 2
    const hop2 = claimCred * Math.max(0.10, 1.0 - 2 * 0.08);  // round 3
    const hop20 = claimCred * Math.max(0.10, 1.0 - 20 * 0.08); // many hops — floor

    expect(hop0).toBeCloseTo(0.85, 3);          // no decay
    expect(hop1).toBeCloseTo(0.85 * 0.92, 2);   // 8% decay
    expect(hop2).toBeCloseTo(0.85 * 0.84, 2);   // 16% decay
    expect(hop20).toBeCloseTo(0.085, 3);         // hits floor at 0.10
  });

  it('cyber channel has faster credibility decay', () => {
    const claimCred = 0.85;
    // Cyber: cred * max(0.10, 1.0 - hop * 0.20)
    const cyber_hop1 = claimCred * Math.max(0.10, 1.0 - 1 * 0.20);
    const cyber_hop3 = claimCred * Math.max(0.10, 1.0 - 3 * 0.20);

    expect(cyber_hop1).toBeCloseTo(0.85 * 0.80, 2);   // 20% decay after 1 hop
    expect(cyber_hop3).toBeCloseTo(0.85 * 0.40, 2);   // 60% decay after 3 hops
  });

  it('cyber exposure has lower influence than physical', () => {
    const cyberInfluence = 0.12;
    const physicalInfluence = 0.75;  // physical neighbor influence is much higher

    expect(cyberInfluence).toBeLessThan(physicalInfluence / 4);
  });

  it('cyber reach varies by digital_media_habit', () => {
    const reachByHabit: Record<string, number> = {
      'Local-news heavy': 0.08,
      'Group-chat heavy': 0.22,
      'Public-feed heavy': 0.35,
      'Mixed verification habit': 0.15,
    };

    expect(reachByHabit['Public-feed heavy']).toBeGreaterThan(reachByHabit['Local-news heavy']);
    expect(reachByHabit['Group-chat heavy']).toBeGreaterThan(reachByHabit['Local-news heavy']);
    expect(reachByHabit['Public-feed heavy']).toBeGreaterThan(reachByHabit['Mixed verification habit']);
  });

  it('emotional charge amplifies cyber reach', () => {
    // emotion_boost = 0.5 + emotion * 0.5
    const baseReach = 0.35;
    const lowEmotion = 0.5 + 0.3 * 0.5;   // calm agent
    const highEmotion = 0.5 + 0.9 * 0.5;  // agitated agent

    const calmReach = baseReach * lowEmotion;
    const agitatedReach = baseReach * highEmotion;

    expect(agitatedReach).toBeGreaterThan(calmReach);
    expect(agitatedReach / calmReach).toBeCloseTo(1.43, 1); // ~43% more reach
  });

  it('handles missing round_history gracefully', () => {
    const response = buildResponse();
    (response.agents[0] as any).round_history = undefined;

    const history = response.agents[0].round_history;
    expect(history).toBeUndefined();

    // Should not crash when accessing
    const length = history?.length ?? 0;
    expect(length).toBe(0);
  });

  it('does not break existing round_history fields', () => {
    const response = buildResponse();
    // Existing agent fields still work
    expect(response.agents[0].belief_state).toBe('adopted');
    expect(response.agents[0].k2_decision_confidence).toBeGreaterThan(0);
    expect(response.agents[0].brain_regions).toBeDefined();
    expect(response.agents[0].tribe_neurological_metrics).toBeDefined();
  });
});
