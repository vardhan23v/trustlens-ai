"""Unified evidence schema. Every finding in a report — a rule hit, a Gemini observation, a specialist
model result, an external source — is also emitted in this one shape, so the assessment code and any
later fusion model read a single list."""
from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["RULE", "MODEL", "GEMINI", "EXTERNAL_SOURCE"]
Direction = Literal["SUPPORTS", "CONTRADICTS", "NEUTRAL", "UNKNOWN"]
# What question the evidence bears on. Evidence only counts toward its own dimension.
Dimension = Literal["claim", "media_authenticity", "context", "content_risk"]


class EvidenceSignal(BaseModel):
    signal_id: str
    category: str
    modality: str = ""  # image | video | audio | text (OCR / transcript) | external
    source_type: SourceType
    model: str = ""  # which model produced it, when one did
    finding: str
    # direction is relative to the dimension's positive reading: the claim being true / the media being authentic
    direction: Direction = "UNKNOWN"
    confidence: str = ""  # low | medium | high — how sure this one source is; not a calibrated probability
    reliability: str = ""  # how far this kind of evidence can be trusted in general
    relevance: str = ""  # which dimension / atomic claim it applies to
    dimension: Dimension = "content_risk"
    evidence: str = ""
    source_reference: str = ""
    limitations: list[str] = Field(default_factory=list)
