"""Demo chips: forensics and rules run live; vision + crew outputs come from recorded fixtures."""
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import DEMO_DIR
from app.models.report import TrustReport
from app.services import flow, reporter

router = APIRouter()

# Media-only demos, one list per mode. `fixture` holds the recorded Gemini output for that mode.
DEMOS = [
    {"id": "genuine_notice", "label": "Genuine notice", "input_type": "image", "mode": "ai_generated",
     "file": "demo_notice_genuine.jpg", "fixture": "genuine_notice.ai.json"},
    {"id": "edited_notice", "label": "Edited notice", "input_type": "image", "mode": "ai_generated",
     "file": "demo_notice_edited.jpg", "fixture": "edited_notice.ai.json"},
    {"id": "viral_post", "label": "Viral post", "input_type": "image", "mode": "news_claim",
     "file": "demo_viral_post.jpg", "fixture": "viral_post.news.json"},
]
_BY_ID = {d["id"]: d for d in DEMOS}


def get_demo(demo_id: str) -> dict:
    demo = _BY_ID.get(demo_id)
    if demo is None or not (DEMO_DIR / demo["file"]).exists():
        raise HTTPException(404, "Unknown demo.")
    return demo


def load_fixture(demo: dict) -> dict | None:
    path = DEMO_DIR / demo["fixture"]
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@router.get("/demos")
def list_demos():
    return [{"id": d["id"], "label": d["label"], "input_type": d["input_type"], "mode": d["mode"], "text": None,
             "image_url": f"/api/demos/{d['id']}/image", "cached": (DEMO_DIR / d["fixture"]).exists()}
            for d in DEMOS if (DEMO_DIR / d["file"]).exists()]


@router.get("/demos/{demo_id}/image")
def demo_image(demo_id: str):
    demo = get_demo(demo_id)
    return FileResponse(DEMO_DIR / demo["file"], media_type="image/jpeg")


@router.post("/analyze/demo/{demo_id}", response_model=TrustReport)
async def analyze_demo(demo_id: str):
    demo = get_demo(demo_id)
    data = (DEMO_DIR / demo["file"]).read_bytes()
    fixture = load_fixture(demo)  # no fixture recorded yet → falls back to a live run
    if demo["mode"] == "ai_generated":
        state = await flow.run("image", image_bytes=data, image_format="JPEG", intent="synthetic_detection",
                               fixture=fixture, mode="ai_generated", media_type="image")
    else:
        state = await flow.run("claim", image_bytes=data, image_format="JPEG", fixture=fixture, mode="news_claim",
                               media_type="image", timeout=120)
    return reporter.build(state)
