import { ArrowRight, AudioLines, BrainCircuit, MapPinned, NotebookPen, Sparkles } from 'lucide-react';

export function ProductLanding({ onEnter }: { onEnter: () => void }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-bg-deep text-text-primary">
      <div className="pointer-events-none absolute inset-0 opacity-80">
        <div className="lab-grid absolute inset-0" />
        <div className="absolute left-[-8%] top-[-10%] h-[34rem] w-[34rem] rounded-full bg-[radial-gradient(circle,hsl(var(--pastel-2)/0.22),transparent_62%)] blur-3xl" />
        <div className="absolute right-[-8%] top-[18%] h-[30rem] w-[30rem] rounded-full bg-[radial-gradient(circle,hsl(var(--pastel-3)/0.18),transparent_64%)] blur-3xl" />
        <div className="absolute bottom-[-12%] left-[24%] h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle,hsl(var(--pastel-1)/0.18),transparent_66%)] blur-3xl" />
      </div>

      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-[1450px] flex-col px-6 pb-10 pt-6 md:px-10">
        <header className="flex items-center justify-between gap-4">
          <div className="inline-flex items-center gap-3 rounded-full border border-white/[0.1] bg-white/[0.04] px-4 py-2">
            <div className="grid h-11 w-11 place-items-center rounded-2xl border border-white/[0.08] bg-[linear-gradient(180deg,rgba(12,22,30,0.95),rgba(8,14,22,0.98))]">
              <img src="/cortexia-mark.svg" alt="Cortexia logo" className="h-6 w-6 object-contain" />
            </div>
            <div>
              <div className="lab-kicker">Cortexia Compass</div>
              <div className="text-sm text-text-secondary">TRIBE + K2 social simulation studio</div>
            </div>
          </div>

          <button
            type="button"
            onClick={onEnter}
            className="inline-flex items-center gap-2 rounded-full border border-pastel-2/25 bg-[linear-gradient(135deg,hsl(var(--pastel-2)/0.18),hsl(var(--pastel-3)/0.14))] px-5 py-3 text-sm font-medium text-text-primary shadow-[0_14px_40px_rgba(4,12,20,0.24)] transition-transform hover:-translate-y-0.5"
          >
            Open dashboard
            <ArrowRight className="h-4 w-4" />
          </button>
        </header>

        <section className="grid flex-1 items-center gap-8 py-10 xl:grid-cols-[1.08fr_0.92fr]">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-4 py-2 font-mono text-[11px] uppercase tracking-[0.18em] text-pastel-2">
              Synthetic people. Live map. Interviewable nodes.
            </div>

            <h1 className="mt-8 max-w-4xl text-5xl font-semibold leading-[0.94] tracking-[-0.04em] md:text-7xl">
              See how a scenario spreads through a city before it happens.
            </h1>

            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-text-secondary md:text-xl">
              Cortexia Compass turns one scenario into a city-scale simulation. TRIBE models each person&apos;s cognitive
              state, K2 Think interprets how the narrative lands, and the map shows how it spreads across interviewable
              synthetic people you can inspect, question, and report on.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={onEnter}
                className="inline-flex items-center gap-2 rounded-full border border-pastel-2/30 bg-[hsl(var(--pastel-2)/0.12)] px-6 py-3.5 text-sm font-medium text-text-primary"
              >
                Start simulation
                <ArrowRight className="h-4 w-4" />
              </button>
              <div className="rounded-full border border-white/[0.08] bg-white/[0.03] px-5 py-3.5 text-sm text-text-secondary">
                TRIBE generates state outputs. K2 Think explains and operationalizes them.
              </div>
            </div>

            <div className="mt-10 grid gap-4 md:grid-cols-3">
              <MetricCard value="110" label="synthetic people per city run" />
              <MetricCard value="Voice" label="ElevenLabs interviews for each node" />
              <MetricCard value="Report" label="exportable spread and mechanism summary" />
            </div>
          </div>

          <div className="brand-shell rounded-[38px] p-5 md:p-7">
            <div className="grid gap-4 md:grid-cols-2">
              <JourneyCard
                icon={MapPinned}
                title="1. Configure"
                body="Pick a city, choose a use case, and describe the scenario in plain language."
              />
              <JourneyCard
                icon={BrainCircuit}
                title="2. Simulate"
                body="K2 reasons through every person and generates a map of adoption, rejection, and uncertainty."
              />
              <JourneyCard
                icon={AudioLines}
                title="3. Interview"
                body="Click any node and talk to that person in-character with voice replies."
              />
              <JourneyCard
                icon={NotebookPen}
                title="4. Report"
                body="Capture notes, inspect spread mechanisms, and export a team-ready brief."
              />
            </div>

            <div className="mt-5 rounded-[28px] border border-white/[0.08] bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-5">
              <div className="flex items-center gap-2 text-pastel-1">
                <Sparkles className="h-4 w-4" />
                <div className="font-mono text-[10px] uppercase tracking-[0.16em]">Why this version is strong</div>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-text-secondary">
                The product flow is intentionally simple: one clear landing page, one dashboard, one main map, interviewable
                people, lightweight note taking, and immediate reporting. The complexity stays under the hood in K2.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function MetricCard({ value, label }: { value: string; label: string }) {
  return (
    <div className="lab-panel rounded-[26px] px-5 py-5">
      <div className="relative z-10">
        <div className="text-2xl font-semibold text-text-primary">{value}</div>
        <div className="mt-2 text-sm leading-relaxed text-text-secondary">{label}</div>
      </div>
    </div>
  );
}

function JourneyCard({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof MapPinned;
  title: string;
  body: string;
}) {
  return (
    <div className="lab-panel rounded-[28px] p-5">
      <div className="relative z-10">
        <div className="grid h-12 w-12 place-items-center rounded-[18px] border border-white/[0.08] bg-[linear-gradient(135deg,hsl(var(--pastel-2)/0.16),hsl(var(--pastel-3)/0.12))] text-pastel-2">
          <Icon className="h-5 w-5" />
        </div>
        <h2 className="mt-4 text-lg font-semibold">{title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary">{body}</p>
      </div>
    </div>
  );
}
