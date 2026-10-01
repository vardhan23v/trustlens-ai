from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.config import settings
from app.models.report import TrustReport
from app.services import flow, image_forensics, reporter, result_cache
from app.services.news import fetch as news_fetch

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
    text, article = _clean(body.text), None
    if news_fetch.URL_ONLY.match(text):  # an article link: fetch it (guarded) and verify its headline claim
        try:
            article = await run_in_threadpool(news_fetch.fetch_article, text)
        except news_fetch.SourceUnavailable as e:
            raise HTTPException(422, f"Source unavailable: {e}. This says nothing about whether the claim is true - "
                                     "paste the headline or text instead.")
        text = ". ".join(x for x in (article["headline"], article["description"]) if x)[:1500] or article["text"][:1500]
        article = {k: article[k] for k in ("url", "headline", "publisher", "author", "published")}
    state = await flow.run("claim", text=text, article=article)
    return reporter.build(state)


@router.post("/analyze/news", response_model=TrustReport)
async def analyze_news(text: str = Form(""), file: UploadFile | None = File(None)):
    """Fake news / claim verification with any combination of: claim or article text, article URL, image.
    With an image, media authenticity and the claim are assessed separately."""
    text = text.strip()
    if file is None or not file.filename:
        return await analyze_claim(TextIn(text=text))
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(413, f"Text is too long (max {MAX_TEXT_CHARS} characters).")
    data = await file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"Image is larger than {settings.MAX_UPLOAD_MB} MB.")
    fmt = image_forensics.sniff_format(data)
    if fmt not in ALLOWED:
        raise HTTPException(415, "Unsupported file. Upload a JPG, PNG or WebP image.")
    k = result_cache.key("news", data + b"\0" + text.encode())
    cached = result_cache.get(k)
    if cached:
        return cached
    report = reporter.build(await flow.run("claim", text=text, image_bytes=data, image_format=fmt))
    result_cache.put(k, report)
    return report
