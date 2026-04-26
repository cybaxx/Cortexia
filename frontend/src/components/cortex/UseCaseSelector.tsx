import { motion } from 'framer-motion';
import {
  ArrowRight,
  Building2,
  HeartPulse,
  LandPlot,
  Microscope,
  Radar,
  Vote,
  type LucideIcon,
} from 'lucide-react';
import { USE_CASES, type UseCaseId } from '@/data/useCases';
import { useCortexStore } from '@/store/cortex';

const ICON: Record<UseCaseId, LucideIcon> = {
  political: Vote,
  public_health: HeartPulse,
  urban: LandPlot,
  corporate: Building2,
};

const LAB_NOTES = [
  'Trace how a narrative moves through a synthetic population.',
  'Review vulnerable segments, mechanisms, and geographic spread.',
  'Export a researcher-facing brief when the model stabilizes.',
];

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
    <div className="relative min-h-screen overflow-hidden bg-bg-deep text-text-primary">
      <div className="pointer-events-none absolute inset-0 opacity-60">
        <div className="lab-grid absolute inset-0" />
        <div className="absolute inset-x-[8%] top-0 h-[420px] rounded-full bg-[radial-gradient(circle,hsl(var(--pastel-2)/0.14),transparent_62%)] blur-3xl" />
        <div className="absolute bottom-[-12%] right-[-5%] h-[420px] w-[420px] rounded-full bg-[radial-gradient(circle,hsl(var(--pastel-3)/0.18),transparent_60%)] blur-3xl" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative z-10 mx-auto flex min-h-screen w-full max-w-[1380px] flex-col justify-center px-6 py-10"
      >
        <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <section className="brand-shell rounded-[36px] p-7 md:p-8">
            <div className="inline-flex items-center gap-3 rounded-full border border-white/[0.1] bg-white/[0.03] px-4 py-2">
              <div className="grid h-10 w-10 place-items-center rounded-2xl border border-white/[0.08] bg-[linear-gradient(180deg,rgba(12,22,30,0.95),rgba(8,14,22,0.98))]">
                <img src="/cortexia-mark.svg" alt="Cortexia logo" className="h-6 w-6 object-contain" />
              </div>
              <div>
                <div className="lab-kicker">Cortexia Research Lab</div>
                <div className="text-sm text-text-secondary">Synthetic narrative diagnostics for real-world interventions</div>
              </div>
            </div>

            <h1 className="mt-8 max-w-xl text-4xl font-semibold tracking-tight sm:text-5xl">
              Open a research program and start an investigation.
            </h1>
            <p className="mt-4 max-w-xl text-base leading-relaxed text-text-secondary">
              Choose the operating domain first. Cortexia will load the right benchmark language, simulation framing,
              and reporting cues so the workspace reads like a live lab notebook instead of a generic dashboard.
            </p>

            <div className="mt-8 grid gap-3">
              {LAB_NOTES.map((item) => (
                <div key={item} className="lab-panel rounded-[22px] px-4 py-4">
                  <div className="relative z-10 flex items-start gap-3">
                    <div className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-2xl border border-white/[0.08] bg-white/[0.03]">
                      <Microscope className="h-4 w-4 text-pastel-2" />
                    </div>
                    <p className="text-sm leading-relaxed text-text-secondary">{item}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              <div className="brand-card rounded-[24px] p-4">
                <div className="lab-kicker">Workflow</div>
                <div className="mt-2 text-sm text-text-secondary">Intake, propagation, mechanisms, intervention design.</div>
              </div>
              <div className="brand-card rounded-[24px] p-4">
                <div className="lab-kicker">Output</div>
                <div className="mt-2 text-sm text-text-secondary">A concise spread brief for decision-makers and analysts.</div>
              </div>
            </div>
          </section>

          <section className="brand-shell rounded-[36px] p-7 md:p-8">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="lab-kicker">Program Selection</div>
                <h2 className="mt-2 text-2xl font-semibold">Research domains</h2>
              </div>
              <div className="hidden rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-xs text-text-secondary md:block">
                4 domain presets
              </div>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              {USE_CASES.map((uc, index) => {
                const Icon = ICON[uc.id];
                return (
                  <motion.button
                    key={uc.id}
                    type="button"
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.05 * index, duration: 0.35 }}
                    onClick={() => pick(uc.id)}
                    className="group lab-panel rounded-[30px] p-5 text-left transition-all hover:-translate-y-0.5 hover:border-pastel-2/30"
                  >
                    <div className="relative z-10">
                      <div className="flex items-start justify-between gap-4">
                        <div className="grid h-12 w-12 place-items-center rounded-[18px] border border-white/[0.08] bg-[linear-gradient(135deg,hsl(var(--pastel-2)/0.16),hsl(var(--pastel-3)/0.12))] text-pastel-2">
                          <Icon className="h-5 w-5" strokeWidth={1.7} />
                        </div>
                        <Radar className="mt-1 h-4 w-4 text-text-muted transition-colors group-hover:text-pastel-3" />
                      </div>

                      <h3 className="mt-5 text-xl font-semibold transition-colors group-hover:text-pastel-2">{uc.label}</h3>
                      <p className="mt-2 text-sm leading-relaxed text-text-secondary">{uc.description}</p>

                      <div className="mt-5 rounded-[18px] border border-white/[0.08] bg-white/[0.03] px-4 py-3">
                        <div className="lab-kicker">Benchmark</div>
                        <p className="mt-2 text-sm leading-relaxed text-text-secondary">{uc.benchmarkLabel}</p>
                      </div>

                      <div className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-pastel-1">
                        Open lab workspace
                        <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                      </div>
                    </div>
                  </motion.button>
                );
              })}
            </div>
          </section>
        </div>
      </motion.div>
    </div>
  );
};
