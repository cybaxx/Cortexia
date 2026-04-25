/**
 * Stylized brain silhouette with four regions. Opacity / glow tracks TRIBE-relevant
 * BSV fields (cognitive, emotional, defensive) — simulates fMRI “lights up” for demo;
 * in production, bind each region to Modal TRIBE v2 per-region tensors.
 */
export const BrainViz = ({
  cognitiveLoad,
  emotionalAgitation,
  defensivePosture,
}: {
  cognitiveLoad: number;
  emotionalAgitation: number;
  defensivePosture: number;
}) => {
  const pfc = Math.min(1, Math.max(0, cognitiveLoad));
  const lim = Math.min(1, Math.max(0, emotionalAgitation));
  const ins = Math.min(1, Math.max(0, defensivePosture));
  const par = Math.min(1, (1 - ins) * 0.5 + pfc * 0.3);

  const fill = (o: number) => `hsla(230, 55%, 72%, ${0.15 + o * 0.55})`;
  const ring = (o: number) => `hsla(160, 40%, 65%, ${0.2 + o * 0.5})`;

  return (
    <div className="space-y-1.5">
      <div className="font-mono text-[8px] uppercase tracking-[0.12em] text-text-muted">Neurological sim (MVP)</div>
      <svg viewBox="0 0 120 100" className="w-full h-24" aria-hidden>
        <defs>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.2" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <path
          d="M60 8 C 28 8 10 32 10 50 C 10 70 32 90 60 92 C 88 90 110 70 110 50 C 110 32 92 8 60 8 Z"
          fill="hsla(220, 15%, 18%, 0.9)"
          stroke="hsla(220, 10%, 40%, 0.5)"
          strokeWidth="0.5"
        />
        <path
          d="M38 32 Q 52 20 64 32 Q 70 18 80 32 Q 78 50 64 55 Q 50 50 38 32"
          fill={fill(pfc)}
          filter="url(#glow)"
        />
        <path
          d="M32 50 Q 44 40 50 55 Q 46 70 32 64 Q 30 55 32 50"
          fill={fill(lim)}
          filter="url(#glow)"
        />
        <path
          d="M80 50 Q 92 38 100 50 Q 98 64 80 64 Q 76 55 80 50"
          fill={fill(ins)}
          filter="url(#glow)"
        />
        <path
          d="M50 64 Q 60 70 70 64 Q 64 80 50 78 Q 48 70 50 64"
          fill={fill(par)}
          filter="url(#glow)"
        />
        <ellipse cx="60" cy="18" rx="3" ry="1.2" fill={ring(pfc * 0.6)} />
      </svg>
      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 font-mono text-[7px] text-text-muted">
        <span className="text-text-secondary/90">PFC · load {pfc.toFixed(2)}</span>
        <span className="text-text-secondary/90">Limbic · {lim.toFixed(2)}</span>
        <span className="text-text-secondary/90">Insula · def {ins.toFixed(2)}</span>
        <span className="text-text-secondary/90">Parietal · {par.toFixed(2)}</span>
      </div>
    </div>
  );
};
