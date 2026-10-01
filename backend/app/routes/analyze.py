from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.models.report import TrustReport
from app.services import flow, image_forensics, reporter

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
async def analyze_image(file: UploadFile = File(...)):
    data = await file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)  # in memory only, never written to disk
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"Image is larger than {settings.MAX_UPLOAD_MB} MB.")
    fmt = image_forensics.sniff_format(data)
    if fmt not in ALLOWED:
        raise HTTPException(415, "Unsupported file. Upload a JPG, PNG or WebP image.")
    state = await flow.run("image", image_bytes=data, image_format=fmt)
    return reporter.build(state)


@router.post("/analyze/text", response_model=TrustReport)
async def analyze_text(body: TextIn):
    state = await flow.run("text", text=_clean(body.text))
    return reporter.build(state)


@router.post("/analyze/claim", response_model=TrustReport)
async def analyze_claim(body: TextIn):
    state = await flow.run("claim", text=_clean(body.text))
    return reporter.build(state)
