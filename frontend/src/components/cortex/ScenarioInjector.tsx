import { useCortexStore } from '@/store/cortex';

const Memo = ({
  id,
  title,
  subtitle,
  tone,
}: {
  id: 'A' | 'B';
  title: string;
  subtitle: string;
  tone: 'adopt' | 'strain';
}) => {
  const selected = useCortexStore((s) => s.selectedMemo);
  const setMemo = useCortexStore((s) => s.setMemo);
  const isSel = selected === id;
  const badge = tone === 'adopt' ? 'bg-accent-adopt/15 text-accent-adopt' : 'bg-accent-strain/15 text-accent-strain';
  return (
    <button
      onClick={() => setMemo(id)}
      className={`w-full text-left rounded-sm border bg-bg-elevated px-3 py-3 transition-colors ${
        isSel ? 'border-accent-adopt/50' : 'border-white/[0.06] hover:border-white/[0.12]'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-text-muted">Catalyst</span>
        <span className={`font-mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm ${badge}`}>
          Memo {id}
        </span>
      </div>
      <div className="text-[13px] text-text-primary font-medium">{title}</div>
      <div className="text-[11px] text-text-secondary mt-1 leading-snug">{subtitle}</div>
    </button>
  );
};

export const ScenarioInjector = () => {
  const setStatus = useCortexStore((s) => s.setStatus);
  const status = useCortexStore((s) => s.status);
  const memo = useCortexStore((s) => s.selectedMemo);
  const pushLog = useCortexStore((s) => s.pushLog);

  return (
    <aside className="absolute top-12 left-0 bottom-16 w-[300px] bg-bg-surface border-r border-white/[0.08] z-20 flex flex-col">
      <div className="px-4 py-3 border-b border-white/[0.08]">
        <h2 className="font-mono text-[11px] uppercase tracking-[0.14em] text-text-secondary">
          CATALYST CONFIGURATION
        </h2>
        <p className="font-mono text-[9px] text-text-muted mt-1">Select media to inject</p>
      </div>

      <div className="px-4 py-4 space-y-3">
        <Memo
          id="A"
          tone="adopt"
          title="Policy Memo A"
          subtitle="Affordable transit expansion · neutral framing, civic appeals."
        />
        <Memo
          id="B"
          tone="strain"
          title="Policy Memo B"
          subtitle="Property-tax restructuring · loss-frame emphasis, urgency cues."
        />
      </div>

      <div className="px-4 py-3 border-t border-white/[0.08] mt-auto">
        <div className="font-mono text-[9px] uppercase tracking-wider text-text-muted mb-2">Cohort</div>
        <div className="grid grid-cols-3 gap-1.5">
          {['Adults', 'Voters', 'Drivers'].map((c) => (
            <span
              key={c}
              className="font-mono text-[9px] text-text-secondary text-center py-1 rounded-sm bg-bg-elevated border border-white/[0.06]"
            >
              {c}
            </span>
          ))}
        </div>

        <button
          onClick={() => {
            setStatus('running');
            pushLog({ kind: 'info', text: `Catalyst injected: Policy Memo ${memo ?? 'A'}.` });
          }}
          disabled={!memo}
          className="mt-3 w-full font-mono text-[11px] uppercase tracking-[0.14em] py-2.5 rounded-sm bg-accent-adopt/15 text-accent-adopt border border-accent-adopt/30 hover:bg-accent-adopt/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Inject Catalyst
        </button>
        <button
          onClick={() => setStatus('idle')}
          className="mt-2 w-full font-mono text-[11px] uppercase tracking-[0.14em] py-2 rounded-sm bg-bg-elevated text-text-secondary border border-white/[0.06] hover:border-white/[0.14] transition-colors"
        >
          Reset Sandbox
        </button>
        <div className="mt-3 font-mono text-[9px] text-text-muted">
          Status: <span className="text-text-secondary">{status}</span>
        </div>
      </div>
    </aside>
  );
};
