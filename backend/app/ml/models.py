"""Loaders and inference for the specialist models (CPU, ONNX Runtime / CTranslate2, no PyTorch).

Every public function returns the model's real output or raises; callers (services/flow.py) record
what happened per slot. Nothing here invents a value: if a model cannot run, the slot is reported
MODEL_UNAVAILABLE or FAILED and the analysis continues on Gemini + deterministic evidence.
"""
import io
import json
import os

import numpy as np
from PIL import Image

from app.ml import registry
from app.ml.registry import MODEL_DIR, loader


def _session(path):
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.intra_op_num_threads = registry.threads()
    so.inter_op_num_threads = 1
    so.enable_cpu_mem_arena = False  # give memory back between runs: the container is small
    so.log_severity_level = 3
    return ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


def _label_index(id2label: dict, *words: str) -> int | None:
    for i, name in id2label.items():
        if any(w in str(name).lower() for w in words):
            return int(i)
    return None


# ---------------------------------------------------------------- AI-generated image detector
@loader("image_synthetic")
def _load_image():
    base = MODEL_DIR / "image_synthetic"
    cfg = json.loads((base / "config.json").read_text())
    pre = json.loads((base / "preprocessor_config.json").read_text())
    if cfg.get("num_labels") != 1:
        # the corrected export has one sigmoid output; anything else is the withdrawn conversion with wrong weights
        raise RuntimeError("image detector files are the withdrawn export (config.num_labels != 1)")
    sess = _session(base / "onnx" / "model.onnx")

    def px(v, default):  # configs give a size as a number or as {height, width} / {shortest_edge}
        if isinstance(v, dict):
            v = v.get("height") or v.get("shortest_edge")
        return int(v or default)

    side = px(pre.get("crop_size"), cfg.get("image_size") or 384)
    return {"sess": sess, "id2label": cfg.get("id2label") or {}, "pre": pre, "side": side,
            "resize": max(side, px(pre.get("size"), side)), "input": sess.get_inputs()[0].name}


def _prep_image(m: dict, image_bytes: bytes) -> np.ndarray:
    im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    side, short = m["side"], m["resize"]
    w, h = im.size
    scale = short / min(w, h)  # shorter side to `short`, then a centre crop: aspect ratio is kept
    im = im.resize((max(side, round(w * scale)), max(side, round(h * scale))), Image.BICUBIC)
    w, h = im.size
    left, top = (w - side) // 2, (h - side) // 2
    im = im.crop((left, top, left + side, top + side))
    x = np.asarray(im, dtype=np.float32) / 255.0
    mean = np.array(m["pre"].get("image_mean") or [0.5, 0.5, 0.5], dtype=np.float32)
    std = np.array(m["pre"].get("image_std") or [0.5, 0.5, 0.5], dtype=np.float32)
    return ((x - mean) / std).transpose(2, 0, 1)[None]


def detect_image(image_bytes: bytes) -> dict:
    """{'p_generated': 0..1}: the detector's score that the image is AI-generated (not a calibrated probability)."""
    m = registry.get("image_synthetic")
    if m is None:
        raise RuntimeError("unavailable")
    logits = m["sess"].run(None, {m["input"]: _prep_image(m, image_bytes)})[0][0]
    if logits.shape[-1] == 1:  # single logit: sigmoid = P(generated)
        p = float(1 / (1 + np.exp(-float(logits[0]))))
    else:
        fake = _label_index(m["id2label"], "fake", "generated", "synthetic", "ai")
        p = float(_softmax(logits)[fake if fake is not None else -1])
    return {"p_generated": round(p, 4)}


# ---------------------------------------------------------------- synthetic-speech detector
@loader("audio_spoof")
def _load_audio():
    base = MODEL_DIR / "audio_spoof"
    cfg = json.loads((base / "config.json").read_text())
    pre = json.loads((base / "preprocessor_config.json").read_text())
    sess = _session(base / "onnx" / "model.onnx")
    return {"sess": sess, "id2label": cfg.get("id2label") or {}, "normalize": bool(pre.get("do_normalize", True)),
            "input": sess.get_inputs()[0].name}


CHUNK_S, MAX_CHUNKS, SR = 8, 5, 16000


def detect_speech(pcm: np.ndarray) -> dict:
    """pcm: mono float32 at 16 kHz. Scores up to MAX_CHUNKS evenly spaced windows and returns their mean."""
    m = registry.get("audio_spoof")
    if m is None:
        raise RuntimeError("unavailable")
    n = CHUNK_S * SR
    if len(pcm) < SR:  # under one second: nothing to score
        raise ValueError("audio shorter than one second")
    starts = [0] if len(pcm) <= n else np.linspace(0, len(pcm) - n, min(MAX_CHUNKS, int(np.ceil(len(pcm) / n)))).astype(int)
    fake = _label_index(m["id2label"], "fake", "spoof", "synthetic", "deepfake")
    scores = []
    for s in starts:
        x = pcm[s:s + n].astype(np.float32)
        if m["normalize"]:
            x = (x - x.mean()) / (x.std() + 1e-7)
        logits = m["sess"].run(None, {m["input"]: x[None]})[0][0]
        scores.append(float(_softmax(logits)[fake if fake is not None else -1]))
    return {"p_synthetic": round(float(np.mean(scores)), 4), "windows": [round(s, 3) for s in scores],
            "window_starts_s": [round(int(s) / SR, 1) for s in starts]}


