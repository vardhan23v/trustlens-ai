"""Runs the specialist models for one request and turns their real outputs into evidence.

`runs`  : slot -> {status, detail}   what happened (RAN / NOT_APPLICABLE / FAILED / MODEL_UNAVAILABLE)
`out`   : raw model outputs kept on the flow state, read by reporter.py and fusion.py

A model that cannot load or fails is recorded as such and the analysis goes on with Gemini and the
deterministic checks. No value is ever filled in for a model that did not run.
"""
import difflib
import logging
import re
import time

from app.ml import registry
from app.models.report import Evidence, Signal
from app.rules.scoring import SEVERITY_RANK

log = logging.getLogger("trustlens.specialists")

HIGH, LOW = 0.85, 0.15  # detector score bands; in between the detector is treated as undecided
ASR_MAX_S = 75  # CPU transcription is roughly real-time on a small host: longer audio is truncated, and said so
NLI_STRONG = 0.8
RELEVANCE_MIN = 0.2


def _run(runs: dict, slot: str, fn, describe):
    """Run one model. Returns its output, or None when it is unavailable or failed."""
    why = registry.why_unavailable(slot)
    spec = registry.BY_SLOT[slot]
    if why:
        runs[slot] = {"status": "MODEL_UNAVAILABLE", "detail": f"{why} Done instead by: {spec.stand_in}."}
        return None
    t0 = time.time()
    try:
        result = fn()
    except RuntimeError as e:
        if str(e) == "unavailable":  # could not be loaded right now (memory, missing file)
            why = registry.why_unavailable(slot) or "Not enough free memory on this deployment to load the model."
            runs[slot] = {"status": "MODEL_UNAVAILABLE", "detail": f"{why} Done instead by: {spec.stand_in}."}
            return None
        runs[slot] = {"status": "FAILED", "detail": f"The model raised an error on this file. Done instead by: {spec.stand_in}."}
        log.warning("model %s failed: %s", slot, str(e)[:200])
        return None
    except Exception as e:
        runs[slot] = {"status": "FAILED", "detail": f"The model raised an error on this file. Done instead by: {spec.stand_in}."}
        log.warning("model %s failed: %s", slot, str(e)[:200])
        return None
    runs[slot] = {"status": "RAN", "detail": f"{describe(result)} ({time.time() - t0:.1f} s)"}
    return result


def _band(p: float) -> str:
    return "high" if p >= HIGH else "low" if p <= LOW else "undecided"


def image(runs: dict, out: dict, image_bytes: bytes, want_ocr: bool) -> None:
    from app.ml import models
    r = _run(runs, "image_synthetic", lambda: models.detect_image(image_bytes),
             lambda r: f"Score {r['p_generated']:.2f} that the image is AI-generated ({_band(r['p_generated'])})")
    if r:
        out["p_generated"] = r["p_generated"]
    if want_ocr:
        r = _run(runs, "ocr", lambda: models.read_text(image_bytes),
                 lambda r: f"Read {r['lines']} line(s) of text, mean confidence {r['mean_confidence']:.2f}")
        if r:
            out["ocr_text"], out["ocr_conf"], out["ocr_lines"] = r["text"], r["mean_confidence"], r["lines"]


def media(runs: dict, out: dict, prepared, is_video: bool) -> None:
    from app.ml import models
    if is_video and prepared.frames:
        def frames():
            return [(t, models.detect_image(jpg)["p_generated"]) for t, jpg in prepared.frames]
        r = _run(runs, "video_deepfake", frames,
                 lambda r: f"{sum(p >= HIGH for _, p in r)} of {len(r)} sampled frames scored as AI-generated "
                           f"(highest {max(p for _, p in r):.2f})")
        if r:
            out["frame_scores"] = [(round(t, 1), p) for t, p in r]
    pcm = getattr(prepared, "pcm", None)
    if pcm is None or len(pcm) < 16000:
        for slot in ("audio_spoof", "asr"):
            runs[slot] = {"status": "NOT_APPLICABLE", "detail": "The file has no usable audio track."}
        return
    r = _run(runs, "audio_spoof", lambda: models.detect_speech(pcm),
             lambda r: f"Score {r['p_synthetic']:.2f} that the speech is synthetic, over {len(r['windows'])} window(s)")
    if r:
        out["p_synthetic"], out["speech_windows"] = r["p_synthetic"], list(zip(r["window_starts_s"], r["windows"]))
    clip = pcm[:ASR_MAX_S * 16000]
    r = _run(runs, "asr", lambda: models.transcribe(clip),
             lambda r: f"Transcribed {r['speech_s']:.0f} s of speech in {len(r['segments'])} segment(s), language "
                       f"{r['language']} ({r['language_probability']:.2f})"
                       + (f"; only the first {ASR_MAX_S} s were transcribed" if len(pcm) > len(clip) else ""))
    if r:
        out["asr_text"], out["asr_language"] = r["text"], r["language"]
        out["asr_segments"], out["asr_speech_s"] = r["segments"], r["speech_s"]


def _norm(t: str) -> list[str]:
    return re.findall(r"[a-z0-9ऀ-ൿ]+", t.lower())


def agreement(a: str, b: str) -> float | None:
    """How closely two readings of the same content agree (0..1), compared word by word."""
    wa, wb = _norm(a), _norm(b)
    if len(wa) < 3 or len(wb) < 3:
        return None
    return round(difflib.SequenceMatcher(None, wa, wb).ratio(), 2)


