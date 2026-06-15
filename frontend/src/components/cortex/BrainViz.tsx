import { Component, Suspense, lazy, useState, type ReactNode } from 'react';
import type { BrainRegions, DominantSignal, TribeNeurologicalMetrics } from '@/types/simulation';

const Brain3D = lazy(() =>
  import('./Brain3D').then((m) => ({ default: m.Brain3D })),
);

class Safe3DBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() { return { hasError: true }; }
  render() {
    if (this.state.hasError) return null;
    return this.props.children;
  }
}

const REGION_META: Array<{
  key: keyof BrainRegions;
  label: string;
  short: string;
  accent: string;
  path: string;
}> = [
  { key: 'prefrontal_cortex', label: 'Prefrontal Cortex', short: 'PFC', accent: 'hsl(var(--pastel-2))', path: 'M42 26 C52 12, 68 12, 78 26 C76 40, 64 44, 52 42 C44 40, 40 34, 42 26 Z' },
  { key: 'anterior_cingulate', label: 'Anterior Cingulate', short: 'ACC', accent: 'hsl(var(--pastel-1))', path: 'M46 34 C54 28, 66 28, 74 34 C70 44, 56 46, 46 34 Z' },
  { key: 'hippocampus', label: 'Hippocampus', short: 'HPC', accent: 'hsl(var(--pastel-1))', path: 'M36 48 C44 42, 48 48, 46 58 C40 62, 34 58, 36 48 Z' },
  { key: 'amygdala', label: 'Amygdala', short: 'AMY', accent: 'hsl(var(--pastel-3))', path: 'M73 48 C80 44, 86 48, 84 58 C78 62, 72 58, 73 48 Z' },
  { key: 'insula', label: 'Insula', short: 'INS', accent: 'hsl(var(--pastel-3))', path: 'M61 42 C70 39, 76 48, 71 58 C62 62, 53 56, 54 48 C55 45, 57 43, 61 42 Z' },
  { key: 'temporoparietal_junction', label: 'TPJ', short: 'TPJ', accent: 'hsl(var(--pastel-2))', path: 'M82 34 C92 34, 98 44, 96 54 C92 60, 84 58, 80 50 C78 44, 78 38, 82 34 Z' },
];

function fillFor(value: number, accent: string) {
  return `${accent.replace('hsl', 'hsla').replace(')', ` / ${0.16 + value * 0.62})`)}`;
}

export const BrainViz = ({
  tribeMetrics,
  regions,
  dominantSignal,
  summary,
}: {
  tribeMetrics: TribeNeurologicalMetrics | null;
  regions?: BrainRegions | null;
  dominantSignal?: DominantSignal;
  summary?: string;
}) => {
  const [show3D, setShow3D] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Neural response model</p>
          <p className="mt-1 text-[13px] leading-relaxed text-text-secondary">
            {summary ?? 'Run a simulation to generate a region-level readout.'}
          </p>
        </div>
        {regions && (
          <button
            onClick={() => setShow3D(!show3D)}
            className="rounded-[8px] border border-white/[0.10] px-2.5 py-1 text-[10px] text-text-muted hover:border-pastel-2/30 hover:text-pastel-2 transition-colors"
          >
            {show3D ? '2D' : '3D'}
          </button>
        )}
      </div>

      {/* ---- 3D brain overlay ---- */}
      {show3D && regions && (
        <Safe3DBoundary>
          <Suspense fallback={null}>
            <Brain3D regions={regions} metrics={tribeMetrics} />
          </Suspense>
        </Safe3DBoundary>
      )}

      {/* ---- 2D brain (always visible as fallback) ---- */}
      {(!show3D || !regions) && (
        <div className="rounded-[28px] border border-white/10 bg-bg-deep/55 p-4 shadow-[0_24px_80px_rgba(8,12,20,0.35)]">
          <svg viewBox="0 0 120 96" className="h-48 w-full" aria-hidden>
            <defs>
              <filter id="brain-glow" x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="1.8" result="blurred" />
                <feMerge>
                  <feMergeNode in="blurred" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <linearGradient id="brain-shell" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="rgba(216,236,233,0.22)" />
                <stop offset="100%" stopColor="rgba(137,195,255,0.16)" />
              </linearGradient>
            </defs>
            <path d="M60 8 C32 8 14 26 12 46 C10 70 28 88 56 90 C84 92 108 74 108 48 C108 24 88 8 60 8 Z" fill="url(#brain-shell)" stroke="rgba(255,255,255,0.20)" strokeWidth="0.9" />
            <path d="M60 10 C58 24 58 74 60 88" stroke="rgba(255,255,255,0.12)" strokeWidth="0.6" strokeDasharray="2 3" />
            {REGION_META.map((region) => {
              const value = regions?.[region.key] ?? 0.08;
              return (
                <path
                  key={region.key}
                  d={region.path}
                  fill={fillFor(value, region.accent)}
                  stroke={region.accent}
                  strokeWidth={value > 0.72 ? 1.6 : 0.8}
                  filter="url(#brain-glow)"
                />
              );
            })}
          </svg>
        </div>
      )}

      {/* ---- Region values ---- */}
      <div className="grid grid-cols-2 gap-2">
        {REGION_META.map((region) => {
          const value = regions?.[region.key] ?? 0;
          return (
            <div key={region.key} className="rounded-2xl border border-white/[0.08] bg-white/[0.06] px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">
                  {region.short}
                </span>
                <span className="text-[12px] font-medium text-text-primary">{value.toFixed(2)}</span>
              </div>
              <div className="mt-1 text-[11px] text-text-secondary">{region.label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
