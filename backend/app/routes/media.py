"""Video / audio type detection for /api/analyze (routes/analyze.py)."""
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
