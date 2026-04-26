import { create } from 'zustand';
import type { UseCaseId } from '@/data/useCases';
import type { Agent } from '@/lib/agents';
import { getRecentRuns, getRunById, postSimulate } from '@/lib/api/simulate';
import { exportCasePdf } from '@/lib/exportCasePdf';
import type {
  AgentSimulationPayload,
  CaseSummary,
  EvidenceInput,
  EvidenceTrace,
  InterventionItem,
  MechanismsReport,
  PersistedRunResponse,
  RecentRunSummary,
  SimulateResponse,
  SpreadModel,
} from '@/types/simulation';

export type Screen = 'landing' | 'dashboard';
export type WorkspaceStage = 'evidence' | 'spread' | 'mechanisms' | 'interventions';
export type RunState = 'idle' | 'running' | 'ready' | 'error';

export interface AudioUploadState {
  fileName: string;
  mimeType: string;
  durationSeconds?: number | null;
  transcriptConfidence?: number | null;
  sourceType: string;
}

export interface ExportState {
  lastExportAt?: number | null;
  exportFormat: 'json' | 'markdown' | 'pdf';
}

export type AgentParamPatch = Partial<
  Pick<Agent, 'cognitiveLoad' | 'emotionalAgitation' | 'defensivePosture' | 'state'>
>;

interface CortexState {
  screen: Screen;
  stage: WorkspaceStage;
  useCase: UseCaseId | null;
  cityId: string;
  caseGoal: string;
  messageComplexity: number;
  status: RunState;
  apiError: string | null;

  evidence: EvidenceInput;
  audioUpload: AudioUploadState | null;
  exportState: ExportState;
  recentRuns: RecentRunSummary[];
  recentRunsStatus: 'idle' | 'loading' | 'ready' | 'error';

  latestResponse: SimulateResponse | null;
  caseSummary: CaseSummary | null;
  spreadModel: SpreadModel | null;
  mechanisms: MechanismsReport | null;
  interventionPlaybook: InterventionItem[];
  evidenceTrace: EvidenceTrace | null;
  evidenceGraph: SimulateResponse['evidence_graph'] | null;
  swarmDynamics: SimulateResponse['swarm_dynamics'] | null;

  agentOverrides: Record<number, AgentParamPatch>;
  agentSimulationById: Record<number, AgentSimulationPayload>;
  selectedAgentId: number | null;

  setScreen: (screen: Screen) => void;
  setStage: (stage: WorkspaceStage) => void;
  setUseCase: (useCase: UseCaseId | null) => void;
  setCityId: (cityId: string) => void;
  setCaseGoal: (caseGoal: string) => void;
  setMessageComplexity: (messageComplexity: number) => void;
  setEvidenceField: <K extends keyof EvidenceInput>(key: K, value: EvidenceInput[K]) => void;
  setAudioUpload: (audioUpload: AudioUploadState | null) => void;
  patchAgent: (id: number, partial: AgentParamPatch) => void;
  getAgentPayload: (id: number) => AgentSimulationPayload | undefined;
  setSelectedAgentId: (id: number | null) => void;
  runSimulation: () => Promise<void>;
  exportCase: (format?: 'json' | 'markdown' | 'pdf') => void;
  loadRecentRuns: () => Promise<void>;
  openRun: (runId: number) => Promise<void>;
}

const DEFAULT_GOAL =
  'Understand how this information spreads, identify vulnerable segments, and recommend interventions that reduce harm.';

function emptyEvidence(): EvidenceInput {
  return {
    text_input: '',
    source_url: '',
    transcript: '',
    edited_analysis_text: '',
    speaker_context: '',
    audio_input: null,
  };
}

function buildMarkdownExport(response: SimulateResponse): string {
  const sections = [
    `# ${response.case_summary.title}`,
    `## Goal\n${response.case_summary.goal}`,
    `## Key Finding\n${response.case_summary.key_finding}`,
    `## Spread Model\n- Spread risk: ${response.spread_model.spread_risk}\n- Adoption rate: ${response.spread_model.belief_adoption_rate}%\n- Population reached: ${response.spread_model.population_reached}%`,
    `## Mechanisms\n${response.mechanisms.mechanism_summary}`,
    `## Interventions\n${response.intervention_playbook
      .map(
        (item) =>
          `### ${item.title}\n- Audience: ${item.target_audience}\n- Mechanism: ${item.mechanism_addressed}\n- Channel: ${item.recommended_channel}\n- Messenger: ${item.recommended_messenger}\n- Strategy: ${item.message_strategy}`,
      )
      .join('\n\n')}`,
    `## Evidence Trace\n${response.evidence_trace.analysis_text}`,
  ];
  return sections.join('\n\n');
}

