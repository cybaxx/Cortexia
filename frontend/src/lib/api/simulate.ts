import type {
  ActionCenterProviderStatus,
  ActionCenterResearchRequest,
  ActionCenterResponse,
  AgentConversationMessage,
  PersistedAgentProfile,
  PersistedRunResponse,
  RecentRunSummary,
  SimulateRequest,
  SimulateResponse,
  TranscriptionResponse,
} from '@/types/simulation';

const configuredBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const base = import.meta.env.DEV ? '' : configuredBase;

function normalizeApiAssetUrl(url?: string | null): string | null | undefined {
  if (!url) return url;
  if (/^https?:\/\//i.test(url)) return url;
  if (configuredBase) return `${configuredBase.replace(/\/$/, '')}${url.startsWith('/') ? url : `/${url}`}`;
  return url;
}

function normalizeConversationMessage(message: AgentConversationMessage): AgentConversationMessage {
  return {
    ...message,
    audio_url: normalizeApiAssetUrl(message.audio_url),
  };
}

export async function postSimulate(body: SimulateRequest): Promise<SimulateResponse> {
  const url = `${base.replace(/\/$/, '')}/api/simulate`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 900_000);
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(t || `Simulation failed (${res.status})`);
    }
    return res.json() as Promise<SimulateResponse>;
  } finally {
    clearTimeout(timeoutId);
  }
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

export function getRunReportUrl(runId: number): string {
  return `${base.replace(/\/$/, '')}/api/runs/${runId}/report`;
}

export async function searchRunsSemantic(query: string, limit = 5): Promise<SemanticSearchResult[]> {
  const url = `${base.replace(/\/$/, '')}/api/runs/search?q=${encodeURIComponent(query)}&limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `Semantic search failed (${res.status})`);
  }
  const payload = (await res.json()) as { results: SemanticSearchResult[] };
  return payload.results;
}

export interface SemanticSearchResult {
  run_id: number;
  domain: string;
  city_id: string;
  risk_level: string;
  similarity: number;
  snippet: string;
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
  return payload.messages.map(normalizeConversationMessage);
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
  const payload = (await res.json()) as AgentConversationMessage;
  return normalizeConversationMessage(payload);
}

export async function getRunAgentProfile(runId: number, agentId: number): Promise<PersistedAgentProfile> {
  const url = `${base.replace(/\/$/, '')}/api/runs/${runId}/agents/${agentId}/profile`;
  const res = await fetch(url);
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `Fetching agent profile failed (${res.status})`);
  }
  return res.json() as Promise<PersistedAgentProfile>;
}

export async function putRunAgentNotes(runId: number, agentId: number, spreadNotes: string): Promise<string> {
  const url = `${base.replace(/\/$/, '')}/api/runs/${runId}/agents/${agentId}/notes`;
  const res = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ spread_notes: spreadNotes }),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `Saving agent notes failed (${res.status})`);
  }
  const payload = (await res.json()) as { spread_notes: string };
  return payload.spread_notes;
}

export async function getActionCenterStatus(): Promise<Record<string, ActionCenterProviderStatus>> {
  const url = `${base.replace(/\/$/, '')}/api/action-center/status`;
  const res = await fetch(url);
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `Fetching Action Center status failed (${res.status})`);
  }
  const payload = (await res.json()) as { providers: Record<string, ActionCenterProviderStatus> };
  return payload.providers;
}

export async function postActionCenterResearch(body: ActionCenterResearchRequest): Promise<ActionCenterResponse> {
  const url = `${base.replace(/\/$/, '')}/api/action-center/research`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `Running Action Center research failed (${res.status})`);
  }
  return res.json() as Promise<ActionCenterResponse>;
}
