"""Merge + dedupe signals, enforce safeguards, score, compute the claim verdict → TrustReport.

Safeguards live here (not in prompts): the LLM can add signals or raise severity, never remove or
downgrade a RULE signal; score and verdict are computed in Python only.
"""
import re
from urllib.parse import urlparse

from app.models.llm_outputs import SIGNAL_KEYS, Extracted, LLMSignal
from app.models.report import (Assessment, AxisAssessment, CategoryBreakdown, ClaimStatus, Evidence, Signal,
                               TimelineEvent, TrustReport)
from app.services import specialists
from app.services.news import retrieval
from app.rules import text_rules
from app.rules.scoring import CATEGORY_CAPS, SEVERITY_RANK, band, category_of, penalty_for

FORENSIC_KEYS = {"editing_software_exif", "exif_time_mismatch", "ela_anomaly"}  # only Python can measure these

RECOMMENDATION = {
    "HIGH": "Do not pay, click or share any code yet. Verify with the organisation through its official app, "
            "website or a number from your own records.",
    "MEDIUM": "Pause before acting. Confirm the sender through an official channel and check the items listed "
              "under 'what to verify'.",
    "LOW": "No risk signals were found. This does not prove authenticity — if money or credentials are involved, "
           "confirm through an official channel.",
}
CLAIM_RECOMMENDATION = {
    "DEBUNKED_BY_SOURCE": "Do not forward this. A published fact-check rates this claim as false or misleading — "
                          "read the linked source before sharing.",
    "VERIFIED_BY_SOURCE": "A published fact-check supports this claim. Read the linked source before relying on it.",
    "UNVERIFIED": "Treat this claim as unverified. No fact-check source confirmed or refuted it — check the items "
                  "under 'what to verify' before sharing.",
}

DEBUNK_RE = re.compile(r"false|fake|misleading|incorrect|untrue|not true|hoax|fabricated|altered|no evidence|"
                       r"unproven|pants on fire|partly false|missing context", re.I)
SOFT_RE = re.compile(r"partly|missing context|misleading", re.I)
VERIFY_RE = re.compile(r"true|correct|accurate|confirmed", re.I)
HEDGE_RE = re.compile(r"mostly|half|partly", re.I)
FACTCHECK_OUTLETS = [
    "afp", "altnews", "alt news", "boomlive", "boom", "factly", "snopes", "politifact", "factcheck", "fact check",
    "fact-check", "fullfact", "full fact", "reuters", "apnews", "associated press", "thequint", "webqoof",
    "newschecker", "vishvasnews", "vishvas", "newsmeter", "factcrescendo", "fact crescendo", "pib", "thip",
    "logically", "dfrac", "youturn", "leadstories", "lead stories", "checkyourfact", "indiatoday", "india today",
    "usatoday", "the hindu", "thehindu", "bbc", "newsmobile", "digiteye", "telugupost", "onlyfact", "misbar",
]


def _norm_url(u: str) -> str:
    return u.strip().rstrip("/").lower()


def _from_llm(sig: LLMSignal, rule_keys: set[str]) -> Signal:
    key = sig.key.strip().lower().replace(" ", "_").replace("-", "_")
    explanation = sig.explanation.strip()
    if key not in SIGNAL_KEYS:
        explanation = f"{explanation} (Reported by Gemini as \"{sig.key}\".)".strip()
        key = "misleading_claim"
    elif key in FORENSIC_KEYS and key not in rule_keys:
        key = "inconsistency"  # Gemini cannot measure EXIF/ELA; keep its observation as an inconsistency
    severity = sig.severity.strip().lower() if sig.severity.strip().lower() in SEVERITY_RANK else "medium"
    evidence = sig.evidence.strip().strip('"')
    if not evidence:
        severity = "low"  # no quoted evidence → cannot carry weight
    title = " ".join(sig.title.split()[:6]) or key.replace("_", " ").capitalize()
    return Signal(key=key, title=title, severity=severity, category=category_of(key), sources=["GEMINI"],
                  explanation=explanation, evidence=evidence, uncertainty=sig.uncertainty.strip())


def merge(rule_signals: list[Signal], llm_signals: list[LLMSignal]) -> list[Signal]:
    """Dedupe by key. RULE signals are never removed or downgraded."""
    merged: dict[str, Signal] = {}
    for s in rule_signals:
        cur = merged.get(s.key)
        if cur is None or SEVERITY_RANK[s.severity] > SEVERITY_RANK[cur.severity]:
            merged[s.key] = s.model_copy()
    rule_keys = set(merged)
    for raw in llm_signals:
        g = _from_llm(raw, rule_keys)
        cur = merged.get(g.key)
        if cur is None:
            merged[g.key] = g
            continue
        injection = "injection" in g.title.lower() and "injection" not in cur.title.lower()
        if SEVERITY_RANK[g.severity] > SEVERITY_RANK[cur.severity]:
            cur.severity = g.severity
        if "GEMINI" not in cur.sources:
            cur.sources = cur.sources + ["GEMINI"]
            if g.explanation and "RULE" in cur.sources:
                cur.explanation = g.explanation  # plain-language reasoning from Gemini; rule evidence kept
            cur.uncertainty = cur.uncertainty or g.uncertainty
            if not cur.evidence:
                cur.evidence = g.evidence
        elif g.evidence and g.evidence not in cur.evidence:
            cur.evidence = f"{cur.evidence} · {g.evidence}"[:400]  # second GEMINI finding with the same key
        if injection:
            cur.title, cur.severity = g.title, "high"
            cur.evidence = g.evidence or cur.evidence
    return list(merged.values())


