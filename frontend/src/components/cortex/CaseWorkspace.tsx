import { useMemo, useRef, useState, type ReactNode } from 'react';
import {
  AlertCircle,
  ArrowRight,
  AudioLines,
  Download,
  FileAudio2,
  FileText,
  Link2,
  Loader2,
  Mic,
  MicOff,
  Network,
  ShieldAlert,
} from 'lucide-react';
import { getUseCase } from '@/data/useCases';
import { getCityById } from '@/data/cities';
import { useCortexStore, type WorkspaceStage } from '@/store/cortex';
import { postTranscribeAudio } from '@/lib/api/simulate';
import { MapView } from './MapView';

const STAGES: Array<{ id: WorkspaceStage; label: string; blurb: string }> = [
  { id: 'evidence', label: 'Evidence', blurb: 'Ingest source material and define the case.' },
  { id: 'spread', label: 'Spread Model', blurb: 'Model spread risk, hotspots, and vulnerable segments.' },
  { id: 'mechanisms', label: 'Mechanisms', blurb: 'Inspect why this narrative moves people.' },
  { id: 'interventions', label: 'Interventions', blurb: 'Turn findings into a practical response plan.' },
];

function badgeTone(risk: string) {
  if (risk === 'High') return 'text-pastel-3 border-pastel-3/25 bg-[hsl(var(--pastel-3)/0.10)]';
  if (risk === 'Low') return 'text-pastel-2 border-pastel-2/25 bg-[hsl(var(--pastel-2)/0.10)]';
  return 'text-pastel-1 border-pastel-1/25 bg-[hsl(var(--pastel-1)/0.10)]';
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
  const setEvidenceField = useCortexStore((s) => s.setEvidenceField);
  const setAudioUpload = useCortexStore((s) => s.setAudioUpload);
  const runSimulation = useCortexStore((s) => s.runSimulation);
  const exportCase = useCortexStore((s) => s.exportCase);
  const setScreen = useCortexStore((s) => s.setScreen);
  const status = useCortexStore((s) => s.status);
  const apiError = useCortexStore((s) => s.apiError);
  const caseSummary = useCortexStore((s) => s.caseSummary);
  const spreadModel = useCortexStore((s) => s.spreadModel);
  const mechanisms = useCortexStore((s) => s.mechanisms);
  const interventionPlaybook = useCortexStore((s) => s.interventionPlaybook);
  const evidenceTrace = useCortexStore((s) => s.evidenceTrace);
  const latestResponse = useCortexStore((s) => s.latestResponse);

  const domain = getUseCase(useCase);
  const city = getCityById(cityId);
  const canModel =
    (evidence.edited_analysis_text?.trim() ||
      evidence.transcript?.trim() ||
      evidence.text_input.trim()).length >= 12;

  const stageIndex = STAGES.findIndex((item) => item.id === stage);

  return (
    <div className="min-h-screen bg-bg-deep text-text-primary">
      <div className="mx-auto flex min-h-screen max-w-[1600px] gap-5 px-4 pb-5 pt-4">
        <main className="min-w-0 flex-1">
          <header className="rounded-[34px] border border-white/[0.1] bg-bg-surface/[0.92] px-6 py-5 shadow-[0_16px_60px_rgba(8,12,20,0.26)]">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
                  Cortexia · Research Workspace
                </div>
                <h1 className="mt-2 text-2xl font-semibold tracking-tight">
                  {domain?.label ?? 'Case Workspace'}
                </h1>
                <p className="mt-2 max-w-3xl text-sm leading-relaxed text-text-secondary">
                  Ingest evidence, model spread, diagnose mechanisms, and build an intervention playbook grounded in
                  TRIBE-informed behavioral dynamics.
                </p>
              </div>
              <div className="flex items-center gap-3">
                <div className="rounded-full border border-white/[0.08] bg-white/[0.04] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.12em] text-text-secondary">
                  {city.label}
                </div>
                <button
                  type="button"
                  onClick={() => setScreen('useCases')}
                  className="rounded-full border border-white/[0.08] px-4 py-2 text-sm text-text-secondary transition-colors hover:border-white/[0.16] hover:text-text-primary"
                >
                  Switch domain
                </button>
              </div>
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-4">
              {STAGES.map((item, index) => {
                const active = item.id === stage;
                const completed = index < stageIndex && status !== 'idle';
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setStage(item.id)}
                    className={`rounded-[24px] border px-4 py-3 text-left transition-all ${
                      active
                        ? 'border-pastel-2/35 bg-[hsl(var(--pastel-2)/0.12)]'
                        : 'border-white/[0.08] bg-white/[0.03] hover:border-white/[0.16]'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">
                        {String(index + 1).padStart(2, '0')}
                      </span>
                      {completed && <ArrowRight className="h-4 w-4 text-pastel-2" />}
                    </div>
                    <div className="mt-2 text-sm font-semibold text-text-primary">{item.label}</div>
                    <p className="mt-1 text-xs leading-relaxed text-text-secondary">{item.blurb}</p>
                  </button>
                );
              })}
            </div>
          </header>

          <section className="mt-5">
            {stage === 'evidence' && (
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
            {stage === 'spread' && <SpreadStage />}
            {stage === 'mechanisms' && <MechanismsStage />}
            {stage === 'interventions' && <InterventionsStage />}
          </section>
        </main>

        <aside className="sticky top-4 h-[calc(100vh-2rem)] w-[360px] shrink-0">
          <div className="flex h-full flex-col overflow-hidden rounded-[34px] border border-white/[0.12] bg-[linear-gradient(180deg,rgba(18,24,34,0.98),rgba(12,18,28,0.98))] shadow-[0_24px_120px_rgba(8,12,20,0.45)]">
            <div className="border-b border-white/[0.08] px-5 py-4">
              <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-text-muted">Case summary</div>
              <h2 className="mt-2 text-lg font-semibold text-text-primary">
                {caseSummary?.title ?? `${domain?.label ?? 'Case'} in ${city.label}`}
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                {caseSummary?.key_finding ??
                  'Use the evidence stage to ingest text, source context, or audio, then model how the narrative spreads.'}
              </p>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto px-5 py-5 cortex-scroll">
              <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.04] p-4">
                <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">Run state</div>
                <div className="mt-2 flex items-center gap-3">
                  <span className={`h-2.5 w-2.5 rounded-full ${status === 'running' ? 'bg-pastel-2 animate-pulse' : status === 'error' ? 'bg-pastel-3' : 'bg-pastel-1'}`} />
                  <span className="text-sm font-medium text-text-primary">{status}</span>
                </div>
                {caseSummary && (
                  <div className={`mt-3 inline-flex rounded-full border px-3 py-1 text-xs font-medium ${badgeTone(caseSummary.spread_risk)}`}>
                    Spread risk: {caseSummary.spread_risk}
                  </div>
                )}
              </div>

              {caseSummary && (
                <div className="grid grid-cols-2 gap-3">
                  <MetricCard label="Confidence" value={`${Math.round(caseSummary.overall_confidence * 100)}%`} />
                  <MetricCard label="Region" value={caseSummary.target_region} />
                </div>
              )}

              {evidenceTrace && (
                <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.04] p-4">
                  <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">Evidence trace</div>
                  <div className="mt-3 space-y-3">
                    {evidenceTrace.claims.slice(0, 3).map((claim) => (
                      <div key={claim.id} className="rounded-[18px] border border-white/[0.06] bg-bg-deep/40 p-3">
                        <div className="text-sm leading-relaxed text-text-primary">{claim.text}</div>
                        <div className={`mt-2 inline-flex rounded-full border px-2.5 py-1 text-[11px] ${badgeTone(claim.risk)}`}>
                          {claim.risk} claim
                        </div>
                      </div>
                    ))}
                    <div className="flex flex-wrap gap-2">
                      {evidenceTrace.themes.map((theme) => (
                        <span key={theme} className="rounded-full border border-white/[0.08] px-3 py-1 text-xs text-text-secondary">
                          {theme}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {interventionPlaybook.length > 0 && (
                <div className="rounded-[24px] border border-white/[0.08] bg-white/[0.04] p-4">
                  <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">Recommended next step</div>
                  <div className="mt-2 text-sm font-medium text-text-primary">{caseSummary?.recommended_next_step}</div>
                  <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                    {interventionPlaybook[0].why_this_should_work}
                  </p>
                </div>
              )}

              {apiError && (
                <div className="rounded-[24px] border border-pastel-3/25 bg-[hsl(var(--pastel-3)/0.08)] p-4 text-sm text-pastel-3">
                  {apiError}
                </div>
              )}
            </div>

            <div className="border-t border-white/[0.08] px-5 py-4">
              <button
                type="button"
                onClick={() => void runSimulation()}
                disabled={!canModel || status === 'running'}
                className="w-full rounded-[24px] border border-pastel-2/25 bg-[linear-gradient(135deg,hsl(var(--pastel-2)/0.42),hsl(var(--pastel-1)/0.24),hsl(var(--pastel-3)/0.24))] px-4 py-3 font-mono text-[12px] font-semibold uppercase tracking-[0.14em] text-text-primary disabled:opacity-40"
              >
                {status === 'running' ? 'Modeling Case…' : 'Model Case'}
              </button>
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
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-white/[0.08] bg-white/[0.04] p-4">
      <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">{label}</div>
      <div className="mt-2 text-lg font-semibold text-text-primary">{value}</div>
    </div>
  );
}

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
  const setEvidenceField = useCortexStore((s) => s.setEvidenceField);
  const status = useCortexStore((s) => s.status);
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
    <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
      <div className="space-y-5">
        <section className="rounded-[34px] border border-white/[0.1] bg-bg-surface/[0.9] p-6">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">Target region</span>
              <select
                value={cityId}
                onChange={(e) => setCityId(e.target.value)}
                className="h-12 w-full rounded-[20px] border border-white/[0.08] bg-bg-elevated px-4 text-sm text-text-primary"
              >
                <option value="la">Los Angeles, CA</option>
                <option value="sf">San Francisco, CA</option>
                <option value="sd">San Diego, CA</option>
                <option value="sj">San Jose, CA</option>
                <option value="sac">Sacramento, CA</option>
              </select>
            </label>
            <label className="space-y-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">Signal complexity</span>
              <select
                value={String(messageComplexity)}
                onChange={(e) => setMessageComplexity(Number(e.target.value))}
                className="h-12 w-full rounded-[20px] border border-white/[0.08] bg-bg-elevated px-4 text-sm text-text-primary"
              >
                <option value="0">Simple</option>
                <option value="0.5">Realistic</option>
                <option value="1">Stress Test</option>
              </select>
            </label>
          </div>

          <label className="mt-4 block space-y-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">Case goal</span>
            <textarea
              value={caseGoal}
              onChange={(e) => setCaseGoal(e.target.value)}
              className="min-h-[96px] w-full rounded-[24px] border border-white/[0.08] bg-bg-elevated px-4 py-3 text-sm leading-relaxed text-text-primary"
            />
          </label>
        </section>

        <section className="rounded-[34px] border border-white/[0.1] bg-bg-surface/[0.9] p-6">
          <div className="flex items-center gap-3">
            <FileText className="h-5 w-5 text-pastel-1" />
            <div>
              <h3 className="text-lg font-semibold">Evidence intake</h3>
              <p className="text-sm text-text-secondary">Collect raw text, source context, and optional audio transcript.</p>
            </div>
          </div>

          <div className="mt-5 space-y-4">
            <label className="block space-y-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">Raw text input</span>
              <textarea
                value={evidence.text_input}
                onChange={(e) => setEvidenceField('text_input', e.target.value)}
                className="min-h-[140px] w-full rounded-[24px] border border-white/[0.08] bg-bg-elevated px-4 py-3 text-sm leading-relaxed text-text-primary"
                placeholder="Paste the narrative, quote, claim, or excerpt you want to analyze."
              />
            </label>

            <label className="block space-y-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">Source URL</span>
              <input
                value={evidence.source_url ?? ''}
                onChange={(e) => setEvidenceField('source_url', e.target.value)}
                className="h-12 w-full rounded-[20px] border border-white/[0.08] bg-bg-elevated px-4 text-sm text-text-primary"
                placeholder="https://"
              />
            </label>

            <label className="block space-y-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">Speaker context</span>
              <input
                value={evidence.speaker_context ?? ''}
                onChange={(e) => setEvidenceField('speaker_context', e.target.value)}
                className="h-12 w-full rounded-[20px] border border-white/[0.08] bg-bg-elevated px-4 text-sm text-text-primary"
                placeholder="Who said this, in what context, and to whom?"
              />
            </label>
          </div>
        </section>

        <section className="rounded-[34px] border border-white/[0.1] bg-bg-surface/[0.9] p-6">
          <div className="flex items-center gap-3">
            <AudioLines className="h-5 w-5 text-pastel-2" />
            <div>
              <h3 className="text-lg font-semibold">Audio evidence</h3>
              <p className="text-sm text-text-secondary">Upload or record audio, then transcribe it with ElevenLabs.</p>
            </div>
          </div>

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
                <MetricCard label="Transcript" value={`${Math.round((evidence.audio_input.transcript_confidence ?? 0) * 100)}%`} />
                <MetricCard label="Source" value={evidence.audio_input.source_type ?? 'audio'} />
              </div>
            )}
          </div>

          <label className="mt-4 block space-y-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">Transcript</span>
            <textarea
              value={evidence.transcript ?? ''}
              onChange={(e) => {
                setEvidenceField('transcript', e.target.value);
                setEvidenceField('audio_input', {
                  ...(evidence.audio_input ?? {}),
                  transcript_edited: true,
                });
              }}
              className="min-h-[120px] w-full rounded-[24px] border border-white/[0.08] bg-bg-elevated px-4 py-3 text-sm leading-relaxed text-text-primary"
              placeholder="Audio transcription will appear here."
            />
          </label>
        </section>
      </div>

      <div className="space-y-5">
        <section className="rounded-[34px] border border-white/[0.1] bg-bg-surface/[0.9] p-6">
          <div className="flex items-center gap-3">
            <ShieldAlert className="h-5 w-5 text-pastel-3" />
            <div>
              <h3 className="text-lg font-semibold">Canonical analysis text</h3>
              <p className="text-sm text-text-secondary">This is the final text the spread model will analyze.</p>
            </div>
          </div>
          <textarea
            value={evidence.edited_analysis_text ?? ''}
            onChange={(e) => setEvidenceField('edited_analysis_text', e.target.value)}
            className="mt-5 min-h-[280px] w-full rounded-[24px] border border-white/[0.08] bg-bg-elevated px-4 py-3 text-sm leading-relaxed text-text-primary"
            placeholder="Refine the transcript and source excerpt into the analysis text you want Cortexia to model."
          />
          <div className="mt-4 text-sm text-text-secondary">
            {canModel
              ? `${analysisPreview.length} characters ready for modeling.`
              : 'Add enough evidence to build a model-ready case.'}
          </div>
        </section>

        <section className="rounded-[34px] border border-white/[0.1] bg-bg-surface/[0.9] p-6">
          <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">Research preview</div>
          <div className="mt-4 rounded-[24px] border border-white/[0.08] bg-white/[0.03] p-4">
            <div className="text-sm font-semibold text-text-primary">What Cortexia will do next</div>
            <ul className="mt-3 space-y-2 text-sm leading-relaxed text-text-secondary">
              <li>Identify the highest-risk claims and themes in the evidence.</li>
              <li>Model which synthetic agents are most likely to adopt, reject, or amplify the narrative.</li>
              <li>Generate mechanism-linked intervention options with channels, messengers, and confidence.</li>
            </ul>
          </div>
          {status === 'error' && (
            <div className="mt-4 rounded-[20px] border border-pastel-3/20 bg-[hsl(var(--pastel-3)/0.08)] px-4 py-3 text-sm text-pastel-3">
              <AlertCircle className="mr-2 inline h-4 w-4" />
              The last modeling run failed. Review the evidence inputs and try again.
            </div>
          )}
        </section>

        <section className="rounded-[34px] border border-white/[0.1] bg-bg-surface/[0.9] p-6">
          <div className="flex items-center gap-3">
            <Link2 className="h-5 w-5 text-pastel-2" />
            <div>
              <h3 className="text-lg font-semibold">Regional map preview</h3>
              <p className="text-sm text-text-secondary">
                The map stays in the product. Once you model the case, this regional view becomes the live spread canvas.
              </p>
            </div>
          </div>
          <div className="mt-5 h-[320px] overflow-hidden rounded-[28px] border border-white/[0.08]">
            <MapView />
          </div>
        </section>
      </div>
    </div>
  );
}

function SpreadStage() {
  const spreadModel = useCortexStore((s) => s.spreadModel);
  const latestResponse = useCortexStore((s) => s.latestResponse);

  if (!spreadModel || !latestResponse) {
    return <EmptyStage title="Spread Model" body="Model the case to unlock spread diagnostics." />;
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
      <div className="space-y-5">
        <section className="grid gap-4 md:grid-cols-4">
          <MetricCard label="Spread risk" value={String(spreadModel.risk_score)} />
          <MetricCard label="Adoption rate" value={`${spreadModel.belief_adoption_rate}%`} />
          <MetricCard label="Population reached" value={`${spreadModel.population_reached}%`} />
          <MetricCard label="Avg load" value={spreadModel.avg_cognitive_load.toFixed(2)} />
        </section>

        <section className="rounded-[34px] border border-white/[0.1] bg-bg-surface/[0.9] p-4">
          <div className="mb-4 flex items-center justify-between gap-4 px-2">
            <div>
              <h3 className="text-lg font-semibold">Spread map</h3>
              <p className="text-sm text-text-secondary">
                Geographic view of modeled adoption, rejection, and concentration of risk with cleaner nodes and lower-noise pathways.
              </p>
            </div>
            <div className={`rounded-full border px-3 py-1 text-xs font-medium ${badgeTone(spreadModel.spread_risk)}`}>
              {spreadModel.spread_risk} risk
            </div>
          </div>
          <div className="h-[560px] overflow-hidden rounded-[28px] border border-white/[0.08]">
            <MapView />
          </div>
        </section>
      </div>

      <div className="space-y-5">
        <DataCard title="Map reading guide">
          <div className="rounded-[20px] border border-white/[0.08] bg-white/[0.04] p-4">
            <div className="text-sm font-semibold text-text-primary">What to look for</div>
            <ul className="mt-3 space-y-2 text-sm leading-relaxed text-text-secondary">
              <li>Dense peach circles indicate neighborhoods where corrective framing is failing.</li>
              <li>Pastel blue nodes are agents more likely to adopt the corrective narrative.</li>
              <li>Click any node to open its mechanism-level readout and intervention hint.</li>
            </ul>
          </div>
        </DataCard>

        <DataCard title="High-risk segments">
          {spreadModel.high_risk_segments.slice(0, 4).map((segment) => (
            <div key={`${segment.label}-${segment.dominant_driver}`} className="rounded-[20px] border border-white/[0.08] bg-white/[0.04] p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold text-text-primary">{segment.label}</div>
                <span className={`rounded-full border px-2.5 py-1 text-[11px] ${badgeTone(segment.risk_level)}`}>
                  {segment.risk_level}
                </span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">{segment.why_vulnerable}</p>
            </div>
          ))}
        </DataCard>

        <DataCard title="Belief pathways">
          {spreadModel.belief_adoption_pathways.map((pathway) => (
            <div key={pathway.id} className="flex items-center justify-between gap-3 rounded-[18px] border border-white/[0.08] bg-white/[0.04] p-3">
              <div>
                <div className="text-sm font-medium text-text-primary">{pathway.label}</div>
                <div className="text-xs text-text-secondary">{pathway.description}</div>
              </div>
              <div className="text-sm font-semibold text-pastel-2">{Math.round(pathway.share * 100)}%</div>
            </div>
          ))}
        </DataCard>
      </div>
    </div>
  );
}

function MechanismsStage() {
  const mechanisms = useCortexStore((s) => s.mechanisms);
  const agents = useCortexStore((s) => s.agentSimulationById);

  if (!mechanisms) {
    return <EmptyStage title="Mechanisms" body="Run the case model to inspect the cognitive and social drivers." />;
  }

  const topAgents = Object.values(agents)
    .sort((a, b) => b.k2_decision_confidence - a.k2_decision_confidence)
    .slice(0, 3);

  return (
    <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
      <div className="space-y-5">
        <section className="rounded-[34px] border border-white/[0.1] bg-bg-surface/[0.9] p-6">
          <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">Mechanism summary</div>
          <h3 className="mt-3 text-xl font-semibold">{mechanisms.mechanism_summary}</h3>
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            {mechanisms.dominant_cognitive_drivers.map((driver) => (
              <div key={driver.signal} className="rounded-[24px] border border-white/[0.08] bg-white/[0.04] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold text-text-primary">{driver.signal.replaceAll('_', ' ')}</div>
                  <div className="text-sm font-semibold text-pastel-2">{Math.round(driver.share * 100)}%</div>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">{driver.description}</p>
              </div>
            ))}
          </div>
        </section>

        <DataCard title="Evidence links">
          {mechanisms.evidence_links.map((link) => (
            <div key={link.label} className="rounded-[18px] border border-white/[0.08] bg-white/[0.04] p-3">
              <div className="text-sm text-text-primary">{link.label}</div>
              <div className="mt-1 text-xs text-text-secondary">{link.type} · {link.risk}</div>
            </div>
          ))}
        </DataCard>
      </div>

      <div className="space-y-5">
        <DataCard title="Representative agents">
          {topAgents.map((agent) => (
            <div key={agent.id} className="rounded-[20px] border border-white/[0.08] bg-white/[0.04] p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-text-primary">{agent.name}</div>
                  <div className="text-xs text-text-secondary">{agent.role}</div>
                </div>
                <div className="rounded-full border border-white/[0.08] px-2.5 py-1 text-[11px] text-text-secondary">
                  {Math.round(agent.k2_decision_confidence * 100)}%
                </div>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-text-secondary">{agent.agent_insight.vulnerability}</p>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">{agent.agent_insight.best_intervention}</p>
            </div>
          ))}
        </DataCard>

        <DataCard title="Confidence notes">
          {mechanisms.confidence_notes.map((note) => (
            <div key={note} className="rounded-[18px] border border-white/[0.08] bg-white/[0.04] p-3 text-sm text-text-secondary">
              {note}
            </div>
          ))}
        </DataCard>
      </div>
    </div>
  );
}

function InterventionsStage() {
  const interventionPlaybook = useCortexStore((s) => s.interventionPlaybook);
  const evidenceTrace = useCortexStore((s) => s.evidenceTrace);

  if (interventionPlaybook.length === 0) {
    return <EmptyStage title="Interventions" body="Model the case to generate an intervention playbook." />;
  }

  return (
    <div className="space-y-5">
      <section className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-5">
          {interventionPlaybook.map((item) => (
            <div key={item.id} className="rounded-[34px] border border-white/[0.1] bg-bg-surface/[0.9] p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-text-muted">Intervention</div>
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
              <div className="mt-4 rounded-[24px] border border-white/[0.08] bg-white/[0.04] p-4">
                <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">Message strategy</div>
                <p className="mt-2 text-sm leading-relaxed text-text-primary">{item.message_strategy}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="space-y-5">
          <DataCard title="Supporting evidence">
            {interventionPlaybook[0].supporting_evidence.map((line) => (
              <div key={line} className="rounded-[18px] border border-white/[0.08] bg-white/[0.04] p-3 text-sm text-text-secondary">
                {line}
              </div>
            ))}
          </DataCard>

          {evidenceTrace && (
            <DataCard title="Case brief">
              <div className="rounded-[20px] border border-white/[0.08] bg-white/[0.04] p-4">
                <div className="text-sm font-semibold text-text-primary">Themes</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {evidenceTrace.themes.map((theme) => (
                    <span key={theme} className="rounded-full border border-white/[0.08] px-3 py-1 text-xs text-text-secondary">
                      {theme}
                    </span>
                  ))}
                </div>
              </div>
              <div className="rounded-[20px] border border-white/[0.08] bg-white/[0.04] p-4 text-sm leading-relaxed text-text-secondary">
                {evidenceTrace.analysis_text}
              </div>
            </DataCard>
          )}
        </div>
      </section>
    </div>
  );
}

function InterventionField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[20px] border border-white/[0.08] bg-white/[0.04] p-4">
      <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">{label}</div>
      <div className="mt-2 text-sm leading-relaxed text-text-primary">{value}</div>
    </div>
  );
}

function DataCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-[34px] border border-white/[0.1] bg-bg-surface/[0.9] p-6">
      <div className="mb-4 flex items-center gap-3">
        <Network className="h-5 w-5 text-pastel-2" />
        <h3 className="text-lg font-semibold">{title}</h3>
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function EmptyStage({ title, body }: { title: string; body: string }) {
  return (
    <section className="rounded-[34px] border border-white/[0.1] bg-bg-surface/[0.9] p-8">
      <h3 className="text-xl font-semibold">{title}</h3>
      <p className="mt-3 max-w-xl text-sm leading-relaxed text-text-secondary">{body}</p>
    </section>
  );
}
