import { Component, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  ArrowLeft,
  AudioLines,
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  Globe2,
  Loader2,
  MapPinned,
  MessageSquare,
  Network,
  NotebookPen,
  RadioTower,
  Sparkles,
} from 'lucide-react';
import { CITY_PRESETS, getCityById } from '@/data/cities';
import { USE_CASES } from '@/data/useCases';
import { useCortexStore } from '@/store/cortex';
import { MapView } from './MapView';

class MapErrorBoundary extends Component<
  {
    safeMode: boolean;
    onRetrySafeMode: () => void;
    children: ReactNode;
  },
  { hasError: boolean }
> {
  constructor(props: { safeMode: boolean; onRetrySafeMode: () => void; children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidUpdate(prevProps: { safeMode: boolean }) {
    if (prevProps.safeMode !== this.props.safeMode && this.state.hasError) {
      this.setState({ hasError: false });
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="rounded-[24px] border border-amber-300/20 bg-amber-500/10 p-5 text-sm text-amber-50">
          <div className="font-medium">The map visualization hit a rendering error.</div>
          <div className="mt-2 text-amber-100/80">
            The simulation data is still available. Retry in safe mode to render agent markers without the network arc overlays.
          </div>
          {!this.props.safeMode && (
            <button
              type="button"
              onClick={this.props.onRetrySafeMode}
              className="mt-4 rounded-[16px] border border-amber-200/30 bg-white/10 px-4 py-2 text-sm text-white"
            >
              Retry map in safe mode
            </button>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}

const NOTES_STORAGE_KEY = 'cortexia-compass-notes';

const COMPLEXITY_PRESETS = [
  { label: 'Simple', value: 0.3, description: 'Clear, low-friction scenario framing.' },
  { label: 'Balanced', value: 0.55, description: 'Default setting for realistic narratives.' },
  { label: 'Complex', value: 0.82, description: 'Dense, emotionally layered, or ambiguous message.' },
];

const INTERVIEW_PROMPTS = [
  'Why did this person react this way?',
  'What would change their mind?',
  'What are they likely to tell a friend next?',
];

const WORKFLOW_STEPS = [
  {
    id: 'evidence',
    title: 'Step 1',
    heading: 'Upload information',
    body: 'Set the scenario, choose the city, and prepare the case you want to simulate.',
  },
  {
    id: 'simulation',
    title: 'Step 2',
    heading: 'Map and simulation',
    body: 'Review the propagation map, inspect candidate nodes, and prepare for interviews.',
  },
  {
    id: 'report',
    title: 'Step 3',
    heading: 'Final report',
    body: 'Review findings, interventions, and export the final report package.',
  },
] as const;

export function SimulationDashboard({ onBack }: { onBack: () => void }) {
  const cityId = useCortexStore((s) => s.cityId);
  const setCityId = useCortexStore((s) => s.setCityId);
  const stage = useCortexStore((s) => s.stage);
  const setStage = useCortexStore((s) => s.setStage);
  const useCase = useCortexStore((s) => s.useCase);
  const setUseCase = useCortexStore((s) => s.setUseCase);
  const caseGoal = useCortexStore((s) => s.caseGoal);
  const setCaseGoal = useCortexStore((s) => s.setCaseGoal);
  const messageComplexity = useCortexStore((s) => s.messageComplexity);
  const setMessageComplexity = useCortexStore((s) => s.setMessageComplexity);
  const evidence = useCortexStore((s) => s.evidence);
  const setEvidenceField = useCortexStore((s) => s.setEvidenceField);
  const status = useCortexStore((s) => s.status);
  const apiError = useCortexStore((s) => s.apiError);
  const runSimulation = useCortexStore((s) => s.runSimulation);
  const latestResponse = useCortexStore((s) => s.latestResponse);
  const caseSummary = useCortexStore((s) => s.caseSummary);
  const spreadModel = useCortexStore((s) => s.spreadModel);
  const mechanisms = useCortexStore((s) => s.mechanisms);
  const interventionPlaybook = useCortexStore((s) => s.interventionPlaybook);
  const exportCase = useCortexStore((s) => s.exportCase);

  const [notes, setNotes] = useState('');
  const [mapSafeMode, setMapSafeMode] = useState(true);
  const city = getCityById(cityId);
  const selectedUseCase = USE_CASES.find((item) => item.id === useCase) ?? USE_CASES[1] ?? USE_CASES[0];
  const scenarioText = evidence.text_input.trim();
  const canonicalText =
    evidence.edited_analysis_text?.trim() || evidence.transcript?.trim() || scenarioText;
  const readyToRun = canonicalText.length >= 12 && Boolean(useCase);
  const runIsReady = status === 'ready' && Boolean(latestResponse);
  const stepId = stage === 'evidence' ? 'evidence' : stage === 'interventions' ? 'report' : 'simulation';
  const stepIndex = WORKFLOW_STEPS.findIndex((item) => item.id === stepId);
  const currentStep = WORKFLOW_STEPS[stepIndex] ?? WORKFLOW_STEPS[0];

  useEffect(() => {
    const saved = window.localStorage.getItem(NOTES_STORAGE_KEY);
    if (saved) setNotes(saved);
  }, []);

  useEffect(() => {
    window.localStorage.setItem(NOTES_STORAGE_KEY, notes);
  }, [notes]);

  useEffect(() => {
    if (latestResponse) {
      setMapSafeMode(true);
    }
  }, [latestResponse]);

  const complexityMeta = useMemo(() => {
    const closest = [...COMPLEXITY_PRESETS].sort(
      (a, b) => Math.abs(a.value - messageComplexity) - Math.abs(b.value - messageComplexity),
    )[0];
    return closest ?? COMPLEXITY_PRESETS[1];
  }, [messageComplexity]);

  const dominantPathway = spreadModel?.belief_adoption_pathways?.[0];
  const spreadStory = spreadModel?.core_story || spreadModel?.network_summary || caseSummary?.key_finding;

  function goToStep(step: (typeof WORKFLOW_STEPS)[number]['id']) {
    if (step === 'evidence') {
      setStage('evidence');
      return;
    }
    if (step === 'report') {
      setStage('interventions');
      return;
    }
    setStage('spread');
  }

  function goNext() {
    if (stepId === 'evidence') {
      goToStep('simulation');
      return;
    }
    if (stepId === 'simulation') {
      goToStep('report');
    }
  }

  function goBackStep() {
    if (stepId === 'report') {
      goToStep('simulation');
      return;
    }
    if (stepId === 'simulation') {
      goToStep('evidence');
    }
  }

  return (
    <div className="relative min-h-screen bg-bg-deep text-text-primary">
      <div className="pointer-events-none fixed inset-0 opacity-65">
        <div className="lab-grid absolute inset-0" />
        <div className="absolute left-[2%] top-[5%] h-[26rem] w-[26rem] rounded-full bg-[radial-gradient(circle,hsl(var(--pastel-2)/0.14),transparent_64%)] blur-3xl" />
        <div className="absolute bottom-[-8%] right-[4%] h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle,hsl(var(--pastel-3)/0.14),transparent_64%)] blur-3xl" />
      </div>

      <div className="relative z-10 mx-auto w-full max-w-[1550px] px-4 pb-8 pt-4 md:px-6">
        <header className="brand-shell rounded-[34px] px-5 py-5 md:px-7">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-4xl">
              <button
                type="button"
                onClick={onBack}
                className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-4 py-2 text-sm text-text-secondary"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to landing
              </button>
              <div className="lab-kicker">Pipeline</div>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight md:text-5xl">
                One phase at a time.
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-relaxed text-text-secondary md:text-base">
                The workflow is now split into distinct screens so you are not forced to scroll through the full
                pipeline at once. Upload the case first, then move into the simulation map and candidate inspection,
                and only then land on the report screen.
              </p>
              <div className="mt-5 rounded-[22px] border border-white/[0.08] bg-white/[0.03] px-5 py-4">
                <div className="lab-kicker">{currentStep.title}</div>
                <div className="mt-2 text-lg font-medium text-text-primary">{currentStep.heading}</div>
                <div className="mt-2 text-sm leading-relaxed text-text-secondary">{currentStep.body}</div>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              {WORKFLOW_STEPS.map((item, index) => {
                const active = item.id === stepId;
                const complete = index < stepIndex;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => goToStep(item.id)}
                    className={`rounded-[22px] border px-4 py-4 text-left transition-colors ${
                      active
                        ? 'border-pastel-2/30 bg-[hsl(var(--pastel-2)/0.10)]'
                        : complete
                          ? 'border-white/[0.12] bg-white/[0.04]'
                          : 'border-white/[0.08] bg-white/[0.02]'
                    }`}
                  >
                    <div className="lab-kicker">{item.title}</div>
                    <div className="mt-2 text-sm font-medium text-text-primary">{item.heading}</div>
                    <div className="mt-2 text-xs leading-relaxed text-text-secondary">{item.body}</div>
                  </button>
                );
              })}
            </div>
          </div>
        </header>

        <section className="mt-5">
          {stepId === 'evidence' && (
            <div className="grid gap-5">
              <Panel
                title="Scenario Setup"
                kicker="1. Configure"
                icon={Globe2}
                body="Pick the city, choose the use case, and describe the scenario you want to simulate."
              >
                <div className="space-y-4">
                  <Field label="City">
                    <select
                      value={cityId}
                      onChange={(event) => setCityId(event.target.value)}
                      className="lab-input w-full rounded-[18px] px-4 py-3 text-sm"
                    >
                      {CITY_PRESETS.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field label="Use Case">
                    <div className="grid gap-2 sm:grid-cols-2">
                      {USE_CASES.map((option) => (
                        <button
                          key={option.id}
                          type="button"
                          onClick={() => setUseCase(option.id)}
                          className={`rounded-[18px] border px-4 py-3 text-left transition-colors ${
                            selectedUseCase.id === option.id
                              ? 'border-pastel-2/35 bg-[hsl(var(--pastel-2)/0.10)]'
                              : 'border-white/[0.08] bg-white/[0.03]'
                          }`}
                        >
                          <div className="text-sm font-medium text-text-primary">{option.label}</div>
                          <div className="mt-1 text-xs leading-relaxed text-text-secondary">{option.description}</div>
                        </button>
                      ))}
                    </div>
                  </Field>

                  <Field label="Scenario">
                    <textarea
                      value={evidence.text_input}
                      onChange={(event) => setEvidenceField('text_input', event.target.value)}
                      placeholder="Example: A short-form video claims a new city policy will quietly remove parking from family neighborhoods and people start forwarding it as proof of a hidden agenda."
                      className="lab-input min-h-[180px] w-full rounded-[20px] px-4 py-4 text-sm leading-relaxed"
                    />
                  </Field>

                  <div className="grid gap-4 lg:grid-cols-2">
                    <Field label="Goal">
                      <textarea
                        value={caseGoal}
                        onChange={(event) => setCaseGoal(event.target.value)}
                        placeholder="What do you want to learn from this simulation?"
                        className="lab-input min-h-[120px] w-full rounded-[20px] px-4 py-4 text-sm leading-relaxed"
                      />
                    </Field>

                    <Field label="Speaker or audience context">
                      <textarea
                        value={evidence.speaker_context ?? ''}
                        onChange={(event) => setEvidenceField('speaker_context', event.target.value)}
                        placeholder="Optional: who is spreading this, where it is appearing, or why it may be resonant locally."
                        className="lab-input min-h-[120px] w-full rounded-[20px] px-4 py-4 text-sm leading-relaxed"
                      />
                    </Field>
                  </div>

                  <Field label="Narrative complexity">
                    <div className="rounded-[20px] border border-white/[0.08] bg-white/[0.03] p-4">
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.01}
                        value={messageComplexity}
                        onChange={(event) => setMessageComplexity(Number(event.target.value))}
                        className="w-full accent-[hsl(var(--pastel-2))]"
                      />
                      <div className="mt-3 flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-medium text-text-primary">{complexityMeta.label}</div>
                          <div className="text-xs text-text-secondary">{complexityMeta.description}</div>
                        </div>
                        <div className="font-mono text-[11px] text-pastel-2">{messageComplexity.toFixed(2)}</div>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {COMPLEXITY_PRESETS.map((preset) => (
                          <button
                            key={preset.label}
                            type="button"
                            onClick={() => setMessageComplexity(preset.value)}
                            className="rounded-full border border-white/[0.08] bg-bg-deep/45 px-3 py-1.5 text-[11px] text-text-secondary"
                          >
                            {preset.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </Field>

                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => void runSimulation()}
                      disabled={!readyToRun || status === 'running'}
                      className="inline-flex items-center justify-center gap-2 rounded-[20px] border border-pastel-2/30 bg-[linear-gradient(135deg,hsl(var(--pastel-2)/0.18),hsl(var(--pastel-3)/0.12))] px-5 py-4 text-sm font-medium text-text-primary disabled:opacity-45"
                    >
                      {status === 'running' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                      Run TRIBE + K2 simulation
                    </button>
                    <button
                      type="button"
                      onClick={goNext}
                      className="inline-flex items-center justify-center gap-2 rounded-[20px] border border-white/[0.08] bg-white/[0.03] px-5 py-4 text-sm text-text-primary"
                    >
                      Continue to map
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>

                  <div className="rounded-[18px] border border-white/[0.08] bg-bg-deep/45 px-4 py-3 text-xs leading-relaxed text-text-secondary">
                    TRIBE is used for the agent-level cognitive state generation. K2 Think is used for the interpretive
                    reasoning trace, belief outcome explanation, spread narrative, and interview conversations.
                  </div>

                  {apiError && <div className="rounded-[18px] border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-100">{apiError}</div>}
                </div>
              </Panel>
            </div>
          )}

          {stepId === 'simulation' && (
            <div className="space-y-5">
              <Panel
                title="Simulation Map"
                kicker="2. Spread"
                icon={MapPinned}
                body="Every node represents one synthetic person. Click any node to inspect its TRIBE state, K2 reasoning, timeline, and future interview panel."
              >
                <div className="mb-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setMapSafeMode(true)}
                    className={`rounded-full border px-3 py-1.5 text-[11px] ${
                      mapSafeMode
                        ? 'border-pastel-2/30 bg-[hsl(var(--pastel-2)/0.10)] text-text-primary'
                        : 'border-white/[0.08] bg-white/[0.03] text-text-secondary'
                    }`}
                  >
                    Safe mode
                  </button>
                  <button
                    type="button"
                    onClick={() => setMapSafeMode(false)}
                    className={`rounded-full border px-3 py-1.5 text-[11px] ${
                      !mapSafeMode
                        ? 'border-pastel-2/30 bg-[hsl(var(--pastel-2)/0.10)] text-text-primary'
                        : 'border-white/[0.08] bg-white/[0.03] text-text-secondary'
                    }`}
                  >
                    Rich overlays
                  </button>
                </div>
                <div className="rounded-[28px] border border-white/[0.08] bg-bg-deep/55 p-2">
                  <MapErrorBoundary safeMode={mapSafeMode} onRetrySafeMode={() => setMapSafeMode(true)}>
                    <MapView showArcs={!mapSafeMode} />
                  </MapErrorBoundary>
                </div>
              </Panel>

              <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
                <div className="grid gap-5 lg:grid-cols-2">
                  <Panel
                    title="Interview Flow"
                    kicker="Node actions"
                    icon={MessageSquare}
                    body="Open a node on the map and use these prompts to start strong interviews later."
                  >
                    <div className="space-y-2">
                      {INTERVIEW_PROMPTS.map((prompt) => (
                        <div key={prompt} className="rounded-[18px] border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-sm text-text-secondary">
                          {prompt}
                        </div>
                      ))}
                      <div className="rounded-[18px] border border-dashed border-white/[0.10] bg-bg-deep/45 px-4 py-3 text-sm text-text-secondary">
                        ElevenLabs interviews are not implemented yet. This is the stage where they will plug in.
                      </div>
                    </div>
                  </Panel>

                  <Panel
                    title="Spread Notes"
                    kicker="Capture"
                    icon={NotebookPen}
                    body="Use this as your working notebook while you inspect propagation and candidate reactions."
                  >
                    <textarea
                      value={notes}
                      onChange={(event) => setNotes(event.target.value)}
                      placeholder="Notes on clusters, surprising reactions, target segments, what changed after interviews, and which interventions seem most promising."
                      className="lab-input min-h-[220px] w-full rounded-[20px] px-4 py-4 text-sm leading-relaxed"
                    />
                  </Panel>
                </div>

                <div className="space-y-5">
                  <Panel
                    title="Why It Spread"
                    kicker="Mechanisms"
                    icon={BrainCircuit}
                    body="A concise explanation of what the current run says is moving this narrative."
                  >
                    <div className="space-y-3">
                      <div className="rounded-[20px] border border-white/[0.08] bg-white/[0.03] px-4 py-4 text-sm leading-relaxed text-text-secondary">
                        {spreadStory ?? 'Run a simulation to see the spread storyline.'}
                      </div>
                      <div className="rounded-[20px] border border-white/[0.08] bg-white/[0.03] px-4 py-4 text-sm leading-relaxed text-text-secondary">
                        {mechanisms?.mechanism_summary ?? 'Mechanism analysis will appear after the run completes.'}
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <ReadoutCard label="Spread risk" value={caseSummary?.spread_risk ?? 'Awaiting run'} />
                        <ReadoutCard
                          label="Adoption rate"
                          value={spreadModel ? `${spreadModel.belief_adoption_rate}%` : 'Awaiting run'}
                        />
                        <ReadoutCard
                          label="Population reached"
                          value={spreadModel ? `${spreadModel.population_reached}%` : 'Awaiting run'}
                        />
                        <ReadoutCard label="Dominant pathway" value={dominantPathway?.label ?? 'Awaiting run'} />
                      </div>
                    </div>
                  </Panel>

                  <Panel
                    title="TRIBE Output"
                    kicker="Neural State"
                    icon={BrainCircuit}
                    body="This is the upstream cognitive-state layer feeding the K2 reasoning pass."
                  >
                    <div className="space-y-3">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <ReadoutCard label="Provider" value={latestResponse?.tribe_meta?.provider ?? 'Awaiting run'} />
                        <ReadoutCard label="Model" value={latestResponse?.tribe_meta?.model_id ?? 'Awaiting run'} />
                        <ReadoutCard
                          label="Dominant ROI"
                          value={latestResponse?.tribe_meta?.dominant_roi ?? 'Awaiting run'}
                        />
                        <ReadoutCard
                          label="Signal confidence"
                          value={
                            latestResponse?.tribe_meta?.signal_confidence != null
                              ? `${Math.round(latestResponse.tribe_meta.signal_confidence * 100)}%`
                              : 'Awaiting run'
                          }
                        />
                      </div>
                      <div className="rounded-[20px] border border-white/[0.08] bg-bg-deep/45 p-4">
                        <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">
                          Formatted neural state
                        </div>
                        <pre className="mt-3 max-h-[120px] overflow-y-auto whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-text-secondary cortex-scroll">
                          {latestResponse?.tribe_meta?.formatted_state ??
                            'Run a simulation to inspect the TRIBE formatted state output driving the downstream K2 pass.'}
                        </pre>
                      </div>
                    </div>
                  </Panel>

                  <div className="flex gap-3">
                    <button
                      type="button"
                      onClick={goBackStep}
                      className="inline-flex items-center gap-2 rounded-[18px] border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-sm text-text-primary"
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Back to intake
                    </button>
                    <button
                      type="button"
                      onClick={goNext}
                      className="inline-flex items-center gap-2 rounded-[18px] border border-pastel-2/30 bg-[hsl(var(--pastel-2)/0.10)] px-4 py-3 text-sm text-text-primary"
                    >
                      Continue to report
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {stepId === 'report' && (
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
              <div className="space-y-5">
                <Panel
                  title="Report"
                  kicker="3. Export"
                  icon={Download}
                  body="This is the final report phase after simulation review and candidate inspection."
                >
                  <div className="space-y-4">
                    <div className="rounded-[20px] border border-white/[0.08] bg-bg-deep/45 px-4 py-4 text-sm leading-relaxed text-text-secondary">
                      {runIsReady
                        ? caseSummary?.key_finding
                        : 'The report section will fill in once TRIBE and K2 complete a simulation run.'}
                    </div>

                    <div className="space-y-2">
                      {interventionPlaybook.slice(0, 4).map((item) => (
                        <div key={item.id} className="rounded-[18px] border border-white/[0.08] bg-white/[0.03] px-4 py-3">
                          <div className="text-sm font-medium text-text-primary">{item.title}</div>
                          <div className="mt-1 text-xs leading-relaxed text-text-secondary">{item.message_strategy}</div>
                        </div>
                      ))}
                      {interventionPlaybook.length === 0 && (
                        <div className="rounded-[18px] border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-sm text-text-secondary">
                          No report output yet.
                        </div>
                      )}
                    </div>

                    <div className="grid gap-2 sm:grid-cols-3">
                      <button
                        type="button"
                        onClick={() => exportCase('pdf')}
                        disabled={!runIsReady}
                        className="rounded-[18px] border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-sm text-text-primary disabled:opacity-40"
                      >
                        Export PDF
                      </button>
                      <button
                        type="button"
                        onClick={() => exportCase('markdown')}
                        disabled={!runIsReady}
                        className="rounded-[18px] border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-sm text-text-primary disabled:opacity-40"
                      >
                        Export Markdown
                      </button>
                      <button
                        type="button"
                        onClick={() => exportCase('json')}
                        disabled={!runIsReady}
                        className="rounded-[18px] border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-sm text-text-primary disabled:opacity-40"
                      >
                        Export JSON
                      </button>
                    </div>
                  </div>
                </Panel>
              </div>

              <div className="space-y-5">
                <Panel
                  title="Report Context"
                  kicker="Summary"
                  icon={FileText}
                  body="The final screen is intentionally narrow: findings, interventions, and exports."
                >
                  <div className="space-y-3">
                    <ReadoutCard label="City" value={city.label} />
                    <ReadoutCard label="Use case" value={selectedUseCase.label} />
                    <ReadoutCard label="Spread risk" value={caseSummary?.spread_risk ?? 'Awaiting run'} />
                    <ReadoutCard label="Dominant pathway" value={dominantPathway?.label ?? 'Awaiting run'} />
                  </div>
                </Panel>

                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={goBackStep}
                    className="inline-flex items-center gap-2 rounded-[18px] border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-sm text-text-primary"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Back to simulation
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function Panel({
  title,
  kicker,
  icon: Icon,
  body,
  children,
}: {
  title: string;
  kicker: string;
  icon: typeof Globe2;
  body: string;
  children: ReactNode;
}) {
  return (
    <section className="brand-shell rounded-[30px] p-5">
      <div className="flex items-start gap-3">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-[18px] border border-white/[0.08] bg-[linear-gradient(135deg,hsl(var(--pastel-2)/0.16),hsl(var(--pastel-3)/0.12))] text-pastel-2">
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <div className="lab-kicker">{kicker}</div>
          <h2 className="mt-2 text-xl font-semibold text-text-primary">{title}</h2>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">{body}</p>
        </div>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <div className="mb-2 font-mono text-[11px] uppercase tracking-[0.14em] text-text-muted">{label}</div>
      {children}
    </label>
  );
}

function StageChip({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof BrainCircuit;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-[22px] border border-white/[0.08] bg-white/[0.03] px-4 py-4">
      <div className="flex items-center gap-3">
        <Icon className="h-4 w-4 text-pastel-2" />
        <div className="text-sm font-medium text-text-primary">{title}</div>
      </div>
      <div className="mt-2 text-sm leading-relaxed text-text-secondary">{body}</div>
    </div>
  );
}

function ReadoutCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[18px] border border-white/[0.08] bg-white/[0.03] px-4 py-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">{label}</div>
      <div className="mt-2 text-sm font-medium text-text-primary">{value}</div>
    </div>
  );
}
