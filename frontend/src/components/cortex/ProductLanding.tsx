import { ArrowRight, AudioLines, BrainCircuit, MapPinned, NotebookPen } from 'lucide-react';

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
          <div className="inline-flex items-center gap-3 rounded-[10px] border border-white/[0.18] bg-bg-surface px-4 py-2">
            <div className="grid h-14 w-14 place-items-center rounded-[10px] border border-white/[0.18] bg-[linear-gradient(180deg,hsl(var(--pastel-1)/0.14),hsl(var(--pastel-3)/0.06))] p-1.5">
              <img src="/cortexia-mark.svg" alt="Cortexia logo" className="h-full w-full object-contain" />
            </div>
            <div>
              <div className="lab-kicker">Cortexia</div>
              <div className="text-sm text-text-secondary">TRIBE + K2 social simulation studio</div>
            </div>
          </div>

          <button
            type="button"
            onClick={onEnter}
            className="ui-button-primary inline-flex items-center gap-2 px-5 py-3 text-sm transition-transform hover:-translate-y-0.5"
          >
            Open dashboard
            <ArrowRight className="h-4 w-4" />
          </button>
        </header>

        <section className="grid flex-1 items-center gap-8 py-10 xl:grid-cols-[1.08fr_0.92fr]">
          <div>
            <h1 className="max-w-4xl text-5xl font-semibold leading-[0.94] tracking-[-0.04em] md:text-7xl">
              City-scale narrative simulation.
            </h1>

            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-text-secondary md:text-xl">
              Cortexia Compass turns one scenario into a city-scale simulation. TRIBE models each person&apos;s cognitive
              state, K2 Think interprets how the narrative lands, and the map shows how it spreads across interviewable
              synthetic people you can inspect, question, and report on.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <button type="button" onClick={onEnter} className="ui-button-primary inline-flex items-center gap-2 px-6 py-3.5 text-sm">
                Start simulation
                <ArrowRight className="h-4 w-4" />
              </button>
              <div className="rounded-[10px] border border-white/[0.18] bg-bg-surface px-5 py-3.5 text-sm text-text-secondary">
                TRIBE generates state outputs. K2 Think explains and operationalizes them.
              </div>
            </div>
          </div>

          <div className="brand-shell rounded-[12px] p-5 md:p-7">
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
          </div>
        </section>
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
    <div className="lab-panel rounded-[10px] p-5">
      <div className="relative z-10">
        <div className="grid h-12 w-12 place-items-center rounded-[10px] border border-white/[0.18] bg-[linear-gradient(180deg,hsl(var(--pastel-1)/0.14),hsl(var(--pastel-3)/0.06))] text-pastel-1">
          <Icon className="h-5 w-5" />
        </div>
        <h2 className="mt-4 text-lg font-semibold">{title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary">{body}</p>
      </div>
    </div>
  );
}
