import { X } from 'lucide-react';
import { Suspense, lazy, type CSSProperties } from 'react';
import { Slider } from '@/components/ui/slider';
import type { Agent } from '@/lib/agents';
import type { AgentSimulationPayload } from '@/types/simulation';
import { useCortexStore } from '@/store/cortex';

const BrainViz = lazy(() =>
  import('./BrainViz').then((module) => ({ default: module.BrainViz })),
);

const ParamRow = ({
  label,
  value,
  onChange,
  accentVar,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  accentVar: string;
}) => (
  <div className="space-y-1">
    <div className="flex justify-between font-mono text-[9px] text-text-secondary">
      <span className="uppercase tracking-wider">{label}</span>
      <span className="text-text-primary">{value.toFixed(2)}</span>
    </div>
    <Slider
      value={[value]}
      min={0}
      max={1}
      step={0.01}
      onValueChange={([v]) => onChange(v)}
      className="[&_.bg-primary]:bg-[var(--param-slider)]"
      style={{ ['--param-slider' as string]: `hsl(var(${accentVar}))` } as CSSProperties}
    />
  </div>
);

const K2ThinkTrace = ({ lines }: { lines: string[] }) => (
  <div className="rounded-[24px] border border-white/[0.08] bg-bg-deep/55 p-3 max-h-40 overflow-y-auto">
    <div className="mb-2 font-mono text-[9px] uppercase tracking-[0.12em] text-pastel-2/90">K2 Think trace</div>
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
}: {
  agent: Agent;
  x: number;
  y: number;
  onClose: () => void;
  payload?: AgentSimulationPayload;
}) => {
  const patchAgent = useCortexStore((s) => s.patchAgent);
  return (
    <div
      className="pointer-events-auto absolute z-50 w-[min(34rem,96vw)] max-h-[min(82vh,720px)] overflow-y-auto overscroll-contain rounded-[32px] border border-white/[0.12] p-4 shadow-[0_32px_120px_rgba(6,10,20,0.52)]"
      style={{
        left: Math.min(x + 12, (typeof window !== 'undefined' ? window.innerWidth : 720) - 560),
        top: y + 12,
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
        Each node is now simulated independently. The regional brain map below is generated from this agent&apos;s own
        TRIBE state, local context, and K2 decision path.
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

      <div className="mt-4 space-y-3">
        <ParamRow
          label="Cognitive load (local override)"
          value={agent.cognitiveLoad}
          onChange={(v) => patchAgent(agent.id, { cognitiveLoad: v })}
          accentVar="--pastel-1"
        />
        <ParamRow
          label="Emotional agitation (local override)"
          value={agent.emotionalAgitation}
          onChange={(v) => patchAgent(agent.id, { emotionalAgitation: v })}
          accentVar="--pastel-3"
        />
        <ParamRow
          label="Defensive posture (local override)"
          value={agent.defensivePosture}
          onChange={(v) => patchAgent(agent.id, { defensivePosture: v })}
          accentVar="--pastel-2"
        />
      </div>

      <div className="mt-3 border-t border-white/[0.06] pt-3 font-mono text-[9px] text-text-muted">
        ID 0x{agent.id.toString(16).padStart(4, '0')} · lat {agent.position[1].toFixed(3)} · lng{' '}
        {agent.position[0].toFixed(3)}
      </div>
    </div>
  );
};
