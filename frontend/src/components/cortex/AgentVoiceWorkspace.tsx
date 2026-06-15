import { AudioLines, Loader2, Mic, MicOff, Send, X } from 'lucide-react';
import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { getAgentConversationHistory, postAgentConversation, postTranscribeAudio } from '@/lib/api/simulate';
import type { AgentConversationMessage, AgentSimulationPayload } from '@/types/simulation';

const BrainViz = lazy(() =>
  import('./BrainViz').then((module) => ({ default: module.BrainViz })),
);

const INTERVIEW_PROMPTS = [
  'Why did this person react this way?',
  'What would change your mind about this claim?',
  'What are you likely to tell a friend next?',
];

function K2ThinkTrace({ lines }: { lines: string[] }) {
  const safeLines = Array.isArray(lines) ? lines : [];
  return (
    <div className="rounded-[24px] border border-white/[0.08] bg-bg-deep/55 p-3">
      <div className="mb-2 font-mono text-[9px] uppercase tracking-[0.12em] text-pastel-2/90">Interpretation of neural response model</div>
      <ol className="list-decimal list-inside space-y-1.5 font-mono text-[10px] text-text-secondary leading-relaxed">
        {safeLines.length === 0 ? (
          <li className="text-text-muted">No reasoning lines returned for this agent.</li>
        ) : (
          safeLines.map((line, i) => (
            <li key={i} className="pl-0.5">
              {line}
            </li>
          ))
        )}
      </ol>
    </div>
  );
}

