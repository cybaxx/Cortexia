import { create } from 'zustand';
import type { UseCaseId } from '@/data/useCases';
import { getUseCase } from '@/data/useCases';
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

interface CortexState {
  screen: Screen;
  useCase: UseCaseId | null;
  status: 'idle' | 'running';
  selectedMemo: 'A' | 'B' | null;
  injectPhase: InjectPhase;

  /** Latest completed run (either A or B just finished) */
  currentReport: PropagationReport | null;
  rejectionHotspots: RejectionHotspot[];
  memoAResult: MemoRunSnapshot | null;
  memoBResult: MemoRunSnapshot | null;
  memoDiff: MemoDiffSummary | null;

  metrics: SimulationMetrics;

  setScreen: (s: Screen) => void;
  setUseCase: (id: UseCaseId | null) => void;
  setMemo: (m: 'A' | 'B' | null) => void;
  setStatus: (s: 'idle' | 'running') => void;
  setInjectPhase: (p: InjectPhase) => void;
  /** Orchestrated inject with timed phases and report generation */
  startInject: () => void;
  resetSandbox: () => void;
  /** PDF helper reads this title */
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
  setMemo: (selectedMemo) => set({ selectedMemo }),
  setStatus: (status) => set({ status }),
  setInjectPhase: (injectPhase) => set({ injectPhase }),

  reportTitle: () => {
    const { useCase } = get();
    const u = getUseCase(useCase);
    return u ? `Cortexia — ${u.label}` : 'Cortexia — Propagation Report';
  },

  startInject: async () => {
    const { useCase, selectedMemo } = get();
    if (!useCase || !selectedMemo) return;
    const ph = get().injectPhase;
    if (ph !== 'idle' && ph !== 'complete') return;

    set({ injectPhase: 'initializing', status: 'running', rejectionHotspots: [], currentReport: null, memoDiff: null });

    await sleep(1500);
    if (get().screen !== 'simulation') return;
    set({ injectPhase: 'propagating' });

    await sleep(2800);
    if (get().screen !== 'simulation') return;

    const report = buildPropagationReport(useCase, selectedMemo);
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
      metrics: {
        populationReached: 0,
        avgCognitiveLoad: 0,
        beliefAdoptionRate: 0,
        spatialTension: 'Low',
      },
    }),
}));
