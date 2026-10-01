"""Demo chips: forensics and rules run live; vision + crew outputs come from recorded fixtures."""
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import DEMO_DIR
from app.models.report import TrustReport
from app.services import flow, reporter

router = APIRouter()

DEMOS = [
    {"id": "genuine_notice", "label": "Genuine notice", "input_type": "image", "file": "demo_notice_genuine.jpg"},
    {"id": "edited_notice", "label": "Edited notice", "input_type": "image", "file": "demo_notice_edited.jpg"},
    {"id": "scam_sms", "label": "Scam SMS", "input_type": "text", "file": "demo_scam_sms.txt"},
    {"id": "viral_claim", "label": "Viral claim", "input_type": "claim", "file": "demo_claim.txt"},
    {"id": "injection", "label": "Injection", "input_type": "text", "file": "demo_injection.txt"},
]
_BY_ID = {d["id"]: d for d in DEMOS}


def get_demo(demo_id: str) -> dict:
    demo = _BY_ID.get(demo_id)
    if demo is None or not (DEMO_DIR / demo["file"]).exists():
        raise HTTPException(404, "Unknown demo.")
    return demo


def load_fixture(demo_id: str) -> dict | None:
    path = DEMO_DIR / f"{demo_id}.crew.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@router.get("/demos")
def list_demos():
    out = []
    for d in DEMOS:
        path = DEMO_DIR / d["file"]
        if not path.exists():
            continue
        is_image = d["input_type"] == "image"
        out.append({
            "id": d["id"], "label": d["label"], "input_type": d["input_type"],
            "text": None if is_image else path.read_text(encoding="utf-8").strip(),
            "image_url": f"/api/demos/{d['id']}/image" if is_image else None,
            "cached": (DEMO_DIR / f"{d['id']}.crew.json").exists(),
        })
    return out


@router.get("/demos/{demo_id}/image")
def demo_image(demo_id: str):
    demo = get_demo(demo_id)
    if demo["input_type"] != "image":
        raise HTTPException(404, "Not an image demo.")
    return FileResponse(DEMO_DIR / demo["file"], media_type="image/jpeg")


@router.post("/analyze/demo/{demo_id}", response_model=TrustReport)
async def analyze_demo(demo_id: str):
    demo = get_demo(demo_id)
    path = DEMO_DIR / demo["file"]
    fixture = load_fixture(demo_id)  # no fixture recorded yet → falls back to a live run
    if demo["input_type"] == "image":
        state = await flow.run("image", image_bytes=path.read_bytes(), image_format="JPEG", fixture=fixture)
    else:
        state = await flow.run(demo["input_type"], text=path.read_text(encoding="utf-8").strip(), fixture=fixture)
    return reporter.build(state)
