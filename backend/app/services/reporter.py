"""Merge + dedupe signals, enforce safeguards, score, compute the claim verdict → TrustReport.

Safeguards live here (not in prompts): the LLM can add signals or raise severity, never remove or
downgrade a RULE signal; score and verdict are computed in Python only.
"""
import re
from urllib.parse import urlparse

from app.models.llm_outputs import SIGNAL_KEYS, Extracted, LLMSignal
from app.models.report import Assessment, AxisAssessment, CategoryBreakdown, Evidence, Signal, TrustReport
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


def verdict(evidence: list[Evidence], factcheck_urls: set[str]) -> tuple[str, float, list[str]]:
    """VERIFIED/DEBUNKED only from a fact-check outlet with an explicit rating; otherwise UNVERIFIED."""
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
    if refutes and supports:
        return "UNVERIFIED", 0.3, ["Sources disagree: some fact-checks refute the claim and some support it."]
    if refutes:
        soft = all(SOFT_RE.search(e.rating) for e in refutes)
        return "DEBUNKED_BY_SOURCE", 0.6 if soft else 0.9, []
    if supports:
        return "VERIFIED_BY_SOURCE", 0.8, []
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
    gemini_ok = not state.crew_error
    synthetic = state.intent == "synthetic_detection"
    visual = state.visual

    # --- media ---
    # counted from Gemini's own list: merged signals are de-duplicated by key
    ai = [i for i in (visual.indicators if visual else [])
          if i.kind.strip().lower() == "ai_generation" and i.evidence.strip()]
    manip = by_key.get("manipulation_indicator")
    strong = [s for s in signals if s.category in ("visual_analysis", "image_forensics") and s.severity != "low"]
    claimed = (visual.assessment.strip().lower() if visual else "")
    if (ela and ela.severity == "high") or (manip and manip.severity == "high" and manip.evidence and claimed == "manipulated"):
        media = Assessment(state="MANIPULATED", label="Manipulation detected",
                           summary="Signs of editing were found in a specific region of the image. This is evidence, not proof.")
    elif synthetic and claimed == "likely_synthetic" and (any(i.severity.lower() == "high" for i in ai)
                                                        or sum(i.severity.lower() != "low" for i in ai) >= 2):
        media = Assessment(state="LIKELY_SYNTHETIC", label="Likely synthetic / AI-generated",
                           summary="Several visual indicators of AI generation were found. Pixel-based detection is unreliable, so treat this as likely, not certain.")
    elif synthetic and gemini_ok and claimed == "likely_authentic" and not strong:
        media = Assessment(state="LIKELY_AUTHENTIC", label="Likely authentic",
                           summary="No obvious synthetic or editing indicators were detected. A carefully made fake can still pass.")
    elif synthetic:
        why = ("Gemini's visual examination was unavailable, so only metadata and compression checks ran."
               if not gemini_ok else "The indicators found are weak or mixed.")
        media = Assessment(state="INCONCLUSIVE", label="Inconclusive", summary=why)
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


MEDIA_KIND_KEY = {"visual_manipulation": "manipulation_indicator", "ai_generation": "ai_generation_indicator",
                  "audio": "audio_anomaly", "av_sync": "av_inconsistency", "context": "inconsistency"}
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


def _media_axis(heading: str, claimed: str, obs: list, gemini_ok: bool, what: str) -> AxisAssessment:
    """One media question, decided here from Gemini's observations (its own label is only one input)."""
    claimed = (claimed or "").strip().lower()
    strong = [o for o in obs if o.severity.lower() != "low" and o.evidence.strip()]
    high = [o for o in strong if o.severity.lower() == "high"]
    where = ", ".join(sorted({o.timestamp for o in strong if o.timestamp})[:4])
    at = f" (at {where})" if where else ""
    if not gemini_ok:
        return AxisAssessment(heading=heading, state="INCONCLUSIVE", label="Inconclusive",
                              summary="Gemini could not examine the file, so nothing was assessed.")
    if claimed == "not_applicable":
        return AxisAssessment(heading=heading, state="NOT_ASSESSED", label="Not applicable",
                              summary=f"The file has no {what} to assess.")
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
                              summary="Nothing suspicious was observed. A well-made fake can still pass, and no specialist detector was run.")
    return AxisAssessment(heading=heading, state="INCONCLUSIVE", label="Inconclusive",
                          summary="The observations are weak or mixed." + at)


