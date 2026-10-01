"""The one analysis endpoint: a mode plus a media file or pasted text."""
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.models.report import TrustReport
from app.routes.media import MAX_MEDIA_MB, sniff_media
from fastapi.concurrency import run_in_threadpool

from app.services import flow, image_forensics, reporter, result_cache, store

router = APIRouter()
IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
UNSUPPORTED = ("Unsupported file. Upload an image (JPG, PNG, WebP), a video (MP4, MOV, WebM) or audio "
               "(MP3, WAV, M4A, OGG).")


MAX_TEXT_CHARS = 8000


async def _finish(k: str, state) -> TrustReport:
    report = reporter.build(state)
    report.report_id = store.new_id()
    result_cache.put(k, report)
    await run_in_threadpool(store.save, k, report)
    return report


async def _cached(k: str) -> TrustReport | None:
    cached = result_cache.get(k)
    if cached is None:
        cached = await run_in_threadpool(store.by_key, k)  # survives restarts when a database is configured
        if cached:
            result_cache.put(k, cached)
    return cached


async def _analyze_text(mode: str, text: str) -> TrustReport:
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(413, f"Text is too long (max {MAX_TEXT_CHARS} characters).")
    k = result_cache.key("analyze", text.encode(), f"{mode}:text")
    cached = await _cached(k)
    if cached:
        return cached
    if mode == "ai_generated":
        state = await flow.run("text", text=text, mode=mode, media_type="text")
    else:
        state = await flow.run("claim", text=text, mode=mode, media_type="text", timeout=120)
    return await _finish(k, state)


@router.post("/analyze", response_model=TrustReport)
async def analyze(
    mode: Literal["news_claim", "ai_generated"] = Form(...),
    file: UploadFile | None = File(None),
    text: str = Form(""),
):
    """NEWS / CLAIM: extract the claim, check it against sources, and assess the media and its context
    separately. AI-GENERATED: assess whether the media (or text) itself is synthetic or manipulated.
    Send either a file (image, video, audio) or text."""
    text = text.strip()
    if file is None or not file.filename:
        if not text:
            raise HTTPException(422, "Upload a file or paste some text to analyse.")
        return await _analyze_text(mode, text)
    limit = max(settings.MAX_UPLOAD_MB, MAX_MEDIA_MB) * 1024 * 1024
    data = await file.read(limit + 1)
    # The type comes from the file's own bytes; the name and browser-supplied type are not trusted.
    fmt = image_forensics.sniff_format(data)
    mime = None if fmt in IMAGE_FORMATS else sniff_media(data)
    if fmt not in IMAGE_FORMATS and mime is None:
        raise HTTPException(415, UNSUPPORTED)
    is_image = fmt in IMAGE_FORMATS
    cap = settings.MAX_UPLOAD_MB if is_image else MAX_MEDIA_MB
    if len(data) > cap * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {cap} MB." + ("" if is_image else " Trim the clip and try again."))
    media_type = "image" if is_image else mime.split("/")[0]

    k = result_cache.key("analyze", data, f"{mode}:{media_type}")
    cached = await _cached(k)
    if cached:
        return cached  # identical file + mode: identical report
    if is_image and mode == "ai_generated":
        state = await flow.run("image", image_bytes=data, image_format=fmt, intent="synthetic_detection",
                               mode=mode, media_type=media_type)
    elif is_image:
        state = await flow.run("claim", image_bytes=data, image_format=fmt, mode=mode, media_type=media_type,
                               timeout=120)
    elif mode == "ai_generated":
        state = await flow.run("media", image_bytes=data, media_mime=mime, mode=mode, media_type=media_type,
                               timeout=120)
    else:
        state = await flow.run("claim", image_bytes=data, media_mime=mime, mode=mode, media_type=media_type,
                               timeout=170)
    return await _finish(k, state)


@router.get("/reports/{report_id}", response_model=TrustReport)
async def get_report(report_id: str):
    """Reopen a stored report by its id. There is deliberately no endpoint that lists reports."""
    if not store.enabled():
        raise HTTPException(404, "Stored reports are not available on this deployment.")
    report = await run_in_threadpool(store.by_id, report_id.strip().upper()[:32])
    if report is None:
        raise HTTPException(404, "No report with that id.")
    return report
