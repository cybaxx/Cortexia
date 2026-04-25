import { useCortexStore } from '@/store/cortex';
import { getUseCase } from '@/data/useCases';

const Metric = ({
  label,
  value,
  context,
}: {
  label: string;
  value: string;
  context: string;
}) => (
  <div className="flex-1 flex flex-col justify-center px-4 sm:px-5 border-r border-white/[0.06] last:border-r-0 min-w-0">
    <div className="font-mono text-[9px] uppercase tracking-[0.14em] text-text-secondary truncate">{label}</div>
    <div className="flex items-baseline gap-1.5 mt-0.5 min-w-0">
      <span className="font-mono text-[18px] sm:text-[20px] text-text-primary leading-none shrink-0">{value}</span>
    </div>
    <p className="font-mono text-[8px] text-text-muted leading-tight mt-1 line-clamp-2">{context}</p>
  </div>
);

export const BottomBar = () => {
  const m = useCortexStore((s) => s.metrics);
  const useCase = useCortexStore((s) => s.useCase);
  const def = getUseCase(useCase);
  const bench = def?.adoptionBenchmark ?? 40;

  const adoptionContext =
    m.beliefAdoptionRate === 0
      ? 'Run a catalyst to measure adoption against benchmark.'
      : m.beliefAdoptionRate >= bench
        ? `${m.beliefAdoptionRate}% — at or above the ~${bench}% target for this domain.`
        : `${m.beliefAdoptionRate}% — below the ~${bench}% benchmark; see report for copy fixes.`;

  const reachContext =
    m.populationReached === 0
      ? 'No run yet. Reach estimates surface area of exposure.'
      : `${m.populationReached}% of the synthetic map surface saw the message.`;

  const loadContext =
    m.avgCognitiveLoad === 0
      ? 'Average TRIBE v2 cognitive load (0–1) appears after a run.'
      : m.avgCognitiveLoad > 0.78
        ? `${m.avgCognitiveLoad.toFixed(2)} — high; audiences may show confusion or overload.`
        : `${m.avgCognitiveLoad.toFixed(2)} — ${m.avgCognitiveLoad > 0.55 ? 'moderate' : 'controlled'} load vs. typical 0.45–0.70 band.`;

  const tensionContext =
    m.spatialTension === 'Low'
      ? 'Low geographic polarization vs. modelled alternative runs.'
      : m.spatialTension === 'Moderate'
        ? 'Moderate tension: some cluster disagreement on the map.'
        : 'High tension: strong geographic rejection pockets — see map overlay.';

  return (
    <footer className="absolute bottom-0 left-0 right-0 min-h-16 py-1 bg-bg-surface border-t border-white/[0.08] flex z-30 flex-wrap sm:flex-nowrap">
      <Metric label="Population reached" value={m.populationReached ? `${m.populationReached}%` : '—'} context={reachContext} />
      <Metric label="Avg cognitive load" value={m.avgCognitiveLoad ? m.avgCognitiveLoad.toFixed(2) : '—'} context={loadContext} />
      <Metric label="Belief adoption" value={m.beliefAdoptionRate ? `${m.beliefAdoptionRate}%` : '—'} context={adoptionContext} />
      <Metric label="Spatial tension" value={m.beliefAdoptionRate ? m.spatialTension : '—'} context={tensionContext} />
    </footer>
  );
};
