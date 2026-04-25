import { useCortexStore } from '@/store/cortex';

const Metric = ({ label, value, hint }: { label: string; value: string; hint?: string }) => (
  <div className="flex-1 flex flex-col justify-center px-5 border-r border-white/[0.06] last:border-r-0">
    <div className="font-mono text-[9px] uppercase tracking-[0.14em] text-text-secondary">{label}</div>
    <div className="flex items-baseline gap-2 mt-0.5">
      <span className="font-mono text-[20px] text-text-primary leading-none">{value}</span>
      {hint && <span className="font-mono text-[9px] text-text-muted">{hint}</span>}
    </div>
  </div>
);

export const BottomBar = () => {
  const m = useCortexStore((s) => s.metrics);
  return (
    <footer className="absolute bottom-0 left-0 right-0 h-16 bg-bg-surface border-t border-white/[0.08] flex z-30">
      <Metric label="Population Reached" value={`${m.populationReached}%`} hint="of N=10,432" />
      <Metric label="Avg Cognitive Load" value={m.avgCognitiveLoad.toFixed(2)} hint="0–1 scale" />
      <Metric label="Belief Adoption Rate" value={`${m.beliefAdoptionRate}%`} hint="Δ +3.1%" />
      <Metric label="Spatial Tension" value={m.spatialTension} hint="cluster index" />
    </footer>
  );
};