def score(signals: list[Signal]) -> tuple[int, list[CategoryBreakdown]]:
    raw: dict[str, float] = {}
    for s in signals:
        s.category = category_of(s.key)
        s.penalty = penalty_for(s.key, s.severity)
        raw[s.category] = raw.get(s.category, 0) + s.penalty
    breakdown = [CategoryBreakdown(category=c, raw=v, cap=CATEGORY_CAPS[c], applied=min(v, CATEGORY_CAPS[c]))
                 for c, v in raw.items() if v > 0]
    total = sum(b.applied for b in breakdown)
    return max(0, min(100, int(round(100 - total)))), breakdown


def _is_outlet(source: str, url: str) -> bool:
    hay = f"{source} {urlparse(url).netloc}".lower()
    return any(o in hay for o in FACTCHECK_OUTLETS)


LISTED = {"official", "wire", "established", "factcheck"}


def _independent(items: list[Evidence]) -> int:
    """Independent sources = distinct sites. Ten copies of one outlet's story count once."""
    return len({retrieval.registrable(e.source_site) or e.source.lower() for e in items})


def _stance_status(evidence: list[Evidence]) -> tuple[str, int, int]:
    """SUPPORTED / CONTRADICTED / MIXED / UNVERIFIED from listed sources only (rules/source_registry.json).
    Needs two independent listed sources, or one official source or fact-checker, on one side."""
    listed = [e for e in evidence if e.source_type in LISTED]
    sup = [e for e in listed if e.stance == "supports"]
    ref = [e for e in listed if e.stance == "refutes"]
    n_sup, n_ref = _independent(sup), _independent(ref)
    strong = lambda items, n: n >= 2 or any(e.source_type in ("official", "factcheck") for e in items)  # noqa: E731
    s_ok, r_ok = bool(sup) and strong(sup, n_sup), bool(ref) and strong(ref, n_ref)
    if s_ok and r_ok:
        return "MIXED", n_sup, n_ref
    if r_ok and not sup:
        return "CONTRADICTED", n_sup, n_ref
    if s_ok and not ref:
        return "SUPPORTED", n_sup, n_ref
    if sup and ref:
        return "MIXED", n_sup, n_ref
    return "UNVERIFIED", n_sup, n_ref


def verdict(evidence: list[Evidence], factcheck_urls: set[str]) -> tuple[str, float, list[str]]:
    """VERIFIED/DEBUNKED from a fact-check outlet with an explicit rating, or from independent listed
    sources agreeing; otherwise UNVERIFIED. Never from the model's own opinion."""
    status, n_sup, n_ref = _stance_status([e for e in evidence if e.claim_index == 0] or evidence)
    refutes, supports = [], []
    for e in evidence:
        rating = e.rating.strip()
        if not e.url or not rating or rating.lower() == "none":
            continue
        if _norm_url(e.url) not in factcheck_urls and not _is_outlet(e.source, e.url):
            continue
        if e.stance == "refutes" and DEBUNK_RE.search(rating):
            refutes.append(e)
        elif e.stance == "supports" and VERIFY_RE.search(rating) and not HEDGE_RE.search(rating) \
                and not DEBUNK_RE.search(rating):
            supports.append(e)
    if (refutes and supports) or status == "MIXED":
        return "UNVERIFIED", 0.3, ["Sources disagree: some refute the claim and some support it."]
    if refutes:
        soft = all(SOFT_RE.search(e.rating) for e in refutes)
        return "DEBUNKED_BY_SOURCE", 0.6 if soft else 0.9, []
    if supports:
        return "VERIFIED_BY_SOURCE", 0.8, []
    if status == "CONTRADICTED":
        return "DEBUNKED_BY_SOURCE", 0.75 if n_ref >= 2 else 0.6, [
            f"{n_ref} independent listed source(s) contradict the claim; stance was read from their headlines."]
    if status == "SUPPORTED":
        return "VERIFIED_BY_SOURCE", 0.7 if n_sup >= 2 else 0.55, [
            f"{n_sup} independent listed source(s) support the claim; stance was read from their headlines."]
    return "UNVERIFIED", 0.3, []


KIND_KEY = {"ai_generation": "ai_generation_indicator", "manipulation": "manipulation_indicator",
            "visual_inconsistency": "visual_inconsistency"}
INTENT_LABEL = {"synthetic_detection": "AI / Synthetic Detection", "artifact_authenticity": "Artifact Authenticity"}
NOT_TRUE_NOTE = "\"Not AI-generated\" does not mean \"true\": a genuine image can still carry a false or deceptive claim."

SYNTHETIC_RECOMMENDATION = {
    "LIKELY_SYNTHETIC": "Treat this image as likely AI-generated or synthetic. Do not rely on it as a record of a "
                        "real event; look for the original source before sharing.",
    "MANIPULATED": "Treat this image as likely edited. Ask for the original file and compare before relying on it.",
    "LIKELY_AUTHENTIC": "No signs of AI generation or editing were found. That does not prove the image is "
                        "authentic, and it says nothing about whether what it shows or claims is true.",
    "INCONCLUSIVE": "The evidence is not strong enough either way. Treat the image as unverified and check its "
                    "original source.",
}
ARTIFACT_RECOMMENDATION = {
    "LIKELY_FABRICATED": "Do not act on this yet. Several signs suggest it is fabricated or deceptive: confirm "
                         "through the organisation's own app, website or a number from your own records.",
    "MANIPULATED": "Do not rely on this image. It shows signs of editing: ask for the original record and "
                   "confirm it through an official channel.",
    "INCONCLUSIVE": "Pause before acting. Some signals need checking: confirm the details through an official "
                    "channel and the items under 'what to verify'.",
    "UNVERIFIED": "No deception signals were found, but a screenshot cannot prove that the event really "
                  "happened. If money or credentials are involved, confirm it in the official app or record.",
}
BOOSTERS = {
    "synthetic_detection": ["The original file straight from the camera or creator, not a screenshot or forward",
                            "The source page or account where the image first appeared",
                            "A reverse image search to find earlier copies",
                            "Other photos or footage of the same scene from independent sources"],
    "artifact_authenticity": ["The original record: the transaction in your own bank/UPI app, or the statement entry",
                              "Original email headers or the full message thread, not a screenshot",
                              "The source URL or the organisation's official notice page",
                              "The original file rather than a screenshot or forwarded copy"],
}


