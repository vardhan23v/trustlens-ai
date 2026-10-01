"""TrustLensFlow — one CrewAI Flow run per request.

forensics (image) → vision_extract (image, Gemini) → rules (deterministic) → analyze (CrewAI crew, Gemini)
The report is built from the final state by services/reporter.py. Score and verdict are Python-only.
"""
import asyncio
import logging
import re
from typing import Optional

from app.config import settings  # noqa: F401  (first: disables CrewAI telemetry)

from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel, Field

from app.models.llm_outputs import (ClaimEvidence, Extracted, MediaAssessment, NewsImageExtract, SignalSet,
                                    VisualAssessment)
from app.models.report import Ela, Signal
from app.rules import text_rules
from app.services import gemini_media, gemini_text, gemini_vision, image_forensics
from app.services.media import probe
from app.services.crew import crews

log = logging.getLogger("trustlens.flow")


class FlowState(BaseModel):
    input_type: str = "text"  # image | text | claim | media
    mode: str = ""  # product mode: news_claim | ai_generated ("" = legacy callers, tests, demos)
    media_type: str = ""  # image | video | audio
    stages: list[dict] = Field(default_factory=list)  # what actually ran, in order
    media_meta: dict = Field(default_factory=dict)  # container facts from ffmpeg
    sampled_frames: int = 0  # keyframes sent to Gemini instead of the whole video (0 = whole file sent)
    media: Optional[MediaAssessment] = None  # media: Gemini's examination of the video/audio file
    media_mime: str = ""
    news_image: Optional[NewsImageExtract] = None  # claim mode with an image: OCR + image-vs-caption check
    caption: str = ""  # claim mode with an image: what the user says the image shows
    article: Optional[dict] = None  # claim mode: the article the user asked to verify, if a URL was given
    intent: str = "artifact_authenticity"  # image only: synthetic_detection | artifact_authenticity
    visual: Optional[VisualAssessment] = None  # synthetic_detection: Gemini's visual examination
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


# Tool names in a container's encoder/software tag. A fact about the file, not proof of anything.
_AI_TOOLS = re.compile(r"\b(sora|runway|kling|veo|pika|luma|heygen|synthesia|elevenlabs|d-id|deepfacelab|faceswap|"
                       r"stable ?video|genmo|hailuo)\b", re.I)
_EDIT_TOOLS = re.compile(r"\b(capcut|premiere|after effects|davinci|final cut|imovie|filmora|inshot|kinemaster|"
                         r"audacity|adobe)\b", re.I)


def _encoder_signal(meta: dict) -> Signal | None:
    tag = " | ".join(str(meta[k]) for k in ("encoder", "software", "comment", "handler") if meta.get(k))
    for rx, sev, what in ((_AI_TOOLS, "medium", "a generative AI tool"), (_EDIT_TOOLS, "low", "an editing tool")):
        m = rx.search(tag)
        if m:
            return Signal(key="editing_software_exif", title="Container tag names a tool", severity=sev,
                          category="image_forensics", sources=["RULE"],
                          explanation=f"The file's metadata names {what}. Tags are easily changed or stripped, and "
                                      "ordinary editing is not manipulation.", evidence=f"\"{m.group(0)}\" in: {tag[:120]}")
    return None


_VISUAL_WORDS = re.compile(r"\b(video|footage|presenter|anchor|mouth|lips?|face|frame|on[- ]screen|visual|picture|"
                           r"camera|lighting)\b", re.I)


