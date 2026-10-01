"""Structured outputs produced by Gemini (CrewAI task outputs + vision schema)."""
from typing import Literal

from pydantic import BaseModel, Field

SIGNAL_KEYS: list[str] = [
    "impersonation", "urgency", "threat", "financial_request", "credential_request",
    "registration_fee", "kyc_threat", "suspicious_url", "domain_mismatch", "url_shortener",
    "ip_url", "http_not_https", "fake_authority", "misleading_claim", "inconsistency",
    "editing_software_exif", "exif_time_mismatch", "ela_anomaly", "unusual_language",
    "action_pressure",
    # image media analysis (synthetic_detection intent)
    "ai_generation_indicator", "manipulation_indicator", "visual_inconsistency",
]


class Extracted(BaseModel):
    classification: str = "other"  # screenshot|message|news_claim|document|social_post|other
    extracted_text: str = ""
    sender: str = ""
    sender_domain: str = ""
    company: str = ""
    person: str = ""
    claim: str = ""
    date: str = ""
    urls: list[str] = Field(default_factory=list)
    phone_numbers: list[str] = Field(default_factory=list)
    email_addresses: list[str] = Field(default_factory=list)
    money_amounts: list[str] = Field(default_factory=list)
    requested_action: str = ""


class LLMSignal(BaseModel):
    key: str
    title: str = ""
    severity: str = "medium"  # high|medium|low
    explanation: str = ""
    evidence: str = ""
    uncertainty: str = ""


class SignalSet(BaseModel):
    signals: list[LLMSignal] = Field(default_factory=list)
    inconsistencies: list[str] = Field(default_factory=list)
    overall_assessment: str = "unverified"  # low_risk|medium_risk|high_risk|unverified
    recommendation: str = ""
    what_to_verify: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    source: str = ""
    url: str = ""
    rating: str = "none"
    stance: str = "unrelated"  # supports|refutes|mixed|unrelated
    quote: str = ""


class ClaimEvidence(BaseModel):
    claim: str = ""
    entities: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    what_to_verify: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)


class VisualIndicator(BaseModel):
    kind: str = "visual_inconsistency"  # ai_generation | manipulation | visual_inconsistency
    title: str = ""
    severity: str = "medium"  # high|medium|low
    explanation: str = ""
    evidence: str = ""  # where in the image and what is visible there
    uncertainty: str = ""


class VisualAssessment(BaseModel):
    """Gemini vision output for the synthetic_detection intent."""
    media_type: str = "other"  # photo|screenshot|document|illustration|other
    description: str = ""
    visible_text: str = ""
    indicators: list[VisualIndicator] = Field(default_factory=list)
    authentic_cues: list[str] = Field(default_factory=list)
    assessment: str = "inconclusive"  # likely_synthetic|likely_authentic|manipulated|inconclusive
    limitations: list[str] = Field(default_factory=list)


Severity = Literal["high", "medium", "low"]
