"""Specialist-model registry: one swap-in point for pretrained models (see docs/MODEL_SELECTION.md).

* Weights live in backend/models/<slot>/ (scripts/fetch_models.py; baked into the Docker image).
  Nothing is downloaded at request time: a slot whose files are missing is MODEL_UNAVAILABLE.
* Models are loaded lazily, once, under a lock. Before loading, the container's memory limit is
  checked; other models are unloaded first if needed, and a model that still would not fit reports
  MODEL_UNAVAILABLE instead of risking the whole service.
* All run on CPU through ONNX Runtime / CTranslate2 — no PyTorch.
* Each slot carries what the model is, where it came from and its known limits; those travel into
  every report. A model's score is evidence, never a verdict (services/fusion.py decides states).
"""
import gc
import importlib.util
import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger("trustlens.ml")
MODEL_DIR = Path(os.getenv("TRUSTLENS_MODEL_DIR") or Path(__file__).resolve().parents[2] / "models")

# Where scripts/fetch_models.py gets each slot's files.
SOURCES: dict[str, dict] = {
    # The author's own repository: its ONNX export was regenerated from the corrected checkpoint (single
    # sigmoid output). The older community conversion carries the wrong weights and is rejected at load.
    "image_synthetic": {"repo": "buildborderless/CommunityForensics-DeepfakeDet-ViT",
                        "files": ["onnx/model.onnx", "config.json", "preprocessor_config.json"]},
    "audio_spoof": {"repo": "ai8shiro/deepfake-audio-wav2vec2-ONNX",
                    "files": ["onnx/model.onnx", "config.json", "preprocessor_config.json"]},
    "asr": {"repo": "Systran/faster-whisper-base", "snapshot": True},
    "nli": {"repo": "onnx-community/multilingual-MiniLMv2-L6-mnli-xnli-ONNX",
            "files": ["onnx/model_quantized.onnx", "config.json", "tokenizer.json"]},
    "embedding": {"repo": "Xenova/paraphrase-multilingual-MiniLM-L12-v2",
                  "files": ["onnx/model_quantized.onnx", "config.json", "tokenizer.json"]},
}


@dataclass(frozen=True)
class Spec:
    slot: str
    task: str
    model: str  # what is installed for this slot
    modalities: tuple[str, ...]
    modes: tuple[str, ...]
    stand_in: str  # what does the job when the model is unavailable
    needs: tuple[str, ...]  # python modules the loader imports
    marker: str  # a file under MODEL_DIR/<slot> that proves the weights are present ("" = bundled in a package)
    est_mb: int  # rough resident memory once loaded
    limits: tuple[str, ...] = field(default_factory=tuple)


SPECS: list[Spec] = [
    Spec("image_synthetic", "AI-generated image detector", "Community Forensics ViT (ONNX)", ("image",),
         ("ai_generated", "news_claim"), "Gemini visual examination + EXIF/ELA", ("onnxruntime",), "onnx/model.onnx", 250,
         ("Trained on photographs versus generated images; screenshots, documents and graphics are outside its training data",
          "Independent tests put detectors of this kind near 78% accuracy on unseen generators; heavy compression and resizing lower it",
          "Its score is not a calibrated probability")),
    Spec("video_deepfake", "Video frame detector", "Community Forensics ViT on sampled keyframes", ("video",),
         ("ai_generated", "news_claim"), "Gemini examination of sampled keyframes", ("onnxruntime",),
         "../image_synthetic/onnx/model.onnx", 0,
         ("Frame-level only: each sampled still is scored on its own, so motion, flicker and lip-sync are not analysed",
          "Detects generated imagery, not face-swap deepfakes of a real recording",
          "Its score is not a calibrated probability")),
    Spec("audio_spoof", "Synthetic-speech detector", "wav2vec2 deepfake-audio classifier (ONNX)", ("video", "audio"),
         ("ai_generated", "news_claim"), "Gemini listening to the audio track", ("onnxruntime",), "onnx/model.onnx", 650,
         ("Fine-tuned on ASVspoof 2021 replay-attack data: its ability to recognise modern text-to-speech or cloned voices is unproven",
          "Sensitive to compression, background music and language; English training data",
          "Treated as weak evidence: it never decides the audio state on its own")),
    Spec("asr", "Speech transcription", "Whisper base (faster-whisper, int8) with voice-activity detection",
         ("video", "audio"), ("news_claim", "ai_generated"), "Gemini transcribes the audio", ("faster_whisper",),
         "model.bin", 350,
         ("The base model makes more errors than larger Whisper models, especially on Indian languages, names and noisy audio",
          "Can repeat or invent words in silence or music")),
    Spec("ocr", "OCR", "RapidOCR (PP-OCR, ONNX)", ("image",), ("news_claim",), "Gemini reads the visible text",
         ("rapidocr_onnxruntime",), "", 250,
         ("Bundled models read Latin script and Chinese; Indic scripts are not recognised",
          "Small, stylised or low-contrast text is often missed")),
    Spec("embedding", "Semantic relevance (embeddings)", "paraphrase-multilingual-MiniLM-L12-v2 (ONNX, int8)",
         ("image", "video", "audio", "text"), ("news_claim",), "keyword search of news feeds",
         ("onnxruntime", "tokenizers"), "onnx/model_quantized.onnx", 300,
         ("Compares the claim with each source headline only, not the article body",)),
    Spec("nli", "Entailment / contradiction (NLI)", "multilingual MiniLMv2 NLI (ONNX, int8)",
         ("image", "video", "audio", "text"), ("news_claim",), "Gemini reads each source headline's stance",
         ("onnxruntime", "tokenizers"), "onnx/model_quantized.onnx", 300,
         ("Judges a headline against the claim; headlines phrased as questions usually come out neutral",
          "Trained on machine-translated sentence pairs: weaker outside English")),
    Spec("text_synthetic", "AI-written text detector", "none evaluated", ("text",), ("ai_generated",),
         "Gemini reading of the writing style", ("__no_model__",), "", 0),
]
BY_SLOT = {s.slot: s for s in SPECS}