# ---------------------------------------------------------------- speech transcription
@loader("asr")
def _load_asr():
    from faster_whisper import WhisperModel
    return WhisperModel(str(MODEL_DIR / "asr"), device="cpu", compute_type="int8", cpu_threads=registry.threads(),
                        num_workers=1)


def transcribe(pcm: np.ndarray) -> dict:
    """Whisper with voice-activity detection. pcm: mono float32 at 16 kHz."""
    m = registry.get("asr")
    if m is None:
        raise RuntimeError("unavailable")
    segments, info = m.transcribe(pcm, beam_size=1, vad_filter=True, condition_on_previous_text=False)
    segs = [{"start": round(s.start, 1), "end": round(s.end, 1), "text": s.text.strip(),
             "no_speech_prob": round(s.no_speech_prob, 3)} for s in segments]
    return {"text": " ".join(s["text"] for s in segs).strip(), "segments": segs, "language": info.language,
            "language_probability": round(float(info.language_probability), 3),
            "duration_s": round(float(info.duration), 1), "speech_s": round(float(info.duration_after_vad), 1)}


# ---------------------------------------------------------------- OCR
@loader("ocr")
def _load_ocr():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR(intra_op_num_threads=registry.threads(), inter_op_num_threads=1)


def read_text(image_bytes: bytes) -> dict:
    m = registry.get("ocr")
    if m is None:
        raise RuntimeError("unavailable")
    im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if max(im.size) > 2000:  # keep memory and time bounded on large uploads
        im.thumbnail((2000, 2000))
    result, _ = m(np.asarray(im)[:, :, ::-1])
    lines = [(str(t), float(c)) for _, t, c in (result or []) if str(t).strip()]
    return {"text": "\n".join(t for t, _ in lines), "lines": len(lines),
            "mean_confidence": round(float(np.mean([c for _, c in lines])), 3) if lines else 0.0}


# ---------------------------------------------------------------- embeddings
@loader("embedding")
def _load_embed():
    from tokenizers import Tokenizer
    base = MODEL_DIR / "embedding"
    tok = Tokenizer.from_file(str(base / "tokenizer.json"))
    tok.enable_truncation(max_length=128)
    tok.no_padding()
    sess = _session(base / "onnx" / "model_quantized.onnx")
    return {"tok": tok, "sess": sess, "inputs": [i.name for i in sess.get_inputs()]}


def _embed(m: dict, text: str) -> np.ndarray:
    enc = m["tok"].encode(text)
    mask = np.array([enc.attention_mask], dtype=np.int64)
    feed = {"input_ids": np.array([enc.ids], dtype=np.int64), "attention_mask": mask,
            "token_type_ids": np.array([enc.type_ids], dtype=np.int64)}
    hidden = m["sess"].run(None, {k: v for k, v in feed.items() if k in m["inputs"]})[0]
    if hidden.ndim == 3:  # token embeddings: mean-pool over real tokens (how this model was trained)
        w = mask[..., None].astype(np.float32)
        hidden = (hidden * w).sum(axis=1) / np.maximum(w.sum(axis=1), 1e-9)
    return hidden[0]


def similarity(query: str, texts: list[str]) -> list[float]:
    """Cosine similarity of each text to the query (multilingual sentence embeddings)."""
    m = registry.get("embedding")
    if m is None:
        raise RuntimeError("unavailable")
    vecs = np.array([_embed(m, t) for t in [query] + texts])
    vecs = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
    return [round(float(v), 3) for v in vecs[1:] @ vecs[0]]


# ---------------------------------------------------------------- NLI
@loader("nli")
def _load_nli():
    from tokenizers import Tokenizer
    base = MODEL_DIR / "nli"
    tok = Tokenizer.from_file(str(base / "tokenizer.json"))
    tok.enable_truncation(max_length=256)
    tok.no_padding()
    sess = _session(base / "onnx" / "model_quantized.onnx")
    cfg = json.loads((base / "config.json").read_text())
    return {"tok": tok, "sess": sess, "id2label": cfg.get("id2label") or {},
            "inputs": [i.name for i in sess.get_inputs()]}


def entailment(premise: str, hypothesis: str) -> dict:
    """Does the premise (a source headline) entail, contradict or say nothing about the hypothesis (the claim)?"""
    m = registry.get("nli")
    if m is None:
        raise RuntimeError("unavailable")
    enc = m["tok"].encode(premise, hypothesis)
    feed = {"input_ids": np.array([enc.ids], dtype=np.int64), "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
            "token_type_ids": np.array([enc.type_ids], dtype=np.int64)}
    probs = _softmax(m["sess"].run(None, {k: v for k, v in feed.items() if k in m["inputs"]})[0][0])
    out = {str(m["id2label"].get(str(i), i)).lower(): round(float(p), 3) for i, p in enumerate(probs)}
    out["label"] = max((k for k in out), key=lambda k: out[k])
    return out
