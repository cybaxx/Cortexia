import { create } from 'zustand';
import type { UseCaseId } from '@/data/useCases';
import { getUseCase } from '@/data/useCases';
import type { Agent } from '@/lib/agents';
import { postSimulate } from '@/lib/api/simulate';
import type { AgentSimulationPayload, MacroResult, ReportHotspot } from '@/types/simulation';

export type Screen = 'useCases' | 'simulation';
export type InjectPhase = 'idle' | 'initializing' | 'propagating' | 'report' | 'complete';

export interface SimulationMetrics {
  populationReached: number;
  avgCognitiveLoad: number;
  beliefAdoptionRate: number;
  spatialTension: 'Low' | 'Moderate' | 'High';
}

export type AgentParamPatch = Partial<
  Pick<Agent, 'cognitiveLoad' | 'emotionalAgitation' | 'defensivePosture' | 'state'>
>;

interface CortexState {
  screen: Screen;
  useCase: UseCaseId | null;
  cityId: string;
  catalystText: string;
  sourceUrl: string;
  /** 0..1 scales how much the model perturbs TRIBE BSV per agent */
  messageComplexity: number;
  status: 'idle' | 'running';
  injectPhase: InjectPhase;
  rejectionHotspots: ReportHotspot[];
  apiError: string | null;
  metrics: SimulationMetrics;
  agentOverrides: Record<number, AgentParamPatch>;
  /** Latest server payload per agent id (TRIBE + K2). */
  agentSimulationById: Record<number, AgentSimulationPayload>;
  macroResult: MacroResult | null;

  setScreen: (s: Screen) => void;
  setUseCase: (id: UseCaseId | null) => void;
  setCityId: (id: string) => void;
  setCatalystText: (t: string) => void;
  setSourceUrl: (t: string) => void;
  setMessageComplexity: (n: number) => void;
  setStatus: (s: 'idle' | 'running') => void;
  setInjectPhase: (p: InjectPhase) => void;
  patchAgent: (id: number, partial: AgentParamPatch) => void;
  runSimulation: () => Promise<void>;
  resetSandbox: () => void;
  reportTitle: () => string;
  getAgentPayload: (id: number) => AgentSimulationPayload | undefined;
}

function metricsFromPayload(
  agents: AgentSimulationPayload[],
  summary: { total: number; adopted: number },
  hotspots: ReportHotspot[],
): SimulationMetrics {
  const avgLoad =
    agents.reduce((total, agent) => total + agent.tribe_neurological_metrics.cognitive_load, 0) /
    Math.max(1, agents.length);
  const hotspotShare = hotspots.reduce((total, hotspot) => total + hotspot.share, 0);
  return {
    populationReached: Math.round((agents.filter((agent) => agent.belief_state !== 'neutral').length / Math.max(1, summary.total)) * 100),
    avgCognitiveLoad: Math.round(avgLoad * 100) / 100,
    beliefAdoptionRate: Math.round((summary.adopted / Math.max(1, summary.total)) * 100),
    spatialTension: hotspotShare > 0.48 ? 'High' : hotspotShare > 0.22 ? 'Moderate' : 'Low',
  };
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export const useCortexStore = create<CortexState>((set, get) => ({
  screen: 'useCases',
  useCase: null,
  cityId: 'la',
  catalystText: '',
  sourceUrl: '',
  messageComplexity: 0.5,
  status: 'idle',
  injectPhase: 'idle',
  rejectionHotspots: [],
  apiError: null,
  metrics: {
    populationReached: 0,
    avgCognitiveLoad: 0,
    beliefAdoptionRate: 0,
    spatialTension: 'Low',
  },
  agentOverrides: {},
  agentSimulationById: {},
  macroResult: null,

  setScreen: (screen) => set({ screen }),
  setUseCase: (useCase) =>
    set({
      useCase,
      rejectionHotspots: [],
      apiError: null,
      agentSimulationById: {},
      macroResult: null,
    }),
  setCityId: (cityId) => set({ cityId }),
  setCatalystText: (catalystText) => set({ catalystText }),
  setSourceUrl: (sourceUrl) => set({ sourceUrl }),
  setMessageComplexity: (messageComplexity) => set({ messageComplexity }),
  setStatus: (status) => set({ status }),
  setInjectPhase: (injectPhase) => set({ injectPhase }),

  patchAgent: (id, partial) =>
    set((s) => ({
      agentOverrides: { ...s.agentOverrides, [id]: { ...s.agentOverrides[id], ...partial } },
    })),

  getAgentPayload: (id) => get().agentSimulationById[id],

  reportTitle: () => {
    const { useCase } = get();
    const u = getUseCase(useCase);
    return u ? `Cortexia — ${u.label}` : 'Cortexia — Propagation Report';
  },

  runSimulation: async () => {
    const { useCase, catalystText, cityId, sourceUrl, messageComplexity, injectPhase } = get();
    if (!useCase) return;
    if (injectPhase !== 'idle' && injectPhase !== 'complete') return;
    const text = catalystText.trim();
    if (text.length < 12) return;

    set({
      injectPhase: 'initializing',
      status: 'running',
      rejectionHotspots: [],
      apiError: null,
      macroResult: null,
    });

    try {
      const res = await postSimulate({
        catalyst_text: text,
        source_url: sourceUrl.trim() || null,
        city_id: cityId,
        use_case: useCase,
        message_complexity: messageComplexity,
      });

      if (get().screen !== 'simulation') return;

      const byId: Record<number, AgentSimulationPayload> = {};
      for (const a of res.agents) {
        byId[a.id] = a;
      }
      set({
        injectPhase: 'propagating',
        agentSimulationById: byId,
        macroResult: res.macro_result,
        rejectionHotspots: res.macro_result.hotspots,
      });

      await sleep(1500); // Live reaction wave
      if (get().screen !== 'simulation') return;

      const metrics = metricsFromPayload(res.agents, res.summary, res.macro_result.hotspots);
      set({
        injectPhase: 'report',
        metrics,
      });

      await sleep(400);
      set({ injectPhase: 'complete', status: 'idle' });
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Simulation request failed';
      set({
        injectPhase: 'complete',
        status: 'idle',
        agentSimulationById: {},
        apiError: msg,
        rejectionHotspots: [],
        macroResult: null,
      });
    }
  },

  resetSandbox: () =>
    set({
      injectPhase: 'idle',
      status: 'idle',
      rejectionHotspots: [],
      apiError: null,
      agentOverrides: {},
      agentSimulationById: {},
      macroResult: null,
      catalystText: '',
      sourceUrl: '',
      messageComplexity: 0.5,
      metrics: {
        populationReached: 0,
        avgCognitiveLoad: 0,
        beliefAdoptionRate: 0,
        spatialTension: 'Low',
      },
    }),
}));