def _assess_image(state, signals: list[Signal], risk: str) -> tuple[Assessment, Assessment]:
    """Two separate answers for an image: is the MEDIA authentic, and is the ARTIFACT it shows genuine.
    Both are derived here from signals; Gemini's own opinion is only one input and never the final word."""
    by_key = {s.key: s for s in signals}
    ela, editor = by_key.get("ela_anomaly"), by_key.get("editing_software_exif")
    synthetic = state.intent == "synthetic_detection"
    visual = state.visual
    gemini_ok = (visual is not None) if synthetic else not state.crew_error

    # --- media ---
    # counted from Gemini's own list: merged signals are de-duplicated by key
    ai = [i for i in (visual.indicators if visual else [])
          if i.kind.strip().lower() == "ai_generation" and i.evidence.strip()]
    manip = by_key.get("manipulation_indicator")
    strong = [s for s in signals if s.category in ("visual_analysis", "image_forensics") and s.severity != "low"]
    claimed = (visual.assessment.strip().lower() if visual else "")
    # pretrained detector score (None when it did not run or does not apply to this kind of image)
    p = getattr(state, "model_out", {}).get("p_generated") if synthetic else None
    if p is not None and not specialists.detector_applies(state):
        p = None
    det_hi, det_lo = p is not None and p >= specialists.HIGH, p is not None and p <= specialists.LOW
    gem_synth = claimed == "likely_synthetic" and (any(i.severity.lower() == "high" for i in ai)
                                                   or sum(i.severity.lower() != "low" for i in ai) >= 2)
    score = f" (detector score {p:.2f})" if p is not None else ""
    if (ela and ela.severity == "high") or (manip and manip.severity == "high" and manip.evidence and claimed == "manipulated"):
        media = Assessment(state="MANIPULATED", label="Manipulation detected",
                           summary="Signs of editing were found in a specific region of the image. This is evidence, not proof.")
    elif synthetic and gem_synth and det_lo:
        media = Assessment(state="INCONCLUSIVE", label="Evidence conflicts",
                           summary=f"Gemini found visual indicators of AI generation, but the pretrained detector scored the image as a photograph{score}. Both are shown; neither settles it.")
    elif synthetic and gem_synth:
        media = Assessment(state="LIKELY_SYNTHETIC", label="Likely synthetic / AI-generated",
                           summary=("Gemini's visual indicators and the pretrained detector agree" + score + "." if det_hi else
                                    "Several visual indicators of AI generation were found" + score + ".")
                                   + " Detection is unreliable, so treat this as likely, not certain.")
    elif synthetic and det_hi and gemini_ok and claimed == "likely_authentic":
        media = Assessment(state="INCONCLUSIVE", label="Evidence conflicts",
                           summary=f"The pretrained detector scored the image as AI-generated{score}, but Gemini found no visual indicators. Both are shown; neither settles it.")
    elif synthetic and det_hi:
        media = Assessment(state="LIKELY_SYNTHETIC", label="Likely synthetic / AI-generated",
                           summary=f"The pretrained detector scored the image as AI-generated{score}"
                                   + (" and Gemini did not contradict it." if gemini_ok else "; Gemini's examination was unavailable, so this rests on the detector alone.")
                                   + " Detectors are wrong on a meaningful share of images.")
    elif synthetic and gemini_ok and claimed == "likely_authentic" and not strong:
        media = Assessment(state="LIKELY_AUTHENTIC", label="Likely authentic",
                           summary=("Gemini found no synthetic or editing indicators and the pretrained detector scored the image as a photograph" + score + "."
                                    if det_lo else "No obvious synthetic or editing indicators were detected" + score + ".")
                                   + " A carefully made fake can still pass.")
    elif synthetic and det_lo and not gemini_ok and not strong:
        media = Assessment(state="LIKELY_AUTHENTIC", label="Likely authentic",
                           summary=f"The pretrained detector scored the image as a photograph{score}. Gemini's examination was unavailable, so this rests on the detector alone.")
    elif synthetic:
        why = ("Gemini's visual examination was unavailable, so only metadata and compression checks ran."
               if not gemini_ok else "The indicators found are weak or mixed.")
        media = Assessment(state="INCONCLUSIVE", label="Inconclusive",
                           summary=why + (f" The pretrained detector was undecided{score}." if p is not None else ""))
    elif ela or editor:
        media = Assessment(state="INCONCLUSIVE", label="Editing traces present",
                           summary="Metadata or compression checks found traces of processing. AI generation was not assessed in this mode.")
    else:
        note = (" Compression analysis does not apply to PNG screenshots." if state.ela.status == "not_applicable_lossless" else "")
        media = Assessment(state="NOT_ASSESSED", label="No editing traces found",
                           summary="Metadata and compression checks found nothing." + note + " AI generation was not assessed in this mode.")

    # --- artifact ---
    if synthetic:
        artifact = Assessment(state="NOT_ASSESSED", label="Not assessed in this mode",
                              summary="Whether the message, transaction or document shown is genuine was not checked. " + NOT_TRUE_NOTE)
    elif risk == "HIGH":
        artifact = Assessment(state="LIKELY_FABRICATED", label="Likely fabricated or deceptive",
                              summary="Multiple signals suggest this does not represent a genuine communication, transaction or document.")
    elif media.state == "MANIPULATED":
        artifact = Assessment(state="MANIPULATED", label="Manipulation detected",
                              summary="The image shows signs of editing, so what it displays cannot be relied on.")
    elif not gemini_ok:
        artifact = Assessment(state="INCONCLUSIVE", label="Inconclusive",
                              summary="Gemini could not read the image, so its content was not analysed.")
    elif risk == "MEDIUM":
        artifact = Assessment(state="INCONCLUSIVE", label="Inconclusive",
                              summary="Some signals were found, but not enough to call it fabricated.")
    else:
        artifact = Assessment(state="UNVERIFIED", label="Authenticity not established",
                              summary="No deception signals were found, but an image alone cannot confirm that the event or document is genuine.")
    return media, artifact


