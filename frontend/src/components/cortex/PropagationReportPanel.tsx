import { motion, AnimatePresence } from 'framer-motion';
import { useCortexStore } from '@/store/cortex';
import { getUseCase } from '@/data/useCases';
import { exportPropagationPdf } from '@/lib/exportPdf';
import { MemoDiffView } from './MemoDiffView';
import { Loader2, FileDown } from 'lucide-react';

export const PropagationReportPanel = () => {
  const useCase = useCortexStore((s) => s.useCase);
  const injectPhase = useCortexStore((s) => s.injectPhase);
  const currentReport = useCortexStore((s) => s.currentReport);
  const selectedMemo = useCortexStore((s) => s.selectedMemo);
  const memoAResult = useCortexStore((s) => s.memoAResult);
  const memoBResult = useCortexStore((s) => s.memoBResult);
  const memoDiff = useCortexStore((s) => s.memoDiff);
  const def = getUseCase(useCase);

  const canExport = currentReport && injectPhase === 'complete' && def && selectedMemo;
  const showReport = currentReport && (injectPhase === 'report' || injectPhase === 'complete');
  const showShimmer = injectPhase === 'initializing' || injectPhase === 'propagating';

  return (
    <aside className="absolute top-12 right-0 bottom-16 w-[min(100%,400px)] max-w-[100vw] bg-bg-surface border-l border-white/[0.08] z-20 flex flex-col shadow-[-4px_0_24px_rgba(0,0,0,0.25)]">
      <div className="px-4 py-3 border-b border-white/[0.08] flex items-start justify-between gap-2">
        <div>
          <h2 className="font-mono text-[11px] uppercase tracking-[0.14em] text-text-secondary">Propagation report</h2>
          <p className="font-mono text-[9px] text-text-muted mt-0.5">Fills in as the run completes · stakeholder-ready</p>
        </div>
        {canExport && currentReport && selectedMemo && (
          <button
            type="button"
            onClick={() =>
              exportPropagationPdf({
                title: def!.label,
                subtitle: def!.benchmarkLabel,
                report: currentReport,
                memoLabel: selectedMemo,
              })
            }
            className="shrink-0 flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-wider text-accent-adopt border border-accent-adopt/35 rounded-sm px-2 py-1.5 hover:bg-accent-adopt/10 transition-colors"
          >
            <FileDown className="h-3.5 w-3.5" />
            Export PDF
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto cortex-scroll px-4 py-3 space-y-5">
        {showShimmer && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-text-muted font-mono text-[10px]">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {injectPhase === 'initializing' && 'Synthesizing reach surfaces…'}
              {injectPhase === 'propagating' && 'Mapping rejection clusters and cognitive load…'}
            </div>
            <div className="h-2 bg-white/[0.06] rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-accent-adopt/50"
                initial={{ width: '12%' }}
                animate={{ width: injectPhase === 'propagating' ? '88%' : '40%' }}
                transition={{ duration: 2.2, ease: 'easeInOut' }}
              />
            </div>
            <p className="text-[11px] text-text-secondary/90 leading-relaxed">
              The report below will update section-by-section. We preserve the map animation; this panel turns into
              the deliverable narrative.
            </p>
          </div>
        )}

        <AnimatePresence mode="wait">
          {showReport && currentReport && (
            <motion.div
              key={currentReport.adoptionRate + (def?.id ?? '')}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-5"
            >
              <section>
                <h3 className="font-mono text-[9px] uppercase tracking-[0.16em] text-text-muted mb-2">Overall reach & adoption</h3>
                <p className="text-[12px] text-text-primary leading-relaxed">
                  <span className="text-accent-adopt font-medium">{currentReport.reachPct}%</span> surface reach.{' '}
                  <span className="text-text-primary font-medium">{currentReport.adoptionRate}%</span> belief adoption
                  {currentReport.benchmarkComparison === 'above' && (
                    <span className="text-emerald-400/90"> — above </span>
                  )}
                  {currentReport.benchmarkComparison === 'below' && (
                    <span className="text-amber-400/90"> — below </span>
                  )}
                  {currentReport.benchmarkComparison === 'at' && <span> — at </span>}
                  the <span className="text-text-secondary">{currentReport.benchmark}%</span> benchmark for{' '}
                  {def?.label.toLowerCase() ?? 'this use case'}.
                </p>
                <p className="text-[10px] text-text-muted mt-1.5 leading-snug border-l border-white/[0.1] pl-2">
                  {def?.benchmarkLabel}
                </p>
              </section>

              <section>
                <h3 className="font-mono text-[9px] uppercase tracking-[0.16em] text-text-muted mb-2">Where it&apos;s rejected</h3>
                <p className="text-[11px] text-text-secondary mb-2 leading-relaxed">
                  Hotspots (see <span className="text-rose-400/90">red wash</span> on the map) are clusters where the message meets elevated defensive posture. Highest strain:
                </p>
                <ul className="space-y-1.5">
                  {currentReport.rejectionHotspots.map((h) => (
                    <li
                      key={h.id}
                      className="text-[11px] text-text-primary/95 bg-bg-elevated/60 border border-white/[0.06] rounded-sm px-2 py-1.5"
                    >
                      <span className="text-rose-300/90 font-medium">{h.label}</span>
                      <span className="text-text-muted"> · {h.area}</span>
                      <span className="text-text-muted"> — ~{Math.round(h.share * 100)}% of modelled rejections</span>
                    </li>
                  ))}
                </ul>
              </section>

              <section>
                <h3 className="font-mono text-[9px] uppercase tracking-[0.16em] text-text-muted mb-2">Why (cognitive resistance)</h3>
                <p className="text-[12px] text-text-primary/95 leading-relaxed">{currentReport.whyResistance}</p>
              </section>

              <section>
                <h3 className="font-mono text-[9px] uppercase tracking-[0.16em] text-text-muted mb-2">Recommendations</h3>
                <ol className="list-decimal list-inside space-y-1.5 text-[12px] text-text-primary/95 leading-relaxed">
                  {currentReport.recommendations.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ol>
              </section>

              <section>
                <h3 className="font-mono text-[9px] uppercase tracking-[0.16em] text-text-muted mb-2">Predicted outcome (if applied)</h3>
                <p className="text-[12px] text-text-primary/90 leading-relaxed border border-accent-adopt/20 bg-accent-adopt/[0.06] rounded-md px-3 py-2">
                  {currentReport.predictedOutcome}
                </p>
              </section>
            </motion.div>
          )}
        </AnimatePresence>

        {memoAResult && memoBResult && memoDiff && <MemoDiffView />}

        {!showReport && !showShimmer && def && (
          <p className="text-[11px] text-text-muted leading-relaxed">
            Select a memo, then use <span className="text-accent-adopt">Inject catalyst</span> to run TRIBE v2 and generate this report. Run both memos to unlock the A vs B diff.
          </p>
        )}
      </div>
    </aside>
  );
};
