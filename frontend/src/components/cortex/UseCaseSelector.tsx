import { motion } from 'framer-motion';
import { USE_CASES, type UseCaseId } from '@/data/useCases';
import { useCortexStore } from '@/store/cortex';

export const UseCaseSelector = () => {
  const setUseCase = useCortexStore((s) => s.setUseCase);
  const setScreen = useCortexStore((s) => s.setScreen);
  const reset = useCortexStore((s) => s.resetSandbox);

  const pick = (id: UseCaseId) => {
    reset();
    setUseCase(id);
    setScreen('simulation');
  };

  return (
    <div className="min-h-screen w-full bg-bg-deep text-text-primary flex flex-col items-center justify-center p-6 relative overflow-hidden">
      <div
        className="absolute inset-0 pointer-events-none opacity-40"
        style={{
          background:
            'radial-gradient(ellipse 80% 50% at 50% 0%, rgba(59,130,246,0.12), transparent), radial-gradient(ellipse 60% 40% at 80% 100%, rgba(245,158,11,0.08), transparent)',
        }}
      />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative z-10 max-w-4xl w-full"
      >
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-muted text-center">
          Cortexia · HackTech 2026
        </p>
        <h1 className="text-center text-2xl sm:text-3xl font-semibold tracking-tight mt-2">
          Choose a use case
        </h1>
        <p className="text-center text-text-secondary text-sm mt-2 max-w-xl mx-auto">
          We&apos;ll pre-load two memo variants and a benchmark curve for that domain. You can run Memo A, then
          Memo B, and compare which framing propagates.
        </p>
        <div className="grid sm:grid-cols-2 gap-4 mt-10">
          {USE_CASES.map((uc, i) => (
            <motion.button
              key={uc.id}
              type="button"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.06 * i, duration: 0.35 }}
              onClick={() => pick(uc.id)}
              className="text-left rounded-lg border border-white/[0.08] bg-bg-surface/90 hover:border-accent-adopt/40 hover:bg-bg-elevated/80 transition-all p-5 group"
            >
              <div className="text-2xl mb-2">{uc.icon}</div>
              <div className="font-medium text-text-primary group-hover:text-accent-adopt/95 transition-colors">
                {uc.label}
              </div>
              <p className="text-xs text-text-secondary mt-1.5 leading-relaxed">{uc.description}</p>
              <span className="inline-block mt-3 font-mono text-[9px] uppercase tracking-wider text-text-muted group-hover:text-accent-adopt/80">
                Load scenario →
              </span>
            </motion.button>
          ))}
        </div>
      </motion.div>
    </div>
  );
};