MEDIA_KIND_KEY = {"visual_manipulation": "manipulation_indicator", "visual_ai_generation": "ai_generation_indicator",
                  "audio_synthesis": "audio_anomaly", "audio_edit": "audio_anomaly", "av_sync": "av_inconsistency",
                  "context": "inconsistency"}
_AUDIO_WORDS = re.compile(r"\b(voice|voiceover|speech|audio|sound|prosody|pronunciation|spoken|breath|tone)\b", re.I)


def obs_kind(o, audio_only: bool) -> str:
    """Normalise an observation's kind. Older/looser labels are placed by what the observation talks about."""
    k = o.kind.strip().lower()
    if k in MEDIA_KIND_KEY:
        return k
    if k.startswith("audio") or (audio_only and k != "av_sync"):
        return "audio_synthesis"
    if k == "ai_generation":
        return "audio_synthesis" if _AUDIO_WORDS.search(f"{o.title} {o.evidence}") else "visual_ai_generation"
    return k if k in ("av_sync", "context") else "visual_manipulation"
SPECIALIST_NOTE = ("Specialist models: video deepfake detector - MODEL_UNAVAILABLE; audio spoof detector - "
                   "MODEL_UNAVAILABLE; container metadata (ffmpeg) - UNAVAILABLE. Gemini alone examined this file.")
MEDIA_RECOMMENDATION = {
    "MANIPULATED": "Treat this recording with caution: signs of editing or mismatch were observed. Look for the "
                   "original upload and compare before relying on or sharing it.",
    "LIKELY_SYNTHETIC": "Treat this recording as possibly AI-generated. Do not rely on it as a record of a real "
                        "event; look for the original source.",
    "LIKELY_AUTHENTIC": "No signs of editing or synthesis were observed. That does not prove the recording is "
                        "authentic, and it says nothing about whether what is said in it is true.",
    "INCONCLUSIVE": "The evidence is not strong enough either way. Treat the recording as unverified and check "
                    "its original source.",
}


def _media_axis(heading: str, claimed: str, obs: list, gemini_ok: bool, what: str,
                model: str = "", model_text: str = "") -> AxisAssessment:
    """`model`: "high" when a pretrained detector strongly flags this track, "low" when it scores it as genuine,
    "" when no detector result may be used. `model_text` is the sentence describing that result."""
    """One media question, decided here from Gemini's observations (its own label is only one input)."""
    claimed = (claimed or "").strip().lower()
    strong = [o for o in obs if o.severity.lower() != "low" and o.evidence.strip()]
    high = [o for o in strong if o.severity.lower() == "high"]
    where = ", ".join(sorted({o.timestamp for o in strong if o.timestamp})[:4])
    at = f" (at {where})" if where else ""
    if claimed == "not_applicable":
        return AxisAssessment(heading=heading, state="NOT_ASSESSED", label="Not applicable",
                              summary=f"The file has no {what} to assess.")
    if not gemini_ok:
        if model == "high":
            return AxisAssessment(heading=heading, state="LIKELY_SYNTHETIC", label="Possibly synthetic",
                                  summary=f"{model_text} Gemini's examination was unavailable, so this rests on the detector alone.")
        return AxisAssessment(heading=heading, state="INCONCLUSIVE", label="Inconclusive",
                              summary="Gemini could not examine the file." + (f" {model_text}" if model_text else " Nothing was assessed."))
    if model == "high" and claimed in ("likely_authentic", "consistent") and not strong:
        return AxisAssessment(heading=heading, state="INCONCLUSIVE", label="Evidence conflicts",
                              summary=f"{model_text} Gemini observed nothing suspicious. Both are shown; neither settles it.")
    if model == "high" and claimed not in ("manipulated", "inconsistent"):
        return AxisAssessment(heading=heading, state="LIKELY_SYNTHETIC", label="Possibly synthetic",
                              summary=f"{model_text}" + (f" Gemini also observed indicators{at}." if strong else " Gemini did not contradict it.")
                                      + " Detectors are wrong on a meaningful share of files.")
    if claimed in ("manipulated", "inconsistent") and strong:
        label = "Inconsistent" if claimed == "inconsistent" else "Manipulation indicators"
        return AxisAssessment(heading=heading, state="MANIPULATED", label=label,
                              summary=f"{len(strong)} observation(s){at} point to editing or mismatch. This is evidence, not proof.")
    if claimed == "likely_synthetic" and (high or len(strong) >= 2):
        return AxisAssessment(heading=heading, state="LIKELY_SYNTHETIC", label="Possibly synthetic",
                              summary=f"Several indicators of synthesis were observed{at}. No specialist detector confirmed this.")
    if claimed in ("likely_authentic", "consistent") and not strong:
        label = "Consistent" if claimed == "consistent" else "No indicators found"
        return AxisAssessment(heading=heading, state="LIKELY_AUTHENTIC", label=label,
                              summary="Nothing suspicious was observed. " + (model_text + " " if model_text else "")
                                      + "A well-made fake can still pass.")
    return AxisAssessment(heading=heading, state="INCONCLUSIVE", label="Inconclusive",
                          summary="The observations are weak or mixed." + at + (f" {model_text}" if model_text else ""))


