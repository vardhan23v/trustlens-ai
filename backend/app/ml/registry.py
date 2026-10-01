"""Specialist-model registry: one swap-in point for pretrained detectors.

Nothing here downloads weights at import time. A detector is only attempted when TRUSTLENS_ML=1 and
its runtime is installed; otherwise it reports MODEL_UNAVAILABLE and the analysis continues on
Gemini + deterministic evidence. No detector is enabled in this build (see docs/MODEL_SELECTION.md):
the deployed container has no torch runtime, so every row below is honestly MODEL_UNAVAILABLE.
"""
import importlib.util
import os
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class Spec:
    slot: str  # image_synthetic | video_deepfake | audio_spoof | ocr | asr | embedding | nli
    task: str
    candidate: str  # the candidate this slot is reserved for (docs/MODEL_SELECTION.md)
    modalities: tuple[str, ...]
    modes: tuple[str, ...]
    stand_in: str  # what does this job today, if anything


SPECS: list[Spec] = [
    Spec("image_synthetic", "AI-generated image detector", "B-Free / UnivFD-class detector", ("image",),
         ("ai_generated", "news_claim"), "Gemini visual examination + EXIF/ELA"),
    Spec("video_deepfake", "Video deepfake detector", "DeepfakeBench-compatible temporal detector", ("video",),
         ("ai_generated", "news_claim"), "Gemini examination of sampled keyframes"),
    Spec("audio_spoof", "Synthetic-speech / anti-spoof detector", "wav2vec2 anti-deepfake model", ("video", "audio"),
         ("ai_generated", "news_claim"), "Gemini listening to the audio track"),
    Spec("text_synthetic", "AI-written text detector", "none evaluated", ("text",), ("ai_generated",),
         "Gemini reading of the writing style"),
    Spec("ocr", "OCR", "PaddleOCR", ("image", "video"), ("news_claim",), "Gemini reads the visible text"),
    Spec("asr", "Speech transcription", "Whisper large-v3-turbo", ("video", "audio"), ("news_claim", "ai_generated"),
         "Gemini transcribes the audio"),
    Spec("embedding", "Semantic retrieval embeddings", "BAAI/bge-m3", ("image", "video", "audio", "text"), ("news_claim",),
         "keyword search of news feeds"),
    Spec("nli", "Entailment / contradiction (NLI)", "DeBERTa-v3 NLI cross-encoder", ("image", "video", "audio", "text"),
         ("news_claim",), "Gemini reads each source headline's stance"),
]

# slot -> loader returning a callable detector. Empty: no detector has been validated for this build.
_LOADERS: dict[str, Callable[[], Callable]] = {}
_loaded: dict[str, Optional[Callable]] = {}


def enabled() -> bool:
    return os.getenv("TRUSTLENS_ML", "") == "1" and importlib.util.find_spec("torch") is not None


def get(slot: str) -> Optional[Callable]:
    """The detector for a slot, loaded once and cached; None when unavailable (never raises)."""
    if slot in _loaded:
        return _loaded[slot]
    det = None
    if enabled() and slot in _LOADERS:
        try:
            det = _LOADERS[slot]()
        except Exception:
            det = None
    _loaded[slot] = det
    return det


def status(mode: str, modality: str) -> list[dict]:
    """Honest per-request status of each specialist slot relevant to this mode and modality."""
    out = []
    for s in SPECS:
        if mode not in s.modes or modality not in s.modalities:
            continue
        ok = get(s.slot) is not None
        out.append({"slot": s.slot, "task": s.task, "candidate": s.candidate,
                    "status": "AVAILABLE" if ok else "MODEL_UNAVAILABLE",
                    "detail": "" if ok else f"Not installed on this deployment. Done instead by: {s.stand_in}."})
    return out
