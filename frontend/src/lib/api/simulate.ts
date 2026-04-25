import type { SimulateRequest, SimulateResponse } from '@/types/simulation';

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
