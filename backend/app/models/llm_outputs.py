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
    # video / audio analysis
    "av_inconsistency", "audio_anomaly",
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
    claim_index: int = 0  # which sub-claim (1-based) this item speaks to; 0 = the claim as a whole


class SubClaim(BaseModel):
    text: str = ""
    dimension: str = "event"  # entity | action | amount | time | location | event


class ClaimEvidence(BaseModel):
    claim: str = ""
    entities: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    what_to_verify: list[str] = Field(default_factory=list)
    sub_claims: list[SubClaim] = Field(default_factory=list)
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


class NewsImageExtract(BaseModel):
    """Gemini's reading of an image submitted for claim verification (one call: OCR + context check)."""
    extracted_text: str = ""  # all visible text, verbatim
    claim_in_image: str = ""  # the factual claim the image itself makes or is used for, if any
    visual_description: str = ""  # what is actually depicted
    time_place_clues: list[str] = Field(default_factory=list)  # visible dates, signs, landmarks, language
    caption_consistency: str = "no_caption"  # consistent | inconsistent | cannot_tell | no_caption
    mismatches: list[str] = Field(default_factory=list)  # concrete conflicts between image and caption
    visual_notes: str = ""  # visually odd regions, or "none"
    # media authenticity of the image itself, judged in the same call
    media_assessment: str = "inconclusive"  # likely_synthetic|likely_authentic|manipulated|inconclusive
    indicators: list[VisualIndicator] = Field(default_factory=list)
    language: str = ""


class MediaObservation(BaseModel):
    timestamp: str = ""  # "MM:SS" where it occurs; empty only if it applies to the whole file
    kind: str = "visual"  # visual_manipulation | visual_ai_generation | audio_synthesis | audio_edit | av_sync | context
    title: str = ""
    severity: str = "medium"
    explanation: str = ""
    evidence: str = ""  # what is seen or heard at that moment
    uncertainty: str = ""


class MediaAssessment(BaseModel):
    """Gemini's examination of an uploaded video or audio file."""
    media_kind: str = "video"  # video | audio
    has_speech: bool = False
    transcript: str = ""
    language: str = ""
    spoken_claims: list[str] = Field(default_factory=list)
    on_screen_text: str = ""  # captions, tickers, banners visible in the frames (video only)
    description: str = ""
    observations: list[MediaObservation] = Field(default_factory=list)
    visual_assessment: str = "inconclusive"  # likely_authentic|manipulated|likely_synthetic|inconclusive|not_applicable
    audio_assessment: str = "inconclusive"  # likely_authentic|likely_synthetic|manipulated|inconclusive|not_applicable
    av_consistency: str = "inconclusive"  # consistent|inconsistent|inconclusive|not_applicable
    limitations: list[str] = Field(default_factory=list)


Severity = Literal["high", "medium", "low"]
