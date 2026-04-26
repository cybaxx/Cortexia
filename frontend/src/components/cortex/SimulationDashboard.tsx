import { Component, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  ArrowLeft,
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
  Globe2,
  Loader2,
  MapPinned,
  MessageSquare,
  Network,
  NotebookPen,
  RadioTower,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { CITY_PRESETS, getCityById } from '@/data/cities';
import { USE_CASES } from '@/data/useCases';
import { getActionCenterStatus, postActionCenterResearch } from '@/lib/api/simulate';
import { useCortexStore } from '@/store/cortex';
import type { ActionCenterProviderStatus, ActionCenterResponse } from '@/types/simulation';
import { AgentVoiceWorkspace } from './AgentVoiceWorkspace';
import { MapView } from './MapView';

class MapErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean }
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="rounded-[24px] border border-amber-300/20 bg-amber-500/10 p-5 text-sm text-amber-50">
          <div className="font-medium">The map visualization hit a rendering error.</div>
          <div className="mt-2 text-amber-100/80">
            The simulation data is still available. Refresh the page to retry the rich network view.
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

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
    heading: 'Action center',
    body: 'Research the live web, generate actions, verify sources, and export the final package.',
  },
] as const;

const REPORT_TABS = [
  { id: 'brief', label: 'Brief' },
  { id: 'research', label: 'Live Research' },
  { id: 'interventions', label: 'Interventions' },
  { id: 'export', label: 'Export' },
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
  const selectedAgentId = useCortexStore((s) => s.selectedAgentId);
  const setSelectedAgentId = useCortexStore((s) => s.setSelectedAgentId);

  const [reportTab, setReportTab] = useState<(typeof REPORT_TABS)[number]['id']>('brief');
  const [actionCenterStatus, setActionCenterStatus] = useState<Record<string, ActionCenterProviderStatus> | null>(null);
  const [actionCenter, setActionCenter] = useState<ActionCenterResponse | null>(null);
  const [actionCenterLoading, setActionCenterLoading] = useState(false);
  const [actionCenterError, setActionCenterError] = useState<string | null>(null);
  const city = getCityById(cityId);
  const selectedUseCase = USE_CASES.find((item) => item.id === useCase) ?? USE_CASES[1] ?? USE_CASES[0];
  const scenarioText = evidence.text_input.trim();
  const canonicalText =
    evidence.edited_analysis_text?.trim() || evidence.transcript?.trim() || scenarioText;
  const readyToRun = canonicalText.length >= 12 && Boolean(useCase);
  const runIsReady = status === 'ready' && Boolean(latestResponse);
  const stepId = stage === 'evidence' ? 'evidence' : stage === 'interventions' ? 'report' : 'simulation';
  const stepIndex = WORKFLOW_STEPS.findIndex((item) => item.id === stepId);
  useEffect(() => {
    let cancelled = false;
    async function loadActionCenterStatus() {
      try {
        const providers = await getActionCenterStatus();
        if (!cancelled) setActionCenterStatus(providers);
      } catch {
        if (!cancelled) setActionCenterStatus(null);
      }
    }
    void loadActionCenterStatus();
    return () => {
      cancelled = true;
    };
  }, []);

  const dominantPathway = spreadModel?.belief_adoption_pathways?.[0];
  const selectedAgentPayload = selectedAgentId != null ? latestResponse?.agents.find((agent) => agent.id === selectedAgentId) : undefined;
  const spreadStory = spreadModel?.core_story || spreadModel?.network_summary || caseSummary?.key_finding;
  const tribeSurfaceSummary = latestResponse?.tribe_meta?.surface_summary;
  const dominantResponse = tribeSurfaceSummary?.dominant_response ?? null;
  const weakestResponse = tribeSurfaceSummary?.weakest_response ?? null;
  const strongestLink = tribeSurfaceSummary?.strongest_link ?? null;
  const narrativeFlags = tribeSurfaceSummary?.narrative_flags?.slice(0, 3) ?? [];
  const compositeHighlights = tribeSurfaceSummary?.composite_highlights?.slice(0, 3) ?? [];
  const tribeSignalConfidence = latestResponse?.tribe_meta?.signal_confidence;
  const topMechanisms = mechanisms?.dominant_cognitive_drivers?.slice(0, 3) ?? [];
  const hasActionCenter = Boolean(actionCenter);
  const exportItems = [
    runIsReady ? 'Simulation summary' : null,
    latestResponse?.tribe_meta ? 'TRIBE neural state output' : null,
    interventionPlaybook.length > 0 ? 'Intervention playbook' : null,
    hasActionCenter ? 'Action Center brief' : null,
    hasActionCenter && actionCenter.sources.length > 0 ? 'Live research sources' : null,
    hasActionCenter && actionCenter.browser_verification_queue.length > 0 ? 'Browser verification queue' : null,
  ].filter((item): item is string => Boolean(item));

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

  async function runActionCenterResearch() {
    if (!canonicalText) return;
    setActionCenterLoading(true);
    setActionCenterError(null);
    try {
      const result = await postActionCenterResearch({
        domain: selectedUseCase.id,
        city_id: cityId,
        case_goal: caseGoal,
        scenario: canonicalText,
        spread_risk: caseSummary?.spread_risk ?? null,
        key_finding: caseSummary?.key_finding ?? null,
        dominant_pathway: dominantPathway?.label ?? null,
      });
      setActionCenter(result);
      if (result.provider_status) setActionCenterStatus(result.provider_status);
    } catch (error) {
      setActionCenterError(error instanceof Error ? error.message : 'Action Center research failed');
    } finally {
      setActionCenterLoading(false);
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
        <header className="brand-shell rounded-[12px] px-5 py-5 md:px-7">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-4xl">
              <button
                type="button"
                onClick={onBack}
                className="ui-button-secondary mb-5 inline-flex items-center gap-2 px-4 py-2 text-sm"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to landing
              </button>
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
                    className={`rounded-[10px] border px-4 py-4 text-left transition-colors ${
                      active
                        ? 'border-white/[0.2] bg-[linear-gradient(180deg,hsl(var(--pastel-1)/0.16),hsl(var(--bg-elevated))_28%)] opacity-100 shadow-[inset_4px_0_0_0_hsl(var(--pastel-1)),0_0_0_1px_hsl(var(--pastel-1)/0.24),0_4px_24px_rgba(0,0,0,0.4)]'
                        : complete
                          ? 'border-white/[0.14] bg-bg-surface opacity-95'
                          : 'border-white/[0.14] bg-bg-input opacity-92'
                    }`}
                  >
                    <div className={`lab-kicker ${active ? 'text-pastel-1' : 'text-text-secondary'}`}>{item.title}</div>
                    <div className="mt-2 text-sm font-semibold text-text-primary">{item.heading}</div>
                    <div className="mt-2 text-[12px] leading-relaxed text-text-secondary">{item.body}</div>
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
                      className="lab-input w-full rounded-[5px] px-4 py-3 text-sm"
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
                          className={`rounded-[10px] border px-4 py-3 text-left transition-colors ${
                            selectedUseCase.id === option.id
                              ? 'border-white/[0.22] bg-[hsl(var(--pastel-1)/0.15)] shadow-[inset_0_0_0_1px_hsl(var(--pastel-1)/0.18)]'
                              : 'border-white/[0.14] bg-[linear-gradient(180deg,hsl(var(--bg-surface)),hsl(var(--bg-elevated)))] hover:border-white/[0.22] hover:bg-[linear-gradient(180deg,hsl(var(--bg-surface)),hsl(var(--bg-input)))]'
                          }`}
                        >
                          <div className={`text-sm font-semibold ${selectedUseCase.id === option.id ? 'text-pastel-1' : 'text-text-primary'}`}>{option.label}</div>
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
                      className="lab-input min-h-[180px] w-full rounded-[5px] px-4 py-4 text-sm leading-relaxed"
                    />
                  </Field>

                  <Field label="Goal">
                    <textarea
                      value={caseGoal}
                      onChange={(event) => setCaseGoal(event.target.value)}
                      placeholder="What do you want to learn from this simulation?"
                      className="lab-input min-h-[120px] w-full rounded-[5px] px-4 py-4 text-sm leading-relaxed"
                    />
                  </Field>

                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => void runSimulation()}
                      disabled={!readyToRun || status === 'running'}
                      className="ui-button-primary inline-flex items-center justify-center gap-2 px-5 py-4 text-sm disabled:opacity-45"
                    >
                      {status === 'running' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                      Run TRIBE + K2 simulation
                    </button>
                    <button
                      type="button"
                      onClick={goNext}
                      disabled={!latestResponse || status === 'running'}
                      className="ui-button-secondary inline-flex items-center justify-center gap-2 px-5 py-4 text-sm disabled:cursor-not-allowed disabled:opacity-45"
                    >
                      Continue to map
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>

                  <div className="rounded-[10px] border border-white/[0.18] bg-bg-input px-4 py-3 text-xs leading-relaxed text-text-secondary">
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
                {status === 'running' && !latestResponse ? (
                  <div className="rounded-[12px] border border-white/[0.12] bg-bg-input px-6 py-10">
                    <div className="flex items-center gap-3">
                      <Loader2 className="h-5 w-5 animate-spin text-pastel-2" />
                      <div>
                        <div className="text-sm font-medium text-text-primary">Simulation in progress</div>
                        <div className="mt-1 text-sm text-text-secondary">
                          TRIBE, K2, and the propagation loop are running now. The map will populate automatically when the run finishes.
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="rounded-[12px] border border-white/[0.12] bg-bg-input p-2">
                      <MapErrorBoundary>
                        <MapView />
                      </MapErrorBoundary>
                    </div>
                  </>
                )}
              </Panel>

              <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_360px] xl:items-stretch">
                  <Panel
                    title="Selected Person"
                    kicker="Node actions"
                    icon={MessageSquare}
                    body="Select a node to open that person’s persistent voice-agent workspace. Ask by text or microphone, and ElevenLabs speaks the reply back from that exact simulated profile."
                    className="h-full xl:col-span-2"
                  >
                    <AgentVoiceWorkspace
                      payload={selectedAgentPayload}
                      runId={latestResponse?.run_id}
                      onClear={() => setSelectedAgentId(null)}
                    />
                  </Panel>

                  <Panel
                    title="Why It Spread"
                    kicker="Mechanisms"
                    icon={BrainCircuit}
                    body="This combines the spread outcome with TRIBE’s dominant response, processing order, and reinforcement links so the mechanism is less ambiguous."
                    className="h-full"
                  >
                    <div className="space-y-3">
                      <div className="rounded-[10px] border border-white/[0.12] bg-bg-surface px-4 py-4 text-sm leading-relaxed text-text-secondary">
                        {spreadStory ?? 'Run a simulation to see the spread storyline.'}
                      </div>
                      <div className="rounded-[10px] border border-white/[0.12] bg-bg-surface px-4 py-4 text-sm leading-relaxed text-text-secondary">
                        {mechanisms?.mechanism_summary ?? 'Mechanism analysis will appear after the run completes.'}
                        {dominantResponse && (
                          <span>
                            {' '}
                            TRIBE shows the strongest response was <span className="text-text-primary">{dominantResponse.label.toLowerCase()}</span>,
                            peaking at {dominantResponse.peak.toFixed(2)} and {dominantResponse.sustained ? 'staying sustained' : `arriving ${dominantResponse.trajectory}`}.
                          </span>
                        )}
                        {strongestLink && (
                          <span>
                            {' '}
                            The clearest cross-signal interaction was <span className="text-text-primary">{strongestLink.label.toLowerCase()}</span> at r={strongestLink.r.toFixed(2)}.
                          </span>
                        )}
                      </div>
                      {(compositeHighlights.length > 0 || narrativeFlags.length > 0 || topMechanisms.length > 0) && (
                        <div className="rounded-[10px] border border-white/[0.12] bg-bg-input p-4">
                          <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-text-muted">TRIBE readout</div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {compositeHighlights.map((item) => (
                              <div
                                key={item.id}
                                className="ui-tag rounded-[3px] px-3 py-1.5 text-[11px]"
                              >
                                <span className="text-text-primary">{item.label}</span> {formatSignedMetric(item.value)}
                              </div>
                            ))}
                            {topMechanisms.map((item) => (
                              <div
                                key={item.signal}
                                className="ui-tag rounded-[3px] px-3 py-1.5 text-[11px]"
                              >
                                <span className="text-text-primary">{item.description}</span> {Math.round(item.share * 100)}%
                              </div>
                            ))}
                          </div>
                          {narrativeFlags.length > 0 && (
                            <div className="mt-3 space-y-2">
                              {narrativeFlags.map((flag) => (
                                <div key={flag} className="rounded-[6px] border border-white/[0.06] bg-bg-surface px-3 py-2 text-xs leading-relaxed text-text-secondary">
                                  {flag}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
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
                        <ReadoutCard
                          label="TRIBE confidence"
                          value={tribeSignalConfidence != null ? `${Math.round(tribeSignalConfidence * 100)}%` : 'Awaiting run'}
                        />
                        <ReadoutCard
                          label="Weakest response"
                          value={weakestResponse?.label ?? 'Awaiting run'}
                        />
                      </div>
                    </div>
                  </Panel>

                <div className="xl:col-span-3 flex gap-3">
                  <button
                    type="button"
                    onClick={goBackStep}
                    className="ui-button-secondary inline-flex items-center gap-2 px-4 py-3 text-sm"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Back to intake
                  </button>
                  <button
                    type="button"
                    onClick={goNext}
                    className="ui-button-primary inline-flex items-center gap-2 px-4 py-3 text-sm"
                  >
                    Continue to report
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          )}

          {stepId === 'report' && (
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
              <div className="space-y-5">
                <Panel
                  title="Action Center"
                  kicker="3. Export"
                  icon={ShieldCheck}
                  body="This final step turns the simulation into an operational brief, live research dossier, intervention plan, and export package."
                >
                  <div className="space-y-5">
                    <div className="flex flex-wrap gap-2">
                      {REPORT_TABS.map((tab) => (
                        <button
                          key={tab.id}
                          type="button"
                          onClick={() => setReportTab(tab.id)}
                          className={`rounded-[3px] border px-4 py-2 text-sm transition-colors ${
                            reportTab === tab.id
                              ? 'border-white/[0.2] bg-[hsl(var(--pastel-1)/0.15)] text-pastel-1'
                              : 'border-white/[0.14] bg-bg-elevated text-text-secondary'
                          }`}
                        >
                          {tab.label}
                        </button>
                      ))}
                    </div>

                    {reportTab === 'brief' && (
                      <div className="space-y-4">
                        {!hasActionCenter ? (
                          <div className="rounded-[6px] border border-white/[0.06] bg-bg-surface px-4 py-4 text-sm leading-relaxed text-text-secondary">
                            Run live research to generate the Action Center brief.
                          </div>
                        ) : (
                          <>
                            <div className="rounded-[6px] border border-white/[0.06] bg-bg-input px-5 py-5">
                              <div className="lab-kicker">Executive brief</div>
                              <div className="mt-3 text-[26px] font-bold tracking-[-0.02em] text-text-primary">
                                {actionCenter.brief.headline}
                              </div>
                              <p className="mt-3 text-sm leading-relaxed text-text-secondary">
                                {actionCenter.brief.executive_summary}
                              </p>
                            </div>

                            <div className="grid gap-3 sm:grid-cols-3">
                              <ReadoutCard label="Urgency" value={actionCenter.brief.urgency} />
                              <ReadoutCard label="Decision window" value={actionCenter.brief.decision_window} />
                              <ReadoutCard label="Dominant pathway" value={dominantPathway?.label ?? 'Unavailable'} />
                            </div>

                            <div className="rounded-[6px] border border-white/[0.06] bg-bg-surface px-4 py-4 text-sm leading-relaxed text-text-secondary">
                              {actionCenter.brief.confidence_note}
                            </div>

                            {actionCenter.monitoring_queries.length > 0 && (
                              <div className="rounded-[6px] border border-white/[0.06] bg-bg-surface p-4">
                                <div className="mb-3 flex items-center gap-2">
                                  <Search className="h-4 w-4 text-pastel-2" />
                                  <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">
                                    Monitoring queries
                                  </div>
                                </div>
                                <div className="grid gap-2">
                                  {actionCenter.monitoring_queries.map((query) => (
                                    <div key={query} className="rounded-[6px] border border-white/[0.06] bg-bg-input px-3 py-2 text-sm text-text-secondary">
                                      {query}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    )}

                    {reportTab === 'research' && (
                      <div className="space-y-4">
                        <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
                          <div className="rounded-[6px] border border-white/[0.06] bg-bg-surface p-4">
                            <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">
                              Live sources
                            </div>
                            <div className="mt-3 space-y-3">
                              {!hasActionCenter && (
                                <div className="text-sm leading-relaxed text-text-secondary">
                                  Run live research to populate the source dossier.
                                </div>
                              )}
                              {hasActionCenter && actionCenter.sources.length === 0 && (
                                <div className="text-sm leading-relaxed text-text-secondary">
                                  The research pass returned no live sources.
                                </div>
                              )}
                              {(actionCenter?.sources ?? []).map((source) => (
                                <a
                                  key={source.url}
                                  href={source.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="block rounded-[6px] border border-white/[0.06] bg-bg-input px-4 py-3"
                                >
                                  <div className="flex items-start justify-between gap-3">
                                    <div>
                                      <div className="text-sm font-medium text-text-primary">{source.title}</div>
                                      <div className="mt-1 text-[11px] uppercase tracking-[0.12em] text-text-muted">
                                        {source.domain}
                                      </div>
                                    </div>
                                    <ExternalLink className="h-4 w-4 text-text-muted" />
                                  </div>
                                  <p className="mt-2 text-xs leading-relaxed text-text-secondary">{source.snippet}</p>
                                </a>
                              ))}
                            </div>
                          </div>

                          <div className="rounded-[6px] border border-white/[0.06] bg-bg-surface p-4">
                            <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">
                              Pattern extraction
                            </div>
                            <div className="mt-3 space-y-3">
                              {!hasActionCenter && (
                                <div className="text-sm leading-relaxed text-text-secondary">
                                  Run live research to populate the structured extraction panel.
                                </div>
                              )}
                              {hasActionCenter && actionCenter.extracted_patterns.length === 0 && (
                                <div className="text-sm leading-relaxed text-text-secondary">
                                  No structured extraction items were returned for this research pass.
                                </div>
                              )}
                              {(actionCenter?.extracted_patterns ?? []).map((pattern, index) => (
                                <div key={`${pattern.url}-${index}`} className="rounded-[6px] border border-white/[0.06] bg-bg-input px-4 py-3">
                                  <div className="flex items-center justify-between gap-3">
                                    <div className="text-sm font-medium text-text-primary">{pattern.risk_level}</div>
                                    <div className="text-[11px] text-text-muted">{pattern.geography || 'General relevance'}</div>
                                  </div>
                                  <p className="mt-2 text-xs leading-relaxed text-text-secondary">{pattern.claim}</p>
                                  <p className="mt-2 text-xs leading-relaxed text-text-muted">{pattern.why_it_matters}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>

                        <div className="rounded-[6px] border border-white/[0.06] bg-bg-input p-4">
                          <div className="mb-3 flex items-center gap-2">
                            <ShieldCheck className="h-4 w-4 text-pastel-2" />
                            <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">
                              Browser verification queue
                            </div>
                          </div>
                          <div className="space-y-2">
                            {!hasActionCenter && (
                              <div className="text-sm leading-relaxed text-text-secondary">
                                Run live research to populate the browser verification queue.
                              </div>
                            )}
                            {hasActionCenter && actionCenter.browser_verification_queue.length === 0 && (
                              <div className="text-sm leading-relaxed text-text-secondary">
                                This research pass did not surface any browser-priority URLs.
                              </div>
                            )}
                            {(actionCenter?.browser_verification_queue ?? []).map((item) => (
                              <div key={`${item.url}-${item.reason}`} className="rounded-[6px] border border-white/[0.06] bg-bg-surface px-4 py-3">
                                <div className="text-sm font-medium text-text-primary">{item.reason}</div>
                                <div className="mt-1 break-all text-xs text-pastel-2">{item.url}</div>
                                <div className="mt-2 text-xs leading-relaxed text-text-secondary">{item.check_for}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}

                    {reportTab === 'interventions' && (
                      <div className="space-y-3">
                        {(actionCenter?.recommended_actions ?? []).map((item) => (
                          <div key={`${item.title}-${item.timeline}`} className="rounded-[6px] border border-white/[0.06] bg-bg-surface p-4">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div className="text-base font-medium text-text-primary">{item.title}</div>
                              <div className="text-[11px] uppercase tracking-[0.12em] text-text-muted">{item.timeline}</div>
                            </div>
                            <div className="mt-3 grid gap-3 sm:grid-cols-2">
                              <ReadoutCard label="Owner" value={item.owner} />
                              <ReadoutCard label="Audience" value={item.audience} />
                            </div>
                            <p className="mt-3 text-sm leading-relaxed text-text-secondary">{item.action}</p>
                            <p className="mt-2 text-xs leading-relaxed text-text-muted">{item.why_now}</p>
                          </div>
                        ))}

                        {!hasActionCenter && (
                          <div className="rounded-[6px] border border-white/[0.06] bg-bg-surface px-4 py-3 text-sm text-text-secondary">
                            Run live research to generate recommended actions.
                          </div>
                        )}

                        {hasActionCenter && actionCenter.recommended_actions.length === 0 && (
                          <div className="rounded-[6px] border border-white/[0.06] bg-bg-surface px-4 py-3 text-sm text-text-secondary">
                            The research pass completed without any recommended actions.
                          </div>
                        )}
                      </div>
                    )}

                    {reportTab === 'export' && (
                      <div className="space-y-4">
                        <div className="rounded-[6px] border border-white/[0.06] bg-bg-input px-4 py-4 text-sm leading-relaxed text-text-secondary">
                          {runIsReady ? caseSummary?.key_finding : 'Complete a simulation run before exporting.'}
                        </div>

                        <div className="grid gap-2 sm:grid-cols-3">
                          <button
                            type="button"
                            onClick={() => exportCase('pdf')}
                            disabled={!runIsReady}
                            className="ui-button-secondary px-4 py-3 text-sm text-text-primary disabled:opacity-40"
                          >
                            Export PDF
                          </button>
                          <button
                            type="button"
                            onClick={() => exportCase('markdown')}
                            disabled={!runIsReady}
                            className="ui-button-secondary px-4 py-3 text-sm text-text-primary disabled:opacity-40"
                          >
                            Export Markdown
                          </button>
                          <button
                            type="button"
                            onClick={() => exportCase('json')}
                            disabled={!runIsReady}
                            className="ui-button-secondary px-4 py-3 text-sm text-text-primary disabled:opacity-40"
                          >
                            Export JSON
                          </button>
                        </div>

                        {exportItems.length > 0 && (
                          <div className="rounded-[6px] border border-white/[0.06] bg-bg-surface p-4">
                            <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">
                              Included in export
                            </div>
                            <div className="mt-3 grid gap-2">
                              {exportItems.map((item) => (
                                <div key={item} className="rounded-[6px] border border-white/[0.06] bg-bg-input px-3 py-2 text-sm text-text-secondary">
                                  {item}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </Panel>
              </div>

              <div className="space-y-5">
                <Panel
                  title="Control Tower"
                  kicker="Status"
                  icon={RadioTower}
                  body="Provider status, action-center run controls, and what this final step can do right now."
                >
                  <div className="space-y-4">
                    <button
                      type="button"
                      onClick={() => void runActionCenterResearch()}
                      disabled={actionCenterLoading || !canonicalText}
                      className="ui-button-primary inline-flex w-full items-center justify-center gap-2 px-4 py-3 text-sm disabled:opacity-40"
                    >
                      {actionCenterLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                      Run live research
                    </button>

                    {actionCenterError && (
                      <div className="rounded-[18px] border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-100">
                        {actionCenterError}
                      </div>
                    )}

                    <div className="space-y-2">
                      {Object.entries(actionCenterStatus ?? {}).map(([key, provider]) => (
                        <div key={key} className="rounded-[6px] border border-white/[0.06] bg-bg-input px-4 py-3 hover:border-l-2 hover:border-l-pastel-2">
                          <div className="flex items-center justify-between gap-3">
                            <div className="text-sm font-medium capitalize text-text-primary">{key.replace('_', ' ')}</div>
                            <div className={`${providerModeClass(provider.mode, provider.enabled)} rounded-[3px] px-2.5 py-1 text-[10px] uppercase tracking-[0.12em]`}>
                              {provider.mode}
                            </div>
                          </div>
                          <div className="mt-2 text-xs leading-relaxed text-text-secondary">{provider.detail}</div>
                        </div>
                      ))}
                    </div>

                  </div>
                </Panel>

                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={goBackStep}
                    className="ui-button-secondary inline-flex items-center gap-2 px-4 py-3 text-sm"
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
  className,
}: {
  title: string;
  kicker: string;
  icon: typeof Globe2;
  body: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`brand-shell rounded-[12px] p-5 ${className ?? ''}`}>
      <div className="flex items-start gap-3">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-[10px] border border-white/[0.18] bg-[linear-gradient(180deg,hsl(var(--pastel-1)/0.14),hsl(var(--pastel-3)/0.06))] text-pastel-1">
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
      <div className="mb-2 font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-text-muted">{label}</div>
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
    <div className="rounded-[10px] border border-white/[0.12] bg-bg-surface px-4 py-4">
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
    <div className="rounded-[10px] border border-white/[0.12] bg-bg-surface px-4 py-3">
      <div className="font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-text-muted">{label}</div>
      <div className="mt-2 text-sm font-semibold text-text-primary">{value}</div>
    </div>
  );
}

function providerModeClass(mode: string, enabled: boolean) {
  if (!enabled) return 'ui-tag';
  const normalized = mode.toUpperCase();
  if (normalized === 'LIVE-SEARCH') return 'status-tag-live-search';
  if (normalized === 'STRUCTURED-EXTRACT') return 'status-tag-structured-extract';
  if (normalized === 'SYNTHESIS') return 'status-tag-synthesis';
  if (normalized === 'OPERATOR-ASSISTED') return 'status-tag-operator-assisted';
  return 'status-tag-live-search';
}

function formatSignedMetric(value: number) {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}`;
}
