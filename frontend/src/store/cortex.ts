import { create } from 'zustand';
import type { UseCaseId } from '@/data/useCases';
import { getUseCase } from '@/data/useCases';
import type { Agent } from '@/lib/agents';
import { postSimulate } from '@/lib/api/simulate';
import { exportCasePdf } from '@/lib/exportCasePdf';
import type {
  AgentSimulationPayload,
  CaseSummary,
  EvidenceInput,
  EvidenceTrace,
  InterventionItem,
  MechanismsReport,
  SimulateResponse,
  SpreadModel,
} from '@/types/simulation';

export type Screen = 'useCases' | 'workspace';
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

  latestResponse: SimulateResponse | null;
  caseSummary: CaseSummary | null;
  spreadModel: SpreadModel | null;
  mechanisms: MechanismsReport | null;
  interventionPlaybook: InterventionItem[];
  evidenceTrace: EvidenceTrace | null;

  agentOverrides: Record<number, AgentParamPatch>;
  agentSimulationById: Record<number, AgentSimulationPayload>;

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
  runSimulation: () => Promise<void>;
  exportCase: (format?: 'json' | 'markdown' | 'pdf') => void;
  resetWorkspace: () => void;
  workspaceTitle: () => string;
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

export const useCortexStore = create<CortexState>((set, get) => ({
  screen: 'useCases',
  stage: 'evidence',
  useCase: null,
  cityId: 'la',
  caseGoal: DEFAULT_GOAL,
  messageComplexity: 0.5,
  status: 'idle',
  apiError: null,

  evidence: emptyEvidence(),
  audioUpload: null,
  exportState: { exportFormat: 'json', lastExportAt: null },

  latestResponse: null,
  caseSummary: null,
  spreadModel: null,
  mechanisms: null,
  interventionPlaybook: [],
  evidenceTrace: null,

  agentOverrides: {},
  agentSimulationById: {},

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
      agentSimulationById: {},
      apiError: null,
    }),
  setCityId: (cityId) => set({ cityId }),
  setCaseGoal: (caseGoal) => set({ caseGoal }),
  setMessageComplexity: (messageComplexity) => set({ messageComplexity }),
  setEvidenceField: (key, value) =>
    set((state) => ({
      evidence: {
        ...state.evidence,
        [key]: value,
      },
    })),
  setAudioUpload: (audioUpload) => set({ audioUpload }),

  patchAgent: (id, partial) =>
    set((state) => ({
      agentOverrides: { ...state.agentOverrides, [id]: { ...state.agentOverrides[id], ...partial } },
    })),

  getAgentPayload: (id) => get().agentSimulationById[id],

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
      apiError: null,
      latestResponse: null,
      caseSummary: null,
      spreadModel: null,
      mechanisms: null,
      interventionPlaybook: [],
      evidenceTrace: null,
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

      const byId: Record<number, AgentSimulationPayload> = {};
      for (const agent of res.agents) byId[agent.id] = agent;

      set({
        latestResponse: res,
        caseSummary: res.case_summary,
        spreadModel: res.spread_model,
        mechanisms: res.mechanisms,
        interventionPlaybook: res.intervention_playbook,
        evidenceTrace: res.evidence_trace,
        agentSimulationById: byId,
        status: 'ready',
        stage: 'spread',
      });
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

  resetWorkspace: () =>
    set({
      screen: 'useCases',
      stage: 'evidence',
      useCase: null,
      cityId: 'la',
      caseGoal: DEFAULT_GOAL,
      messageComplexity: 0.5,
      status: 'idle',
      apiError: null,
      evidence: emptyEvidence(),
      audioUpload: null,
      exportState: { exportFormat: 'json', lastExportAt: null },
      latestResponse: null,
      caseSummary: null,
      spreadModel: null,
      mechanisms: null,
      interventionPlaybook: [],
      evidenceTrace: null,
      agentOverrides: {},
      agentSimulationById: {},
    }),

  workspaceTitle: () => {
    const useCase = getUseCase(get().useCase);
    return useCase ? `Cortexia — ${useCase.label} Case Workspace` : 'Cortexia — Case Workspace';
  },
}));
