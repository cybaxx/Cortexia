import type { Agent } from '@/lib/agents';

const Bar = ({ label, value, color }: { label: string; value: number; color: string }) => (
  <div>
    <div className="flex justify-between font-mono text-[9px] text-text-secondary mb-0.5">
      <span className="uppercase tracking-wider">{label}</span>
      <span className="text-text-primary">{value.toFixed(2)}</span>
    </div>
    <div className="h-1 w-full bg-bg-elevated rounded-sm overflow-hidden">
      <div className="h-full rounded-sm" style={{ width: `${value * 100}%`, backgroundColor: color }} />
    </div>
  </div>
);

export const AgentPopup = ({
  agent,
  x,
  y,
}: {
  agent: Agent;
  x: number;
  y: number;
}) => (
  <div
    className="pointer-events-none absolute z-40 w-[220px] rounded-sm border border-white/[0.08] p-3 shadow-2xl"
    style={{
      left: x + 14,
      top: y + 14,
      backgroundColor: 'rgba(17, 24, 39, 0.95)',
      backdropFilter: 'blur(6px)',
    }}
  >
    <div className="flex items-center justify-between mb-2">
      <div>
        <div className="text-[12px] text-text-primary font-medium">{agent.name}</div>
        <div className="font-mono text-[9px] text-text-muted uppercase tracking-wider">{agent.role}</div>
      </div>
      <span
        className="font-mono text-[8px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm"
        style={{
          color: agent.state === 'strain' ? 'hsl(var(--accent-strain))' : agent.state === 'adopt' ? 'hsl(var(--accent-adopt))' : 'hsl(var(--text-secondary))',
          backgroundColor:
            agent.state === 'strain' ? 'rgba(245,158,11,0.12)' : agent.state === 'adopt' ? 'rgba(59,130,246,0.14)' : 'rgba(255,255,255,0.05)',
        }}
      >
        {agent.state}
      </span>
    </div>
    <div className="space-y-1.5">
      <Bar label="Cognitive Load" value={agent.cognitiveLoad} color="hsl(var(--accent-strain))" />
      <Bar label="Emotional Agitation" value={agent.emotionalAgitation} color="hsl(var(--accent-strain))" />
      <Bar label="Defensive Posture" value={agent.defensivePosture} color="hsl(var(--accent-adopt))" />
    </div>
    <div className="mt-2 pt-2 border-t border-white/[0.06] font-mono text-[8px] text-text-muted">
      ID 0x{agent.id.toString(16).padStart(4, '0')} · lat {agent.position[1].toFixed(3)} · lng {agent.position[0].toFixed(3)}
    </div>
  </div>
);
