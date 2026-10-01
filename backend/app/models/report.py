"""API contract. Mirrored exactly by frontend/src/types/report.ts."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.models.evidence import EvidenceSignal
from app.models.llm_outputs import Extracted

Severity = Literal["high", "medium", "low"]
Category = Literal["image_forensics", "visual_analysis", "url_domain", "message_content", "claim_evidence"]
Intent = Literal["synthetic_detection", "artifact_authenticity"]
AssessmentState = Literal["LIKELY_AUTHENTIC", "LIKELY_FABRICATED", "LIKELY_SYNTHETIC", "MANIPULATED",
                          "INCONCLUSIVE", "UNVERIFIED", "NOT_ASSESSED", "SUPPORTED", "CONTRADICTED",
                          "MISLEADING_CONTEXT", "EVIDENCE_UNAVAILABLE"]
Mode = Literal["news_claim", "ai_generated"]
Source = Literal["RULE", "GEMINI", "MODEL"]

DISCLAIMER = "Trust Score is a risk indicator, not proof of authenticity or fraud."


class Signal(BaseModel):
    key: str
    title: str
    severity: Severity
    category: Category = "message_content"
    sources: list[Source] = Field(default_factory=lambda: ["RULE"])
    explanation: str = ""
    evidence: str = ""
    uncertainty: str = ""
    penalty: float = 0  # points before the per-category cap


class Evidence(BaseModel):
    source: str
    url: str
    rating: str = "none"
    stance: str = "unrelated"
    quote: str = ""
    title: str = ""  # headline exactly as the feed/API returned it
    published: str = ""  # YYYY-MM-DD from the source feed; empty = unknown (never guessed)
    source_site: str = ""  # publisher site, for counting independent sources
    source_type: str = "other"  # official | wire | established | factcheck | other (rules/source_registry.json)
    claim_index: int = 0
    # second opinion from the specialist models (None / "" when they did not run)
    relevance: Optional[float] = None  # cosine similarity of the headline to the claim
    nli_label: str = ""  # entailment | contradiction | neutral: headline versus claim
    nli_score: float = 0.0
    stance_note: str = ""  # why a source was set aside, if it was


class ClaimStatus(BaseModel):
    """One decomposed claim and what independent sources say about it. Decided in Python."""
    text: str
    dimension: str = "event"
    status: Literal["SUPPORTED", "CONTRADICTED", "MIXED", "UNVERIFIED"] = "UNVERIFIED"
    supporting: int = 0  # independent listed sources (one per site)
    contradicting: int = 0


class TimelineEvent(BaseModel):
    date: str  # YYYY-MM-DD or "UNKNOWN"
    source: str
    title: str
    stance: str
    url: str


class Ela(BaseModel):
    status: Literal["ok", "not_applicable_lossless", "not_applicable", "error"] = "not_applicable"
    heatmap_b64: Optional[str] = None  # PNG, base64 (no data: prefix)
    region: Optional[list[int]] = None  # [x, y, w, h] in original pixels
    width: Optional[int] = None
    height: Optional[int] = None


class CategoryBreakdown(BaseModel):
    category: Category
    raw: float  # sum of signal penalties in this category
    cap: float
    applied: float  # min(raw, cap) — what was actually subtracted


class Assessment(BaseModel):
    """One axis of the result. Computed in Python from the signals, never taken from the model."""
    state: AssessmentState
    label: str
    summary: str
    confidence: str = ""  # low | medium | high: how much relevant evidence stands behind the state
    basis: str = ""  # what that confidence rests on


class Stage(BaseModel):
    """One pipeline stage as it actually went. No percentages, nothing invented."""
    name: str
    status: Literal["done", "skipped", "failed", "unavailable"]
    detail: str = ""


class SpecialistModel(BaseModel):
    slot: str
    task: str
    candidate: str = ""
    status: str = "MODEL_UNAVAILABLE"  # RAN | NOT_APPLICABLE | NOT_RUN | FAILED | MODEL_UNAVAILABLE
    detail: str = ""
    limitations: list[str] = Field(default_factory=list)


class AxisAssessment(Assessment):
    heading: str  # e.g. "Visual authenticity"


class TrustReport(BaseModel):
    analysis_mode: Literal["live", "demo_cached"] = "live"
    input_type: Literal["image", "text", "claim", "media"]
    # The product mode the user chose and the kind of file they uploaded.
    mode: Optional[Mode] = None
    report_id: str = ""  # set when the analysis completes; reopens the stored report if a database is configured
    media_type: str = ""  # image | video | audio
    stages: list[Stage] = Field(default_factory=list)
    specialist_models: list[SpecialistModel] = Field(default_factory=list)
    media_metadata: dict = Field(default_factory=dict)  # container facts read by ffmpeg
    evidence_signals: list[EvidenceSignal] = Field(default_factory=list)  # every finding in one schema
    change_factors: list[str] = Field(default_factory=list)  # "What would change the assessment?"
    score_scope: str = ""  # what the 0-100 number does and does not measure in this mode
    # Claim verification: decomposed claims, dated source timeline, and the article that was fetched (if any).
    claims: list[ClaimStatus] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    article: Optional[dict] = None
    inputs_provided: list[str] = Field(default_factory=list)  # claim mode: text | url | image
    # Video / audio: each question answered separately (visual, audio, A/V consistency, spoken claim).
    assessment_axes: list[AxisAssessment] = Field(default_factory=list)
    # Image input only: what the user asked TrustLens to verify, and the two separate answers.
    # "Not AI-generated" does not mean "true", so media and artifact are assessed independently.
    analysis_intent: Optional[Intent] = None
    overall_assessment: Optional[Assessment] = None
    media_assessment: Optional[Assessment] = None
    artifact_assessment: Optional[Assessment] = None
    confidence_boosters: list[str] = Field(default_factory=list)  # "What would increase confidence?"
    classification: str = "other"
    trust_score: int
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    verdict: Optional[Literal["VERIFIED_BY_SOURCE", "DEBUNKED_BY_SOURCE", "UNVERIFIED"]] = None
    confidence: Optional[float] = None
    extracted: Extracted = Field(default_factory=Extracted)
    signals: list[Signal] = Field(default_factory=list)
    score_breakdown: list[CategoryBreakdown] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    recommendation: str = ""
    what_to_verify: list[str] = Field(default_factory=list)
    inconsistencies: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    ela: Ela = Field(default_factory=Ela)
    gemini_error: Optional[str] = None
    agents_used: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER
