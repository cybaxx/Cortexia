import { AnimatePresence, motion } from 'framer-motion';
import { useCortexStore } from '@/store/cortex';

export const PropagationReportPanel = () => {
  const injectPhase = useCortexStore((s) => s.injectPhase);
  const macroResult = useCortexStore((s) => s.macroResult);

  const showReport = macroResult && (injectPhase === 'report' || injectPhase === 'complete');

  return (
    <AnimatePresence>
      {showReport && (
        <aside className="absolute bottom-4 right-4 top-16 z-20 w-[min(96vw,34rem)]">
          <motion.div
            initial={{ x: 42, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 42, opacity: 0 }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
            className="flex h-full flex-col overflow-hidden rounded-[34px] border border-white/[0.12] bg-[linear-gradient(180deg,rgba(21,30,40,0.95),rgba(13,18,27,0.98))] shadow-[0_28px_120px_rgba(8,12,20,0.48)]"
          >
            <div className="flex-1 overflow-y-auto px-6 pb-8 pt-6 cortex-scroll">
              <div className="border-b border-white/10 pb-6">
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Independent run report</div>
                <div className="mt-4 flex items-end gap-4">
                  <div className="text-7xl font-semibold tracking-[-0.06em] text-text-primary">{macroResult.score}</div>
                  <div className="pb-2 text-text-secondary">
                    <div className="text-sm uppercase tracking-[0.12em] text-text-muted">Message score</div>
                    <div className="mt-1 rounded-full border border-white/10 bg-white/[0.06] px-3 py-1.5 text-sm font-medium text-text-primary">
                      {macroResult.risk_level}
                    </div>
                  </div>
                </div>
                <p className="mt-4 text-sm leading-relaxed text-text-secondary">{macroResult.summary_text}</p>
                <div className="mt-4 rounded-[24px] border border-white/[0.08] bg-white/[0.04] p-4">
                  <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">Input used</div>
                  <p className="mt-2 text-sm leading-relaxed text-text-primary">{macroResult.input_summary}</p>
                  {macroResult.source_context_summary && (
                    <p className="mt-3 text-sm leading-relaxed text-text-secondary">
                      Source context: {macroResult.source_context_summary}
                    </p>
                  )}
                  {macroResult.source_warning && (
                    <p className="mt-3 text-xs uppercase tracking-[0.12em] text-pastel-3">
                      {macroResult.source_warning}
                    </p>
                  )}
                </div>
              </div>

              <div className="mt-6 grid grid-cols-3 gap-3">
                <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.06] p-4">
                  <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">Adopted</div>
                  <div className="mt-2 text-3xl font-semibold text-pastel-2">{macroResult.sentiment_mix.adopted}</div>
                </div>
                <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.06] p-4">
                  <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">Rejected</div>
                  <div className="mt-2 text-3xl font-semibold text-pastel-3">{macroResult.sentiment_mix.rejected}</div>
                </div>
                <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.06] p-4">
                  <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">Neutral</div>
                  <div className="mt-2 text-3xl font-semibold text-pastel-1">{macroResult.sentiment_mix.neutral}</div>
                </div>
              </div>

              <section className="mt-7">
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Where resistance clusters</div>
                <div className="mt-3 space-y-3">
                  {macroResult.hotspots.length === 0 ? (
                    <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.06] p-4 text-sm text-text-secondary">
                      No meaningful rejection hotspot formed in this run.
                    </div>
                  ) : (
                    macroResult.hotspots.map((hotspot) => (
                      <div key={hotspot.id} className="rounded-[24px] border border-white/[0.08] bg-white/[0.06] p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <div className="text-sm font-semibold text-text-primary">{hotspot.label}</div>
                            <div className="mt-1 text-xs text-text-muted">{hotspot.area}</div>
                          </div>
                          <div className="rounded-full bg-pastel-3/15 px-3 py-1 text-xs font-medium text-pastel-3">
                            {Math.round(hotspot.share * 100)}% of rejections
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>

              <section className="mt-7">
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Key insights</div>
                <div className="mt-3 space-y-3">
                  {macroResult.insights.map((insight, idx) => (
                    <div key={`${insight.where}-${idx}`} className="rounded-[24px] border border-white/[0.08] bg-white/[0.06] p-4">
                      <div className="text-sm font-semibold text-text-primary">{insight.where}</div>
                      <p className="mt-2 text-sm leading-relaxed text-text-secondary">{insight.why}</p>
                      <p className="mt-2 text-xs uppercase tracking-[0.12em] text-text-muted">{insight.who}</p>
                    </div>
                  ))}
                </div>
              </section>

              <section className="mt-7">
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-pastel-2">Suggested rewrite</div>
                <div className="mt-3 rounded-[28px] border border-pastel-2/25 bg-pastel-2/10 p-5 text-sm leading-relaxed text-text-primary">
                  {macroResult.suggested_rewrite}
                </div>
              </section>
            </div>
          </motion.div>
        </aside>
      )}
    </AnimatePresence>
  );
};
