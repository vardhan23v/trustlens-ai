"""Deterministic image forensics: EXIF (positive evidence only) and Error Level Analysis."""
import base64
import io
import re
from datetime import datetime

import numpy as np
import piexif
from PIL import Image, ImageChops, ImageOps

from app.models.report import Ela, Signal

EDITORS = re.compile(
    r"photoshop|gimp|lightroom|snapseed|picsart|canva|pixlr|affinity|paint\.net|photopea|faceapp|remini", re.I
)
CAMERA_SW = re.compile(r"^(ver|v)?[\d._\- ]+$|android|ios|iphone|samsung|pixel|camera|firmware|hdr\+|miui|oneplus", re.I)

# ELA tunables (calibrated on the two demo notices: genuine peaks at 2.5, edited at 4.6)
ELA_QUALITIES = (95, 90, 85, 80, 75, 70, 65, 60)  # re-save sweep ("JPEG ghost" search)
DISPLAY_QUALITY = 90
BLOCK = 16
HIGH_RATIO, MED_RATIO = 4.0, 3.0
MAX_ELA_PIXELS = 16_000_000


def sniff_format(image_bytes: bytes) -> str | None:
    """Return 'JPEG' | 'PNG' | 'WEBP' | other PIL format name, or None if not an image."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as im:
            im.verify()
            return im.format
    except Exception:
        return None


def _dec(v) -> str:
    if isinstance(v, bytes):
        return v.decode("utf-8", "ignore").strip("\x00 ").strip()
    return str(v).strip() if v else ""


def _parse_dt(s: str) -> datetime | None:
    try:
        return datetime.strptime(s[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def exif(image_bytes: bytes) -> list[Signal]:
    """Signals only on positive evidence. Missing EXIF is never a signal."""
    software = dt = dt_orig = ""
    try:
        d = piexif.load(image_bytes)
        zeroth, ex = d.get("0th", {}), d.get("Exif", {})
        software = _dec(zeroth.get(piexif.ImageIFD.Software)) or _dec(zeroth.get(piexif.ImageIFD.ProcessingSoftware))
        dt = _dec(zeroth.get(piexif.ImageIFD.DateTime))
        dt_orig = _dec(ex.get(piexif.ExifIFD.DateTimeOriginal))
    except Exception:
        try:
            with Image.open(io.BytesIO(image_bytes)) as im:
                e = im.getexif()
                software, dt = _dec(e.get(0x0131)), _dec(e.get(0x0132))
                dt_orig = _dec(e.get_ifd(0x8769).get(0x9003))
        except Exception:
            return []

    out: list[Signal] = []
    if software:
        if EDITORS.search(software):
            out.append(Signal(
                key="editing_software_exif", title="Editing software in metadata", severity="high",
                category="image_forensics", sources=["RULE"],
                explanation="The image metadata says it was last saved by an image editor. That shows it was "
                            "processed, not what was changed.",
                evidence=f"EXIF Software = \"{software}\""))
        elif not CAMERA_SW.search(software):
            out.append(Signal(
                key="editing_software_exif", title="Non-camera software in metadata", severity="medium",
                category="image_forensics", sources=["RULE"],
                explanation="The image metadata names software that is not a camera app, so the file was "
                            "processed after capture.",
                evidence=f"EXIF Software = \"{software}\""))
    a, b = _parse_dt(dt_orig), _parse_dt(dt)
    if a and b and abs((b - a).total_seconds()) > 60:
        out.append(Signal(
            key="exif_time_mismatch", title="Modified after creation", severity="low",
            category="image_forensics", sources=["RULE"],
            explanation="The metadata's creation time and last-modified time differ, so the file was re-saved later.",
            evidence=f"created {dt_orig} · modified {dt}"))
    return out


def _heatmap_b64(scaled: Image.Image) -> str:
    heat = ImageOps.colorize(scaled, black="#0B0F17", white="#22D3EE", mid="#F97316")
    heat.thumbnail((900, 1200))
    buf = io.BytesIO()
    heat.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _error_map(im: Image.Image, quality: int) -> np.ndarray:
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    resaved = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    return np.asarray(ImageChops.difference(im, resaved).convert("L"), dtype=np.float32)


def ela(image_bytes: bytes, fmt: str) -> tuple[Ela, Signal | None]:
    """Error Level Analysis for lossy formats. A signal, never proof.

    The image is re-saved at several JPEG qualities. Content that already went through JPEG
    compression at one of them barely changes at that quality, while content pasted in later
    still does — so an edited region stands out against the rest of the image at that quality.
    """
    if fmt not in ("JPEG", "WEBP"):
        return Ela(status="not_applicable_lossless"), None
    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = im.size
        bh, bw = h // BLOCK, w // BLOCK

        def blocks_of(a: np.ndarray) -> np.ndarray:
            return a[: bh * BLOCK, : bw * BLOCK].reshape(bh, BLOCK, bw, BLOCK).mean(axis=(1, 3))

        best = None  # (ratio, quality, error map, block means)
        if bh >= 4 and bw >= 4 and w * h <= MAX_ELA_PIXELS:
            grey = np.asarray(im.convert("L"), dtype=np.float32)
            content = grey[: bh * BLOCK, : bw * BLOCK].reshape(bh, BLOCK, bw, BLOCK).std(axis=(1, 3)) > 4
            if content.sum() >= 8:
                for q in ELA_QUALITIES:
                    arr = _error_map(im, q)
                    blocks = blocks_of(arr)
                    max_b = float(blocks.max())
                    if max_b < 1.0:
                        continue  # nothing above noise at this quality
                    # hottest block vs the typical block that has content (not vs. blank background)
                    ratio = max_b / (float(np.median(blocks[content])) + 0.25)
                    if best is None or ratio > best[0]:
                        best = (ratio, q, arr, blocks)

        severity = None
        if best is not None:
            ratio, quality, arr, blocks = best
            hot = blocks > 0.6 * float(blocks.max())
            area_frac = float(hot.sum()) / blocks.size
            ys, xs = np.where(hot)
            x0, y0 = int(xs.min()) * BLOCK, int(ys.min()) * BLOCK
            rw, rh = (int(xs.max()) + 1) * BLOCK - x0, (int(ys.max()) + 1) * BLOCK - y0
            box_frac = (rw * rh) / float(w * h)
            if ratio >= HIGH_RATIO and 0.002 <= area_frac <= 0.35 and box_frac <= 0.5:
                severity = "high"
            elif ratio >= MED_RATIO and area_frac <= 0.5 and box_frac <= 0.5:
                severity = "medium"

        shown = best[2] if severity else _error_map(im, DISPLAY_QUALITY)
        scaled = Image.fromarray(np.clip(shown * (255.0 / max(float(shown.max()), 1.0)), 0, 255).astype(np.uint8), mode="L")
        result = Ela(status="ok", heatmap_b64=_heatmap_b64(scaled), width=w, height=h)
        if severity is None:
            return result, None
        result.region = [x0, y0, rw, rh]
        return result, Signal(
            key="ela_anomaly", title="Compression anomaly region", severity=severity,
            category="image_forensics", sources=["RULE"],
            explanation=f"Compression levels differ sharply in a region around ({x0}, {y0}, {rw}, {rh}) compared "
                        f"with the rest of the image. This can indicate pasted or re-typed content; it is not proof.",
            evidence=f"Error level {ratio:.1f}× the typical level at JPEG quality {quality}, over "
                     f"{area_frac * 100:.1f}% of the image")
    except Exception:
        return Ela(status="error"), None
