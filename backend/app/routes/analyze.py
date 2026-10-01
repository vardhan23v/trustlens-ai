from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.models.report import TrustReport
from app.services import flow, image_forensics, reporter, result_cache

router = APIRouter()
ALLOWED = {"JPEG", "PNG", "WEBP"}
MAX_TEXT_CHARS = 8000


class TextIn(BaseModel):
    text: str


def _clean(text: str) -> str:
    text = text.strip()
    if not text:
        raise HTTPException(422, "Paste some text to analyse.")
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(413, f"Text is too long (max {MAX_TEXT_CHARS} characters).")
    return text


@router.post("/analyze/image", response_model=TrustReport)
async def analyze_image(
    file: UploadFile = File(...),
    # What the user wants verified. (The report's own `analysis_mode` field means live vs cached demo,
    # so the report echoes this back as `analysis_intent`.)
    analysis_mode: Literal["synthetic_detection", "artifact_authenticity"] = Form("artifact_authenticity"),
):
    data = await file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)  # in memory only, never written to disk
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"Image is larger than {settings.MAX_UPLOAD_MB} MB.")
    fmt = image_forensics.sniff_format(data)
    if fmt not in ALLOWED:
        raise HTTPException(415, "Unsupported file. Upload a JPG, PNG or WebP image.")
    k = result_cache.key("image", data, analysis_mode)
    cached = result_cache.get(k)
    if cached:
        return cached  # identical file + mode: identical report
    report = reporter.build(await flow.run("image", image_bytes=data, image_format=fmt, intent=analysis_mode))
    result_cache.put(k, report)
    return report


@router.post("/analyze/text", response_model=TrustReport)
async def analyze_text(body: TextIn):
    text = _clean(body.text)
    k = result_cache.key("text", text.encode())
    cached = result_cache.get(k)
    if cached:
        return cached
    report = reporter.build(await flow.run("text", text=text))
    result_cache.put(k, report)
    return report


@router.post("/analyze/claim", response_model=TrustReport)
async def analyze_claim(body: TextIn):
    state = await flow.run("claim", text=_clean(body.text))
    return reporter.build(state)
