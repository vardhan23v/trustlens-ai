"""Two-mode API (NEWS / CLAIM, AI-GENERATED) across image, video and audio. Gemini and the search
crew are mocked, so this checks routing, separation of dimensions and failure handling — not accuracy.

    python tests/test_modes.py
"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import DEMO_DIR  # noqa: E402
from app.main import app  # noqa: E402
from app.models.llm_outputs import (ClaimEvidence, EvidenceItem, MediaAssessment, MediaObservation,  # noqa: E402
                                    NewsImageExtract, SubClaim, VisualAssessment, VisualIndicator)
from app.services import result_cache  # noqa: E402
from app.services.crew.tools import ToolLedger  # noqa: E402
from app.services.gemini_vision import GeminiUnavailable  # noqa: E402

c = TestClient(app)
MEDIA = Path(__file__).parent / "media"
IMG = (DEMO_DIR / "demo_notice_genuine.jpg").read_bytes()
VID, AUD = (MEDIA / "claim.mp4").read_bytes(), (MEDIA / "claim.mp3").read_bytes()
CLAIM = "UNESCO declared the Indian national anthem the best in the world."


def post(mode, data, name):
    result_cache._items.clear()
    return c.post("/api/analyze", data={"mode": mode}, files={"file": (name, data)})


def axis(r, heading):
    return next(a for a in r["assessment_axes"] if a["heading"] == heading)


def crew(items, errors=()):
    """items: (url, site, stance, title). Returns a fake run_claim_crew."""
    def run(text):
        led = ToolLedger()
        for url, site, _, title in items:
            led.add(url, origin="news", source=site, title=title, published="2026-09-20", site=site)
        led.errors = list(errors)
        return ClaimEvidence(claim=text, sub_claims=[SubClaim(text=text)], evidence=[
            EvidenceItem(source=site, url=url, stance=stance, quote=title) for url, site, stance, title in items]), led
    return run


NEWS_IMG = NewsImageExtract(extracted_text=CLAIM, claim_in_image=CLAIM, visual_description="A social media post.",
                            media_assessment="likely_authentic")
CLEAN_MEDIA = MediaAssessment(media_kind="video", has_speech=True, transcript=CLAIM, language="English",
                              spoken_claims=[CLAIM], visual_assessment="likely_authentic",
                              audio_assessment="likely_authentic", av_consistency="inconclusive")
REFUTE = [("https://www.reuters.com/a", "reuters.com", "refutes", "UNESCO made no such declaration"),
          ("https://www.thehindu.com/b", "thehindu.com", "refutes", "Anthem claim is a hoax")]
P = "app.services.flow."
checks = []


def check(name, cond):
    checks.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


# ---------- AI-GENERATED ----------
with mock.patch(P + "gemini_vision.assess_synthetic", return_value=VisualAssessment(
        media_type="document", assessment="likely_authentic", authentic_cues=["consistent paper texture"])):
    r = post("ai_generated", IMG, "a.jpg").json()
check("ai image: mode, type, single synthetic axis",
      r["mode"] == "ai_generated" and r["media_type"] == "image" and len(r["assessment_axes"]) == 1
      and r["assessment_axes"][0]["state"] == "LIKELY_AUTHENTIC" and r["artifact_assessment"] is None)
check("ai image: no text-rule signals, low confidence without a detector",
      not [s for s in r["signals"] if s["category"] in ("message_content", "url_domain")]
      and r["assessment_axes"][0]["confidence"] == "low")
check("ai image: detector reported MODEL_UNAVAILABLE, change factors given",
      any(m["slot"] == "image_synthetic" and m["status"] == "MODEL_UNAVAILABLE" for m in r["specialist_models"])
      and len(r["change_factors"]) >= 2 and r["evidence_signals"])

with mock.patch(P + "gemini_vision.assess_synthetic", return_value=VisualAssessment(
        assessment="likely_synthetic", indicators=[
            VisualIndicator(kind="ai_generation", title="Melted lettering", severity="high", evidence="top-left sign"),
            VisualIndicator(kind="ai_generation", title="Six fingers", severity="medium", evidence="right hand")])):
    r = post("ai_generated", IMG, "a.jpg").json()
check("ai image: synthetic indicators -> LIKELY_SYNTHETIC", r["overall_assessment"]["state"] == "LIKELY_SYNTHETIC")

seen = {}


def fake_media(data, mime, prepared=None):
    seen["frames"] = len(prepared.frames) if prepared else 0
    seen["audio"] = bool(prepared and prepared.audio)
    return CLEAN_MEDIA


with mock.patch(P + "gemini_media.assess", side_effect=fake_media):
    r = post("ai_generated", VID, "v.mp4").json()
names = {s["name"]: s["status"] for s in r["stages"]}
check("ai video: sampled frames + audio sent, not the whole file", 2 <= seen["frames"] <= 12 and seen["audio"])
check("ai video: stages recorded honestly",
      names.get("Frame sampling") == "done" and names.get("Container metadata (ffmpeg)") == "done"
      and r["media_metadata"].get("video_codec") == "h264")
check("ai video: spoken claim NOT verified in this mode, no claim search",
      axis(r, "Spoken claims")["state"] == "NOT_ASSESSED" and r["verdict"] is None and not r["evidence"])

with mock.patch(P + "gemini_media.assess", return_value=MediaAssessment(
        media_kind="audio_synthesis", has_speech=True, transcript=CLAIM, audio_assessment="likely_synthetic",
        observations=[MediaObservation(timestamp="00:02", kind="audio_synthesis", title="Flat prosody", severity="high",
                                       evidence="monotone delivery with no breaths")])):
    r = post("ai_generated", AUD, "a.mp3").json()
check("ai audio: LIKELY_SYNTHETIC, visual axis not applicable",
      r["media_type"] == "audio" and axis(r, "Audio authenticity")["state"] == "LIKELY_SYNTHETIC"
      and axis(r, "Visual authenticity")["state"] == "NOT_ASSESSED")

hallucinated = MediaAssessment(media_kind="video", has_speech=True, transcript=CLAIM, description="A news anchor on video.",
                               visual_assessment="likely_synthetic", audio_assessment="likely_authentic", observations=[
    MediaObservation(timestamp="00:00", kind="visual_ai_generation", title="AI presenter", severity="high",
                     evidence="the presenter's mouth is out of sync")])
with mock.patch(P + "gemini_media.assess", return_value=hallucinated):
    r = post("ai_generated", AUD, "a.mp3").json()
check("audio-only: invented visual observations are discarded in code",
      not r["signals"] and axis(r, "Visual authenticity")["state"] == "NOT_ASSESSED"
      and not any("anchor" in n for n in r["notes"]))

# ---------- NEWS / CLAIM ----------
with mock.patch(P + "gemini_vision.extract_news_image", return_value=NEWS_IMG), \
        mock.patch(P + "crews.run_claim_crew", side_effect=crew(REFUTE)):
    r = post("news_claim", IMG, "n.jpg").json()
check("news image: authentic media + contradicted claim stay separate",
      axis(r, "Claim assessment")["state"] == "CONTRADICTED" and axis(r, "Media authenticity")["state"] == "LIKELY_AUTHENTIC"
      and axis(r, "Context consistency")["state"] == "MISLEADING_CONTEXT"
      and r["overall_assessment"]["state"] == "MISLEADING_CONTEXT")
check("news image: claim confidence from independent sources", axis(r, "Claim assessment")["confidence"] == "medium")

copies = [(f"https://www.thehindu.com/x{i}", "thehindu.com", "supports", "Anthem named best") for i in range(5)]
with mock.patch(P + "gemini_vision.extract_news_image", return_value=NEWS_IMG), \
        mock.patch(P + "crews.run_claim_crew", side_effect=crew(copies)):
    r = post("news_claim", IMG, "n.jpg").json()
check("news: five copies from one site are one source -> not SUPPORTED",
      axis(r, "Claim assessment")["state"] == "UNVERIFIED" and r["verdict"] == "UNVERIFIED")

support = [("https://www.reuters.com/s", "reuters.com", "supports", "UNESCO confirms"),
           ("https://www.bbc.com/s", "bbc.com", "supports", "Anthem honoured")]
with mock.patch(P + "gemini_vision.extract_news_image", return_value=NEWS_IMG), \
        mock.patch(P + "crews.run_claim_crew", side_effect=crew(support)):
    r = post("news_claim", IMG, "n.jpg").json()
check("news: two independent listed sources -> SUPPORTED", axis(r, "Claim assessment")["state"] == "SUPPORTED")

with mock.patch(P + "gemini_vision.extract_news_image", return_value=NEWS_IMG), \
        mock.patch(P + "crews.run_claim_crew", side_effect=crew(REFUTE + support)):
    r = post("news_claim", IMG, "n.jpg").json()
dirs = {e["direction"] for e in r["evidence_signals"] if e["source_type"] == "EXTERNAL_SOURCE"}
check("news: conflicting sources -> INCONCLUSIVE, both sides kept",
      axis(r, "Claim assessment")["state"] == "INCONCLUSIVE" and dirs == {"SUPPORTS", "CONTRADICTS"})

with mock.patch(P + "gemini_vision.extract_news_image", return_value=NEWS_IMG), \
        mock.patch(P + "crews.run_claim_crew", side_effect=crew([], errors=["news: timeout"])):
    r = post("news_claim", IMG, "n.jpg").json()
check("news: search failure -> EVIDENCE_UNAVAILABLE, never false",
      axis(r, "Claim assessment")["state"] == "EVIDENCE_UNAVAILABLE" and r["verdict"] == "UNVERIFIED"
      and not any(s["key"] == "debunked_by_source" for s in r["signals"]))

with mock.patch(P + "gemini_vision.extract_news_image", return_value=NewsImageExtract(visual_description="A beach.")), \
        mock.patch(P + "crews.run_claim_crew", side_effect=AssertionError("must not search without a claim")):
    r = post("news_claim", IMG, "n.jpg").json()
check("news: no claim in the image -> NOT_ASSESSED, no search", axis(r, "Claim assessment")["state"] == "NOT_ASSESSED")

with mock.patch(P + "gemini_media.assess", return_value=CLEAN_MEDIA), \
        mock.patch(P + "crews.run_claim_crew", side_effect=crew(REFUTE)):
    r = post("news_claim", VID, "v.mp4").json()
check("news video: genuine recording + false spoken claim",
      axis(r, "Claim assessment")["state"] == "CONTRADICTED" and axis(r, "Visual authenticity")["state"] == "LIKELY_AUTHENTIC"
      and axis(r, "Context consistency")["state"] == "MISLEADING_CONTEXT" and CLAIM in r["extracted"]["extracted_text"])

synthetic_voice = CLEAN_MEDIA.model_copy(update={"media_kind": "audio", "audio_assessment": "likely_synthetic",
                                                  "observations": [MediaObservation(
                                                      timestamp="00:01", kind="audio_synthesis", title="Synthetic timbre",
                                                      severity="high", evidence="metallic artefacts on sibilants")]})
with mock.patch(P + "gemini_media.assess", return_value=synthetic_voice), \
        mock.patch(P + "crews.run_claim_crew", side_effect=crew(support)):
    r = post("news_claim", AUD, "a.mp3").json()
check("news audio: synthetic voice + supported claim are both reported",
      axis(r, "Claim assessment")["state"] == "SUPPORTED" and axis(r, "Audio authenticity")["state"] == "LIKELY_SYNTHETIC")

with mock.patch(P + "gemini_media.assess", return_value=CLEAN_MEDIA), \
        mock.patch(P + "crews.run_claim_crew", side_effect=RuntimeError("503")):
    r = post("news_claim", VID, "v.mp4").json()
check("news video: search crash keeps the media examination",
      axis(r, "Claim assessment")["state"] == "EVIDENCE_UNAVAILABLE"
      and axis(r, "Visual authenticity")["state"] == "LIKELY_AUTHENTIC" and r["gemini_error"])

# ---------- text input ----------
def post_text(mode, text):
    result_cache._items.clear()
    return c.post("/api/analyze", data={"mode": mode, "text": text})


ESSAY = ("In today's fast-paced world, it is important to note that technology plays a pivotal role. " * 3
         + "Moreover, it is worth mentioning that there are several key factors to consider. " * 3)
ai_text = VisualAssessment(media_type="text", assessment="likely_synthetic", indicators=[
    VisualIndicator(kind="ai_generation", title="Stock transitions", severity="medium", evidence="it is important to note that"),
    VisualIndicator(kind="ai_generation", title="Generic statements", severity="medium", evidence="several key factors to consider"),
    VisualIndicator(kind="ai_generation", title="Invented quote", severity="high", evidence="this phrase is not in the text")])
with mock.patch(P + "gemini_text.assess", return_value=ai_text), \
        mock.patch(P + "crews.run_claim_crew", side_effect=AssertionError("no claim search in AI mode")):
    r = post_text("ai_generated", ESSAY).json()
check("ai text: quoted indicators -> LIKELY_SYNTHETIC, low confidence, no claim search",
      r["media_type"] == "text" and r["overall_assessment"]["state"] == "LIKELY_SYNTHETIC"
      and r["assessment_axes"][0]["confidence"] == "low" and r["verdict"] is None)
with mock.patch(P + "gemini_text.assess", return_value=ai_text):
    r = post_text("ai_generated", "Too short to judge.").json()
check("ai text: short text is INCONCLUSIVE whatever the model says", r["overall_assessment"]["state"] == "INCONCLUSIVE")
with mock.patch(P + "crews.run_claim_crew", side_effect=crew(REFUTE)):
    r = post_text("news_claim", CLAIM).json()
check("news text: claim checked, no media axes",
      axis(r, "Claim assessment")["state"] == "CONTRADICTED" and len(r["assessment_axes"]) == 1 and r["media_type"] == "text")
check("neither file nor text -> 422", c.post("/api/analyze", data={"mode": "news_claim"}).status_code == 422)
check("text too long -> 413", post_text("news_claim", "x" * 8001).status_code == 413)

# ---------- failures ----------
with mock.patch(P + "gemini_media.assess", side_effect=GeminiUnavailable("429 quota")):
    r = post("ai_generated", VID, "v.mp4").json()
check("gemini failure: no invented findings, metadata still reported",
      r["gemini_error"] and not [s for s in r["signals"] if "GEMINI" in s["sources"]]
      and r["overall_assessment"]["state"] == "INCONCLUSIVE" and r["media_metadata"])
with mock.patch(P + "gemini_vision.extract_news_image", side_effect=GeminiUnavailable("429 quota")):
    r = post("news_claim", IMG, "n.jpg").json()
check("gemini failure in news mode: claim not judged", axis(r, "Claim assessment")["state"] == "INCONCLUSIVE")
check("wrong file type -> 415", post("ai_generated", b"%PDF-1.4 not media at all......", "x.pdf").status_code == 415)
check("missing / bad mode -> 422", c.post("/api/analyze", data={"mode": "text"}, files={"file": ("a.jpg", IMG)}).status_code == 422)
check("text endpoints are gone", c.post("/api/analyze/text", json={"text": "hi"}).status_code in (404, 405)
      and c.post("/api/analyze/claim", json={"text": "hi"}).status_code in (404, 405))

with mock.patch(P + "gemini_media.assess", return_value=CLEAN_MEDIA), \
        mock.patch(P + "crews.run_claim_crew", side_effect=crew(REFUTE)):
    rep = post("news_claim", VID, "v.mp4").json()
with mock.patch("app.services.report_writer.settings.OPENROUTER_API_KEY", ""):
    pdf = c.post("/api/report/pdf", json={"report": rep})
check("PDF builds from a two-mode report", pdf.status_code == 200 and pdf.content[:5] == b"%PDF-")

bad = [n for n, ok in checks if not ok]
print(f"\n{len(checks) - len(bad)}/{len(checks)} passed")
sys.exit(1 if bad else 0)
