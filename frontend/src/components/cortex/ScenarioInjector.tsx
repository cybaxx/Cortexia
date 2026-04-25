import { useCortexStore } from '@/store/cortex';
import { getUseCase } from '@/data/useCases';
import { Loader2, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const Memo = ({
  id,
  title,
  subtitle,
  tone,
}: {
  id: 'A' | 'B';
  title: string;
  subtitle: string;
  tone: 'adopt' | 'strain';
}) => {
  const selected = useCortexStore((s) => s.selectedMemo);
  const setMemo = useCortexStore((s) => s.setMemo);
  const running = useCortexStore(
    (s) => s.injectPhase === 'initializing' || s.injectPhase === 'propagating' || s.injectPhase === 'report',
  );
  const isSel = selected === id;
  const badge = tone === 'adopt' ? 'bg-accent-adopt/15 text-accent-adopt' : 'bg-accent-strain/15 text-accent-strain';
  return (
    <button
      type="button"
      onClick={() => !running && setMemo(id)}
      disabled={running}
      className={`w-full text-left rounded-sm border bg-bg-elevated px-3 py-3 transition-colors ${
        isSel ? 'border-accent-adopt/50' : 'border-white/[0.06] hover:border-white/[0.12]'
      } ${running ? 'opacity-60 pointer-events-none' : ''}`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-text-muted">Catalyst</span>
        <span className={`font-mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm ${badge}`}>
          Memo {id}
        </span>
      </div>
      <div className="text-[13px] text-text-primary font-medium leading-snug">{title}</div>
      <div className="text-[11px] text-text-secondary mt-1 leading-snug">{subtitle}</div>
    </button>
  );
};

const PHASE_COPY: Record<string, string> = {
  initializing: 'Initializing agents…',
  propagating: 'Propagating signal…',
  report: 'Generating report…',
};

export const ScenarioInjector = () => {
  const useCase = useCortexStore((s) => s.useCase);
  const def = getUseCase(useCase);
  const startInject = useCortexStore((s) => s.startInject);
  const resetSandbox = useCortexStore((s) => s.resetSandbox);
  const setScreen = useCortexStore((s) => s.setScreen);
  const status = useCortexStore((s) => s.status);
  const memo = useCortexStore((s) => s.selectedMemo);
  const phase = useCortexStore((s) => s.injectPhase);

  const running = phase === 'initializing' || phase === 'propagating' || phase === 'report';
  const canClick = memo && (phase === 'idle' || phase === 'complete') && !running;

  return (
    <aside className="absolute top-12 left-0 bottom-16 w-[300px] bg-bg-surface border-r border-white/[0.08] z-20 flex flex-col">
      <div className="px-4 py-3 border-b border-white/[0.08] flex items-center justify-between">
        <div>
          <h2 className="font-mono text-[11px] uppercase tracking-[0.14em] text-text-secondary">CATALYST CONFIGURATION</h2>
          <p className="font-mono text-[9px] text-text-muted mt-1">
            {def ? <span className="text-accent-adopt/90">{def.label}</span> : 'Select a use case from home'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setScreen('useCases');
            resetSandbox();
          }}
          className="font-mono text-[8px] uppercase tracking-wider text-text-muted hover:text-text-secondary"
        >
          Use cases
        </button>
      </div>

      {def && (
        <div className="px-4 py-4 space-y-3 flex-1">
          <Memo
            id="A"
            tone="adopt"
            title={def.memoA.title}
            subtitle={def.memoA.subtitle}
          />
          <p className="text-[9px] text-text-muted leading-relaxed line-clamp-3 border border-white/[0.05] rounded-sm px-2 py-1.5 bg-bg-elevated/30">
            {def.memoA.preview}
          </p>
          <Memo
            id="B"
            tone="strain"
            title={def.memoB.title}
            subtitle={def.memoB.subtitle}
          />
          <p className="text-[9px] text-text-muted leading-relaxed line-clamp-3 border border-white/[0.05] rounded-sm px-2 py-1.5 bg-bg-elevated/30">
            {def.memoB.preview}
          </p>
        </div>
      )}

      <div className="px-4 py-3 border-t border-white/[0.08]">
        <div className="font-mono text-[9px] uppercase tracking-wider text-text-muted mb-2">Cohort (model)</div>
        <div className="grid grid-cols-3 gap-1.5">
          {['Adults', 'Voters', 'Drivers'].map((c) => (
            <span
              key={c}
              className="font-mono text-[9px] text-text-secondary text-center py-1 rounded-sm bg-bg-elevated border border-white/[0.06]"
            >
              {c}
            </span>
          ))}
        </div>

        <motion.button
          type="button"
          onClick={() => startInject()}
          disabled={!canClick || !def}
          className="mt-4 w-full relative overflow-hidden rounded-md font-mono text-[12px] font-semibold uppercase tracking-[0.12em] py-3.5 px-3 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-shadow shadow-lg shadow-blue-500/20"
          style={{
            background: 'linear-gradient(135deg, rgb(37 99 235) 0%, rgb(29 78 216) 45%, rgb(59 130 246) 100%)',
          }}
          whileHover={canClick && def ? { scale: 1.01 } : {}}
          whileTap={canClick && def ? { scale: 0.99 } : {}}
        >
          <span className="absolute inset-0 bg-gradient-to-t from-white/0 to-white/10 pointer-events-none" />
          <span className="relative flex items-center justify-center gap-2">
            <AnimatePresence mode="wait">
              {running ? (
                <motion.span
                  key="load"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center justify-center gap-2"
                >
                  <Loader2 className="h-4 w-4 animate-spin shrink-0" />
                  {PHASE_COPY[phase] ?? 'Working…'}
                </motion.span>
              ) : (
                <motion.span
                  key="go"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center justify-center gap-2"
                >
                  <Sparkles className="h-4 w-4" />
                  Inject catalyst
                </motion.span>
              )}
            </AnimatePresence>
          </span>
        </motion.button>

        <p className="mt-2 font-mono text-[8px] text-text-muted text-center min-h-[2.5em]">
          {running ? (
            <span className="text-accent-adopt/90">
              {phase === 'initializing' && 'Resolving agent graph and TRIBE v2 BSV baselines…'}
              {phase === 'propagating' && 'Routing signal through synthetic population; updating map…'}
              {phase === 'report' && 'Composing deliverable: hotspots, copy drivers, and predicted lift…'}
            </span>
          ) : (
            'Runs Memo ' + (memo ?? '—') + ' · then compare by running the other memo.'
          )}
        </p>

        <button
          type="button"
          onClick={() => resetSandbox()}
          disabled={running}
          className="mt-1 w-full font-mono text-[10px] uppercase tracking-[0.1em] py-2 rounded-sm bg-bg-elevated text-text-secondary border border-white/[0.06] hover:border-white/[0.14] transition-colors disabled:opacity-40"
        >
          Reset sandbox
        </button>
        <div className="mt-2 font-mono text-[8px] text-text-muted text-center">
          Status: <span className="text-text-secondary">{status}</span>
        </div>
      </div>
    </aside>
  );
};
