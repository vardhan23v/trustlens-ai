"""TrustLensFlow — one CrewAI Flow run per request.

forensics (image) → vision_extract (image, Gemini) → rules (deterministic) → analyze (CrewAI crew, Gemini)
The report is built from the final state by services/reporter.py. Score and verdict are Python-only.
"""
import asyncio
import logging
from typing import Optional

from app.config import settings  # noqa: F401  (first: disables CrewAI telemetry)

from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel, Field

from app.models.llm_outputs import ClaimEvidence, Extracted, SignalSet
from app.models.report import Ela, Signal
from app.rules import text_rules
from app.services import gemini_vision, image_forensics
from app.services.crew import crews

log = logging.getLogger("trustlens.flow")


class FlowState(BaseModel):
    input_type: str = "text"  # image | text | claim
    text: str = ""
    image_format: str = ""
    exif_signals: list[Signal] = Field(default_factory=list)
    ela: Ela = Field(default_factory=Ela)
    ela_signal: Optional[Signal] = None
    extracted: Extracted = Field(default_factory=Extracted)
    rule_signals: list[Signal] = Field(default_factory=list)
    all_urls_match_claimed: bool = False
    llm_signals: Optional[SignalSet] = None
    claim_evidence: Optional[ClaimEvidence] = None
    tool_urls: dict[str, dict] = Field(default_factory=dict)
    tool_errors: list[str] = Field(default_factory=list)
    crew_error: Optional[str] = None
    analysis_mode: str = "live"
    agents_used: list[str] = Field(default_factory=list)
    fixture: Optional[dict] = None  # demo mode: recorded vision + crew outputs


def content_text(extracted_text: str) -> str:
    """extracted_text without the model's trailing VISUAL_NOTES line (rules run on document text only)."""
    return "\n".join(l for l in extracted_text.splitlines() if not l.strip().startswith("VISUAL_NOTES:"))


class TrustLensFlow(Flow[FlowState]):
    image_bytes: bytes = b""  # kept off the state: never serialised, never stored

    @start()
    def forensics(self):
        s = self.state
        if s.input_type != "image":
            return
        s.exif_signals = image_forensics.exif(self.image_bytes)
        s.ela, s.ela_signal = image_forensics.ela(self.image_bytes, s.image_format)

    @listen(forensics)
    def vision_extract(self):
        s = self.state
        if s.input_type != "image":
            return
        if s.fixture is not None:
            s.extracted = Extracted.model_validate(s.fixture.get("extracted") or {})
            s.agents_used.append("vision")
            return
        try:
            s.extracted = gemini_vision.extract(self.image_bytes, s.image_format)
            s.agents_used.append("vision")
        except Exception as e:  # continue with an empty extraction; never fabricate
            log.warning("vision step failed: %s", e)
            s.crew_error = f"vision: {e}"

    @listen(vision_extract)
    def rules(self):
        s = self.state
        text = content_text(s.extracted.extracted_text) if s.input_type == "image" else s.text
        result = text_rules.run(text)
        s.rule_signals = result.signals
        s.all_urls_match_claimed = result.domain.all_urls_match_claimed

    @listen(rules)
    def analyze(self):
        s = self.state
        findings = text_rules.summarize(s.exif_signals + ([s.ela_signal] if s.ela_signal else []) + s.rule_signals)
        if s.fixture is not None:
            self._from_fixture()
            return
        if s.crew_error:  # vision already failed: nothing to analyse
            return
        try:
            if s.input_type == "image":
                s.llm_signals = crews.run_image_crew(s.extracted, findings)
                s.agents_used.append("analyst")
            elif s.input_type == "text":
                s.extracted, s.llm_signals = crews.run_text_crew(s.text, findings)
                s.agents_used += ["extractor", "analyst"]
            else:
                s.claim_evidence, ledger = crews.run_claim_crew(s.text)
                s.tool_urls, s.tool_errors = ledger.items, ledger.errors
                s.agents_used.append("claim_verifier")
        except Exception as e:
            log.warning("crew step failed: %s", e)
            s.crew_error = f"crew: {e}"

    def _from_fixture(self):
        s, fx = self.state, self.state.fixture or {}
        if s.input_type == "claim":
            s.claim_evidence = ClaimEvidence.model_validate(fx.get("claim_evidence") or {})
            s.tool_urls = fx.get("tool_urls") or {}
            s.agents_used.append("claim_verifier")
            return
        if s.input_type == "text":
            s.extracted = Extracted.model_validate(fx.get("extracted") or {})
            s.agents_used.append("extractor")
        s.llm_signals = SignalSet.model_validate(fx.get("signal_set") or {})
        s.agents_used.append("analyst")


def run_sync(input_type: str, text: str = "", image_bytes: bytes = b"", image_format: str = "",
             fixture: dict | None = None) -> FlowState:
    flow = TrustLensFlow()
    flow.image_bytes = image_bytes
    inputs = {"input_type": input_type, "text": text, "image_format": image_format}
    if fixture is not None:
        inputs |= {"fixture": fixture, "analysis_mode": "demo_cached"}
    flow.kickoff(inputs=inputs)
    return flow.state


async def run(input_type: str, text: str = "", image_bytes: bytes = b"", image_format: str = "",
              fixture: dict | None = None) -> FlowState:
    """Run the Flow in a worker thread under the global timeout. On timeout the deterministic
    steps are re-run alone so a rule + forensics report is still returned."""
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, run_sync, input_type, text, image_bytes, image_format, fixture),
            settings.FLOW_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        log.warning("flow timed out after %ss", settings.FLOW_TIMEOUT_S)
        return deterministic_only(input_type, text, image_bytes, image_format, "timeout")


def deterministic_only(input_type: str, text: str, image_bytes: bytes, image_format: str, reason: str) -> FlowState:
    s = FlowState(input_type=input_type, text=text, image_format=image_format, crew_error=reason)
    if input_type == "image":
        s.exif_signals = image_forensics.exif(image_bytes)
        s.ela, s.ela_signal = image_forensics.ela(image_bytes, image_format)
    else:
        result = text_rules.run(text)
        s.rule_signals, s.all_urls_match_claimed = result.signals, result.domain.all_urls_match_claimed
    return s
