import { AnimatePresence, motion } from 'framer-motion';
import { useCortexStore } from '@/store/cortex';
import { MapPin, Lightbulb, Sparkles, BarChart3, AlertTriangle, CheckCircle2, MinusCircle } from 'lucide-react';

const RISK_CONFIG: { test: (l: string) => boolean; color: string; bg: string; border: string }[] = [
  { test: (l) => /strong/i.test(l),   color: 'text-emerald-300', bg: 'bg-emerald-400/10', border: 'border-emerald-400/30' },
  { test: (l) => /moderate/i.test(l), color: 'text-amber-300',   bg: 'bg-amber-400/10',   border: 'border-amber-400/30'   },
  { test: (l) => /high/i.test(l),     color: 'text-orange-300',  bg: 'bg-orange-400/10',  border: 'border-orange-400/30'  },
  { test: (l) => /critical/i.test(l), color: 'text-rose-300',    bg: 'bg-rose-400/10',    border: 'border-rose-400/30'    },
];

function getRiskConfig(level: string) {
  return RISK_CONFIG.find((r) => r.test(level ?? '')) ?? RISK_CONFIG[1];
}

function SentimentBar({ label, value, total, color, icon }: {
  label: string;
  value: number;
  total: number;
  color: string;
  icon: React.ReactNode;
}) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          {icon}
          <span className="font-mono text-[9px] uppercase tracking-wider text-white/60">{label}</span>
        </div>
        <div className="flex items-baseline gap-1">
          <span className={`text-xl font-semibold ${color}`}>{value}</span>
          <span className="font-mono text-[9px] text-white/40">{pct}%</span>
        </div>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <motion.div
          className={`h-full rounded-full ${color.replace('text-', 'bg-')}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.9, ease: 'easeOut', delay: 0.1 }}
        />
      </div>
    </div>
  );
}

const slideVariants = {
  initial: { x: 42, opacity: 0 },
  animate: { x: 0, opacity: 1 },
  exit: { x: 42, opacity: 0 },
};

export const PropagationReportPanel = () => {
  const injectPhase = useCortexStore((s) => s.injectPhase);
  const macroResult = useCortexStore((s) => s.macroResult);

  const showReport = macroResult && (injectPhase === 'report' || injectPhase === 'complete');

  return (
    <AnimatePresence>
      {showReport && (
        <aside className="absolute bottom-4 right-4 top-16 z-20 w-[min(96vw,34rem)]">
          <motion.div
            variants={slideVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={{ duration: 0.35, ease: 'easeOut' }}
            className="flex h-full flex-col overflow-hidden rounded-[34px] border border-white/[0.1] shadow-[0_28px_120px_rgba(8,12,20,0.55)]"
            style={{
              background: 'linear-gradient(160deg, rgba(16,22,36,0.98) 0%, rgba(10,14,24,0.99) 100%)',
            }}
          >
            <div className="flex-1 overflow-y-auto cortex-scroll">

              {/* ── HERO SLIDE ── */}
              <div
                className="relative overflow-hidden px-7 pt-7 pb-6"
                style={{
                  background: 'linear-gradient(135deg, rgba(160,214,255,0.07) 0%, rgba(188,231,219,0.05) 50%, rgba(255,191,166,0.07) 100%)',
                  borderBottom: '1px solid rgba(255,255,255,0.07)',
                }}
              >
                {/* Decorative glow blob */}
                <div
                  className="pointer-events-none absolute -top-10 -right-10 h-40 w-40 rounded-full opacity-30"
                  style={{ background: 'radial-gradient(circle, hsl(202 78% 70% / 0.4) 0%, transparent 70%)' }}
                />

                <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-white/40 mb-5">
                  Independent run report
                </div>

                <div className="flex items-end gap-5">
                  {/* Big score */}
                  <div className="relative flex-shrink-0">
                    <div
                      className="flex h-24 w-24 items-center justify-center rounded-[28px] border border-white/[0.1]"
                      style={{
                        background: 'linear-gradient(145deg, rgba(160,214,255,0.15) 0%, rgba(188,231,219,0.08) 100%)',
                        boxShadow: '0 0 40px rgba(160,214,255,0.12), inset 0 1px 0 rgba(255,255,255,0.08)',
                      }}
                    >
                      <span className="text-5xl font-semibold tracking-[-0.05em] text-white">
                        {macroResult!.score}
                      </span>
                    </div>
                    <div className="font-mono text-[8px] uppercase tracking-[0.15em] text-white/40 mt-1.5 text-center">
                      Score
                    </div>
                  </div>

                  {/* Meta */}
                  <div className="min-w-0 flex-1 pb-1 space-y-2">
                    {(() => {
                      const rc = getRiskConfig(macroResult!.risk_level);
                      return (
                        <div className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${rc.color} ${rc.bg} ${rc.border}`}>
                          <AlertTriangle className="h-3 w-3" />
                          {macroResult!.risk_level} risk
                        </div>
                      );
                    })()}
                    <p className="text-sm leading-relaxed text-white/70 line-clamp-3">
                      {macroResult!.summary_text}
                    </p>
                  </div>
                </div>

                {/* Input used — compact card */}
                <div
                  className="mt-5 rounded-[20px] border border-white/[0.07] p-4"
                  style={{ background: 'rgba(255,255,255,0.03)' }}
                >
                  <div className="font-mono text-[8px] uppercase tracking-[0.15em] text-white/35 mb-2">
                    Input used
                  </div>
                  <p className="text-[12px] leading-relaxed text-white/80">{macroResult!.input_summary}</p>
                  {macroResult!.source_context_summary && (
                    <p className="mt-2 text-[11px] leading-relaxed text-white/50">
                      Source: {macroResult!.source_context_summary}
                    </p>
                  )}
                  {macroResult!.source_warning && (
                    <p className="mt-2 font-mono text-[9px] uppercase tracking-[0.1em] text-amber-400/80">
                      {macroResult!.source_warning}
                    </p>
                  )}
                </div>
              </div>

              {/* ── SENTIMENT SLIDE ── */}
              <div
                className="px-7 py-6"
                style={{ borderBottom: '1px solid rgba(255,255,255,0.07)' }}
              >
                <div className="flex items-center gap-2 mb-5">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-white/[0.07]">
                    <BarChart3 className="h-3.5 w-3.5 text-white/60" />
                  </div>
                  <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-white/50">
                    Sentiment breakdown
                  </span>
                </div>

                {(() => {
                  const { adopted, rejected, neutral } = macroResult!.sentiment_mix;
                  const total = adopted + rejected + neutral;
                  return (
                    <div className="space-y-4">
                      <SentimentBar
                        label="Adopted"
                        value={adopted}
                        total={total}
                        color="text-sky-300"
                        icon={<CheckCircle2 className="h-3 w-3 text-sky-400/70" />}
                      />
                      <SentimentBar
                        label="Rejected"
                        value={rejected}
                        total={total}
                        color="text-orange-300"
                        icon={<AlertTriangle className="h-3 w-3 text-orange-400/70" />}
                      />
                      <SentimentBar
                        label="Neutral"
                        value={neutral}
                        total={total}
                        color="text-emerald-300"
                        icon={<MinusCircle className="h-3 w-3 text-emerald-400/70" />}
                      />
                    </div>
                  );
                })()}
              </div>

              {/* ── HOTSPOTS SLIDE ── */}
              <div
                className="px-7 py-6"
                style={{ borderBottom: '1px solid rgba(255,255,255,0.07)' }}
              >
                <div className="flex items-center gap-2 mb-5">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-orange-500/10 border border-orange-500/20">
                    <MapPin className="h-3.5 w-3.5 text-orange-400" />
                  </div>
                  <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-white/50">
                    Where resistance clusters
                  </span>
                </div>

                <div className="space-y-3">
                  {macroResult!.hotspots.length === 0 ? (
                    <div
                      className="rounded-[20px] border border-white/[0.07] p-4 text-[12px] text-white/40"
                      style={{ background: 'rgba(255,255,255,0.02)' }}
                    >
                      No meaningful rejection hotspot formed in this run.
                    </div>
                  ) : (
                    macroResult!.hotspots.map((hotspot, idx) => (
                      <motion.div
                        key={hotspot.id}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.05 * idx }}
                        className="rounded-[20px] border border-white/[0.07] p-4"
                        style={{
                          background: 'linear-gradient(135deg, rgba(255,130,80,0.06) 0%, rgba(255,255,255,0.02) 100%)',
                        }}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-[13px] font-semibold text-white/90">{hotspot.label}</div>
                            <div className="mt-0.5 text-[11px] text-white/45">{hotspot.area}</div>
                          </div>
                          <div className="shrink-0 rounded-full bg-orange-400/15 border border-orange-400/20 px-2.5 py-1 text-[11px] font-medium text-orange-300">
                            {Math.round(hotspot.share * 100)}%
                          </div>
                        </div>
                        <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-white/[0.05]">
                          <motion.div
                            className="h-full rounded-full bg-orange-400/50"
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.round(hotspot.share * 100)}%` }}
                            transition={{ duration: 0.8, ease: 'easeOut', delay: 0.1 + 0.05 * idx }}
                          />
                        </div>
                      </motion.div>
                    ))
                  )}
                </div>
              </div>

              {/* ── INSIGHTS SLIDE ── */}
              <div
                className="px-7 py-6"
                style={{ borderBottom: '1px solid rgba(255,255,255,0.07)' }}
              >
                <div className="flex items-center gap-2 mb-5">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-sky-500/10 border border-sky-500/20">
                    <Lightbulb className="h-3.5 w-3.5 text-sky-400" />
                  </div>
                  <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-white/50">
                    Key insights
                  </span>
                </div>

                <div className="space-y-3">
                  {macroResult!.insights.map((insight, idx) => {
                    const accentColors = [
                      'border-l-sky-400/60',
                      'border-l-emerald-400/60',
                      'border-l-violet-400/60',
                      'border-l-amber-400/60',
                    ];
                    const accent = accentColors[idx % accentColors.length];
                    return (
                      <motion.div
                        key={`${insight.where}-${idx}`}
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.06 * idx }}
                        className={`rounded-r-[20px] rounded-l-[6px] border-l-2 border border-white/[0.06] p-4 ${accent}`}
                        style={{ background: 'rgba(255,255,255,0.025)' }}
                      >
                        <div className="text-[13px] font-semibold text-white/90">{insight.where}</div>
                        <p className="mt-1.5 text-[12px] leading-relaxed text-white/60">{insight.why}</p>
                        <p className="mt-2 font-mono text-[9px] uppercase tracking-[0.1em] text-white/35">
                          {insight.who}
                        </p>
                      </motion.div>
                    );
                  })}
                </div>
              </div>

              {/* ── REWRITE SLIDE ── */}
              <div className="px-7 py-6">
                <div className="flex items-center gap-2 mb-5">
                  <div
                    className="flex h-7 w-7 items-center justify-center rounded-full border border-sky-400/30"
                    style={{ background: 'linear-gradient(135deg, rgba(160,214,255,0.15), rgba(188,231,219,0.1))' }}
                  >
                    <Sparkles className="h-3.5 w-3.5 text-sky-300" />
                  </div>
                  <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-sky-300/70">
                    Suggested rewrite
                  </span>
                </div>

                <div
                  className="rounded-[24px] border border-sky-400/20 p-5 text-[13px] leading-relaxed text-white/80"
                  style={{
                    background: 'linear-gradient(145deg, rgba(160,214,255,0.08) 0%, rgba(188,231,219,0.05) 100%)',
                    boxShadow: '0 0 30px rgba(160,214,255,0.05)',
                  }}
                >
                  {macroResult!.suggested_rewrite}
                </div>
              </div>

            </div>
          </motion.div>
        </aside>
      )}
    </AnimatePresence>
  );
};
