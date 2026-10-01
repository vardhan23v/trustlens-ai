// Mirrors backend/app/models/report.py and backend/app/models/llm_outputs.py exactly.

export type Severity = 'high' | 'medium' | 'low'
export type Category = 'image_forensics' | 'visual_analysis' | 'url_domain' | 'message_content' | 'claim_evidence'
export type Source = 'RULE' | 'GEMINI'
export type InputType = 'image' | 'text' | 'claim' | 'media'
/** The two product modes. Sent as the `mode` form field of POST /api/analyze. */
export type Mode = 'news_claim' | 'ai_generated'
export type MediaType = 'image' | 'video' | 'audio'
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH'
export type Verdict = 'VERIFIED_BY_SOURCE' | 'DEBUNKED_BY_SOURCE' | 'UNVERIFIED'
export type AnalysisMode = 'live' | 'demo_cached'
/** Image input: what the user asked TrustLens to verify. Sent as the `analysis_mode` form field. */
export type Intent = 'synthetic_detection' | 'artifact_authenticity'
export type AssessmentState =
  | 'LIKELY_AUTHENTIC'
  | 'LIKELY_FABRICATED'
  | 'LIKELY_SYNTHETIC'
  | 'MANIPULATED'
  | 'INCONCLUSIVE'
  | 'UNVERIFIED'
  | 'NOT_ASSESSED'
  | 'SUPPORTED'
  | 'CONTRADICTED'
  | 'MISLEADING_CONTEXT'
  | 'EVIDENCE_UNAVAILABLE'

export interface Assessment {
  state: AssessmentState
  label: string
  summary: string
  confidence: string // '' | low | medium | high
  basis: string
}

export interface Stage {
  name: string
  status: 'done' | 'skipped' | 'failed' | 'unavailable'
  detail: string
}

export interface SpecialistModel {
  slot: string
  task: string
  candidate: string
  status: string // AVAILABLE | MODEL_UNAVAILABLE
  detail: string
}

export interface EvidenceSignal {
  signal_id: string
  category: string
  modality: string
  source_type: 'RULE' | 'MODEL' | 'GEMINI' | 'EXTERNAL_SOURCE'
  model: string
  finding: string
  direction: 'SUPPORTS' | 'CONTRADICTS' | 'NEUTRAL' | 'UNKNOWN'
  confidence: string
  reliability: string
  relevance: string
  dimension: 'claim' | 'media_authenticity' | 'context' | 'content_risk'
  evidence: string
  source_reference: string
  limitations: string[]
}

export interface AxisAssessment extends Assessment {
  heading: string
}

export type ElaStatus = 'ok' | 'not_applicable_lossless' | 'not_applicable' | 'error'

export interface Extracted {
  classification: string // screenshot|message|news_claim|document|social_post|other
  extracted_text: string
  sender: string
  sender_domain: string
  company: string
  person: string
  claim: string
  date: string
  urls: string[]
  phone_numbers: string[]
  email_addresses: string[]
  money_amounts: string[]
  requested_action: string
}

export interface Signal {
  key: string
  title: string
  severity: Severity
  category: Category
  sources: Source[]
  explanation: string
  evidence: string
  uncertainty: string
  penalty: number // points before the per-category cap
}

export interface Evidence {
  source: string
  url: string
  rating: string
  stance: string // supports|refutes|mixed|unrelated
  quote: string
  title: string
  published: string // YYYY-MM-DD, or '' when unknown
  source_site: string
  source_type: string // official | wire | established | factcheck | other
  claim_index: number
}

export interface ClaimStatus {
  text: string
  dimension: string
  status: 'SUPPORTED' | 'CONTRADICTED' | 'MIXED' | 'UNVERIFIED'
  supporting: number
  contradicting: number
}

export interface TimelineEvent {
  date: string
  source: string
  title: string
  stance: string
  url: string
}

export interface Article {
  url: string
  headline: string
  publisher: string
  author: string
  published: string
}

export interface Ela {
  status: ElaStatus
  heatmap_b64: string | null // PNG, base64 (no data: prefix)
  region: number[] | null // [x, y, w, h] in original pixels
  width: number | null
  height: number | null
}

export interface CategoryBreakdown {
  category: Category
  raw: number // sum of signal penalties in this category
  cap: number
  applied: number // min(raw, cap) — what was actually subtracted
}

export interface TrustReport {
  analysis_mode: AnalysisMode
  input_type: InputType
  mode: Mode | null
  report_id: string
  media_type: MediaType | ''
  stages: Stage[]
  specialist_models: SpecialistModel[]
  media_metadata: Record<string, string | number>
  evidence_signals: EvidenceSignal[]
  change_factors: string[]
  score_scope: string
  assessment_axes: AxisAssessment[]
  claims: ClaimStatus[]
  timeline: TimelineEvent[]
  article: Article | null
  inputs_provided: string[]
  analysis_intent: Intent | null
  overall_assessment: Assessment | null
  media_assessment: Assessment | null
  artifact_assessment: Assessment | null
  confidence_boosters: string[]
  classification: string
  trust_score: number
  risk_level: RiskLevel
  verdict: Verdict | null
  confidence: number | null
  extracted: Extracted
  signals: Signal[]
  score_breakdown: CategoryBreakdown[]
  evidence: Evidence[]
  recommendation: string
  what_to_verify: string[]
  inconsistencies: string[]
  notes: string[]
  ela: Ela
  gemini_error: string | null
  agents_used: string[]
  caveats: string[]
  disclaimer: string
}

// GET /api/health
export interface Health {
  status: string
  gemini_model: string
  gemini_configured: boolean
  crewai_version: string
  database?: string
}

// GET /api/demos
export interface Demo {
  id: string
  label: string
  input_type: InputType
  mode: Mode
  text: string | null
  image_url: string | null
}
