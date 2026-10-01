"""API contract. Mirrored exactly by frontend/src/types/report.ts."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.models.llm_outputs import Extracted

Severity = Literal["high", "medium", "low"]
Category = Literal["image_forensics", "url_domain", "message_content", "claim_evidence"]
Source = Literal["RULE", "GEMINI"]

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


class TrustReport(BaseModel):
    analysis_mode: Literal["live", "demo_cached"] = "live"
    input_type: Literal["image", "text", "claim"]
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
