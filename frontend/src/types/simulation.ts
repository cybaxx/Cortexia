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

export interface AgentDemographics {
  age_band: string;
  age_years: number;
  education_level: string;
  income_band: string;
  housing_status: string;
  language_profile: string;
  community_tenure: string;
  caregiving_load: string;
  digital_media_habit: string;
  summary: string;
}

export interface AgentSimulationPayload {
  id: number;
  name: string;
  role: string;
  longitude: number;
  latitude: number;
  demographics?: AgentDemographics;
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
  round_history?: Array<{
    round: number;
    phase_label?: string;
    belief_state: 'adopted' | 'rejected' | 'neutral';
    confidence: number;
    confidence_delta?: number;
    sentiment: 'positive' | 'negative' | 'neutral';
    trigger?: string;
    change_summary?: string;
    /** Share of visible neighborhood influence (0–1); matches change_summary support/pushback. */
    supportive_pressure?: number;
    skeptical_pressure?: number;
    /** Raw tie-weighted influence sums (same scale as trigger line weighted_* when present). */
    support_influence?: number;
    pushback_influence?: number;
    messenger_alignment?: number;
    post: string;
  }>;
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

export interface EvidenceGraphNode {
  id: string;
  label: string;
  kind: 'claim' | 'theme' | 'actor' | 'concept' | string;
  risk?: 'High' | 'Moderate' | 'Low' | string;
}

export interface EvidenceGraphEdge {
  source: string;
  target: string;
  label: string;
}

export interface Hotspot {
  id: string;
  label: string;
  area: string;
  share: number;
  lng: number;
  lat: number;
  radiusMeters: number;
  state?: 'adopted' | 'rejected' | 'neutral';
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
  run_id?: number;
  city_id: string;
  domain: string;
  case_goal: string;
  effective_catalyst_text: string;
  tribe_meta?: {
    provider?: string;
    model_id?: string;
    cache_dir?: string;
    input_mode?: string;
    derivation_version?: string;
    pred_shape?: [number, number] | number[];
    signal_confidence?: number;
    dominant_roi?: string;
    formatted_state?: string;
    data_dir?: string;
    composites?: Record<string, number | string | boolean>;
    roi_stats?: Record<string, unknown>;
    connectivity?: Record<string, unknown>;
    surface_summary?: {
      dominant_response?: {
        id: string;
        label: string;
        peak: number;
        auc: number;
        trajectory: string;
        onset_seconds: number;
        sustained: boolean;
      } | null;
      weakest_response?: {
        id: string;
        label: string;
        peak: number;
        auc: number;
        trajectory: string;
        onset_seconds: number;
        sustained: boolean;
      } | null;
      processing_sequence?: Array<{
        id: string;
        label: string;
        onset_seconds: number;
      }>;
      strongest_link?: {
        id: string;
        label: string;
        r: number;
        p: number;
      } | null;
      composite_highlights?: Array<{
        id: string;
        label: string;
        value: number;
        interpretation: string;
      }>;
      narrative_flags?: string[];
    };
    segment_count?: number;
    segments_preview?: Array<{
      id: string;
      label: string;
      peak: number;
      auc: number;
      trajectory: string;
      onset_seconds: number;
      sustained: boolean;
    }>;
  };
  case_summary: CaseSummary;
  spread_model: SpreadModel;
  mechanisms: MechanismsReport;
  intervention_playbook: InterventionItem[];
  evidence_trace: EvidenceTrace;
  evidence_graph?: {
    nodes: EvidenceGraphNode[];
    edges: EvidenceGraphEdge[];
  };
  swarm_dynamics?: {
    narrative_summary: string;
    network_edges?: Array<{
      source_id: number;
      target_id: number;
      source_lng: number;
      source_lat: number;
      target_lng: number;
      target_lat: number;
      weight?: number;
      compatibility?: number;
    }>;
    event_log?: Array<{
      tick: number;
      author_id: number;
      target_agent_id?: number | null;
      action_type: 'talk_to_agent' | 'post_public' | 'do_nothing' | string;
      content: string;
    }>;
    rounds: Array<{
      round: number;
      adoption_rate: number;
      rejection_rate: number;
      neutral_rate: number;
      dominant_mechanism: DominantSignal;
      notable_shift: string;
      posts: Array<{
        agent_id: number;
        name: string;
        role: string;
        belief_state: 'adopted' | 'rejected' | 'neutral';
        confidence: number;
        sentiment: 'positive' | 'negative' | 'neutral';
        dominant_signal: DominantSignal;
        post: string;
        target_agent_id?: number | null;
        action_type?: 'talk_to_agent' | 'post_public' | 'do_nothing' | string;
        weighted_support?: number;
        weighted_pushback?: number;
      }>;
    }>;
  };
  summary: SummaryCounts;
  agents: AgentSimulationPayload[];
  macro_result: LegacyMacroResult;
}

export interface RecentRunSummary {
  id: number;
  created_at: string;
  domain: string;
  city_id: string;
  case_goal: string;
  claim: {
    credibility?: number;
    harm?: number;
    [key: string]: unknown;
  };
  fidelity: number;
}

export interface PersistedRunResponse {
  id: number;
  created_at: string;
  domain: string;
  city_id: string;
  case_goal: string;
  evidence: EvidenceInput;
  analysis_text: string;
  source_excerpt?: string | null;
  source_warning?: string | null;
  claim: Record<string, unknown>;
  fidelity: number;
  response: SimulateResponse;
}

export interface AgentConversationMessage {
  id: number;
  created_at?: string;
  user_message: string;
  agent_reply: string;
  sentiment: 'positive' | 'negative' | 'neutral' | string;
  stance: 'adopted' | 'rejected' | 'neutral' | string;
  audio_filename?: string | null;
  audio_url?: string | null;
}

export interface PersistedAgentProfile {
  run_id: number;
  agent_id: number;
  name: string;
  role: string;
  latitude: number;
  longitude: number;
  demographics: Record<string, unknown>;
  spread_notes: string;
  tribe: Record<string, unknown>;
  calibrated: Record<string, unknown>;
  traits: Record<string, unknown>;
  scores: Record<string, unknown>;
  outcome: Record<string, unknown>;
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

export interface ActionCenterProviderStatus {
  enabled: boolean;
  mode: string;
  detail: string;
}

export interface ActionCenterSource {
  title: string;
  url: string;
  domain: string;
  snippet: string;
  raw_excerpt: string;
  favicon?: string | null;
  score?: number;
}

export interface ActionCenterPattern {
  url: string;
  claim: string;
  risk_level: string;
  geography: string;
  why_it_matters: string;
  evidence: string;
}

export interface ActionCenterBrief {
  headline: string;
  executive_summary: string;
  decision_window: string;
  urgency: 'low' | 'medium' | 'high' | string;
  confidence_note: string;
}

export interface ActionCenterRecommendedAction {
  title: string;
  owner: string;
  audience: string;
  timeline: string;
  action: string;
  why_now: string;
}

export interface ActionCenterSourceBriefing {
  url: string;
  why_it_matters: string;
  credibility_note: string;
}

export interface ActionCenterVerificationItem {
  url: string;
  reason: string;
  check_for: string;
}

export interface ActionCenterResponse {
  providers?: Record<string, ActionCenterProviderStatus>;
  provider_status: Record<string, ActionCenterProviderStatus>;
  queries: string[];
  sources: ActionCenterSource[];
  extracted_patterns: ActionCenterPattern[];
  brief: ActionCenterBrief;
  recommended_actions: ActionCenterRecommendedAction[];
  monitoring_queries: string[];
  source_briefings: ActionCenterSourceBriefing[];
  browser_verification_queue: ActionCenterVerificationItem[];
}

export interface ActionCenterResearchRequest {
  domain: string;
  city_id: string;
  case_goal: string;
  scenario: string;
  spread_risk?: string | null;
  key_finding?: string | null;
  dominant_pathway?: string | null;
  notes?: string | null;
}