class TrustLensFlow(Flow[FlowState]):
    image_bytes: bytes = b""  # the uploaded file. Kept off the state: never serialised, never stored
    prepared: Optional[probe.Prepared] = None

    def _stage(self, name: str, status: str, detail: str = "") -> None:
        self.state.stages.append({"name": name, "status": status, "detail": detail})

    @start()
    def forensics(self):
        s = self.state
        if s.media_mime:
            try:
                self.prepared = pr = probe.prepare(self.image_bytes, s.media_mime)
                s.media_meta = pr.meta
                self._stage("Container metadata (ffmpeg)", "done",
                            ", ".join(f"{k}: {v}" for k, v in list(pr.meta.items())[:6]))
                sig = _encoder_signal(pr.meta)
                if sig:
                    s.exif_signals.append(sig)
                if s.media_mime.startswith("video/"):
                    if pr.frames:
                        s.sampled_frames = len(pr.frames)
                        self._stage("Frame sampling", "done",
                                    f"{len(pr.frames)} frames: uniform sampling plus {len(pr.scene_changes)} scene change(s)")
                    else:
                        self._stage("Frame sampling", "failed", "; ".join(pr.notes) or "No frames could be read")
                    self._stage("Audio extraction", "done" if pr.audio else "skipped",
                                "" if pr.audio else "The video has no usable audio track")
            except Exception as e:  # preprocessing is optional: Gemini still gets the original file
                log.warning("media preprocessing failed: %s", e)
                self._stage("Container metadata (ffmpeg)", "unavailable", str(e)[:120])
            return
        if not (s.input_type == "image" or (s.input_type == "claim" and s.image_format)):
            return
        s.exif_signals = image_forensics.exif(self.image_bytes)
        s.ela, s.ela_signal = image_forensics.ela(self.image_bytes, s.image_format)
        self._stage("Metadata (EXIF)", "done", f"{len(s.exif_signals)} finding(s)")
        self._stage("Error level analysis", "done" if s.ela.status == "ok" else "skipped",
                    "" if s.ela.status == "ok" else "Applies to JPEG only")

    @listen(forensics)
    def vision_extract(self):
        s = self.state
        if s.media_mime:
            how = (f"{s.sampled_frames} sampled frames + audio track" if s.sampled_frames else "original file")
            try:
                s.media = m = gemini_media.assess(self.image_bytes, s.media_mime, self.prepared)
                # Guard in code, not only in the prompt: an audio file has no picture and a silent video has no
                # sound, so any observation about the missing track is a model invention and is discarded.
                audio_only = s.media_mime.startswith("audio/")
                silent = bool(s.media_meta) and "audio_codec" not in s.media_meta
                kept = []
                for o in m.observations:
                    k = o.kind.strip().lower()
                    visual = k.startswith("visual") or k in ("av_sync", "ai_generation") and not k.startswith("audio")
                    if (audio_only and (visual or _VISUAL_WORDS.search(f"{o.title} {o.evidence}"))) or \
                            (silent and (k.startswith("audio") or k == "av_sync")):
                        continue
                    kept.append(o)
                dropped = len(m.observations) - len(kept)
                m.observations = kept
                if audio_only:
                    m.visual_assessment = m.av_consistency = "not_applicable"
                    m.on_screen_text = ""
                    if _VISUAL_WORDS.search(m.description):
                        m.description = ""
                if dropped:
                    self._stage("Consistency guard", "done",
                                f"{dropped} observation(s) about a track this file does not have were discarded")
                text = m.transcript + (f"\nON-SCREEN TEXT: {m.on_screen_text}" if m.on_screen_text.strip() else "")
                s.extracted = Extracted(classification=s.media_type or m.media_kind or "video",
                                        extracted_text=text, claim="; ".join(m.spoken_claims[:5]))
                s.agents_used.append("media")
                self._stage("Gemini multimodal examination", "done", how)
                self._stage("Speech transcription (Gemini)", "done" if m.transcript.strip() else "skipped",
                            m.language or ("" if m.transcript.strip() else "No speech was heard"))
                if s.input_type == "claim":
                    # what gets verified: the factual claims heard, else text shown on screen
                    s.text = " ".join(m.spoken_claims[:4]).strip() or m.on_screen_text.strip()[:600]
                    self._stage("Claim extraction", "done" if s.text else "skipped",
                                f"{len(m.spoken_claims)} spoken claim(s)" if s.text else "No checkable factual claim was found")
            except Exception as e:  # never fabricate: the report will say Gemini could not examine the file
                log.warning("media step failed: %s", e)
                s.crew_error = f"media: {e}"
                self._stage("Gemini multimodal examination", "failed", "Gemini could not examine the file")
            return
        if s.input_type == "claim" and s.image_format:
            s.caption = s.text
            try:
                recorded = (s.fixture or {}).get("news_image")
                n = (NewsImageExtract.model_validate(recorded) if recorded else
                     gemini_vision.extract_news_image(self.image_bytes, s.image_format, s.caption))
                s.news_image = n
                s.agents_used.append("vision")
                # the same call judged the image as media; _assess_image decides the state from these indicators
                s.intent = "synthetic_detection"
                s.visual = VisualAssessment(media_type="image", description=n.visual_description,
                                            visible_text=n.extracted_text, indicators=n.indicators,
                                            assessment=n.media_assessment)
                self._stage("OCR and visual examination (Gemini)", "done", n.language)
                self._stage("Claim extraction", "done" if (n.claim_in_image or s.caption) else "skipped",
                            "" if (n.claim_in_image or s.caption) else "The image makes no checkable factual claim")
                # what gets verified: the user's caption if given, else the claim the image itself makes
                parts = [s.caption, n.claim_in_image if n.claim_in_image.lower() not in s.caption.lower() else ""]
                s.text = " ".join(p for p in parts if p).strip() or n.extracted_text[:1500]
            except Exception as e:
                log.warning("news image step failed: %s", e)
                self._stage("OCR and visual examination (Gemini)", "failed", "Gemini could not read the image")
                if not s.caption:
                    s.crew_error = f"vision: {e}"
            return
        if s.input_type == "text" and s.mode == "ai_generated":
            s.extracted = Extracted(classification="text", extracted_text=s.text)
            try:
                s.visual = gemini_text.assess(s.text)
                s.agents_used.append("text_examiner")
                self._stage("Gemini examination of the writing", "done", f"{len(s.text.split())} words")
            except Exception as e:
                log.warning("text step failed: %s", e)
                s.crew_error = f"text: {e}"
                self._stage("Gemini examination of the writing", "failed", "Gemini could not examine the text")
            return
        if s.input_type != "image":
            return
        if s.fixture is not None:
            if s.intent == "synthetic_detection":  # recorded Gemini visual examination
                s.visual = VisualAssessment.model_validate(s.fixture.get("visual") or {})
                s.extracted = Extracted(classification=s.visual.media_type or "other", extracted_text=s.visual.visible_text)
                self._stage("Gemini visual examination", "done", "recorded result (demo)")
            else:
                s.extracted = Extracted.model_validate(s.fixture.get("extracted") or {})
            s.agents_used.append("vision")
            return
        try:
            if s.intent == "synthetic_detection":
                s.visual = gemini_vision.assess_synthetic(self.image_bytes, s.image_format)
                s.extracted = Extracted(classification=s.visual.media_type or "other",
                                        extracted_text=s.visual.visible_text)
            else:
                s.extracted = gemini_vision.extract(self.image_bytes, s.image_format, s.intent)
            s.agents_used.append("vision")
            self._stage("Gemini visual examination", "done")
        except Exception as e:  # continue with an empty extraction; never fabricate
            log.warning("vision step failed: %s", e)
            s.crew_error = f"vision: {e}"
            self._stage("Gemini visual examination", "failed", "Gemini could not examine the image")

    @listen(vision_extract)
    def rules(self):
        s = self.state
        if s.mode == "ai_generated" or (s.input_type == "image" and s.intent == "synthetic_detection"):
            return  # the question is about the media itself: message/URL rules do not apply
        text = (content_text(s.extracted.extracted_text) if s.input_type == "image"
                else s.extracted.extracted_text if s.media_mime
                else s.news_image.extracted_text if s.news_image else s.text)
        result = text_rules.run(text)
        if s.mode:
            self._stage("Deterministic content rules", "done", f"{len(result.signals)} finding(s) in the extracted text")
        s.rule_signals = text_rules.soften_for_document(result.signals) if s.input_type == "image" else result.signals
        s.all_urls_match_claimed = result.domain.all_urls_match_claimed

    @listen(rules)
    def analyze(self):
        s = self.state
        findings = text_rules.summarize(s.exif_signals + ([s.ela_signal] if s.ela_signal else []) + s.rule_signals)
        if s.fixture is not None:
            if not (s.input_type == "image" and s.intent == "synthetic_detection"):
                self._from_fixture()
                if s.input_type == "claim" and s.mode:
                    self._stage("Evidence retrieval and claim verification", "done",
                                f"{len(s.tool_urls)} source link(s); recorded result (demo)")
            return
        if s.crew_error or (s.input_type == "claim" and not s.text.strip()):
            if s.input_type == "claim" and s.mode:
                self._stage("Evidence retrieval and claim verification", "skipped",
                            "Gemini could not read the file" if s.crew_error else "No checkable claim was extracted")
            return  # vision already failed, or the file carries no claim: nothing to verify
        if s.input_type == "media" or (s.input_type == "image" and s.intent == "synthetic_detection") or (
                s.input_type == "text" and s.mode == "ai_generated"):
            return  # judged by the multimodal Gemini step; a text-only agent cannot see or hear the file
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
                if s.mode:
                    self._stage("Evidence retrieval and claim verification", "done",
                                f"{len(s.tool_urls)} source link(s) returned by search tools"
                                + ("; a search tool failed" if s.tool_errors else ""))
        except Exception as e:
            log.warning("crew step failed: %s", e)
            s.crew_error = f"crew: {e}"
            if s.input_type == "claim" and s.mode:
                self._stage("Evidence retrieval and claim verification", "failed", "The verification step failed")

    def _from_fixture(self):
        s, fx = self.state, self.state.fixture or {}
        if s.input_type == "claim":
            s.claim_evidence = ClaimEvidence.model_validate(fx.get("claim_evidence") or {})
            s.tool_urls = fx.get("tool_urls") or {}
            s.tool_errors = fx.get("tool_errors") or []
            s.agents_used.append("claim_verifier")
            return
        if s.input_type == "text":
            s.extracted = Extracted.model_validate(fx.get("extracted") or {})
            s.agents_used.append("extractor")
        s.llm_signals = SignalSet.model_validate(fx.get("signal_set") or {})
        s.agents_used.append("analyst")


