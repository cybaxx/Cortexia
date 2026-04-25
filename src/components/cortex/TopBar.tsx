import { useCortexStore } from '@/store/cortex';

export const TopBar = () => {
  const status = useCortexStore((s) => s.status);
  return (
    <header className="absolute top-0 left-0 right-0 h-12 bg-bg-surface border-b border-white/[0.08] flex items-center justify-between px-4 z-30">
      <div className="flex items-center gap-3">
        <span className="text-text-primary text-[14px] font-medium tracking-tight">Cortexia</span>
        <span className="h-4 w-px bg-white/10" />
        <span className="font-mono text-[10px] text-text-secondary uppercase tracking-wider">
          Los Angeles · Synthetic Population
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span
          className={`h-1.5 w-1.5 rounded-full ${status === 'running' ? 'bg-accent-adopt animate-pulse' : 'bg-accent-adopt/70'}`}
        />
        <span className="font-mono text-[10px] text-text-secondary uppercase tracking-wider">
          {status === 'running' ? 'Running · Catalyst Injected' : 'Idle — Awaiting Catalyst'}
        </span>
      </div>
    </header>
  );
};
