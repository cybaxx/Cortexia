import { AudioLines, Loader2, Send, X } from 'lucide-react';
import { Suspense, lazy, useEffect, useState } from 'react';
import type { Agent } from '@/lib/agents';
import { getAgentConversationHistory, postAgentConversation } from '@/lib/api/simulate';
import type { AgentConversationMessage, AgentSimulationPayload } from '@/types/simulation';

const BrainViz = lazy(() =>
  import('./BrainViz').then((module) => ({ default: module.BrainViz })),
);

const K2ThinkTrace = ({ lines }: { lines: string[] }) => (
  <div className="rounded-[24px] border border-white/[0.08] bg-bg-deep/55 p-3 max-h-40 overflow-y-auto">
    <div className="mb-2 font-mono text-[9px] uppercase tracking-[0.12em] text-pastel-2/90">Interpretation of neural response model</div>
    <ol className="list-decimal list-inside space-y-1.5 font-mono text-[10px] text-text-secondary leading-relaxed">
      {lines.length === 0 ? (
        <li className="text-text-muted">No reasoning lines returned for this agent.</li>
      ) : (
        lines.map((line, i) => (
          <li key={i} className="pl-0.5">
            {line}
          </li>
        ))
      )}
    </ol>
  </div>
);

export const AgentInspectionModal = ({
  agent,
  x,
  y,
  onClose,
  payload,
  runId,
}: {
  agent: Agent;
  x: number;
  y: number;
  onClose: () => void;
  payload?: AgentSimulationPayload;
  runId?: number;
}) => {
  const [messages, setMessages] = useState<AgentConversationMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadHistory() {
      if (!runId || !payload) return;
      setLoadingHistory(true);
      try {
        const history = await getAgentConversationHistory(runId, payload.id);
        if (!cancelled) setMessages(history);
      } catch {
        if (!cancelled) setMessages([]);
      } finally {
        if (!cancelled) setLoadingHistory(false);
      }
    }
    void loadHistory();
    return () => {
      cancelled = true;
    };
  }, [payload, runId]);

  async function sendMessage() {
    if (!runId || !payload || !draft.trim() || sending) return;
    setSending(true);
    try {
      const reply = await postAgentConversation(runId, payload.id, draft.trim());
      setMessages((current) => [...current, reply]);
      setDraft('');
      if (reply.audio_url) {
        const audio = new Audio(reply.audio_url);
        void audio.play().catch(() => undefined);
      }
    } finally {
      setSending(false);
    }
  }

  return (
    <div
      className="pointer-events-auto absolute left-1/2 top-6 z-50 w-[min(34rem,calc(100%-3rem))] max-h-[calc(100%-3rem)] -translate-x-1/2 overflow-y-auto overscroll-contain rounded-[32px] border border-white/[0.12] p-4 shadow-[0_32px_120px_rgba(6,10,20,0.52)]"
      style={{
        background:
          'linear-gradient(180deg, rgba(18,26,36,0.97) 0%, rgba(14,20,30,0.98) 100%)',
        backdropFilter: 'blur(14px)',
      }}
      role="dialog"
      aria-label="Agent inspection"
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <div className="text-[15px] font-semibold text-text-primary">{agent.name}</div>
          <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">{agent.role}</div>
        </div>
        <div className="flex items-center gap-1.5">
          {payload && (
            <span className="rounded-full border border-white/[0.1] bg-white/[0.05] px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.12em] text-pastel-2/95">
              {payload.belief_state} · {(payload.k2_decision_confidence * 100).toFixed(0)}%
            </span>
          )}
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1 text-text-muted hover:bg-white/[0.08] hover:text-text-primary"
            aria-label="Close"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="mb-3 rounded-[22px] border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-[10px] font-mono text-text-muted">
        Each node is simulated independently. TRIBE provides the base neural state, then Cortexia calibrates it through
        role, demographics, social context, and local network pressure to produce the outcome you see below.
      </div>

      <div className="mb-3 rounded-[28px] border border-white/[0.08] bg-bg-elevated/35 p-3">
        <Suspense
          fallback={
            <div className="rounded-[24px] border border-white/[0.08] bg-bg-deep/40 p-6 text-sm text-text-muted">
              Loading neural view…
            </div>
          }
        >
          <BrainViz
            tribeMetrics={payload?.tribe_neurological_metrics ?? null}
            regions={payload?.brain_regions ?? null}
            dominantSignal={payload?.dominant_signal}
            summary={payload?.brain_summary}
          />
        </Suspense>
      </div>

      {payload && <K2ThinkTrace lines={payload.k2_reasoning_trace} />}

      {payload && (
        <div className="mt-3 grid gap-3">
          {payload.demographics && (
            <div className="rounded-[22px] border border-white/[0.08] bg-white/[0.04] p-3">
              <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-text-muted">Demographic profile</div>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">{payload.demographics.summary}</p>
              <div className="mt-3 flex flex-wrap gap-2 font-mono text-[9px] uppercase tracking-[0.1em] text-text-muted">
                <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-1">
                  age {payload.demographics.age_years}
                </span>
                <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-1">
                  {payload.demographics.education_level}
                </span>
                <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-1">
                  {payload.demographics.income_band}
                </span>
                <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-1">
                  {payload.demographics.housing_status}
                </span>
                <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-1">
                  {payload.demographics.language_profile}
                </span>
                <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-1">
                  {payload.demographics.community_tenure}
                </span>
                <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-1">
                  {payload.demographics.caregiving_load}
                </span>
                <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-1">
                  {payload.demographics.digital_media_habit}
                </span>
              </div>
            </div>
          )}
          <div className="rounded-[22px] border border-white/[0.08] bg-white/[0.04] p-3">
            <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-text-muted">Vulnerability</div>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">{payload.agent_insight.vulnerability}</p>
          </div>
          <div className="rounded-[22px] border border-white/[0.08] bg-white/[0.04] p-3">
            <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-text-muted">Why this state formed</div>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">{payload.agent_insight.cause_of_state}</p>
          </div>
          <div className="rounded-[22px] border border-white/[0.08] bg-white/[0.04] p-3">
            <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-text-muted">Best intervention</div>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">{payload.agent_insight.best_intervention}</p>
          </div>
          {payload.round_history && payload.round_history.length > 0 && (
            <div className="rounded-[22px] border border-white/[0.08] bg-white/[0.04] p-3">
              <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-text-muted">Propagation timeline</div>
              <div className="mt-3 space-y-2">
                {payload.round_history.map((item) => (
                  <div key={`${payload.id}-round-${item.round}`} className="rounded-[16px] border border-white/[0.06] bg-bg-deep/45 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-xs font-medium text-text-primary">
                          {item.phase_label ?? `Round ${item.round}`}
                        </div>
                        <div className="mt-1 text-[11px] text-text-muted">Round {item.round}</div>
                      </div>
                      <div className="text-right text-[11px] text-text-muted">
                        <div>
                          {item.belief_state} · {(item.confidence * 100).toFixed(0)}%
                        </div>
                        {item.confidence_delta != null && (
                          <div className={item.confidence_delta >= 0 ? 'text-pastel-2/90' : 'text-pastel-4/90'}>
                            {item.confidence_delta >= 0 ? '+' : ''}
                            {(item.confidence_delta * 100).toFixed(0)} pts
                          </div>
                        )}
                      </div>
                    </div>
                    {item.trigger && (
                      <div className="mt-2 inline-flex rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.12em] text-text-muted">
                        {item.trigger}
                      </div>
                    )}
                    <p className="mt-2 text-xs leading-relaxed text-text-secondary">{item.post}</p>
                    {item.change_summary && (
                      <p className="mt-2 text-[11px] leading-relaxed text-text-muted">{item.change_summary}</p>
                    )}
                    {(item.supportive_pressure != null || item.skeptical_pressure != null || item.messenger_alignment != null) && (
                      <div className="mt-3 flex flex-wrap gap-2 font-mono text-[9px] uppercase tracking-[0.1em] text-text-muted">
                        {item.supportive_pressure != null && (
                          <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-1">
                            support {item.supportive_pressure.toFixed(2)}
                          </span>
                        )}
                        {item.skeptical_pressure != null && (
                          <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-1">
                            pushback {item.skeptical_pressure.toFixed(2)}
                          </span>
                        )}
                        {item.messenger_alignment != null && (
                          <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-1">
                            fit {item.messenger_alignment.toFixed(2)}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="rounded-[22px] border border-white/[0.08] bg-white/[0.04] p-3">
            <div className="mb-3 flex items-center gap-2">
              <AudioLines className="h-4 w-4 text-pastel-2" />
              <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-text-muted">Talk to this agent</div>
            </div>
            <div className="max-h-44 space-y-2 overflow-y-auto rounded-[18px] border border-white/[0.06] bg-bg-deep/45 p-3">
              {loadingHistory && <div className="text-xs text-text-secondary">Loading prior turns…</div>}
              {!loadingHistory && messages.length === 0 && (
                <div className="text-xs leading-relaxed text-text-secondary">
                  Ask what this person believes, what would change their mind, or why they reacted this way. Cortexia will answer in-character and speak the reply.
                </div>
              )}
              {messages.map((message) => (
                <div key={message.id} className="space-y-1">
                  <div className="text-[11px] text-pastel-1">You: {message.user_message}</div>
                  <div className="text-[11px] leading-relaxed text-text-secondary">{message.agent_reply}</div>
                  {message.audio_url && (
                    <audio controls className="w-full">
                      <source src={message.audio_url} type="audio/mpeg" />
                    </audio>
                  )}
                </div>
              ))}
            </div>
            <div className="mt-3 flex items-end gap-2">
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Ask this person what they think, what makes them trust or doubt the claim, or what would change their mind."
                className="min-h-[84px] flex-1 rounded-[18px] border border-white/[0.08] bg-bg-deep/55 px-3 py-2 text-sm text-text-primary"
              />
              <button
                type="button"
                onClick={() => void sendMessage()}
                disabled={!runId || !payload || sending || !draft.trim()}
                className="inline-flex h-11 items-center justify-center rounded-[16px] border border-pastel-2/25 bg-[hsl(var(--pastel-2)/0.10)] px-3 text-sm text-text-primary disabled:opacity-40"
              >
                {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