def _assess_media(state) -> list[AxisAssessment]:
    m = state.media
    ok = m is not None  # a later failure (e.g. the claim search) does not undo a completed examination
    obs = m.observations if m else []
    kinds = lambda *k: [o for o in obs if o.kind.strip().lower() in k]  # noqa: E731
    # decided from the file's own type, not from the model's description of it
    is_audio_only = (getattr(state, "media_mime", "") or "").startswith("audio/")
    meta = getattr(state, "media_meta", {}) or {}
    no_audio = bool(meta) and "audio_codec" not in meta
    applicable = lambda v: "inconclusive" if (v or "").strip().lower() == "not_applicable" else v  # noqa: E731
    for o in obs:
        o.kind = obs_kind(o, is_audio_only)
    out = getattr(state, "model_out", {})
    frames = out.get("frame_scores") or []
    hot = [x for _, x in frames if x >= specialists.HIGH]
    v_model = ("high" if len(hot) >= 2 and len(hot) * 2 >= len(frames) else
               "low" if frames and max(x for _, x in frames) <= 0.3 else "")
    v_text = (f"The frame detector scored {len(hot)} of {len(frames)} sampled frames as AI-generated." if frames else "")
    # the speech model is weak evidence (trained on replay attacks): it is reported, and never decides the state
    ps = out.get("p_synthetic")
    a_text = (f"The speech detector's score is {ps:.2f} (weak evidence: unproven on modern voice synthesis)." if ps is not None else "")
    axes = [
        # a video always has a picture: "not applicable" from the model is treated as "could not judge"
        _media_axis("Visual authenticity", "not_applicable" if is_audio_only else applicable(m.visual_assessment if m else ""),
                    kinds("visual_manipulation", "visual_ai_generation"), ok, "picture", v_model, v_text),
        _media_axis("Audio authenticity", m.audio_assessment if m else "", kinds("audio_synthesis", "audio_edit"), ok, "audio",
                    "", a_text),
        _media_axis("Audio-visual consistency", "not_applicable" if is_audio_only or no_audio
                    else applicable(m.av_consistency if m else ""), kinds("av_sync"), ok, "combined picture and sound"),
    ]
    if m and m.spoken_claims and getattr(state, "mode", ""):
        axes.append(AxisAssessment(
            heading="Spoken claims", state="NOT_ASSESSED", label="Not checked in this mode",
            summary=f"{len(m.spoken_claims)} factual claim(s) were heard. AI-Generated mode examines the recording "
                    "itself, not whether what is said is true: use News / Claim mode for that."))
    elif m and m.spoken_claims:
        axes.append(AxisAssessment(
            heading="Spoken claims", state="UNVERIFIED", label="Not verified",
            summary=f"{len(m.spoken_claims)} factual claim(s) were heard but not checked against any source. An "
                    "authentic recording can still contain a false claim: paste the claim into Fake News / Claim."))
    else:
        axes.append(AxisAssessment(heading="Spoken claims", state="NOT_ASSESSED", label="None identified",
                                   summary="No checkable factual claim was identified in the speech."))
    return axes


TEXT_RECOMMENDATION = {
    "LIKELY_SYNTHETIC": "Several traits of AI-generated writing were found. Treat the authorship as uncertain and "
                        "ask for the source or drafts if it matters; do not treat this as proof.",
    "LIKELY_AUTHENTIC": "No clear traits of AI-generated writing were found. That does not prove a person wrote it.",
    "INCONCLUSIVE": "The text does not give enough evidence either way. Authorship cannot be judged from this sample.",
}
MIN_WORDS = 40  # below this a text carries too little signal to say anything


def _assess_text(state) -> AxisAssessment:
    """AI-authorship of pasted text. Decided here from Gemini's quoted indicators; always low confidence."""
    v, heading = state.visual, "AI-authorship assessment"
    words = len(state.text.split())
    if v is None:
        return AxisAssessment(heading=heading, state="INCONCLUSIVE", label="Inconclusive",
                              summary="Gemini could not examine the text, so nothing was assessed.")
    if words < MIN_WORDS:
        return AxisAssessment(heading=heading, state="INCONCLUSIVE", label="Too short to assess",
                              summary=f"The text has {words} words. Short text carries too little signal to judge authorship.")
    quoted = [i for i in v.indicators if i.evidence.strip() and i.evidence.strip().strip('"\'')[:40].lower() in state.text.lower()]
    strong = [i for i in quoted if i.severity.lower() != "low"]
    claimed = v.assessment.strip().lower()
    if claimed == "likely_synthetic" and len(strong) >= 2:
        return AxisAssessment(heading=heading, state="LIKELY_SYNTHETIC", label="Likely AI-generated text",
                              summary=f"{len(strong)} quoted traits of AI-generated writing were found. This is likelihood, not proof.")
    if claimed == "likely_authentic" and not strong:
        return AxisAssessment(heading=heading, state="LIKELY_AUTHENTIC", label="No AI-writing indicators found",
                              summary="Nothing typical of AI-generated writing was found. A person may still have used AI and edited it.")
    return AxisAssessment(heading=heading, state="INCONCLUSIVE", label="Inconclusive",
                          summary="The indicators found are weak or mixed.")


def _error_note(err: str) -> str:
    e = err.lower()
    if "not configured" in e:
        why = "no Gemini API key is configured on the server"
    elif "timeout" in e or "timed out" in e or "deadline" in e:
        why = "the request timed out"
    elif "429" in e or "quota" in e or "resource_exhausted" in e or "rate" in e:
        why = "the Gemini quota or rate limit was reached"
    elif "api key" in e or "api_key" in e or "401" in e or "403" in e or "permission" in e:
        why = "the Gemini API key was rejected"
    elif "invalid structured output" in e:
        why = "Gemini returned output that did not match the required schema twice"
    else:
        why = "the Gemini call failed"
    return f"Gemini reasoning was unavailable ({why}); only deterministic checks are shown."


