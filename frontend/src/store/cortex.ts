import { create } from 'zustand';
import type { UseCaseId } from '@/data/useCases';
import { getUseCase } from '@/data/useCases';
import { getCityById } from '@/data/cities';
import type { Agent } from '@/lib/agents';
import {
  buildPropagationReport,
  buildMemoDiff,
  type PropagationReport,
  type RejectionHotspot,
  type MemoDiffSummary,
} from '@/lib/propagationReport';

export type Screen = 'useCases' | 'simulation';
export type InjectPhase = 'idle' | 'initializing' | 'propagating' | 'report' | 'complete';

export interface SimulationMetrics {
  populationReached: number;
  avgCognitiveLoad: number;
  beliefAdoptionRate: number;
  spatialTension: 'Low' | 'Moderate' | 'High';
}

export interface MemoRunSnapshot {
  memo: 'A' | 'B';
  metrics: SimulationMetrics;
  report: PropagationReport;
  completedAt: number;
}

export type AgentParamPatch = Partial<
  Pick<Agent, 'cognitiveLoad' | 'emotionalAgitation' | 'defensivePosture' | 'state'>
>;

interface CortexState {
  screen: Screen;
  useCase: UseCaseId | null;
  cityId: string;
  /** User-authored catalysts (not preloaded) */
  catalystA: string;
  catalystB: string;
  sourceUrl: string;
  status: 'idle' | 'running';
  selectedMemo: 'A' | 'B' | null;
  injectPhase: InjectPhase;
  currentReport: PropagationReport | null;
  rejectionHotspots: RejectionHotspot[];
  memoAResult: MemoRunSnapshot | null;
  memoBResult: MemoRunSnapshot | null;
  memoDiff: MemoDiffSummary | null;
  metrics: SimulationMetrics;
  agentOverrides: Record<number, AgentParamPatch>;

  setScreen: (s: Screen) => void;
  setUseCase: (id: UseCaseId | null) => void;
  setCityId: (id: string) => void;
  setCatalystA: (t: string) => void;
  setCatalystB: (t: string) => void;
  setSourceUrl: (t: string) => void;
  setMemo: (m: 'A' | 'B' | null) => void;
  setStatus: (s: 'idle' | 'running') => void;
  setInjectPhase: (p: InjectPhase) => void;
  patchAgent: (id: number, partial: AgentParamPatch) => void;
  startInject: () => void;
  resetSandbox: () => void;
  reportTitle: () => string;
}

function metricsFromReport(r: PropagationReport, useCase: UseCaseId | null): SimulationMetrics {
  const def = getUseCase(useCase);
  const baseLoad = 0.42 + (r.adoptionRate / 200) * (def?.id === 'corporate' ? 1.1 : 1);
  const load = Math.min(0.95, baseLoad + (r.benchmarkComparison === 'below' ? 0.12 : 0.04));
  const sumShare = r.rejectionHotspots.reduce((a, h) => a + h.share, 0);
  const tension: 'Low' | 'Moderate' | 'High' =
    sumShare > 0.5 ? 'High' : sumShare > 0.25 ? 'Moderate' : 'Low';
  return {
    populationReached: r.reachPct,
    avgCognitiveLoad: Math.round(load * 100) / 100,
    beliefAdoptionRate: r.adoptionRate,
    spatialTension: tension,
  };
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export const useCortexStore = create<CortexState>((set, get) => ({
  screen: 'useCases',
  useCase: null,
  cityId: 'la',
  catalystA: '',
  catalystB: '',
  sourceUrl: '',
  status: 'idle',
  selectedMemo: 'A',
  injectPhase: 'idle',
  currentReport: null,
  rejectionHotspots: [],
  memoAResult: null,
  memoBResult: null,
  memoDiff: null,
  metrics: {
    populationReached: 0,
    avgCognitiveLoad: 0,
    beliefAdoptionRate: 0,
    spatialTension: 'Low',
  },
  agentOverrides: {},

  setScreen: (screen) => set({ screen }),
  setUseCase: (useCase) =>
    set({
      useCase,
      memoAResult: null,
      memoBResult: null,
      memoDiff: null,
      currentReport: null,
      rejectionHotspots: [],
    }),
  setCityId: (cityId) => set({ cityId }),
  setCatalystA: (catalystA) => set({ catalystA }),
  setCatalystB: (catalystB) => set({ catalystB }),
  setSourceUrl: (sourceUrl) => set({ sourceUrl }),
  setMemo: (selectedMemo) => set({ selectedMemo }),
  setStatus: (status) => set({ status }),
  setInjectPhase: (injectPhase) => set({ injectPhase }),

  patchAgent: (id, partial) =>
    set((s) => ({
      agentOverrides: { ...s.agentOverrides, [id]: { ...s.agentOverrides[id], ...partial } },
    })),

  reportTitle: () => {
    const { useCase } = get();
    const u = getUseCase(useCase);
    return u ? `Cortexia — ${u.label}` : 'Cortexia — Propagation Report';
  },

  startInject: async () => {
    const { useCase, selectedMemo, catalystA, catalystB, cityId } = get();
    if (!useCase || !selectedMemo) return;
    const ph = get().injectPhase;
    if (ph !== 'idle' && ph !== 'complete') return;
    const text = selectedMemo === 'A' ? catalystA : catalystB;
    if (text.trim().length < 12) return;

    set({ injectPhase: 'initializing', status: 'running', rejectionHotspots: [], currentReport: null, memoDiff: null });

    await sleep(1500);
    if (get().screen !== 'simulation') return;
    set({ injectPhase: 'propagating' });

    await sleep(2800);
    if (get().screen !== 'simulation') return;

    const city = getCityById(cityId);
    const report = buildPropagationReport(useCase, selectedMemo, text, city.center);
    const hotspots = report.rejectionHotspots;
    const metrics = metricsFromReport(report, useCase);
    const snap: MemoRunSnapshot = {
      memo: selectedMemo,
      metrics,
      report,
      completedAt: Date.now(),
    };

    set({ injectPhase: 'report', currentReport: report, rejectionHotspots: hotspots, metrics });

    if (selectedMemo === 'A') {
      set({ memoAResult: snap });
    } else {
      set({ memoBResult: snap });
    }

    const a = get().memoAResult;
    const b = get().memoBResult;
    if (a && b) {
      set({ memoDiff: buildMemoDiff(useCase, a.report.adoptionRate, b.report.adoptionRate) });
    }

    await sleep(500);
    set({ injectPhase: 'complete', status: 'idle' });
  },

  resetSandbox: () =>
    set({
      injectPhase: 'idle',
      status: 'idle',
      currentReport: null,
      rejectionHotspots: [],
      memoAResult: null,
      memoBResult: null,
      memoDiff: null,
      agentOverrides: {},
      catalystA: '',
      catalystB: '',
      sourceUrl: '',
      metrics: {
        populationReached: 0,
        avgCognitiveLoad: 0,
        beliefAdoptionRate: 0,
        spatialTension: 'Low',
      },
    }),
}));