def run_sync(input_type: str, text: str = "", image_bytes: bytes = b"", image_format: str = "",
             fixture: dict | None = None, intent: str = "artifact_authenticity", media_mime: str = "",
             article: dict | None = None, mode: str = "", media_type: str = "") -> FlowState:
    flow = TrustLensFlow()
    flow.image_bytes = image_bytes
    inputs = {"input_type": input_type, "text": text, "image_format": image_format, "intent": intent,
              "media_mime": media_mime, "mode": mode, "media_type": media_type}
    if article is not None:
        inputs["article"] = article
    if fixture is not None:
        inputs |= {"fixture": fixture, "analysis_mode": "demo_cached"}
    flow.kickoff(inputs=inputs)
    return flow.state


async def run(input_type: str, text: str = "", image_bytes: bytes = b"", image_format: str = "",
              fixture: dict | None = None, intent: str = "artifact_authenticity", media_mime: str = "",
              article: dict | None = None, mode: str = "", media_type: str = "",
              timeout: int | None = None) -> FlowState:
    """Run the Flow in a worker thread under the global timeout. On timeout the deterministic
    steps are re-run alone so a rule + forensics report is still returned."""
    loop = asyncio.get_running_loop()
    limit = timeout or settings.FLOW_TIMEOUT_S
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, run_sync, input_type, text, image_bytes, image_format, fixture, intent,
                                 media_mime, article, mode, media_type),
            limit,
        )
    except asyncio.TimeoutError:
        log.warning("flow timed out after %ss", limit)
        return deterministic_only(input_type, text, image_bytes, image_format, "timeout", intent,
                                  mode=mode, media_type=media_type, media_mime=media_mime)


def deterministic_only(input_type: str, text: str, image_bytes: bytes, image_format: str, reason: str,
                       intent: str = "artifact_authenticity", mode: str = "", media_type: str = "",
                       media_mime: str = "") -> FlowState:
    s = FlowState(input_type=input_type, text=text, image_format=image_format, crew_error=reason, intent=intent,
                  mode=mode, media_type=media_type, media_mime=media_mime)
    if mode:
        s.stages.append({"name": "Analysis", "status": "failed", "detail": "Timed out; only deterministic checks are shown"})
    if media_mime:
        return s
    if image_format:
        s.exif_signals = image_forensics.exif(image_bytes)
        s.ela, s.ela_signal = image_forensics.ela(image_bytes, image_format)
    else:
        result = text_rules.run(text)
        s.rule_signals, s.all_urls_match_claimed = result.signals, result.domain.all_urls_match_claimed
    return s