def build(state) -> TrustReport:
    """state: services.flow.FlowState"""
    notes: list[str] = []
    rule_signals = list(state.exif_signals) + ([state.ela_signal] if state.ela_signal else []) + list(state.rule_signals)
    llm = state.llm_signals
    llm_signals = list(llm.signals) if llm else []
    visual = getattr(state, "visual", None)
    if visual:  # synthetic_detection: Gemini's visual indicators become GEMINI signals
        llm_signals += [LLMSignal(key=KIND_KEY.get(i.kind.strip().lower(), "visual_inconsistency"), title=i.title,
                                  severity=i.severity, explanation=i.explanation, evidence=i.evidence,
                                  uncertainty=i.uncertainty) for i in visual.indicators]
    media = getattr(state, "media", None)
    if media:  # video/audio: Gemini's timestamped observations become GEMINI signals
        audio_only = (getattr(state, "media_mime", "") or "").startswith("audio/")
        for o in media.observations:
            o.kind = obs_kind(o, audio_only)
            if o.kind == "context" and getattr(state, "mode", "") == "ai_generated":
                continue  # this mode examines the media itself; content questions belong to News / Claim
            when = f"At {o.timestamp}: " if o.timestamp.strip() else ""
            llm_signals.append(LLMSignal(
                key=MEDIA_KIND_KEY.get(o.kind, "visual_inconsistency"), title=o.title,
                severity=o.severity, explanation=o.explanation, evidence=(when + o.evidence).strip() if o.evidence.strip() else "",
                uncertainty=o.uncertainty))
    signals = merge(rule_signals, llm_signals)
    if getattr(state, "mode", ""):  # specialist-model findings join the list (and therefore the score)
        signals = specialists.add_model_signals(signals, specialists.model_signals(state))

    if state.all_urls_match_claimed:  # known-org attenuation: a real bank SMS is not a scam for sounding urgent
        signals = [s for s in signals if s.key != "url_shortener"]
        for s in signals:
            if s.key in ("urgency", "action_pressure", "kyc_threat", "threat") and "injection" not in s.title.lower():
                s.severity = "low"
        notes.append("Every link is on the claimed organisation's own domain; pressure signals were capped at low.")

    combo = text_rules.pattern_signal(signals)
    if combo:
        signals.append(combo)

    extracted: Extracted = state.extracted
    evidence: list[Evidence] = []
    claim_rows: list[ClaimStatus] = []
    timeline: list[TimelineEvent] = []
    verdict_value = confidence = None
    what_to_verify = list(llm.what_to_verify) if llm else []
    inconsistencies = list(llm.inconsistencies) if llm else []

    if state.input_type == "claim":
        ce = state.claim_evidence
        ledger = {_norm_url(u): meta for u, meta in state.tool_urls.items()}
        factcheck_urls = {u for u, m in ledger.items() if m.get("origin") == "factcheck"}
        dropped = 0
        for item in (ce.evidence if ce else []):
            meta = ledger.get(_norm_url(item.url))
            if not item.url or meta is None:
                dropped += 1  # URL did not come from a tool → never shown
                continue
            if meta.get("origin") == "factcheck":  # publisher + rating exactly as the fact-check API returned them
                item.source, item.rating = meta.get("source") or item.source, meta.get("rating") or item.rating
            if item.stance == "unrelated":
                continue
            site = meta.get("site") or item.url
            if meta.get("origin") == "news":
                item.source = meta.get("source") or item.source  # publisher exactly as the feed names it
                # a rating counts only if the source's own headline uses that word; otherwise it is "none"
                if item.rating.strip().lower() not in (meta.get("title") or "").lower():
                    item.rating = "none"
            evidence.append(Evidence(
                source=item.source or urlparse(item.url).netloc, url=item.url, rating=item.rating or "none",
                stance=item.stance, quote=item.quote, title=meta.get("title") or item.quote,
                published=meta.get("published") or "", source_site=site,
                source_type="factcheck" if meta.get("origin") == "factcheck" else retrieval.source_tier(site),
                claim_index=item.claim_index if 0 <= item.claim_index <= 4 else 0))
        if dropped:
            notes.append(f"{dropped} evidence item(s) were dropped because their link did not come from a search tool.")
        if getattr(state, "mode", "") and evidence:
            # second opinion before the verdict: sources the NLI model reads the opposite way, or that the
            # embedding model finds off-topic, stop counting for either side
            notes += specialists.check_evidence(state.model_runs, (ce.claim if ce else "") or state.text, evidence)
        verdict_value, confidence, vnotes = verdict(evidence, factcheck_urls)
        notes += vnotes
        if state.tool_errors:
            notes.append("A search tool failed during verification; results may be incomplete.")
        notes.append("Semantic-retrieval and NLI models: MODEL_UNAVAILABLE. Each source's stance was read from its "
                     "headline by Gemini; the verdict is computed in code from independent listed sources.")
        for i, sc in enumerate((ce.sub_claims if ce else [])[:4], 1):
            own = [e for e in evidence if e.claim_index == i]
            status, n_sup, n_ref = _stance_status(own)
            claim_rows.append(ClaimStatus(text=sc.text, dimension=sc.dimension, status=status,
                                          supporting=n_sup, contradicting=n_ref))
        timeline = [TimelineEvent(date=e.published or "UNKNOWN", source=e.source, title=e.title or e.quote,
                                  stance=e.stance, url=e.url)
                    for e in sorted(evidence, key=lambda e: e.published or "9999")][:12]
        if verdict_value == "DEBUNKED_BY_SOURCE":
            top = next((e for e in evidence if e.stance == "refutes" and DEBUNK_RE.search(e.rating)), None) or \
                next(e for e in evidence if e.stance == "refutes")
            signals.append(Signal(
                key="debunked_by_source", title="Debunked by fact-checker", severity="high" if confidence >= 0.9 else "medium",
                category="claim_evidence", sources=["RULE"],
                explanation="A published fact-check rates this claim as false or misleading.",
                evidence=f"{top.source}: \"{top.rating if top.rating != 'none' else top.title}\""))
        if ce:
            what_to_verify = list(ce.what_to_verify)
            extracted = Extracted(classification="news_claim", extracted_text=state.text, claim=ce.claim,
                                  person=", ".join(ce.entities[:6]), date=", ".join(ce.dates[:4]))
        else:
            extracted = Extracted(classification="news_claim", extracted_text=state.text)

    trust_score, breakdown = score(signals)
    risk = band(trust_score)
    if risk == "LOW" and any(s.severity == "high" for s in signals):
        risk = "MEDIUM"  # a high-severity signal is never presented as low risk, whatever the caps allow
        notes.append("Risk level raised to MEDIUM because a high-severity signal is present.")
    signals.sort(key=lambda s: (-SEVERITY_RANK[s.severity], -s.penalty))

    if state.input_type == "claim":
        recommendation = CLAIM_RECOMMENDATION[verdict_value]
        caveats = (["No fact-check source was found; absence of evidence is not evidence of falsehood"]
                   if not evidence else
                   ["The verdict reflects published fact-checks found at analysis time, not an independent investigation"])
        if not evidence and state.tool_errors:
            caveats[0] = "The fact-check search could not be completed, so this claim was not checked against any source"
        caveats.append("The trust score reflects message-level signals only, not whether the claim is true")
    else:
        recommendation = RECOMMENDATION[risk]
        if risk == "LOW" and signals:
            recommendation = recommendation.replace("No risk signals were found.", "Only minor risk signals were found.")
        if risk != "LOW" and llm and llm.recommendation.strip():
            recommendation = f"{recommendation} {llm.recommendation.strip()}"
        caveats = (["Sender identity cannot be verified from text alone"] if state.input_type == "text" else
                   ["EXIF and ELA indicate editing risk, not proof either way",
                    "Absence of metadata is normal for screenshots"])
        if risk == "LOW":
            caveats.append("A well-made forgery with no scam markers would also show no risk signals")

    if state.crew_error:
        notes.append(_error_note(state.crew_error))

    intent = overall = artifact = None
    axes: list[AxisAssessment] = []
    boosters: list[str] = []
    if state.input_type == "claim":
        provided = (["image"] if state.image_format else []) + (["url"] if state.article else []) + (
            ["text"] if (state.caption if state.image_format else state.text).strip() and not state.article
            and not getattr(state, "media_mime", "") else []) + (
            [state.media_type or "media"] if getattr(state, "media_mime", "") else [])
        claim_axis = {
            "DEBUNKED_BY_SOURCE": ("CONTRADICTED", "Contradicted by sources"),
            "VERIFIED_BY_SOURCE": ("SUPPORTED", "Supported by sources"),
        }.get(verdict_value, ("UNVERIFIED", "Unverified"))
        n_src = _independent([e for e in evidence if e.source_type in LISTED])
        axes.append(AxisAssessment(
            heading="Claim assessment", state=claim_axis[0], label=claim_axis[1],
            summary=(f"Based on {n_src} independent listed source(s)." if n_src else
                     "No listed source confirmed or refuted the claim. Missing evidence is not evidence of falsehood.")))
        if state.image_format:
            ni = state.news_image
            m, _ = _assess_image(state, signals, risk)
            axes.append(AxisAssessment(heading="Media authenticity", state=m.state, label=m.label, summary=m.summary))
            cons = (ni.caption_consistency if ni else "").strip().lower()
            if ni and cons == "inconsistent" and ni.mismatches:
                ctx = ("MISLEADING_CONTEXT", "Image does not match the claim", "; ".join(ni.mismatches[:3]))
            elif verdict_value == "DEBUNKED_BY_SOURCE" and m.state != "MANIPULATED":
                ctx = ("MISLEADING_CONTEXT", "Misleading context",
                       "No editing traces were found in the image, but the claim it is used to support is "
                       "contradicted by sources.")
            elif verdict_value == "VERIFIED_BY_SOURCE" and cons in ("consistent", "no_caption"):
                ctx = ("SUPPORTED", "Consistent with sources", "The claim is supported by sources and nothing visible conflicts with it.")
            elif not ni:
                ctx = ("INCONCLUSIVE", "Inconclusive", "Gemini could not read the image, so image and claim were not compared.")
            else:
                ctx = ("UNVERIFIED", "Not established",
                       "Nothing visible contradicts the claim, but an image alone cannot show when or where it was "
                       "taken or that the event happened.")
            axes.append(AxisAssessment(heading="Context consistency", state=ctx[0], label=ctx[1], summary=ctx[2]))
            if ni:
                if ni.visual_description:
                    notes.append("What the image shows: " + ni.visual_description.strip()[:260])
                if ni.time_place_clues:
                    notes.append("Visible time/place clues: " + "; ".join(ni.time_place_clues[:4]))
                extracted.extracted_text = ni.extracted_text or extracted.extracted_text
            caveats.append("A visually authentic image does not make the claim true, and an edited image does not make every claim false")
        if getattr(state, "media_mime", ""):  # claim heard in a video / audio file
            m_axes = _assess_media(state)[:3]
            axes += [a for a in m_axes if a.state != "NOT_ASSESSED"]
            bad = [a for a in m_axes if a.state in ("MANIPULATED", "LIKELY_SYNTHETIC")]
            ctx_obs = [o for o in (media.observations if media else [])
                       if o.kind.strip().lower() == "context" and o.evidence.strip() and o.severity.lower() != "low"]
            if not media:
                ctx = ("INCONCLUSIVE", "Inconclusive", "Gemini could not examine the file, so content and claim were not compared.")
            elif verdict_value == "DEBUNKED_BY_SOURCE" and not bad:
                ctx = ("MISLEADING_CONTEXT", "Misleading context",
                       "No manipulation was observed in the recording, but the claim made in it is contradicted by "
                       "sources. A genuine recording can carry a false statement.")
            elif ctx_obs:
                ctx = ("INCONCLUSIVE", "Context questions",
                       "; ".join(f"{o.timestamp + ': ' if o.timestamp else ''}{o.title}" for o in ctx_obs[:3]))
            elif verdict_value == "VERIFIED_BY_SOURCE" and not bad:
                ctx = ("SUPPORTED", "Consistent with sources", "The claim is supported by sources and nothing observed conflicts with it.")
            else:
                ctx = ("UNVERIFIED", "Not established",
                       "A recording alone cannot show when, where or by whom it was made, or that what is said is true.")
            axes.append(AxisAssessment(heading="Context consistency", state=ctx[0], label=ctx[1], summary=ctx[2]))
            caveats += ["A genuine recording can contain a false claim, and a synthetic voice can state a true one",
                        "Speakers are not identified: who is speaking was not verified"]
            if media:
                caveats += [l for l in media.limitations[:2] if l.strip()]
                if media.description:
                    notes.append("What Gemini observed: " + media.description.strip()[:300])
                if media.language:
                    notes.append(f"Speech language: {media.language}.")
        has_ctx = (state.image_format or getattr(state, "media_mime", "")) and axes[-1].state == "MISLEADING_CONTEXT"
        overall = Assessment(state=axes[-1].state if has_ctx else axes[0].state,
                             label=axes[-1].label if has_ctx else axes[0].label, summary=axes[0].summary)
    else:
        provided = []
    if state.input_type == "media":
        axes = _assess_media(state)
        order = {"MANIPULATED": 0, "LIKELY_SYNTHETIC": 1, "INCONCLUSIVE": 2, "LIKELY_AUTHENTIC": 3}
        ranked = sorted((a for a in axes[:3] if a.state in order), key=lambda a: order[a.state])
        worst = ranked[0] if ranked else axes[0]
        overall = Assessment(state=worst.state, label=worst.label, summary=f"{worst.heading}: {worst.summary}")
        recommendation = MEDIA_RECOMMENDATION.get(worst.state, MEDIA_RECOMMENDATION["INCONCLUSIVE"])
        caveats = ["Only Gemini examined this file; no pretrained deepfake or voice-spoof detector was run",
                   "Detecting synthetic video or cloned voices by inspection is unreliable; a clean result is not proof",
                   NOT_TRUE_NOTE.replace("image", "recording"),
                   "Speakers are not identified: who is speaking was not verified"]
        if media:
            caveats += [l for l in media.limitations[:2] if l.strip()]
            if media.description:
                notes.append("What Gemini observed: " + media.description.strip()[:300])
            if media.language:
                notes.append(f"Speech language: {media.language}.")
        notes.append(SPECIALIST_NOTE)
        boosters = ["The original file from the person or channel that first published it",
                    "The upload date and source page of the earliest copy",
                    "An independent recording or report of the same event",
                    "A specialist deepfake / voice-spoof detector run on the original file"]
    media = None
    if state.input_type == "image":
        intent = state.intent
        media, artifact = _assess_image(state, signals, risk)
        overall = media if intent == "synthetic_detection" else artifact
        boosters = BOOSTERS[intent]
        if intent == "synthetic_detection":
            recommendation = SYNTHETIC_RECOMMENDATION[media.state]
            caveats = ["Detecting AI generation from pixels is unreliable; this is an evidence summary, not a verdict",
                       NOT_TRUE_NOTE, "EXIF and ELA indicate editing risk, not proof either way"]
            if visual:
                caveats += [l for l in visual.limitations[:2] if l.strip()]
                if visual.authentic_cues:
                    notes.append("Cues consistent with a genuine capture: " + "; ".join(visual.authentic_cues[:4]))
                if visual.description:
                    notes.append("What Gemini sees: " + visual.description.strip()[:300])
        else:
            base = ARTIFACT_RECOMMENDATION[artifact.state]
            extra = llm.recommendation.strip() if (llm and artifact.state != "UNVERIFIED") else ""
            recommendation = f"{base} {extra}".strip()
            caveats.insert(0, "A screenshot cannot prove that a payment, message or notice really happened or was sent")
            caveats.append("AI generation was not assessed in this mode")

    if state.input_type == "text" and getattr(state, "mode", "") == "ai_generated":
        axis = _assess_text(state)
        axes, overall = [axis], Assessment(state=axis.state, label=axis.label, summary=axis.summary)
        recommendation = TEXT_RECOMMENDATION[axis.state]
        caveats = ["Detecting AI-written text is unreliable: fluent human writing and edited AI writing look alike",
                   "This says nothing about whether the text is true: use News / Claim mode for that",
                   "A person can write formulaic text, and AI text can be edited to read naturally"]
        if visual:
            caveats += [l for l in visual.limitations[:2] if l.strip()]
            if visual.authentic_cues:
                notes.append("Cues consistent with human writing: " + "; ".join(visual.authentic_cues[:4]))

    report = TrustReport(
        analysis_mode=state.analysis_mode, input_type=state.input_type, analysis_intent=intent,
        assessment_axes=axes, inputs_provided=provided, claims=claim_rows, timeline=timeline, article=getattr(state, "article", None),
        overall_assessment=overall, media_assessment=media, artifact_assessment=artifact,
        confidence_boosters=boosters,
        classification=extracted.classification or "other", trust_score=trust_score, risk_level=risk,
        verdict=verdict_value, confidence=confidence, extracted=extracted, signals=signals,
        score_breakdown=breakdown, evidence=evidence, recommendation=recommendation,
        what_to_verify=what_to_verify[:5], inconsistencies=inconsistencies[:6], notes=notes, ela=state.ela,
        gemini_error="gemini_unavailable" if state.crew_error else None,
        agents_used=state.agents_used, caveats=caveats,
    )
    if getattr(state, "mode", ""):
        from app.services import fusion  # mode-aware layer: evidence schema, per-dimension confidence, stages
        report = fusion.enrich(report, state)
    return report
