"""Specialist-model self-test: loads every model and runs it on a bundled real input.
Nothing is reported as working unless inference actually succeeded in this process."""
import time

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.config import DEMO_DIR
from app.ml import models as _models  # noqa: F401  (registers the loaders; loads no weights)
from app.ml import registry
from app.services import specialists
from app.services.media import probe

router = APIRouter()
_last: dict | None = None
CLAIM = "UNESCO declared India's national anthem the best in the world."
HEADLINES = ["UNESCO did not declare India's national anthem the best in the world",
             "UNESCO names Jana Gana Mana the world's best national anthem",
             "Heavy rain expected in coastal Karnataka this weekend"]


def _selftest() -> dict:
    from app.ml import models
    runs: dict[str, dict] = {}
    out: dict = {}
    t0 = time.time()
    image = (DEMO_DIR / "demo_viral_post.jpg").read_bytes()
    specialists.image(runs, out, image, want_ocr=True)
    try:
        prepared = probe.prepare((DEMO_DIR / "selftest_speech.mp3").read_bytes(), "audio/mpeg")
        specialists.media(runs, out, prepared, is_video=False)
    except Exception as e:
        runs["asr"] = runs["audio_spoof"] = {"status": "FAILED", "detail": f"Audio could not be decoded: {str(e)[:80]}"}
    sims = specialists._run(runs, "embedding", lambda: models.similarity(CLAIM, HEADLINES),
                            lambda r: "cosine to the claim: " + ", ".join(f"{x:.2f}" for x in r))
    nli = specialists._run(runs, "nli", lambda: [models.entailment(h, CLAIM) for h in HEADLINES],
                           lambda r: "labels: " + ", ".join(f"{x['label']} {x[x['label']]:.2f}" for x in r))
    return {
        "seconds": round(time.time() - t0, 1),
        "memory": registry.memory(), "threads": registry.threads(),
        "inputs": {"image": "demo_viral_post.jpg", "audio": "selftest_speech.mp3 (a text-to-speech voice)",
                   "claim": CLAIM, "headlines": HEADLINES},
        "models": {slot: {"model": registry.BY_SLOT[slot].model, **run} for slot, run in runs.items()},
        "outputs": {"image_p_generated": out.get("p_generated"), "ocr_text": (out.get("ocr_text") or "")[:300],
                    "speech_p_synthetic": out.get("p_synthetic"), "speech_windows": out.get("speech_windows"),
                    "transcript": out.get("asr_text"), "transcript_language": out.get("asr_language"),
                    "headline_similarity": sims, "headline_nli": nli},
        "working": sorted(s for s, r in runs.items() if r["status"] == "RAN"),
        "not_working": sorted(s for s, r in runs.items() if r["status"] != "RAN"),
    }


@router.get("/models/selftest")
async def selftest(fresh: bool = False):
    global _last
    if _last is None or fresh:
        _last = await run_in_threadpool(_selftest)
    return _last


@router.get("/models")
def models_status():
    """What is installed, without loading anything."""
    return [{"slot": s.slot, "task": s.task, "model": s.model, "available": not registry.why_unavailable(s.slot),
             "reason": registry.why_unavailable(s.slot), "limitations": list(s.limits)} for s in registry.SPECS]
