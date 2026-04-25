import { motion } from 'framer-motion';
import { Building2, HeartPulse, LandPlot, Vote, type LucideIcon } from 'lucide-react';
import { USE_CASES, type UseCaseId } from '@/data/useCases';
import { useCortexStore } from '@/store/cortex';

const ICON: Record<UseCaseId, LucideIcon> = {
  political: Vote,
  public_health: HeartPulse,
  urban: LandPlot,
  corporate: Building2,
};

export const UseCaseSelector = () => {
  const setUseCase = useCortexStore((s) => s.setUseCase);
  const setScreen = useCortexStore((s) => s.setScreen);
  const reset = useCortexStore((s) => s.resetWorkspace);

  const pick = (id: UseCaseId) => {
    reset();
    setUseCase(id);
    setScreen('workspace');
  };

  return (
    <div className="min-h-screen w-full bg-bg-deep text-text-primary flex flex-col items-center justify-center p-6 relative overflow-hidden">
      <div
        className="absolute inset-0 pointer-events-none opacity-50"
        style={{
          background:
            'radial-gradient(ellipse 80% 50% at 50% 0%, hsl(var(--pastel-2) / 0.14), transparent), radial-gradient(ellipse 60% 40% at 80% 100%, hsl(var(--pastel-3) / 0.1), transparent), radial-gradient(ellipse 50% 30% at 20% 90%, hsl(var(--pastel-1) / 0.08), transparent)',
        }}
      />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative z-10 max-w-4xl w-full"
      >
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-muted text-center">
          Cortexia · Cognitive impact lab
        </p>
        <h1 className="text-center text-2xl sm:text-3xl font-semibold tracking-tight mt-2">
          Choose a domain
        </h1>
        <p className="text-center text-text-secondary text-sm mt-2 max-w-xl mx-auto">
          Each domain loads adoption benchmarks and report templates. In the lab you supply catalyst text (or a source
          URL), pick a target city, and run a simulation against the synthetic population.
        </p>
        <div className="grid sm:grid-cols-2 gap-4 mt-10">
          {USE_CASES.map((uc, i) => {
            const Icon = ICON[uc.id];
            return (
              <motion.button
                key={uc.id}
                type="button"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.06 * i, duration: 0.35 }}
                onClick={() => pick(uc.id)}
                className="group rounded-[30px] border border-white/[0.08] bg-bg-surface/90 p-6 text-left transition-all hover:border-pastel-2/40 hover:bg-bg-elevated/80"
              >
                <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-[18px] border border-white/[0.08] bg-bg-elevated/60 text-pastel-2">
                  <Icon className="h-4 w-4" strokeWidth={1.5} />
                </div>
                <div className="font-medium text-text-primary group-hover:text-pastel-2/95 transition-colors">
                  {uc.label}
                </div>
                <p className="text-xs text-text-secondary mt-1.5 leading-relaxed">{uc.description}</p>
                <span className="inline-block mt-3 font-mono text-[9px] uppercase tracking-wider text-text-muted group-hover:text-pastel-1/80">
                  Open domain →
                </span>
              </motion.button>
            );
          })}
        </div>
      </motion.div>
    </div>
  );
};
