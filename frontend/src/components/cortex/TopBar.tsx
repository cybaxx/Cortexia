import { useCortexStore } from '@/store/cortex';

const PHASE_LABEL: Record<string, string> = {
  idle: 'Ready',
  initializing: 'Initializing agents',
  propagating: 'Propagating signal',
  report: 'Generating report',
  complete: 'Report ready',
};

export const TopBar = () => {
  const status = useCortexStore((s) => s.status);
  const phase = useCortexStore((s) => s.injectPhase);
  const useCase = useCortexStore((s) => s.useCase);

  const chip =
    status === 'running' || ['initializing', 'propagating', 'report'].includes(phase)
      ? PHASE_LABEL[phase] ?? 'Running'
      : phase === 'complete'
        ? 'Report ready'
        : 'Ready';

  return (
    <header className="absolute top-0 left-0 right-0 h-12 bg-bg-surface border-b border-white/[0.08] flex items-center justify-between px-4 z-30">
      <div className="flex items-center gap-3 min-w-0">
        <span className="text-text-primary text-[14px] font-medium tracking-tight shrink-0">Cortexia</span>
        <span className="h-4 w-px bg-white/10 shrink-0" />
        <span className="font-mono text-[10px] text-text-secondary uppercase tracking-wider truncate">
          Los Angeles · {useCase ? 'Synthetic run' : 'Select use case'}
        </span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            status === 'running' || ['initializing', 'propagating', 'report'].includes(phase)
              ? 'bg-accent-adopt animate-pulse'
              : 'bg-emerald-500/80'
          }`}
        />
        <span className="font-mono text-[10px] text-text-secondary uppercase tracking-wider hidden sm:inline">
          {chip}
        </span>
        <span className="font-mono text-[9px] text-text-muted sm:hidden uppercase">{chip}</span>
      </div>
    </header>
  );
};
