import type { SimulateRequest, SimulateResponse, TranscriptionResponse } from '@/types/simulation';

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