function downloadBlob(filename: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function applySimulationResponse(set: (partial: Partial<CortexState>) => void, response: SimulateResponse) {
  const provider = response.tribe_meta?.provider;
  const modelId = response.tribe_meta?.model_id;
  if (!provider || !modelId) {
    throw new Error('Simulation response did not include live TRIBE metadata. Refusing to render fallback data.');
  }

  const byId: Record<number, AgentSimulationPayload> = {};
  for (const agent of response.agents) byId[agent.id] = agent;

  set({
    latestResponse: response,
    caseSummary: response.case_summary,
    spreadModel: response.spread_model,
    mechanisms: response.mechanisms,
    interventionPlaybook: response.intervention_playbook,
    evidenceTrace: response.evidence_trace,
    evidenceGraph: response.evidence_graph ?? null,
    swarmDynamics: response.swarm_dynamics ?? null,
    agentSimulationById: byId,
    selectedAgentId: null,
    status: 'ready',
    stage: 'spread',
  });
}

function applyPersistedRun(set: (partial: Partial<CortexState>) => void, record: PersistedRunResponse) {
  applySimulationResponse(set, record.response);
  set({
    cityId: record.city_id,
    caseGoal: record.case_goal,
    evidence: {
      ...record.evidence,
      edited_analysis_text:
        record.evidence.edited_analysis_text?.trim() || record.response.evidence_trace.analysis_text,
    },
  });
}

function invalidateSimulationResult(state: CortexState): Partial<CortexState> {
  if (!state.latestResponse && !state.caseSummary && !state.spreadModel && !state.mechanisms) {
    return {};
  }
  return {
    status: 'idle',
    apiError: null,
    latestResponse: null,
    caseSummary: null,
    spreadModel: null,
    mechanisms: null,
    interventionPlaybook: [],
    evidenceTrace: null,
    evidenceGraph: null,
    swarmDynamics: null,
    agentSimulationById: {},
    selectedAgentId: null,
  };
}

export const useCortexStore = create<CortexState>((set, get) => ({
  screen: 'landing',
  stage: 'evidence',
  useCase: 'public_health',
  cityId: 'la',
  caseGoal: DEFAULT_GOAL,
  messageComplexity: 0.5,
  status: 'idle',
  apiError: null,

  evidence: emptyEvidence(),
  audioUpload: null,
  exportState: { exportFormat: 'json', lastExportAt: null },
  recentRuns: [],
  recentRunsStatus: 'idle',

  latestResponse: null,
  caseSummary: null,
  spreadModel: null,
  mechanisms: null,
  interventionPlaybook: [],
  evidenceTrace: null,
  evidenceGraph: null,
  swarmDynamics: null,

  agentOverrides: {},
  agentSimulationById: {},
  selectedAgentId: null,

  setScreen: (screen) => set({ screen }),
  setStage: (stage) => set({ stage }),
  setUseCase: (useCase) =>
    set({
      useCase,
      stage: 'evidence',
      latestResponse: null,
      caseSummary: null,
      spreadModel: null,
      mechanisms: null,
      interventionPlaybook: [],
      evidenceTrace: null,
      evidenceGraph: null,
      swarmDynamics: null,
      agentSimulationById: {},
      apiError: null,
    }),
  setCityId: (cityId) =>
    set((state) => ({
      cityId,
      ...invalidateSimulationResult(state),
    })),
  setCaseGoal: (caseGoal) =>
    set((state) => ({
      caseGoal,
      ...invalidateSimulationResult(state),
    })),
  setMessageComplexity: (messageComplexity) =>
    set((state) => ({
      messageComplexity,
      ...invalidateSimulationResult(state),
    })),
  setEvidenceField: (key, value) =>
    set((state) => ({
      evidence: {
        ...state.evidence,
        [key]: value,
      },
      ...invalidateSimulationResult(state),
    })),
  setAudioUpload: (audioUpload) => set({ audioUpload }),

  patchAgent: (id, partial) =>
    set((state) => ({
      agentOverrides: { ...state.agentOverrides, [id]: { ...state.agentOverrides[id], ...partial } },
    })),

  getAgentPayload: (id) => get().agentSimulationById[id],
  setSelectedAgentId: (selectedAgentId) => set({ selectedAgentId }),

  runSimulation: async () => {
    const { useCase, cityId, caseGoal, evidence, messageComplexity } = get();
    if (!useCase) return;

    const canonicalText =
      evidence.edited_analysis_text?.trim() ||
      evidence.transcript?.trim() ||
      evidence.text_input.trim();
    if (canonicalText.length < 12) {
      set({ apiError: 'Add at least 12 characters of evidence or transcript before modeling the case.' });
      return;
    }

    set({
      status: 'running',
      stage: 'spread',
      apiError: null,
      latestResponse: null,
      caseSummary: null,
      spreadModel: null,
      mechanisms: null,
      interventionPlaybook: [],
      evidenceTrace: null,
      evidenceGraph: null,
      swarmDynamics: null,
      agentSimulationById: {},
    });

    try {
      const res = await postSimulate({
        domain: useCase,
        city_id: cityId,
        case_goal: caseGoal.trim() || DEFAULT_GOAL,
        evidence,
        message_complexity: messageComplexity,
      });
      applySimulationResponse(set, res);
      void get().loadRecentRuns();
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Case analysis failed';
      set({ status: 'error', apiError: msg });
    }
  },

  exportCase: (format = 'json') => {
    const response = get().latestResponse;
    if (!response) return;

    if (format === 'json') {
      downloadBlob('cortexia-case.json', JSON.stringify(response, null, 2), 'application/json');
    } else if (format === 'pdf') {
      exportCasePdf(response);
    } else {
      downloadBlob('cortexia-case.md', buildMarkdownExport(response), 'text/markdown');
    }
    set({ exportState: { exportFormat: format, lastExportAt: Date.now() } });
  },

  loadRecentRuns: async () => {
    set({ recentRunsStatus: 'loading' });
    try {
      const runs = await getRecentRuns();
      set({ recentRuns: runs, recentRunsStatus: 'ready' });
    } catch {
      set({ recentRunsStatus: 'error' });
    }
  },

  openRun: async (runId: number) => {
    set({ status: 'running', apiError: null });
    try {
      const record = await getRunById(runId);
      applyPersistedRun(set, record);
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Loading persisted run failed';
      set({ status: 'error', apiError: msg });
    }
  },
}));
