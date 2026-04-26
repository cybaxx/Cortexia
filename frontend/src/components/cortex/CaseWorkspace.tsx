import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  AlertCircle,
  ArrowRight,
  AudioLines,
  BrainCircuit,
  Clock3,
  Download,
  FileAudio2,
  FileText,
  Flag,
  FlaskConical,
  Loader2,
  MapPinned,
  Mic,
  MicOff,
  Network,
  MessageSquare,
  Radar,
  ShieldAlert,
  Sparkles,
  Target,
} from 'lucide-react';
import { getUseCase } from '@/data/useCases';
import { getCityById } from '@/data/cities';
import { useCortexStore, type WorkspaceStage } from '@/store/cortex';
import { postTranscribeAudio } from '@/lib/api/simulate';
import { MapView } from './MapView';

const FLOW_STEPS: Array<{
  id: 'evidence' | 'simulation' | 'report';
  label: string;
  short: string;
  blurb: string;
  stages: WorkspaceStage[];
}> = [
  {
    id: 'evidence',
    label: 'Evidence Intake',
    short: 'Intake',
    blurb: 'Upload the case inputs, refine the source packet, and prepare the model-ready text.',
    stages: ['evidence'],
  },
  {
    id: 'simulation',
    label: 'Simulation & Interviews',
    short: 'Simulation',
    blurb: 'Review the map, simulation outputs, and click nodes to inspect candidate profiles before interviews.',
    stages: ['spread', 'mechanisms'],
  },
  {
    id: 'report',
    label: 'Report',
    short: 'Report',
    blurb: 'Finalize interventions, supporting evidence, and the export-ready brief.',
    stages: ['interventions'],
  },
];

function getFlowStepId(stage: WorkspaceStage): 'evidence' | 'simulation' | 'report' {
  if (stage === 'spread' || stage === 'mechanisms') return 'simulation';
  if (stage === 'interventions') return 'report';
  return 'evidence';
}

function badgeTone(risk: string) {
  if (risk === 'High') return 'text-pastel-1 border-pastel-1/25 bg-[hsl(var(--pastel-1)/0.10)]';
  if (risk === 'Low') return 'text-pastel-2 border-pastel-2/25 bg-[hsl(var(--pastel-2)/0.10)]';
  return 'text-pastel-3 border-pastel-3/25 bg-[hsl(var(--pastel-3)/0.10)]';
}

function statusLabel(status: string) {
  if (status === 'running') return 'Modeling in progress';
  if (status === 'ready') return 'Findings ready';
  if (status === 'error') return 'Needs review';
  return 'Ready for intake';
}

function BrandMark() {
  return (
    <div className="inline-flex items-center gap-3">
      <div className="grid h-11 w-11 place-items-center rounded-2xl border border-white/[0.08] bg-[linear-gradient(180deg,rgba(10,19,28,0.96),rgba(7,13,20,0.98))] shadow-[0_12px_36px_rgba(8,12,20,0.22)]">
        <img src="/cortexia-mark.svg" alt="Cortexia logo" className="h-6 w-6 object-contain" />
      </div>
      <div>
        <div className="lab-kicker">Cortexia Research Lab</div>
        <div className="text-sm font-medium text-text-secondary">Narrative diagnostics workspace</div>
      </div>
    </div>
  );
}

