/** API contract for `POST /api/simulate` (Modal TRIBE + K2 Think). */

export interface TribeNeurologicalMetrics {
  cognitive_load: number;
  emotional_friction: number;
  defensive_activation: number;
  working_memory_strain: number;
}

export interface BrainRegions {
  prefrontal_cortex: number;
  amygdala: number;
  insula: number;
  hippocampus: number;
  anterior_cingulate: number;
  temporoparietal_junction: number;
}

export type DominantSignal =
  | 'cognitive_overload'
  | 'defensive_reactance'
  | 'empathic_resonance'
  | 'memory_alignment'
  | 'social_proof';

export interface AgentSimulationPayload {
  id: number;
  name: string;
  role: string;
  longitude: number;
  latitude: number;
  belief_state: 'adopted' | 'rejected' | 'neutral';
  k2_reasoning_trace: string[];
  k2_decision_confidence: number;
  dominant_signal: DominantSignal;
  brain_regions: BrainRegions;
  brain_summary: string;
  tribe_neurological_metrics: TribeNeurologicalMetrics;
}

export interface SimulateSummary {
  total: number;
  adopted: number;
  rejected: number;
  neutral: number;
}

export interface MacroResultInsight {
  where: string;
  why: string;
  who: string;
}

export interface MacroResultThought {
  agent_id: number;
  text: string;
  sentiment: 'positive' | 'negative' | 'neutral';
  driver: string;
}

export interface ReportHotspot {
  id: string;
  label: string;
  area: string;
  share: number;
  lng: number;
  lat: number;
  radiusMeters: number;
}

export interface SentimentMix {
  adopted: number;
  rejected: number;
  neutral: number;
}

export interface MacroResult {
  score: number;
  risk_level: 'High Risk' | 'Moderate' | 'Strong';
  insights: MacroResultInsight[];
  suggested_rewrite: string;
  synthetic_thoughts: MacroResultThought[];
  hotspots: ReportHotspot[];
  summary_text: string;
  sentiment_mix: SentimentMix;
  input_summary: string;
  source_context_summary?: string | null;
  source_warning?: string | null;
}

export interface SimulateResponse {
  city_id: string;
  use_case: string;
  source_url: string | null;
  effective_catalyst_text: string;
  agents: AgentSimulationPayload[];
  summary: SimulateSummary;
  macro_result: MacroResult;
}

export interface SimulateRequest {
  catalyst_text: string;
  source_url?: string | null;
  city_id: string;
  use_case: string;
  message_complexity: number;
}