_LOADERS: dict[str, Callable[[], Any]] = {}  # filled by app.ml.models
_loaded: dict[str, Any] = {}
_failed: dict[str, str] = {}
_lock = threading.RLock()


def loader(slot: str):
    def register(fn: Callable[[], Any]):
        _LOADERS[slot] = fn
        return fn
    return register


def disabled() -> bool:
    return os.getenv("TRUSTLENS_ML", "1") == "0"


def _weights_present(spec: Spec) -> bool:
    if not spec.marker:
        return True
    base = MODEL_DIR / spec.slot
    return (base / spec.marker).resolve().exists()


def why_unavailable(slot: str) -> str:
    """'' when the slot can be used; otherwise the honest reason."""
    spec = BY_SLOT[slot]
    if disabled():
        return "Specialist models are switched off on this deployment (TRUSTLENS_ML=0)."
    if slot not in _LOADERS and slot != "video_deepfake":
        return "No model has been selected for this task."
    if any(importlib.util.find_spec(m) is None for m in spec.needs):
        return "The model runtime is not installed on this deployment."
    if not _weights_present(spec):
        return "The model weights are not present on this deployment."
    if slot in _failed:
        return _failed[slot]
    return ""


def memory() -> dict:
    """Container memory in MB (cgroup v2, then v1): limit, and what the process really holds. Page cache
    from reading model files is reclaimable, so it is not counted as used. {} when there is no limit."""
    for base, limit_f, stat_f, anon_key in (("/sys/fs/cgroup", "memory.max", "memory.stat", "anon"),
                                            ("/sys/fs/cgroup/memory", "memory.limit_in_bytes", "memory.stat", "rss")):
        try:
            limit = (Path(base) / limit_f).read_text().strip()
            if limit == "max" or int(limit) > 1 << 50:
                return {}
            stat = dict(line.split()[:2] for line in (Path(base) / stat_f).read_text().splitlines() if line.strip())
            used = int(stat.get(anon_key, 0)) + int(stat.get("shmem", 0))
            return {"limit_mb": round(int(limit) / 1e6), "used_mb": round(used / 1e6),
                    "free_mb": round((int(limit) - used) / 1e6)}
        except (OSError, ValueError):
            continue
    return {}


def _memory_free_mb() -> Optional[float]:
    m = memory()
    return m["free_mb"] - 120 if m else None  # keep a margin for the request itself


def threads() -> int:
    """CPU threads a model may use: the container's CPU quota, not the host's core count (using every host
    core on a fractional-CPU container makes inference dozens of times slower)."""
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()[:2]
        if quota != "max":
            return max(1, min(4, round(int(quota) / int(period))))
    except (OSError, ValueError):
        pass
    return max(1, min(4, os.cpu_count() or 2))


def unload(keep: str = "") -> None:
    with _lock:
        for slot in [s for s in _loaded if s != keep]:
            _loaded.pop(slot, None)
        gc.collect()
        try:  # hand freed memory back to the OS (glibc keeps it otherwise)
            import ctypes
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except OSError:
            pass


def get(slot: str) -> Any:
    """The loaded model for a slot, or None when it cannot be used. Never raises."""
    real = "image_synthetic" if slot == "video_deepfake" else slot
    if why_unavailable(slot) or why_unavailable(real):
        return None
    with _lock:
        if real in _loaded:
            return _loaded[real]
        need = BY_SLOT[real].est_mb
        free = _memory_free_mb()
        if free is not None and free < need:
            unload()  # make room: only one or two models are needed at a time
            free = _memory_free_mb()
        if free is not None and free < need:
            # not remembered as a failure: memory may be free again on a later request
            log.warning("model %s skipped: %.0f MB free, about %d MB needed", real, free, need)
            return None
        try:
            _loaded[real] = _LOADERS[real]()
            log.info("model %s loaded", real)
        except Exception as e:
            _failed[real] = "The model could not be loaded on this deployment."
            log.warning("model %s failed to load: %s", real, str(e)[:200])
            return None
        return _loaded[real]


def status(mode: str, modality: str, runs: Optional[dict] = None) -> list[dict]:
    """Per-request status of every slot relevant to this mode and modality.
    `runs` holds what actually happened in this request: slot -> {status, detail}."""
    out = []
    for s in SPECS:
        if mode not in s.modes or modality not in s.modalities:
            continue
        run = (runs or {}).get(s.slot)
        why = why_unavailable(s.slot)
        if run:
            st, detail = run.get("status", "RAN"), run.get("detail", "")
        elif why:
            st, detail = "MODEL_UNAVAILABLE", f"{why} Done instead by: {s.stand_in}."
        else:
            st, detail = "NOT_RUN", "Installed, but not needed for this file."
        out.append({"slot": s.slot, "task": s.task, "candidate": s.model, "status": st, "detail": detail,
                    "limitations": list(s.limits) if st == "RAN" else []})
    return out
