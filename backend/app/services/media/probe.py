"""ffmpeg-based preprocessing for video and audio: container metadata, keyframe sampling, audio track.

Uses a system ffmpeg if present, else the binary bundled with the `imageio-ffmpeg` package. The upload
is written to a private temporary directory only for the duration of the call and always removed.
If ffmpeg is missing or fails, callers fall back to sending the original file and say so.
"""
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PCM_MAX_S = 180
MAX_FRAMES = 12  # sent to Gemini; never every frame
UNIFORM = 8
SCENE_THRESHOLD = 0.35
SUFFIX = {"video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm", "audio/mp4": ".m4a",
          "audio/wav": ".wav", "audio/ogg": ".ogg", "audio/mpeg": ".mp3"}


class ProbeUnavailable(RuntimeError):
    pass


@dataclass
class Prepared:
    meta: dict = field(default_factory=dict)  # facts read from the container, nothing inferred
    frames: list[tuple[float, bytes]] = field(default_factory=list)  # (seconds, JPEG bytes), time-ordered
    scene_changes: list[float] = field(default_factory=list)
    audio: bytes = b""  # MP3, 16 kHz mono
    pcm: object = None  # numpy float32 mono at 16 kHz (first PCM_MAX_S seconds), for the specialist audio models
    notes: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def ffmpeg_path() -> str | None:
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _run(args: list[str], timeout: int = 40) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, timeout=timeout, check=False)


def parse_meta(stderr: str) -> dict:
    """Facts from `ffmpeg -i` output."""
    meta: dict = {}
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
    if m:
        meta["duration_s"] = round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 2)
    m = re.search(r"Input #0, ([^,]+(?:,[^,\s]+)*), from", stderr)
    if m:
        meta["container"] = m.group(1).split(",")[0]
    m = re.search(r"Stream #\d+:\d+.*?: Video: (\w+).*?(\d{2,5})x(\d{2,5})", stderr)
    if m:
        meta |= {"video_codec": m.group(1), "width": int(m.group(2)), "height": int(m.group(3))}
        f = re.search(r"Video:.*?([\d.]+) fps", stderr)
        if f:
            meta["fps"] = float(f.group(1))
    m = re.search(r"Stream #\d+:\d+.*?: Audio: (\w+)(?:.*?(\d+) Hz)?", stderr)
    if m:
        meta["audio_codec"] = m.group(1)
        if m.group(2):
            meta["sample_rate"] = int(m.group(2))
    for key, label in (("creation_time", "creation_time"), ("encoder", "encoder"), ("comment", "comment"),
                       ("handler_name", "handler"), ("software", "software")):
        m = re.search(rf"^\s*{key}\s*:\s*(.+)$", stderr, re.M | re.I)
        if m:
            meta[label] = m.group(1).strip()[:120]
    return meta


def stamp(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


def prepare(data: bytes, mime: str) -> Prepared:
    """Metadata for any file; for video also sampled keyframes and the audio track."""
    exe = ffmpeg_path()
    if not exe:
        raise ProbeUnavailable("ffmpeg is not installed")
    out = Prepared()
    with tempfile.TemporaryDirectory(prefix="trustlens_") as tmp:  # removed on exit, even on error
        src = Path(tmp) / f"in{SUFFIX.get(mime, '.bin')}"
        src.write_bytes(data)
        try:
            info = _run([exe, "-hide_banner", "-i", str(src)], timeout=20)
        except subprocess.TimeoutExpired as e:
            raise ProbeUnavailable("ffmpeg timed out reading the file") from e
        out.meta = parse_meta(info.stderr.decode("utf-8", "replace"))
        if "duration_s" not in out.meta and "video_codec" not in out.meta and "audio_codec" not in out.meta:
            raise ProbeUnavailable("ffmpeg could not read the file")
        if "audio_codec" in out.meta:
            try:  # raw samples for the speech models; optional, so a failure here is not an error
                raw = _run([exe, "-hide_banner", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-t", str(PCM_MAX_S),
                            "-f", "f32le", "pipe:1"], timeout=40)
                if raw.stdout:
                    import numpy as np
                    out.pcm = np.frombuffer(raw.stdout, dtype=np.float32)
            except subprocess.TimeoutExpired:
                out.notes.append("Audio decoding timed out.")
        if not mime.startswith("video/") or "video_codec" not in out.meta:
            return out
        dur = out.meta.get("duration_s") or 0.0
        scale = "scale='min(768,iw)':-2"
        try:
            # 1) scene changes: frames where the picture changes sharply
            sc = _run([exe, "-hide_banner", "-i", str(src), "-vf",
                       f"select='gt(scene,{SCENE_THRESHOLD})',showinfo,{scale}", "-vsync", "vfr",
                       "-frames:v", str(MAX_FRAMES - UNIFORM), "-q:v", "5", str(Path(tmp) / "sc_%02d.jpg")])
            times = [float(t) for t in re.findall(r"pts_time:([\d.]+)", sc.stderr.decode("utf-8", "replace"))]
            for i, t in enumerate(times[:MAX_FRAMES - UNIFORM], 1):
                p = Path(tmp) / f"sc_{i:02d}.jpg"
                if p.exists():
                    out.frames.append((t, p.read_bytes()))
                    out.scene_changes.append(round(t, 2))
            # 2) uniform temporal sampling across the clip
            n = UNIFORM if dur >= 4 else max(2, int(dur * 2) or 2)
            for i in range(n):
                t = dur * (i + 0.5) / n if dur else 0.0
                p = Path(tmp) / f"u_{i:02d}.jpg"
                _run([exe, "-hide_banner", "-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1", "-vf", scale,
                      "-q:v", "5", str(p)], timeout=20)
                if p.exists() and all(abs(t - ft) > 0.4 for ft, _ in out.frames):
                    out.frames.append((t, p.read_bytes()))
            out.frames.sort(key=lambda f: f[0])
            # 3) audio track, if any
            if "audio_codec" in out.meta:
                a = Path(tmp) / "a.mp3"
                _run([exe, "-hide_banner", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(a)])
                if a.exists() and a.stat().st_size > 0:
                    out.audio = a.read_bytes()
                else:
                    out.notes.append("The audio track could not be extracted.")
        except subprocess.TimeoutExpired:
            out.notes.append("Frame sampling timed out; the original file was examined instead.")
            out.frames, out.audio = [], b""
    return out
