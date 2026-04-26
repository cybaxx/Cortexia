import type {
  AgentConversationMessage,
  PersistedRunResponse,
  RecentRunSummary,
  SimulateRequest,
  SimulateResponse,
  TranscriptionResponse,
} from '@/types/simulation';

const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';

export async function postSimulate(body: SimulateRequest): Promise<SimulateResponse> {
  const url = `${base.replace(/\/$/, '')}/api/simulate`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `Simulation failed (${res.status})`);
  }
  return res.json() as Promise<SimulateResponse>;
}

export async function postTranscribeAudio(file: File, languageCode?: string): Promise<TranscriptionResponse> {
  const url = `${base.replace(/\/$/, '')}/api/transcribe`;
  const formData = new FormData();
  formData.append('file', file);
  if (languageCode) formData.append('language_code', languageCode);

  const res = await fetch(url, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `Transcription failed (${res.status})`);
  }
  return res.json() as Promise<TranscriptionResponse>;
}

export async function getRecentRuns(limit = 8): Promise<RecentRunSummary[]> {
  const url = `${base.replace(/\/$/, '')}/api/runs/recent?limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `Fetching recent runs failed (${res.status})`);
  }
  const payload = (await res.json()) as { runs: RecentRunSummary[] };
  return payload.runs;
}

export async function getRunById(runId: number): Promise<PersistedRunResponse> {
  const url = `${base.replace(/\/$/, '')}/api/runs/${runId}`;
  const res = await fetch(url);
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `Fetching run ${runId} failed (${res.status})`);
  }
  return res.json() as Promise<PersistedRunResponse>;
}

export async function getAgentConversationHistory(
  runId: number,
  agentId: number,
): Promise<AgentConversationMessage[]> {
  const url = `${base.replace(/\/$/, '')}/api/runs/${runId}/agents/${agentId}/conversation`;
  const res = await fetch(url);
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `Fetching agent conversation failed (${res.status})`);
  }
  const payload = (await res.json()) as { messages: AgentConversationMessage[] };
  return payload.messages;
}

export async function postAgentConversation(
  runId: number,
  agentId: number,
  message: string,
): Promise<AgentConversationMessage> {
  const url = `${base.replace(/\/$/, '')}/api/runs/${runId}/agents/${agentId}/conversation`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `Sending agent conversation failed (${res.status})`);
  }
  return res.json() as Promise<AgentConversationMessage>;
}