export function AgentVoiceWorkspace({
  payload,
  runId,
  onClear,
}: {
  payload?: AgentSimulationPayload;
  runId?: number;
  onClear: () => void;
}) {
  const [messages, setMessages] = useState<AgentConversationMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sending, setSending] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function loadHistory() {
      if (!runId || !payload) return;
      setLoadingHistory(true);
      try {
        const history = await getAgentConversationHistory(runId, payload.id);
        if (!cancelled) setMessages(history);
      } catch {
        if (!cancelled) setMessages([]);
      } finally {
        if (!cancelled) setLoadingHistory(false);
      }
    }
    void loadHistory();
    return () => {
      cancelled = true;
    };
  }, [payload, runId]);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  async function sendPrompt(message: string) {
    if (!runId || !payload || !message.trim() || sending) return;
    setSending(true);
    setVoiceError(null);
    try {
      const reply = await postAgentConversation(runId, payload.id, message.trim());
      setMessages((current) => [...current, reply]);
      setDraft('');
      if (reply.audio_url) {
        const audio = new Audio(reply.audio_url);
        void audio.play().catch(() => undefined);
      }
    } catch (error) {
      setVoiceError(error instanceof Error ? error.message : 'Voice agent request failed.');
    } finally {
      setSending(false);
    }
  }

  async function startRecording() {
    if (!payload || !runId || recording || transcribing) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setVoiceError('This browser does not support microphone capture for the voice agent.');
      return;
    }
    setVoiceError(null);
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    chunksRef.current = [];
    const recorder = new MediaRecorder(stream);
    recorderRef.current = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
      void transcribeAndSend(blob);
      stream.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      recorderRef.current = null;
      chunksRef.current = [];
    };
    recorder.start();
    setRecording(true);
  }

  function stopRecording() {
    if (!recorderRef.current || !recording) return;
    recorderRef.current.stop();
    setRecording(false);
  }

  async function transcribeAndSend(blob: Blob) {
    if (!blob.size) return;
    setTranscribing(true);
    setVoiceError(null);
    try {
      const extension = blob.type.includes('mp4') ? 'm4a' : 'webm';
      const file = new File([blob], `voice-agent-input.${extension}`, {
        type: blob.type || 'audio/webm',
      });
      const transcription = await postTranscribeAudio(file);
      const text = transcription.text.trim();
      if (!text) {
        setVoiceError('The recording did not produce a usable transcript.');
        return;
      }
      setDraft(text);
      await sendPrompt(text);
    } catch (error) {
      setVoiceError(error instanceof Error ? error.message : 'Transcription failed.');
    } finally {
      setTranscribing(false);
    }
  }

  if (!payload || !runId) {
    return (
      <div className="rounded-[28px] border border-white/[0.08] bg-bg-deep/45 p-5 text-sm leading-relaxed text-text-secondary">
        Select a person on the map to open their live voice-agent workspace. Their TRIBE state, demographics, timeline,
        and conversation history will load here.
      </div>
    );
  }

  return (
    <div className="rounded-[32px] border border-white/[0.12] bg-[linear-gradient(180deg,rgba(18,26,36,0.97)_0%,rgba(14,20,30,0.98)_100%)] p-4 shadow-[0_32px_120px_rgba(6,10,20,0.35)]">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <div className="text-[15px] font-semibold text-text-primary">{payload.name}</div>
          <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.12em] text-text-muted">{payload.role}</div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="rounded-full border border-white/[0.1] bg-white/[0.05] px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.12em] text-pastel-2/95">
            {payload.belief_state} · {(payload.k2_decision_confidence * 100).toFixed(0)}%
          </span>
          <button
            type="button"
            onClick={onClear}
            className="rounded-full p-1 text-text-muted hover:bg-white/[0.08] hover:text-text-primary"
            aria-label="Close selected agent"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="mb-3 rounded-[28px] border border-white/[0.08] bg-bg-elevated/35 p-3">
        <Suspense
          fallback={
            <div className="rounded-[24px] border border-white/[0.08] bg-bg-deep/40 p-6 text-sm text-text-muted">
              Loading neural view…
            </div>
          }
        >
          <BrainViz
            tribeMetrics={payload.tribe_neurological_metrics}
            regions={payload.brain_regions}
            dominantSignal={payload.dominant_signal}
            summary={payload.brain_summary}
          />
        </Suspense>
      </div>

      <K2ThinkTrace lines={payload.k2_reasoning_trace} />

      <div className="mt-3 grid gap-3">
        <div className="rounded-[22px] border border-white/[0.08] bg-white/[0.04] p-3">
          <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-text-muted">Voice-agent prompts</div>
          <div className="mt-3 grid gap-2">
            {INTERVIEW_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => setDraft(prompt)}
                className="rounded-[16px] border border-white/[0.08] bg-bg-deep/45 px-3 py-2 text-left text-sm text-text-secondary"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-[22px] border border-white/[0.08] bg-white/[0.04] p-3">
          <div className="mb-3 flex items-center gap-2">
            <AudioLines className="h-4 w-4 text-pastel-2" />
            <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-text-muted">Voice agent</div>
          </div>
          <div className="max-h-44 space-y-2 overflow-y-auto rounded-[18px] border border-white/[0.06] bg-bg-deep/45 p-3">
            {loadingHistory && <div className="text-xs text-text-secondary">Loading prior turns…</div>}
            {!loadingHistory && messages.length === 0 && (
              <div className="text-xs leading-relaxed text-text-secondary">
                Speak or type to this person. The reply is generated in-character and returned as voice plus transcript.
              </div>
            )}
            {messages.map((message) => (
              <div key={message.id} className="space-y-1">
                <div className="text-[11px] text-pastel-1">You: {message.user_message}</div>
                <div className="text-[11px] leading-relaxed text-text-secondary">{message.agent_reply}</div>
                {message.audio_url && (
                  <audio controls className="w-full">
                    <source src={message.audio_url} type="audio/mpeg" />
                  </audio>
                )}
              </div>
            ))}
          </div>
          {voiceError && (
            <div className="mt-3 rounded-[16px] border border-red-400/20 bg-red-500/10 px-3 py-2 text-xs text-red-100">
              {voiceError}
            </div>
          )}
          <div className="mt-3 flex items-end gap-2">
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask this person what they think, then send or record your question."
              className="min-h-[84px] flex-1 rounded-[18px] border border-white/[0.08] bg-bg-deep/55 px-3 py-2 text-sm text-text-primary"
            />
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={() => void (recording ? stopRecording() : startRecording())}
                disabled={!runId || !payload || sending || transcribing}
                className={`inline-flex h-11 items-center justify-center rounded-[16px] border px-3 text-sm text-text-primary disabled:opacity-40 ${
                  recording
                    ? 'border-red-400/30 bg-red-500/10'
                    : 'border-white/[0.08] bg-white/[0.03]'
                }`}
              >
                {transcribing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : recording ? (
                  <MicOff className="h-4 w-4" />
                ) : (
                  <Mic className="h-4 w-4" />
                )}
              </button>
              <button
                type="button"
                onClick={() => void sendPrompt(draft)}
                disabled={!runId || !payload || sending || !draft.trim()}
                className="inline-flex h-11 items-center justify-center rounded-[16px] border border-pastel-2/25 bg-[hsl(var(--pastel-2)/0.10)] px-3 text-sm text-text-primary disabled:opacity-40"
              >
                {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
