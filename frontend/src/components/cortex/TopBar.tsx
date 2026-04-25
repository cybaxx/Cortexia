import { useCortexStore } from '@/store/cortex';
import { getCityById } from '@/data/cities';
import { getUseCase } from '@/data/useCases';

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
  const cityId = useCortexStore((s) => s.cityId);
  const city = getCityById(cityId);
  const domain = getUseCase(useCase);

  const chip =
    status === 'running' || ['initializing', 'propagating', 'report'].includes(phase)
      ? PHASE_LABEL[phase] ?? 'Running'
      : phase === 'complete'
        ? 'Report ready'
        : 'Ready';

  return (
    <header className="absolute left-4 right-4 top-4 z-30 flex h-12 items-center justify-between rounded-full border border-white/[0.1] bg-bg-surface/[0.88] px-5 shadow-[0_14px_50px_rgba(7,11,18,0.28)] backdrop-blur-xl">
      <div className="flex items-center gap-3 min-w-0">
        <span className="text-text-primary text-[14px] font-medium tracking-tight shrink-0">Cortexia</span>
        <span className="h-4 w-px bg-white/10 shrink-0" />
        <span className="font-mono text-[10px] text-text-secondary uppercase tracking-wider truncate">
          {city.label}
          {domain ? ` · ${domain.label}` : ' · Select domain'}
        </span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            status === 'running' || ['initializing', 'propagating', 'report'].includes(phase)
              ? 'bg-accent-adopt animate-pulse'
              : 'bg-pastel-1/[0.85]'
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