def check_evidence(runs: dict, claim: str, evidence: list[Evidence]) -> list[str]:
    """Second opinion on each source: semantic relevance to the claim, and NLI of headline versus claim.
    Mutates the evidence items; returns notes. A source whose headline the NLI model reads as the opposite
    of Gemini's stance is set to 'mixed', so it no longer counts for either side."""
    from app.ml import models
    notes: list[str] = []
    items = [e for e in evidence if (e.title or e.quote).strip()][:14]
    if not claim.strip() or not items:
        return notes
    heads = [(e.title or e.quote).strip()[:300] for e in items]
    sims = _run(runs, "embedding", lambda: models.similarity(claim, heads),
                lambda r: f"Relevance of {len(r)} source headline(s) to the claim: {min(r):.2f} to {max(r):.2f}")
    if sims:
        for e, s in zip(items, sims):
            e.relevance = s
    nli = _run(runs, "nli", lambda: [models.entailment(h, claim) for h in heads],
               lambda r: "Headline versus claim: " + ", ".join(
                   f"{sum(x['label'] == k for x in r)} {k}" for k in ("entailment", "contradiction", "neutral")))
    flipped = off_topic = 0
    for i, e in enumerate(items):
        if nli:
            e.nli_label, e.nli_score = nli[i]["label"], nli[i][nli[i]["label"]]
            opposite = {"supports": "contradiction", "refutes": "entailment"}.get(e.stance)
            if opposite and e.nli_label == opposite and e.nli_score >= NLI_STRONG:
                e.stance_note = f"Gemini read this source as '{e.stance}', the NLI model as {e.nli_label} ({e.nli_score:.2f}); not counted for either side."
                e.stance = "mixed"
                flipped += 1
                continue
        if e.relevance is not None and e.relevance < RELEVANCE_MIN and e.stance in ("supports", "refutes") and e.nli_label in ("", "neutral"):
            e.stance_note = f"Semantic relevance to the claim is {e.relevance:.2f}: treated as off-topic and not counted."
            e.stance = "mixed"
            off_topic += 1
    if flipped:
        notes.append(f"{flipped} source(s) were set aside because Gemini and the NLI model read their headlines in opposite ways.")
    if off_topic:
        notes.append(f"{off_topic} source(s) were set aside as off-topic by the embedding model.")
    return notes


def detector_applies(state) -> bool:
    """The image detector was trained on photographs versus generated pictures. Screenshots, documents
    and text graphics are outside that, so its score is reported but not used for them."""
    kind = (state.visual.media_type if state.visual else "").strip().lower()
    if kind in ("screenshot", "document"):
        return False
    words = len((state.model_out.get("ocr_text") or (state.visual.visible_text if state.visual else "") or "").split())
    return words < 25


def model_signals(state) -> list[Signal]:
    """Model outputs that are strong enough to be findings. They join the signal list (and the score)."""
    out, sig = state.model_out, []
    p = out.get("p_generated")
    if p is not None and p >= 0.7 and detector_applies(state):
        sig.append(Signal(
            key="ai_generation_indicator", title="Detector flags AI generation", severity="high" if p >= HIGH else "medium",
            category="visual_analysis", sources=["MODEL"],
            explanation="A pretrained AI-image detector scored this image as likely generated. Detectors of this "
                        "kind are wrong on a meaningful share of images, so this is evidence, not proof.",
            evidence=f"Community Forensics ViT score {p:.2f} (0 = photograph, 1 = AI-generated)",
            uncertainty="Heavy compression, resizing, filters or screenshots can push the score either way."))
    frames = out.get("frame_scores") or []
    hot = [(t, s) for t, s in frames if s >= HIGH]
    if len(hot) >= 2 and len(hot) * 3 >= len(frames):
        sig.append(Signal(
            key="ai_generation_indicator", title="Frames flagged as AI-generated",
            severity="high" if len(hot) * 2 >= len(frames) else "medium", category="visual_analysis", sources=["MODEL"],
            explanation="A pretrained AI-image detector scored several sampled frames as likely generated. Each frame "
                        "is judged on its own; motion between frames is not analysed.",
            evidence=f"{len(hot)} of {len(frames)} frames, e.g. at " + ", ".join(f"{int(t) // 60:02d}:{int(t) % 60:02d} ({s:.2f})" for t, s in hot[:4]),
            uncertainty="Animation, screen recordings and heavy compression can also score high."))
    ps = out.get("p_synthetic")
    if ps is not None and ps >= HIGH:
        sig.append(Signal(
            key="audio_anomaly", title="Speech detector flags synthesis", severity="low", category="visual_analysis",
            sources=["MODEL"],
            explanation="A pretrained speech-spoofing classifier scored this audio as synthetic. This model was "
                        "trained on replay-attack data and is unproven on modern text-to-speech, so it is weak evidence.",
            evidence=f"wav2vec2 deepfake-audio score {ps:.2f} (mean over {len(out.get('speech_windows') or [])} window(s))",
            uncertainty="Compression, music, noise and non-English speech can all raise the score."))
    return sig


def add_model_signals(signals: list[Signal], extra: list[Signal]) -> list[Signal]:
    """Merge by key: the same finding from Gemini and from a model counts once and shows both sources."""
    by_key = {s.key: s for s in signals}
    for m in extra:
        cur = by_key.get(m.key)
        if cur is None:
            signals.append(m)
            by_key[m.key] = m
            continue
        if "MODEL" not in cur.sources:
            cur.sources = cur.sources + ["MODEL"]
        if SEVERITY_RANK[m.severity] > SEVERITY_RANK[cur.severity]:
            cur.severity = m.severity
        cur.evidence = f"{cur.evidence} · {m.evidence}"[:400] if cur.evidence else m.evidence
    return signals