export const CaseWorkspace = () => {
  const useCase = useCortexStore((s) => s.useCase);
  const stage = useCortexStore((s) => s.stage);
  const setStage = useCortexStore((s) => s.setStage);
  const cityId = useCortexStore((s) => s.cityId);
  const setCityId = useCortexStore((s) => s.setCityId);
  const caseGoal = useCortexStore((s) => s.caseGoal);
  const setCaseGoal = useCortexStore((s) => s.setCaseGoal);
  const messageComplexity = useCortexStore((s) => s.messageComplexity);
  const setMessageComplexity = useCortexStore((s) => s.setMessageComplexity);
  const evidence = useCortexStore((s) => s.evidence);
  const runSimulation = useCortexStore((s) => s.runSimulation);
  const exportCase = useCortexStore((s) => s.exportCase);
  const setScreen = useCortexStore((s) => s.setScreen);
  const status = useCortexStore((s) => s.status);
  const apiError = useCortexStore((s) => s.apiError);
  const caseSummary = useCortexStore((s) => s.caseSummary);
  const spreadModel = useCortexStore((s) => s.spreadModel);
  const interventionPlaybook = useCortexStore((s) => s.interventionPlaybook);
  const latestResponse = useCortexStore((s) => s.latestResponse);
  const recentRuns = useCortexStore((s) => s.recentRuns);
  const recentRunsStatus = useCortexStore((s) => s.recentRunsStatus);
  const loadRecentRuns = useCortexStore((s) => s.loadRecentRuns);
  const openRun = useCortexStore((s) => s.openRun);

  const domain = getUseCase(useCase);
  const city = getCityById(cityId);
  const activeFlowStepId = getFlowStepId(stage);
  const stageIndex = FLOW_STEPS.findIndex((item) => item.id === activeFlowStepId);
  const activeFlowStep = FLOW_STEPS[stageIndex] ?? FLOW_STEPS[0];
  const canonicalText =
    evidence.edited_analysis_text?.trim() || evidence.transcript?.trim() || evidence.text_input.trim();
  const canModel = canonicalText.length >= 12;

  const readinessScore = useMemo(() => {
    let score = 18;
    if (evidence.text_input.trim().length >= 40) score += 32;
    if ((evidence.source_url ?? '').trim()) score += 12;
    if ((evidence.speaker_context ?? '').trim()) score += 12;
    if ((evidence.transcript ?? '').trim().length >= 40) score += 12;
    if ((evidence.edited_analysis_text ?? '').trim().length >= 80) score += 14;
    return Math.min(score, 100);
  }, [evidence]);

  useEffect(() => {
    if (recentRunsStatus === 'idle') {
      void loadRecentRuns();
    }
  }, [loadRecentRuns, recentRunsStatus]);

  function goToFlowStep(stepId: 'evidence' | 'simulation' | 'report') {
    if (stepId === 'simulation') {
      setStage('spread');
      return;
    }
    if (stepId === 'report') {
      setStage('interventions');
      return;
    }
    setStage('evidence');
  }

  return (
    <div className="min-h-screen bg-bg-deep text-text-primary">
      <div className="pointer-events-none fixed inset-0 opacity-45">
        <div className="lab-grid absolute inset-0" />
        <div className="absolute left-[4%] top-[5%] h-[320px] w-[320px] rounded-full bg-[radial-gradient(circle,hsl(var(--pastel-2)/0.12),transparent_64%)] blur-3xl" />
        <div className="absolute bottom-[8%] right-[6%] h-[360px] w-[360px] rounded-full bg-[radial-gradient(circle,hsl(var(--pastel-3)/0.14),transparent_62%)] blur-3xl" />
      </div>

      <div className="relative mx-auto flex min-h-screen max-w-[1600px] gap-5 px-4 pb-6 pt-4">
        <main className="min-w-0 flex-1">
          <header className="brand-shell rounded-[36px] px-6 py-6 md:px-7">
            <div className="flex flex-wrap items-start justify-between gap-5">
              <div className="max-w-4xl">
                <BrandMark />
                <h1 className="mt-4 text-3xl font-semibold tracking-tight md:text-4xl">
                  {domain?.label ?? 'Research workspace'}
                </h1>
                <p className="mt-3 max-w-3xl text-sm leading-relaxed text-text-secondary md:text-base">
                  Work through one guided investigation: assemble the evidence packet, model spread conditions, inspect
                  mechanisms, and leave with an intervention brief your team can act on.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <div className="rounded-full border border-white/[0.08] bg-white/[0.04] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-text-secondary">
                  Region · {city.label}
                </div>
                <div className="rounded-full border border-white/[0.08] bg-white/[0.04] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.14em] text-text-secondary">
                  State · {statusLabel(status)}
                </div>
                <button
                  type="button"
                  onClick={() => setScreen('useCases')}
                  className="brand-chip rounded-full px-4 py-2 text-sm font-medium transition-colors hover:border-white/[0.16] hover:text-white"
                >
                  Switch program
                </button>
              </div>
            </div>

            <div className="mt-6 grid gap-3 md:grid-cols-3">
              <QuickMetric
                kicker="Research objective"
                value={caseGoal.trim() || 'Define the case objective in the intake panel.'}
              />
              <QuickMetric
                kicker="Model readiness"
                value={`${readinessScore}%`}
                detail={canModel ? 'Enough evidence to run the model.' : 'Add more source material to run confidently.'}
              />
              <QuickMetric
                kicker="Current outcome"
                value={caseSummary?.spread_risk ? `${caseSummary.spread_risk} spread risk` : 'No findings yet'}
                detail={caseSummary?.recommended_next_step ?? 'Run a case model to generate a recommended next step.'}
              />
            </div>
          </header>

          <section className="mt-5 grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
            <div className="brand-shell rounded-[32px] p-5">
              <div className="flex items-center gap-3">
                <div className="grid h-10 w-10 place-items-center rounded-2xl border border-white/[0.08] bg-[linear-gradient(135deg,hsl(var(--pastel-2)/0.16),hsl(var(--pastel-3)/0.14))]">
                  <FlaskConical className="h-4.5 w-4.5 text-pastel-2" />
                </div>
                <div>
                  <div className="lab-kicker">Investigation Track</div>
                  <h2 className="text-lg font-semibold">Step through the lab workflow</h2>
                </div>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-3">
                {FLOW_STEPS.map((item, index) => {
                  const active = item.id === activeFlowStepId;
                  const completed = index < stageIndex && status !== 'idle';
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => goToFlowStep(item.id)}
                      className={`rounded-[24px] border px-4 py-4 text-left transition-all ${
                        active
                          ? 'brand-chip shadow-[0_12px_34px_rgba(8,12,20,0.18)]'
                          : 'border-white/[0.08] bg-white/[0.03] hover:border-white/[0.16]'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">
                          {String(index + 1).padStart(2, '0')}
                        </span>
                        {completed && <ArrowRight className="h-4 w-4 text-pastel-2" />}
                      </div>
                      <div className="mt-3 text-sm font-semibold text-text-primary">{item.short}</div>
                      <p className="mt-1 text-xs leading-relaxed text-text-secondary">{item.blurb}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="lab-panel rounded-[32px] p-5">
              <div className="relative z-10 flex flex-wrap items-start justify-between gap-4">
                <div className="max-w-2xl">
                  <div className="lab-kicker">Active Module</div>
                  <h2 className="mt-2 text-2xl font-semibold">{activeFlowStep.label}</h2>
                  <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                    {activeFlowStep.blurb}
                  </p>
                </div>
                <div className="rounded-[20px] border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-sm text-text-secondary">
                  {latestResponse?.run_id ? `Run #${latestResponse.run_id}` : 'New investigation'}
                </div>
              </div>
            </div>
          </section>

          <section className="mt-5">
            {activeFlowStepId === 'evidence' && (
              <EvidenceStage
                cityId={cityId}
                setCityId={setCityId}
                caseGoal={caseGoal}
                setCaseGoal={setCaseGoal}
                messageComplexity={messageComplexity}
                setMessageComplexity={setMessageComplexity}
                canModel={canModel}
              />
            )}
            {activeFlowStepId === 'simulation' && <SimulationStage />}
            {activeFlowStepId === 'report' && <InterventionsStage />}
          </section>
        </main>

        <aside className="sticky top-4 hidden h-[calc(100vh-2rem)] w-[370px] shrink-0 xl:block">
          <div className="brand-shell flex h-full flex-col overflow-hidden rounded-[36px]">
            <div className="border-b border-white/[0.08] px-5 py-5">
              <div className="lab-kicker">Mission Snapshot</div>
              <h2 className="mt-2 text-xl font-semibold">
                {caseSummary?.title ?? `${domain?.label ?? 'Research case'} in ${city.label}`}
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                {caseSummary?.key_finding ??
                  'Build the evidence packet, define the local objective, and run the model when the case is ready.'}
              </p>
            </div>

            <div className="cortex-scroll flex-1 space-y-5 overflow-y-auto px-5 py-5">
              <DataStrip
                title="Run state"
                value={statusLabel(status)}
                detail={status === 'running' ? 'The simulation is updating case findings now.' : 'No active job running.'}
              />

              {activeFlowStepId === 'evidence' && (
                <>
                  <section className="brand-card rounded-[24px] p-4">
                    <div className="lab-kicker">Readiness</div>
                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/[0.06]">
                      <div
                        className="h-full rounded-full bg-[linear-gradient(90deg,hsl(var(--pastel-2)),hsl(var(--pastel-3)))]"
                        style={{ width: `${readinessScore}%` }}
                      />
                    </div>
                    <div className="mt-3 flex items-center justify-between gap-3">
                      <div className="text-sm font-medium text-text-primary">{readinessScore}% case-ready</div>
                      <div className="text-xs text-text-secondary">{canModel ? 'Runnable' : 'Draft'}</div>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                      Canonical analysis text, source context, and local objective make the strongest modeling packet.
                    </p>
                  </section>

                  <section className="brand-card rounded-[24px] p-4">
                    <div className="lab-kicker">Next step</div>
                    <div className="mt-2 text-sm font-medium text-text-primary">Run the model to unlock the map and candidate simulation.</div>
                    <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                      Step two focuses on the propagation map and node-level candidate inspection, so you do not need to scroll through it while uploading evidence.
                    </p>
                  </section>
                </>
              )}

              {activeFlowStepId === 'simulation' && (
                <>
                  {caseSummary && spreadModel && (
                    <section className="brand-card rounded-[24px] p-4">
                      <div className="lab-kicker">Simulation metrics</div>
                      <div className="mt-3 grid grid-cols-2 gap-3">
                        <MetricCard label="Adoption" value={`${spreadModel.belief_adoption_rate}%`} />
                        <MetricCard label="Credibility" value={`${spreadModel.scientific_credibility ?? 0}%`} />
                      </div>
                      <div className={`mt-4 inline-flex rounded-full border px-3 py-1 text-xs font-medium ${badgeTone(caseSummary.spread_risk)}`}>
                        Spread risk: {caseSummary.spread_risk}
                      </div>
                    </section>
                  )}

                  <section className="brand-card rounded-[24px] p-4">
                    <div className="lab-kicker">Interview workflow</div>
                    <div className="mt-2 text-sm font-medium text-text-primary">Click any node on the map to inspect a candidate profile.</div>
                    <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                      ElevenLabs candidate interviews are not implemented yet, but this stage is where that interaction would slot in once you are ready to add it.
                    </p>
                  </section>
                </>
              )}

              {activeFlowStepId === 'report' && interventionPlaybook.length > 0 && (
                <DataStrip
                  title="Best next move"
                  value={caseSummary?.recommended_next_step ?? interventionPlaybook[0].title}
                  detail={interventionPlaybook[0].why_this_should_work}
                />
              )}

              <section className="brand-card rounded-[24px] p-4">
                <div className="lab-kicker">Recent investigations</div>
                <div className="mt-3 space-y-2">
                  {recentRunsStatus === 'loading' && <div className="text-sm text-text-secondary">Loading case history…</div>}
                  {recentRunsStatus !== 'loading' && recentRuns.length === 0 && (
                    <div className="text-sm text-text-secondary">No stored investigations yet.</div>
                  )}
                  {recentRuns.slice(0, 4).map((run) => (
                    <button
                      key={run.id}
                      type="button"
                      onClick={() => void openRun(run.id)}
                      className="w-full rounded-[18px] border border-white/[0.08] bg-white/[0.03] px-3 py-3 text-left transition-colors hover:border-white/[0.16]"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-sm font-medium text-text-primary">Run #{run.id}</div>
                        <div className="text-xs text-text-muted">{Math.round(run.fidelity * 100)}% fidelity</div>
                      </div>
                      <div className="mt-1 text-xs text-text-secondary">{run.city_id.toUpperCase()}</div>
                      <div className="mt-2 line-clamp-2 text-xs leading-relaxed text-text-secondary">{run.case_goal}</div>
                    </button>
                  ))}
                </div>
              </section>

              {apiError && (
                <div className="rounded-[24px] border border-pastel-1/25 bg-[hsl(var(--pastel-1)/0.08)] p-4 text-sm text-pastel-1">
                  {apiError}
                </div>
              )}
            </div>

            <div className="border-t border-white/[0.08] px-5 py-4">
              {activeFlowStepId !== 'report' ? (
                  <button
                    type="button"
                    onClick={() => void runSimulation()}
                    disabled={!canModel || status === 'running'}
                    className="w-full rounded-[24px] border border-pastel-2/25 bg-[linear-gradient(135deg,hsl(var(--pastel-2)/0.34),hsl(var(--pastel-3)/0.24),hsl(var(--pastel-1)/0.18))] px-4 py-3 font-mono text-[12px] font-semibold uppercase tracking-[0.14em] text-text-primary disabled:opacity-40"
                  >
                    {status === 'running' ? 'Running Case Model…' : activeFlowStepId === 'evidence' ? 'Run Simulation' : 'Refresh Simulation'}
                  </button>
              ) : null}
              <div className="mt-3 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => exportCase('json')}
                  disabled={!latestResponse}
                  className="rounded-[18px] border border-white/[0.08] px-3 py-2 text-sm text-text-secondary disabled:opacity-40"
                >
                  Export JSON
                </button>
                <button
                  type="button"
                  onClick={() => exportCase('markdown')}
                  disabled={!latestResponse}
                  className="rounded-[18px] border border-white/[0.08] px-3 py-2 text-sm text-text-secondary disabled:opacity-40"
                >
                  Export Brief
                </button>
                <button
                  type="button"
                  onClick={() => exportCase('pdf')}
                  disabled={!latestResponse}
                  className="col-span-2 inline-flex items-center justify-center gap-2 rounded-[18px] border border-pastel-2/20 bg-[hsl(var(--pastel-2)/0.08)] px-3 py-2 text-sm text-white/90 disabled:opacity-40"
                >
                  <Download className="h-4 w-4" />
                  Export Slides PDF
                </button>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};

function EvidenceStage({
  cityId,
  setCityId,
  caseGoal,
  setCaseGoal,
  messageComplexity,
  setMessageComplexity,
  canModel,
}: {
  cityId: string;
  setCityId: (cityId: string) => void;
  caseGoal: string;
  setCaseGoal: (caseGoal: string) => void;
  messageComplexity: number;
  setMessageComplexity: (value: number) => void;
  canModel: boolean;
}) {
  const evidence = useCortexStore((s) => s.evidence);
  const status = useCortexStore((s) => s.status);
  const useCase = useCortexStore((s) => s.useCase);
  const setEvidenceField = useCortexStore((s) => s.setEvidenceField);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [transcribing, setTranscribing] = useState(false);
  const [recording, setRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);

  const analysisPreview = useMemo(
    () =>
      evidence.edited_analysis_text?.trim() ||
      evidence.transcript?.trim() ||
      evidence.text_input.trim() ||
      'Your canonical analysis text will appear here once you provide source material.',
    [evidence.edited_analysis_text, evidence.text_input, evidence.transcript],
  );

  async function transcribeFile(file: File) {
    setTranscribing(true);
    try {
      const result = await postTranscribeAudio(file);
      setEvidenceField('transcript', result.text);
      if (!evidence.edited_analysis_text?.trim()) {
        setEvidenceField('edited_analysis_text', result.text);
      }
      setEvidenceField('audio_input', {
        filename: result.filename,
        mime_type: result.mime_type,
        duration_seconds: result.duration_seconds,
        transcript_confidence: result.transcript_confidence,
        source_type: result.source_type,
        transcript_edited: false,
      });
      useCortexStore.getState().setAudioUpload({
        fileName: result.filename,
        mimeType: result.mime_type || file.type,
        durationSeconds: result.duration_seconds,
        transcriptConfidence: result.transcript_confidence,
        sourceType: result.source_type,
      });
    } finally {
      setTranscribing(false);
    }
  }

  async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    chunksRef.current = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onstop = async () => {
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
      const file = new File([blob], `cortexia-recording-${Date.now()}.webm`, {
        type: blob.type || 'audio/webm',
      });
      setSelectedFile(file);
      await transcribeFile(file);
      stream.getTracks().forEach((track) => track.stop());
    };
    recorder.start();
    mediaRecorderRef.current = recorder;
    setRecording(true);
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
      <div className="space-y-5">
        <section className="brand-shell rounded-[34px] p-6">
          <SectionHeader
            icon={<Target className="h-5 w-5 text-pastel-2" />}
            kicker="Research setup"
            title="Define the case before you ingest evidence"
            body="Set the region, signal complexity, and objective so the model knows what the investigation is trying to answer."
          />

          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <Field label="Domain">
              <div className="lab-input flex h-12 items-center rounded-[20px] px-4 text-sm text-white/95">
                {getUseCase(useCase)?.label ?? 'Research case'}
              </div>
            </Field>
            <Field label="Target city">
              <select
                value={cityId}
                onChange={(e) => setCityId(e.target.value)}
                className="lab-input h-12 w-full rounded-[20px] px-4 text-sm"
              >
                <option value="la">Los Angeles, CA</option>
                <option value="sf">San Francisco, CA</option>
                <option value="sd">San Diego, CA</option>
                <option value="sj">San Jose, CA</option>
                <option value="sac">Sacramento, CA</option>
              </select>
            </Field>
            <Field label="Signal complexity">
              <select
                value={String(messageComplexity)}
                onChange={(e) => setMessageComplexity(Number(e.target.value))}
                className="lab-input h-12 w-full rounded-[20px] px-4 text-sm"
              >
                <option value="0">Simple</option>
                <option value="0.5">Realistic</option>
                <option value="1">Stress test</option>
              </select>
            </Field>
          </div>

          <Field label="Research objective" className="mt-4">
            <textarea
              value={caseGoal}
              onChange={(e) => setCaseGoal(e.target.value)}
              className="lab-input min-h-[104px] w-full rounded-[24px] px-4 py-3 text-sm leading-relaxed"
            />
          </Field>
        </section>

        <section className="brand-shell rounded-[34px] p-6">
          <SectionHeader
            icon={<FileText className="h-5 w-5 text-pastel-1" />}
            kicker="Source packet"
            title="Assemble the evidence set"
            body="Paste the narrative, add provenance, and capture who said it and to whom. This is the analyst-facing intake layer."
          />

          <div className="mt-5 space-y-4">
            <Field label="Narrative or claim">
              <textarea
                value={evidence.text_input}
                onChange={(e) => setEvidenceField('text_input', e.target.value)}
                className="lab-input min-h-[160px] w-full rounded-[24px] px-4 py-3 text-sm leading-relaxed"
                placeholder="Paste the narrative, quote, claim, or excerpt you want to analyze."
              />
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                Start with the raw language you want to test. The model will normalize it into a canonical analysis text later in the workflow.
              </p>
            </Field>

            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Source URL">
                <input
                  value={evidence.source_url ?? ''}
                  onChange={(e) => setEvidenceField('source_url', e.target.value)}
                  className="lab-input h-12 w-full rounded-[20px] px-4 text-sm"
                  placeholder="https://"
                />
              </Field>
              <Field label="Speaker context">
                <input
                  value={evidence.speaker_context ?? ''}
                  onChange={(e) => setEvidenceField('speaker_context', e.target.value)}
                  className="lab-input h-12 w-full rounded-[20px] px-4 text-sm"
                  placeholder="Who said this, in what context, and to whom?"
                />
              </Field>
            </div>
          </div>
        </section>

        <section className="brand-shell rounded-[34px] p-6">
          <SectionHeader
            icon={<AudioLines className="h-5 w-5 text-pastel-3" />}
            kicker="Audio lane"
            title="Attach or record spoken evidence"
            body="Upload a clip or record directly in the browser. Cortexia will transcribe it and fold it into the case packet."
          />

          <div className="mt-5 flex flex-wrap gap-3">
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-[20px] border border-white/[0.08] bg-bg-elevated px-4 py-3 text-sm text-text-primary">
              <FileAudio2 className="h-4 w-4" />
              Upload audio
              <input
                type="file"
                accept="audio/*,video/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  setSelectedFile(file);
                }}
              />
            </label>

            {'MediaRecorder' in window && (
              <button
                type="button"
                onClick={() => (recording ? stopRecording() : void startRecording())}
                className="inline-flex items-center gap-2 rounded-[20px] border border-white/[0.08] bg-bg-elevated px-4 py-3 text-sm text-text-primary"
              >
                {recording ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                {recording ? 'Stop recording' : 'Record audio'}
              </button>
            )}

            <button
              type="button"
              onClick={() => selectedFile && void transcribeFile(selectedFile)}
              disabled={!selectedFile || transcribing}
              className="inline-flex items-center gap-2 rounded-[20px] border border-pastel-2/25 bg-[hsl(var(--pastel-2)/0.10)] px-4 py-3 text-sm text-text-primary disabled:opacity-40"
            >
              {transcribing ? <Loader2 className="h-4 w-4 animate-spin" /> : <AudioLines className="h-4 w-4" />}
              Transcribe audio
            </button>
          </div>

          <div className="mt-4 rounded-[24px] border border-white/[0.08] bg-bg-elevated/50 p-4">
            <div className="text-sm text-text-secondary">
              {selectedFile ? `Selected audio: ${selectedFile.name}` : 'No audio file selected yet.'}
            </div>
            {evidence.audio_input && (
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <MetricCard label="Duration" value={`${Math.round(evidence.audio_input.duration_seconds ?? 0)}s`} />
                <MetricCard
                  label="Transcript"
                  value={`${Math.round((evidence.audio_input.transcript_confidence ?? 0) * 100)}%`}
                />
                <MetricCard label="Source" value={evidence.audio_input.source_type ?? 'audio'} />
              </div>
            )}
          </div>

          <Field label="Transcript" className="mt-4">
            <textarea
              value={evidence.transcript ?? ''}
              onChange={(e) => {
                setEvidenceField('transcript', e.target.value);
                setEvidenceField('audio_input', {
                  ...(evidence.audio_input ?? {}),
                  transcript_edited: true,
                });
              }}
              className="lab-input min-h-[130px] w-full rounded-[24px] px-4 py-3 text-sm leading-relaxed"
              placeholder="Audio transcription will appear here."
            />
          </Field>
        </section>
      </div>

      <div className="space-y-5">
        <section className="brand-shell rounded-[34px] p-6">
          <SectionHeader
            icon={<ShieldAlert className="h-5 w-5 text-pastel-2" />}
            kicker="Canonical analysis text"
            title="Prepare the final model input"
            body="Use this field as the lab-ready version of the narrative. It should be the cleanest possible representation of the claim you want to test."
          />
          <textarea
            value={evidence.edited_analysis_text ?? ''}
            onChange={(e) => setEvidenceField('edited_analysis_text', e.target.value)}
            className="lab-input mt-5 min-h-[280px] w-full rounded-[24px] px-4 py-3 text-sm leading-relaxed"
            placeholder="Refine the transcript and source excerpt into the analysis text you want Cortexia to model."
          />
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
            <span className="text-text-secondary">
              {canModel ? `${analysisPreview.length} characters ready for modeling.` : 'Add enough evidence to build a model-ready case.'}
            </span>
            <span className="rounded-full border border-white/[0.08] px-3 py-1 text-xs text-text-secondary">
              {status === 'error' ? 'Review before rerun' : 'Analyst editable'}
            </span>
          </div>
        </section>

        <section className="brand-shell rounded-[34px] p-6">
          <SectionHeader
            icon={<BrainCircuit className="h-5 w-5 text-pastel-3" />}
            kicker="Lab protocol"
            title="What the model does next"
            body="This is the analytical sequence Cortexia follows once the evidence packet is ready."
          />
          <div className="mt-4 grid gap-3">
            <StoryStep
              icon={<Flag className="h-4 w-4 text-pastel-1" />}
              title="Normalize the claim"
              body="Parse the core assertion, source grounding, speaker context, and harm signals into a consistent internal representation."
            />
            <StoryStep
              icon={<BrainCircuit className="h-4 w-4 text-pastel-2" />}
              title="Simulate population response"
              body="Run TRIBE-informed state generation and estimate which segments adopt, reject, or stay neutral under current conditions."
            />
            <StoryStep
              icon={<Sparkles className="h-4 w-4 text-pastel-3" />}
              title="Generate an intervention brief"
              body="Convert spread patterns into mechanism summaries, vulnerable audiences, and recommended first-response actions."
            />
          </div>
          {status === 'error' && (
            <div className="mt-4 rounded-[20px] border border-pastel-1/20 bg-[hsl(var(--pastel-1)/0.08)] px-4 py-3 text-sm text-pastel-1">
              <AlertCircle className="mr-2 inline h-4 w-4" />
              The last modeling run failed. Review the evidence inputs and try again.
            </div>
          )}
        </section>

        <section className="brand-shell rounded-[34px] p-6">
          <SectionHeader
            icon={<MapPinned className="h-5 w-5 text-pastel-2" />}
            kicker="Regional preview"
            title="Spread canvas"
            body="The map becomes your live propagation view after a simulation run, but stays visible here so the geography is always part of the analyst workflow."
          />
          <div className="mt-5 h-[320px] overflow-hidden rounded-[28px] border border-white/[0.08]">
            <MapView />
          </div>
        </section>

      </div>
    </div>
  );
}

function SimulationStage() {
  const spreadModel = useCortexStore((s) => s.spreadModel);
  const latestResponse = useCortexStore((s) => s.latestResponse);
  const caseSummary = useCortexStore((s) => s.caseSummary);
  const interventionPlaybook = useCortexStore((s) => s.interventionPlaybook);
  const swarmDynamics = useCortexStore((s) => s.swarmDynamics);
  const mechanisms = useCortexStore((s) => s.mechanisms);
  const agents = useCortexStore((s) => s.agentSimulationById);
  const evidenceGraph = useCortexStore((s) => s.evidenceGraph);

  if (!spreadModel || !latestResponse) {
    return <EmptyStage title="Simulation & interviews" body="Run the case model to unlock the map, simulation outputs, and candidate inspection workflow." />;
  }

  const topAgents = Object.values(agents)
    .sort((a, b) => b.k2_decision_confidence - a.k2_decision_confidence)
    .slice(0, 3);

  return (
    <div className="space-y-5">
      <section className="brand-shell rounded-[34px] p-6">
        <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr] xl:items-center">
          <div>
            <div className="lab-kicker">Primary finding</div>
            <h3 className="mt-2 text-3xl font-semibold tracking-tight text-text-primary">
              {spreadModel.spread_risk === 'Low'
                ? 'The claim struggles to spread broadly.'
                : spreadModel.spread_risk === 'High'
                  ? 'The claim has strong conditions for rapid spread.'
                  : 'The claim is likely to spread in selective segments.'}
            </h3>
            <p className="mt-3 max-w-3xl text-base leading-relaxed text-text-secondary">
              {spreadModel.core_story ?? spreadModel.network_summary}
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            <NarrativeStat label="Spread risk" value={spreadModel.spread_risk} tone={spreadModel.spread_risk} />
            <NarrativeStat label="Claim adoption" value={`${spreadModel.belief_adoption_rate}%`} tone="Moderate" />
            <NarrativeStat label="Claim rejection" value={`${spreadModel.claim_rejection_rate ?? 0}%`} tone="Low" />
            <NarrativeStat label="Credibility" value={`${spreadModel.scientific_credibility ?? 0}%`} tone="Low" />
          </div>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-5">
          <section className="brand-shell rounded-[34px] p-4">
            <div className="mb-4 flex items-center justify-between gap-4 px-2">
              <div>
                <h3 className="text-lg font-semibold">Propagation map</h3>
                <p className="text-sm text-text-secondary">
                  Geographic view of where the claim is most likely to take hold, where resistance forms, and where intervention should start.
                </p>
              </div>
              <div className={`rounded-full border px-3 py-1 text-xs font-medium ${badgeTone(spreadModel.spread_risk)}`}>
                {spreadModel.risk_score}/100
              </div>
            </div>
            <div className="h-[560px] overflow-hidden rounded-[28px] border border-white/[0.08]">
              <MapView />
            </div>
          </section>

          {swarmDynamics?.rounds?.length ? (
            <section className="brand-shell rounded-[34px] p-6">
              <div className="mb-4 flex items-center gap-3">
                <div className="grid h-9 w-9 place-items-center rounded-2xl border border-white/[0.08] bg-[linear-gradient(135deg,hsl(var(--pastel-3)/0.16),hsl(var(--pastel-1)/0.12))]">
                  <Clock3 className="h-4.5 w-4.5 text-pastel-3" />
                </div>
                <div>
                  <div className="lab-kicker">Propagation loop</div>
                  <h3 className="text-lg font-semibold">Simulation rounds</h3>
                </div>
              </div>
              <div className="grid gap-4 xl:grid-cols-3">
                {swarmDynamics.rounds.map((round) => (
                  <div key={round.round} className="brand-card rounded-[24px] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-semibold text-text-primary">Round {round.round}</div>
                      <div className="text-xs text-text-secondary">{round.rejection_rate}% reject</div>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-text-secondary">{round.notable_shift}</p>
                    <div className="mt-3 space-y-2">
                      {round.posts.slice(0, 2).map((post) => (
                        <div key={`${round.round}-${post.agent_id}`} className="rounded-[16px] border border-white/[0.08] bg-white/[0.03] p-3">
                          <div className="text-xs font-medium text-text-primary">{post.name}</div>
                          <div className="text-[11px] text-text-muted">{post.role}</div>
                          <p className="mt-2 text-xs leading-relaxed text-text-secondary">{post.post}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </div>

        <div className="space-y-5">
          <StoryPanel
            icon={<Radar className="h-4.5 w-4.5 text-pastel-2" />}
            kicker="Why it spreads"
            title="Primary spread pattern"
            body={swarmDynamics?.narrative_summary ?? spreadModel.network_summary}
          >
            {swarmDynamics?.rounds?.slice(0, 3).map((round) => (
              <div key={round.round} className="brand-card rounded-[18px] p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium text-text-primary">Round {round.round}</div>
                  <div className="text-sm font-semibold text-pastel-2">{round.adoption_rate}% adopt</div>
                </div>
                <div className="mt-1 text-xs text-text-secondary">{round.notable_shift}</div>
                <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">
                  Dominant mechanism: {round.dominant_mechanism.replaceAll('_', ' ')}
                </div>
              </div>
            ))}
          </StoryPanel>

          <StoryPanel
            icon={<ShieldAlert className="h-4.5 w-4.5 text-pastel-3" />}
            kicker="Who is vulnerable"
            title="Most susceptible audiences"
            body="These segments show the strongest modeled pathway for claim uptake and are the best starting point for an intervention strategy."
          >
            {spreadModel.high_risk_segments.slice(0, 3).map((segment) => (
              <div key={`${segment.label}-${segment.dominant_driver}`} className="brand-card rounded-[20px] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold text-text-primary">{segment.label}</div>
                  <span className={`rounded-full border px-2.5 py-1 text-[11px] ${badgeTone(segment.risk_level)}`}>
                    {segment.risk_level}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">{segment.why_vulnerable}</p>
              </div>
            ))}
          </StoryPanel>

          {mechanisms && (
            <StoryPanel
              icon={<MessageSquare className="h-4.5 w-4.5 text-pastel-3" />}
              kicker="Candidate inspection"
              title="Interview prep"
              body="Click map nodes to inspect candidates today. Voice interviews can plug into this exact stage later without changing the pipeline shape."
            >
              {topAgents.map((agent) => (
                <div key={agent.id} className="brand-card rounded-[20px] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-text-primary">{agent.name}</div>
                      <div className="text-xs text-text-secondary">{agent.role}</div>
                    </div>
                    <div className="rounded-full border border-white/[0.08] px-2.5 py-1 text-[11px] text-text-secondary">
                      {Math.round(agent.k2_decision_confidence * 100)}%
                    </div>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-text-secondary">{agent.agent_insight.vulnerability}</p>
                  <p className="mt-2 text-sm leading-relaxed text-text-secondary">{agent.agent_insight.best_intervention}</p>
                </div>
              ))}
              <div className="rounded-[20px] border border-dashed border-white/[0.10] bg-white/[0.02] p-4 text-sm leading-relaxed text-text-secondary">
                Interview mode with ElevenLabs is intentionally not implemented yet. This panel is the placeholder for that next interaction.
              </div>
            </StoryPanel>
          )}

          {evidenceGraph && evidenceGraph.nodes.length > 0 && (
            <StoryPanel
              icon={<Network className="h-4.5 w-4.5 text-pastel-1" />}
              kicker="Evidence extraction"
              title="Claims and themes"
              body="This graph summarizes the claims, actors, and themes pulled from the intake materials before the simulation ran."
            >
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                  <div className="lab-kicker">Nodes</div>
                  {evidenceGraph.nodes.map((node) => (
                    <div key={node.id} className="brand-card rounded-[18px] p-3">
                      <div className="text-sm font-medium text-text-primary">{node.label}</div>
                      <div className="mt-1 text-xs text-text-secondary">
                        {node.kind}
                        {node.risk ? ` · ${node.risk}` : ''}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="space-y-2">
                  <div className="lab-kicker">Edges</div>
                  {evidenceGraph.edges.map((edge, index) => (
                    <div key={`${edge.source}-${edge.target}-${index}`} className="brand-card rounded-[18px] p-3 text-sm text-text-secondary">
                      {edge.source} → {edge.target}
                      <div className="mt-1 text-xs text-text-muted">{edge.label}</div>
                    </div>
                  ))}
                </div>
              </div>
            </StoryPanel>
          )}

          <StoryPanel
            icon={<Sparkles className="h-4.5 w-4.5 text-pastel-1" />}
            kicker="Recommended action"
            title="Best first move"
            body={caseSummary?.key_finding ?? ''}
          >
            {interventionPlaybook[0] && (
              <div className="brand-card rounded-[22px] p-4">
                <div className="text-sm font-semibold text-text-primary">{interventionPlaybook[0].title}</div>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  {interventionPlaybook[0].why_this_should_work}
                </p>
              </div>
            )}
          </StoryPanel>
        </div>
      </div>
    </div>
  );
}

function InterventionsStage() {
  const interventionPlaybook = useCortexStore((s) => s.interventionPlaybook);
  const evidenceTrace = useCortexStore((s) => s.evidenceTrace);

  if (interventionPlaybook.length === 0) {
    return <EmptyStage title="Intervention design" body="Model the case to generate a response playbook." />;
  }

  return (
    <div className="space-y-5">
      <section className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-5">
          {interventionPlaybook.map((item) => (
            <div key={item.id} className="brand-shell rounded-[34px] p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="lab-kicker">Intervention</div>
                  <h3 className="mt-2 text-xl font-semibold">{item.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-text-secondary">{item.why_this_should_work}</p>
                </div>
                <div className="rounded-full border border-pastel-2/25 bg-[hsl(var(--pastel-2)/0.10)] px-3 py-1 text-sm font-medium text-pastel-2">
                  {Math.round(item.confidence * 100)}% confidence
                </div>
              </div>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <InterventionField label="Audience" value={item.target_audience} />
                <InterventionField label="Mechanism" value={item.mechanism_addressed} />
                <InterventionField label="Channel" value={item.recommended_channel} />
                <InterventionField label="Messenger" value={item.recommended_messenger} />
                <InterventionField label="Time horizon" value={item.time_horizon} />
                <InterventionField label="Expected effect" value={item.expected_effect} />
              </div>
              <div className="brand-card mt-4 rounded-[24px] p-4">
                <div className="lab-kicker">Message strategy</div>
                <p className="mt-2 text-sm leading-relaxed text-text-primary">{item.message_strategy}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="space-y-5">
          <DataCard title="Supporting evidence">
            {interventionPlaybook[0].supporting_evidence.map((line) => (
              <div key={line} className="brand-card rounded-[18px] p-3 text-sm text-text-secondary">
                {line}
              </div>
            ))}
          </DataCard>

          {evidenceTrace && (
            <DataCard title="Case brief">
              <div className="brand-card rounded-[20px] p-4">
                <div className="text-sm font-semibold text-text-primary">Themes</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {evidenceTrace.themes.map((theme) => (
                    <span key={theme} className="rounded-full border border-white/[0.08] px-3 py-1 text-xs text-text-secondary">
                      {theme}
                    </span>
                  ))}
                </div>
              </div>
              <div className="brand-card rounded-[20px] p-4 text-sm leading-relaxed text-text-secondary">
                {evidenceTrace.analysis_text}
              </div>
            </DataCard>
          )}
        </div>
      </section>
    </div>
  );
}

function QuickMetric({
  kicker,
  value,
  detail,
}: {
  kicker: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="brand-card rounded-[24px] p-4">
      <div className="lab-kicker">{kicker}</div>
      <div className="mt-2 text-base font-semibold text-text-primary">{value}</div>
      {detail ? <p className="mt-2 text-sm leading-relaxed text-text-secondary">{detail}</p> : null}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="brand-card rounded-[22px] p-4">
      <div className="lab-kicker">{label}</div>
      <div className="mt-2 text-lg font-semibold text-text-primary">{value}</div>
    </div>
  );
}

function Field({
  label,
  children,
  className = '',
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`block space-y-2 ${className}`}>
      <span className="lab-kicker text-white/88">{label}</span>
      {children}
    </label>
  );
}

function SectionHeader({
  icon,
  kicker,
  title,
  body,
}: {
  icon: ReactNode;
  kicker: string;
  title: string;
  body: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl border border-white/[0.08] bg-[linear-gradient(135deg,hsl(var(--pastel-2)/0.16),hsl(var(--pastel-1)/0.10))]">
        {icon}
      </div>
      <div>
        <div className="lab-kicker">{kicker}</div>
        <h3 className="mt-1 text-lg font-semibold">{title}</h3>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary">{body}</p>
      </div>
    </div>
  );
}

function InterventionField({ label, value }: { label: string; value: string }) {
  return (
    <div className="brand-card rounded-[20px] p-4">
      <div className="lab-kicker">{label}</div>
      <div className="mt-2 text-sm leading-relaxed text-text-primary">{value}</div>
    </div>
  );
}

function DataStrip({
  title,
  value,
  detail,
}: {
  title: string;
  value: string;
  detail?: string;
}) {
  return (
    <section className="brand-card rounded-[24px] p-4">
      <div className="lab-kicker">{title}</div>
      <div className="mt-2 text-sm font-semibold text-text-primary">{value}</div>
      {detail ? <p className="mt-2 text-sm leading-relaxed text-text-secondary">{detail}</p> : null}
    </section>
  );
}

function DataCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="brand-shell rounded-[34px] p-6">
      <div className="mb-4 flex items-center gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-2xl border border-white/[0.08] bg-[linear-gradient(135deg,hsl(var(--pastel-2)/0.16),hsl(var(--pastel-1)/0.10))]">
          <Network className="h-4.5 w-4.5 text-pastel-2" />
        </div>
        <h3 className="text-lg font-semibold">{title}</h3>
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function StoryPanel({
  icon,
  kicker,
  title,
  body,
  children,
}: {
  icon: ReactNode;
  kicker: string;
  title: string;
  body: string;
  children: ReactNode;
}) {
  return (
    <section className="brand-shell rounded-[34px] p-6">
      <div className="mb-4 flex items-center gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-2xl border border-white/[0.08] bg-[linear-gradient(135deg,hsl(var(--pastel-2)/0.16),hsl(var(--pastel-1)/0.10))]">
          {icon}
        </div>
        <div>
          <div className="lab-kicker">{kicker}</div>
          <h3 className="text-lg font-semibold">{title}</h3>
        </div>
      </div>
      <p className="mb-4 text-sm leading-relaxed text-text-secondary">{body}</p>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function StoryStep({ icon, title, body }: { icon: ReactNode; title: string; body: string }) {
  return (
    <div className="brand-card rounded-[22px] p-4">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-2xl border border-white/[0.08] bg-white/[0.03]">
          {icon}
        </div>
        <div>
          <div className="text-sm font-semibold text-text-primary">{title}</div>
          <div className="mt-1 text-sm leading-relaxed text-text-secondary">{body}</div>
        </div>
      </div>
    </div>
  );
}

function NarrativeStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'Low' | 'Moderate' | 'High';
}) {
  return (
    <div className={`rounded-[22px] border px-4 py-4 ${badgeTone(tone)}`}>
      <div className="font-mono text-[10px] uppercase tracking-[0.12em] opacity-80">{label}</div>
      <div className="mt-2 text-xl font-semibold text-text-primary">{value}</div>
    </div>
  );
}

function EmptyStage({ title, body }: { title: string; body: string }) {
  return (
    <section className="brand-shell rounded-[34px] p-8">
      <h3 className="text-xl font-semibold">{title}</h3>
      <p className="mt-3 max-w-xl text-sm leading-relaxed text-text-secondary">{body}</p>
    </section>
  );
}
