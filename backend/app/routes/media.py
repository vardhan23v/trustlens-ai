"""Video / audio analysis. The file is examined in memory by Gemini; nothing is written to disk."""
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.report import TrustReport
from app.services import flow, reporter, result_cache

router = APIRouter()
MAX_MEDIA_MB = 18  # inline request limit for a single Gemini call


def sniff_media(data: bytes) -> str | None:
    """MIME type from magic bytes (the file name and browser-supplied type are not trusted)."""
    if len(data) < 16:
        return None
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"M4A ", b"M4B "):
            return "audio/mp4"
        return "video/quicktime" if brand == b"qt  " else "video/mp4"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "video/webm"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data[:4] == b"OggS":
        return "audio/ogg"
    if data[:3] == b"ID3" or (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "audio/mpeg"
    return None


@router.post("/analyze/media", response_model=TrustReport)
async def analyze_media(file: UploadFile = File(...)):
    data = await file.read(MAX_MEDIA_MB * 1024 * 1024 + 1)
    if len(data) > MAX_MEDIA_MB * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {MAX_MEDIA_MB} MB. Trim the clip and try again.")
    mime = sniff_media(data)
    if mime is None:
        raise HTTPException(415, "Unsupported file. Upload MP4, MOV or WebM video, or MP3, WAV, M4A or OGG audio.")
    k = result_cache.key("media", data)
    cached = result_cache.get(k)
    if cached:
        return cached  # identical file: identical report
    report = reporter.build(await flow.run("media", image_bytes=data, media_mime=mime))
    result_cache.put(k, report)
    return report
