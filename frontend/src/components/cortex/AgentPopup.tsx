import { X } from 'lucide-react';
import type { CSSProperties } from 'react';
import { Slider } from '@/components/ui/slider';
import type { Agent } from '@/lib/agents';
import { useCortexStore } from '@/store/cortex';
import { BrainViz } from './BrainViz';

const ParamRow = ({
  label,
  value,
  onChange,
  color,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  color: string;
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
      style={{ ['--param-slider' as string]: color } as CSSProperties}
    />
  </div>
);

export const AgentPopup = ({ agent, x, y, onClose }: { agent: Agent; x: number; y: number; onClose: () => void }) => {
  const patchAgent = useCortexStore((s) => s.patchAgent);
  return (
    <div
      className="pointer-events-auto absolute z-50 w-[min(18rem,92vw)] max-h-[min(70vh,480px)] overflow-y-auto overscroll-contain rounded-sm border border-white/[0.08] p-3 shadow-2xl"
      style={{
        left: Math.min(x + 14, (typeof window !== 'undefined' ? window.innerWidth : 400) - 300),
        top: y + 14,
        backgroundColor: 'rgba(17, 24, 39, 0.96)',
        backdropFilter: 'blur(6px)',
      }}
      role="dialog"
      aria-label="Agent details"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <div className="text-[12px] text-text-primary font-medium">{agent.name}</div>
          <div className="font-mono text-[9px] text-text-muted uppercase tracking-wider">{agent.role}</div>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="font-mono text-[8px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm"
            style={{
              color:
                agent.state === 'strain' ? 'hsl(var(--accent-strain))' : agent.state === 'adopt' ? 'hsl(var(--accent-adopt))' : 'hsl(var(--text-secondary))',
              backgroundColor:
                agent.state === 'strain'
                  ? 'rgba(245,158,11,0.12)'
                  : agent.state === 'adopt'
                    ? 'rgba(59,130,246,0.14)'
                    : 'rgba(255,255,255,0.05)',
            }}
          >
            {agent.state}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-sm p-0.5 text-text-muted hover:bg-white/[0.08] hover:text-text-primary"
            aria-label="Close"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="mb-2 rounded-sm border border-white/[0.06] bg-bg-elevated/50 p-2">
        <BrainViz
          cognitiveLoad={agent.cognitiveLoad}
          emotionalAgitation={agent.emotionalAgitation}
          defensivePosture={agent.defensivePosture}
        />
      </div>

      <div className="space-y-2 mb-2">
        <ParamRow
          label="Cognitive load"
          value={agent.cognitiveLoad}
          onChange={(v) => patchAgent(agent.id, { cognitiveLoad: v })}
          color="hsl(var(--accent-strain))"
        />
        <ParamRow
          label="Emotional agitation"
          value={agent.emotionalAgitation}
          onChange={(v) => patchAgent(agent.id, { emotionalAgitation: v })}
          color="hsl(var(--accent-strain))"
        />
        <ParamRow
          label="Defensive posture"
          value={agent.defensivePosture}
          onChange={(v) => patchAgent(agent.id, { defensivePosture: v })}
          color="hsl(var(--accent-adopt))"
        />
      </div>

      <div className="mt-2 pt-2 border-t border-white/[0.06] font-mono text-[8px] text-text-muted">
        ID 0x{agent.id.toString(16).padStart(4, '0')} · lat {agent.position[1].toFixed(3)} · lng {agent.position[0].toFixed(3)}
      </div>
    </div>
  );
};
