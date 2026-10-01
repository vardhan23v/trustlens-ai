// Mirrors backend/app/models/report.py and backend/app/models/llm_outputs.py exactly.

export type Severity = 'high' | 'medium' | 'low'
export type Category = 'image_forensics' | 'url_domain' | 'message_content' | 'claim_evidence'
export type Source = 'RULE' | 'GEMINI'
export type InputType = 'image' | 'text' | 'claim'
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH'
export type Verdict = 'VERIFIED_BY_SOURCE' | 'DEBUNKED_BY_SOURCE' | 'UNVERIFIED'
export type AnalysisMode = 'live' | 'demo_cached'
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
}

// GET /api/demos
export interface Demo {
  id: string
  label: string
  input_type: InputType
  text: string | null
  image_url: string | null
}