def _assess_media(state) -> list[AxisAssessment]:
    m, ok = state.media, not state.crew_error
    obs = m.observations if m else []
    kinds = lambda *k: [o for o in obs if o.kind.strip().lower() in k]  # noqa: E731
    # decided from the file's own type, not from the model's description of it
    is_audio_only = (getattr(state, "media_mime", "") or "").startswith("audio/")
    axes = [
        _media_axis("Visual authenticity", "not_applicable" if is_audio_only else (m.visual_assessment if m else ""),
                    kinds("visual_manipulation", "ai_generation"), ok, "picture"),
        _media_axis("Audio authenticity", m.audio_assessment if m else "", kinds("audio"), ok, "audio"),
        _media_axis("Audio-visual consistency", "not_applicable" if is_audio_only else (m.av_consistency if m else ""),
                    kinds("av_sync"), ok, "combined picture and sound"),
    ]
    if m and m.spoken_claims:
        axes.append(AxisAssessment(
            heading="Spoken claims", state="UNVERIFIED", label="Not verified",
            summary=f"{len(m.spoken_claims)} factual claim(s) were heard but not checked against any source. An "
                    "authentic recording can still contain a false claim: paste the claim into Fake News / Claim."))
    else:
        axes.append(AxisAssessment(heading="Spoken claims", state="NOT_ASSESSED", label="None identified",
                                   summary="No checkable factual claim was identified in the speech."))
    return axes


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
        for o in media.observations:
            when = f"At {o.timestamp}: " if o.timestamp.strip() else ""
            llm_signals.append(LLMSignal(
                key=MEDIA_KIND_KEY.get(o.kind.strip().lower(), "visual_inconsistency"), title=o.title,
                severity=o.severity, explanation=o.explanation, evidence=(when + o.evidence).strip() if o.evidence.strip() else "",
                uncertainty=o.uncertainty))
    signals = merge(rule_signals, llm_signals)

    if state.all_urls_match_claimed:  # known-org attenuation: a real bank SMS is not a scam for sounding urgent
        signals = [s for s in signals if s.key != "url_shortener"]
        for s in signals:
            if s.key in ("urgency", "action_pressure", "kyc_threat", "threat") and "injection" not in s.title.lower():
                s.severity = "low"
        notes.append("Every link is on the claimed organisation's own domain; pressure signals were capped at low.")

    extracted: Extracted = state.extracted
    evidence: list[Evidence] = []
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
            evidence.append(Evidence(source=item.source or urlparse(item.url).netloc, url=item.url,
                                     rating=item.rating or "none", stance=item.stance, quote=item.quote))
        if dropped:
            notes.append(f"{dropped} evidence item(s) were dropped because their link did not come from a search tool.")
        verdict_value, confidence, vnotes = verdict(evidence, factcheck_urls)
        notes += vnotes
        if state.tool_errors:
            notes.append("A search tool failed during verification; results may be incomplete.")
        if verdict_value == "DEBUNKED_BY_SOURCE":
            top = next(e for e in evidence if e.stance == "refutes" and DEBUNK_RE.search(e.rating))
            signals.append(Signal(
                key="debunked_by_source", title="Debunked by fact-checker", severity="high" if confidence >= 0.9 else "medium",
                category="claim_evidence", sources=["RULE"],
                explanation="A published fact-check rates this claim as false or misleading.",
                evidence=f"{top.source}: \"{top.rating}\""))
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

    return TrustReport(
        analysis_mode=state.analysis_mode, input_type=state.input_type, analysis_intent=intent,
        assessment_axes=axes,
        overall_assessment=overall, media_assessment=media, artifact_assessment=artifact,
        confidence_boosters=boosters,
        classification=extracted.classification or "other", trust_score=trust_score, risk_level=risk,
        verdict=verdict_value, confidence=confidence, extracted=extracted, signals=signals,
        score_breakdown=breakdown, evidence=evidence, recommendation=recommendation,
        what_to_verify=what_to_verify[:5], inconsistencies=inconsistencies[:6], notes=notes, ela=state.ela,
        gemini_error="gemini_unavailable" if state.crew_error else None,
        agents_used=state.agents_used, caveats=caveats,
    )
