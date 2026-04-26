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
  agent_insight: {
    vulnerability: string;
    cause_of_state: string;
    best_intervention: string;
  };
}

export interface SummaryCounts {
  total: number;
  adopted: number;
  rejected: number;
  neutral: number;
}

export interface EvidenceAudioInput {
  filename?: string | null;
  mime_type?: string | null;
  duration_seconds?: number | null;
  transcript_confidence?: number | null;
  source_type?: string | null;
  transcript_edited?: boolean;
}

export interface EvidenceInput {
  text_input: string;
  source_url?: string | null;
  transcript?: string | null;
  edited_analysis_text?: string | null;
  speaker_context?: string | null;
  audio_input?: EvidenceAudioInput | null;
}

export interface SimulateRequest {
  domain: string;
  city_id: string;
  case_goal: string;
  evidence: EvidenceInput;
  message_complexity: number;
}

export interface EvidenceClaim {
  id: string;
  text: string;
  risk: 'High' | 'Moderate' | 'Low';
}

export interface EvidenceTrace {
  original_text: string;
  transcript?: string | null;
  source_url?: string | null;
  source_excerpt?: string | null;
  analysis_text: string;
  speaker_context?: string | null;
  claims: EvidenceClaim[];
  themes: string[];
  provenance: {
    source_type: string;
    audio_input?: EvidenceAudioInput | null;
    transcript_used: boolean;
    analysis_text_source: string;
  };
  warnings: string[];
}

export interface Hotspot {
  id: string;
  label: string;
  area: string;
  share: number;
  lng: number;
  lat: number;
  radiusMeters: number;
}

export interface SegmentInsight {
  label: string;
  dominant_driver: DominantSignal;
  share: number;
  risk_level: 'High' | 'Moderate';
  why_vulnerable: string;
  recommended_intervention_focus: string;
}

export interface BeliefPathway {
  id: DominantSignal;
  label: string;
  share: number;
  description: string;
}

export interface SpreadModel {
  risk_score: number;
  spread_risk: 'Low' | 'Moderate' | 'High';
  belief_adoption_rate: number;
  claim_rejection_rate?: number;
  scientific_credibility?: number;
  population_reached: number;
  avg_cognitive_load: number;
  avg_defensive_activation: number;
  high_risk_segments: SegmentInsight[];
  belief_adoption_pathways: BeliefPathway[];
  hotspots: Hotspot[];
  network_summary: string;
  core_story?: string;
}

export interface MechanismDriver {
  signal: DominantSignal;
  share: number;
  description: string;
}

export interface EvidenceLink {
  type: string;
  label: string;
  risk: string;
}

export interface MechanismsReport {
  mechanism_summary: string;
  dominant_cognitive_drivers: MechanismDriver[];
  target_segments: SegmentInsight[];
  evidence_links: EvidenceLink[];
  confidence_notes: string[];
}

export interface InterventionItem {
  id: string;
  title: string;
  goal: string;
  target_audience: string;
  mechanism_addressed: string;
  recommended_channel: string;
  recommended_messenger: string;
  message_strategy: string;
  time_horizon: string;
  expected_effect: string;
  confidence: number;
  why_this_should_work: string;
  supporting_evidence: string[];
}

export interface CaseSummary {
  title: string;
  goal: string;
  domain: string;
  target_region: string;
  spread_risk: 'Low' | 'Moderate' | 'High';
  overall_confidence: number;
  key_finding: string;
  recommended_next_step: string;
}

export interface LegacyMacroResult {
  score: number;
  risk_level: 'Low' | 'Moderate' | 'High';
  insights: Array<{ where: string; why: string; who: string }>;
  suggested_rewrite: string;
  synthetic_thoughts: Array<{
    agent_id: number;
    text: string;
    sentiment: 'positive' | 'negative' | 'neutral';
    driver: string;
  }>;
  hotspots: Hotspot[];
  summary_text: string;
  sentiment_mix: SummaryCounts;
  input_summary: string;
  source_context_summary?: string | null;
  source_warning?: string | null;
}

export interface SimulateResponse {
  city_id: string;
  domain: string;
  case_goal: string;
  effective_catalyst_text: string;
  case_summary: CaseSummary;
  spread_model: SpreadModel;
  mechanisms: MechanismsReport;
  intervention_playbook: InterventionItem[];
  evidence_trace: EvidenceTrace;
  summary: SummaryCounts;
  agents: AgentSimulationPayload[];
  macro_result: LegacyMacroResult;
}

export interface TranscriptionResponse {
  text: string;
  language_code?: string | null;
  duration_seconds?: number | null;
  transcript_confidence?: number | null;
  speaker_ids: string[];
  filename: string;
  mime_type?: string | null;
  source_type: string;
}
