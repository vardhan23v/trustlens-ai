"""Mode-aware assessment layer (NEWS / CLAIM and AI-GENERATED).

Takes the report built by reporter.py and makes it answer the mode's own questions:
  * every finding is re-expressed in the unified evidence schema, tagged with the dimension it bears on;
  * each dimension (claim, media authenticity, context) gets its own state and its own confidence,
    computed only from evidence relevant to that dimension;
  * missing evidence adds nothing (it is never negative evidence), a failed search is
    EVIDENCE_UNAVAILABLE rather than "false", and conflicting sources stay visible as INCONCLUSIVE;
  * "what would change the assessment" is derived from what this particular report lacks.

This is relevance gating written as explicit rules. It is not a learned or calibrated fusion model.
"""
from app.config import settings
from app.ml import registry
from app.models.evidence import EvidenceSignal
from app.models.report import Assessment, AxisAssessment, Evidence, Signal, SpecialistModel, Stage, TrustReport
from app.services import specialists
from app.services.news import retrieval

LISTED = {"official", "wire", "established", "factcheck"}
MEDIA_CATEGORIES = {"image_forensics", "visual_analysis"}
SCORE_SCOPE = {
    "ai_generated": "Counts forensic and visual/audio indicators only. A high number means few indicators were "
                    "found; it is not proof that the media is authentic.",
    "news_claim": "Counts risk signals found in the content and sources that contradict the claim. It does not "
                  "measure whether the claim is true: read the claim, media and context assessments separately.",
}
TIER_RELIABILITY = {"official": "high: official or primary source", "factcheck": "high: recognised fact-checker",
                    "wire": "high: wire agency", "established": "medium: established news organisation",
                    "other": "low: unlisted source, not counted toward the claim state"}
STANCE = {"supports": "SUPPORTS", "refutes": "CONTRADICTS", "mixed": "NEUTRAL"}


def _signal_evidence(i: int, s: Signal, modality: str, gemini_model: str) -> EvidenceSignal:
    rule = "RULE" in s.sources
    if s.category in MEDIA_CATEGORIES:
        dim, direction, rel = "media_authenticity", "CONTRADICTS", "whether the media itself is authentic"
    elif s.category == "claim_evidence":
        dim, direction, rel = "claim", "CONTRADICTS", "whether the claim is supported"
    else:
        dim, direction, rel = "content_risk", "NEUTRAL", "risk wording in the extracted text; says nothing about whether the claim is true"
    if rule and s.category == "image_forensics":
        reliability = "medium: measures processing of the file, which ordinary re-saving also causes"
    elif rule:
        reliability = "medium: deterministic pattern match"
    else:
        reliability = "low to medium: a model's observation, not a calibrated probability"
    return EvidenceSignal(
        signal_id=f"sig-{i:02d}-{s.key}", category=s.category,
        modality="text" if dim == "content_risk" else modality,
        # a finding raised only by a pretrained model is MODEL evidence, not Gemini's
        source_type="RULE" if rule else "GEMINI" if "GEMINI" in s.sources else "MODEL",
        model=gemini_model if "GEMINI" in s.sources else "",
        finding=s.title, direction=direction, confidence=s.severity, reliability=reliability, relevance=rel,
        dimension=dim, evidence=s.evidence, limitations=[s.uncertainty] if s.uncertainty else [])


def _source_evidence(i: int, e: Evidence) -> EvidenceSignal:
    limits = (["Stance was read from the source's headline by Gemini"
               + (f"; the NLI model reads it as {e.nli_label} ({e.nli_score:.2f})" if e.nli_label else ", not checked by an NLI model")]
              + ([e.stance_note] if e.stance_note else []) + ([] if e.published else ["Publication date unknown"]))
    return EvidenceSignal(
        signal_id=f"src-{i:02d}", category="claim_evidence", modality="external", source_type="EXTERNAL_SOURCE",
        finding=e.title or e.quote, direction=STANCE.get(e.stance, "UNKNOWN"),
        confidence="medium" if e.rating not in ("", "none") else "low",
        reliability=TIER_RELIABILITY.get(e.source_type, TIER_RELIABILITY["other"]),
        relevance=(f"atomic claim {e.claim_index}" if e.claim_index else "the claim as a whole")
        + (f"; semantic relevance {e.relevance:.2f}" if e.relevance is not None else ""), dimension="claim",
        evidence=e.quote, source_reference=e.url, limitations=limits)


def _independent(items: list[Evidence]) -> int:
    return len({retrieval.registrable(e.source_site) or e.source.lower() for e in items})


def _claim_confidence(state_name: str, evidence: list[Evidence]) -> tuple[str, str]:
    listed = [e for e in evidence if e.source_type in LISTED]
    side = [e for e in listed if e.stance == ("supports" if state_name == "SUPPORTED" else "refutes")]
    if state_name not in ("SUPPORTED", "CONTRADICTED"):
        n = _independent(listed)
        return "low", (f"{n} listed source(s) were found but they do not settle the claim." if n else
                       "No listed source spoke to the claim.")
    n = _independent(side)
    top = any(e.source_type in ("official", "factcheck") for e in side)
    level = "high" if (top and n >= 2) else "medium" if (top or n >= 2) else "low"
    basis = (f"{n} independent listed source(s) on this side" + (", including an official source or fact-checker" if top else "")
             + ". Copies from one site count once.")
    want = "entailment" if state_name == "SUPPORTED" else "contradiction"
    checked = [e for e in side if e.nli_label]
    if checked:  # the NLI model read these headlines itself
        agree = sum(e.nli_label == want for e in checked)
        basis += f" The NLI model independently reads {agree} of {len(checked)} of their headlines the same way."
        if agree == 0 and level == "high":
            level = "medium"  # no headline is corroborated by the second model
    return level, basis


def _media_confidence(axis: Assessment, signals: list[Signal], detectors: bool, gemini_ok: bool) -> tuple[str, str]:
    measured = [s for s in signals if s.category == "image_forensics" and "RULE" in s.sources and s.severity != "low"]
    if axis.state == "NOT_ASSESSED":
        return "", ""
    if not gemini_ok:
        return "low", "Gemini's examination was unavailable; only deterministic checks ran."
    if axis.state == "MANIPULATED" and measured:
        return "medium", "A measured forensic finding supports this, alongside Gemini's observations."
    if detectors and axis.heading in ("Synthetic / manipulation assessment", "Media authenticity", "Visual authenticity"):
        if axis.label == "Evidence conflicts":
            return "low", "The pretrained detector and Gemini disagree, so neither reading is relied on."
        if axis.state in ("LIKELY_SYNTHETIC", "LIKELY_AUTHENTIC"):
            return "medium", "A pretrained detector and Gemini's observations point the same way. Detectors of this kind are wrong on a meaningful share of files."
        return "low", "A pretrained detector ran but was undecided, and Gemini's observations are weak or mixed."
    if axis.heading == "AI-authorship assessment":
        return "low", "Rests on Gemini's reading of the style only. No AI-text detector ran, and such detection is unreliable."
    return "low", "Rests on Gemini's observations only: no specialist detector ran, and visual inspection is unreliable."


def _change_factors(report: TrustReport, state, claim_axis: AxisAssessment | None) -> list[str]:
    out: list[str] = []
    kind = report.media_type
    if kind == "text" and report.mode == "ai_generated":
        out += ["A longer sample by the same author: short text carries little signal",
                "Drafts, edit history or the document's original source",
                "Earlier writing by the same person, to compare style"]
    if kind == "text" and report.mode == "news_claim":
        out.append("The original post, article or broadcast the text came from, with its date")
    if kind == "image":
        if report.ela.status != "ok":
            out.append("The original JPEG instead of a screenshot or PNG copy: compression analysis could not run on this file")
        if not any(s.category == "image_forensics" for s in report.signals):
            out.append("The original camera file with its metadata intact (this copy carries no usable metadata)")
        out.append("The page or account where the image first appeared, and its upload date")
    elif kind == "video":
        out.append("The original upload rather than a forwarded or re-encoded copy")
        if state.sampled_frames:
            out.append(f"A temporal deepfake detector run on the full video: only {state.sampled_frames} still frames were examined here")
        if not report.media_metadata.get("creation_time"):
            out.append("A file that still carries its creation time (this one has none in its metadata)")
    elif kind == "audio":
        out.append("Uncompressed or original-quality audio: compression hides and mimics synthesis artefacts")
        out.append("A longer sample of the same speaker from a known-genuine recording for comparison")
    if any(m.status in ("MODEL_UNAVAILABLE", "FAILED") and m.slot in ("image_synthetic", "video_deepfake", "audio_spoof")
           for m in report.specialist_models):
        out.append("A specialist synthetic-media detector run on the original file (one could not be run for this analysis)")
    elif kind in ("video", "audio"):
        out.append("A speech-synthesis detector validated on modern voice cloning (the one installed is weak evidence)")
    if report.mode == "news_claim" and claim_axis is not None:
        listed = [e for e in report.evidence if e.source_type in LISTED]
        if claim_axis.state == "NOT_ASSESSED":
            out.insert(0, "A clearer capture in which the claim is legible or audible")
        elif claim_axis.state == "EVIDENCE_UNAVAILABLE":
            out.insert(0, "Running the check again when the search service is reachable")
        elif not listed:
            out.insert(0, "An official statement or primary document that addresses the claim")
            out.insert(1, "Coverage of the claim by two independent established news organisations")
        elif _independent(listed) < 2:
            out.insert(0, "A second independent listed source: one site alone does not settle the claim")
        if claim_axis.label == "Sources conflict":
            out.insert(0, "A primary source (official record or statement) to resolve the conflict between sources")
        if listed and any(not e.published for e in listed):
            out.append("Publication dates for the sources that have none, to place them on the timeline")
        if not settings.FACTCHECK_API_KEY:
            out.append("A fact-check database lookup (Google Fact Check Tools is not configured on this deployment)")
    seen: set[str] = set()
    return [x for x in out if not (x in seen or seen.add(x))][:7]


def enrich(report: TrustReport, state) -> TrustReport:
    mode, kind = state.mode, state.media_type
    gemini_ok = not state.crew_error or bool(state.media or state.visual or state.news_image)
    report.mode, report.media_type, report.media_metadata = mode, kind, dict(state.media_meta)
    report.stages = [Stage(**st) for st in state.stages]
    report.specialist_models = [SpecialistModel(**m) for m in registry.status(mode, kind, state.model_runs)]
    report.score_scope = SCORE_SCOPE[mode]
    report.notes = [n for n in report.notes if not n.startswith("Specialist models:")]
    out = state.model_out
    # a detector result that may be used for this file (the image detector does not apply to screenshots / documents)
    image_det = out.get("p_generated") is not None and specialists.detector_applies(state)
    detectors = image_det or bool(out.get("frame_scores"))
    if out.get("p_generated") is not None and not image_det:
        report.notes.append(f"The AI-image detector scored this image {out['p_generated']:.2f}, but it was trained on "
                            "photographs: for screenshots, documents and text graphics its score is shown and not used.")
    # two independent readings of the same content: how far do they agree?
    gem_text = (state.media.transcript if state.media else "")
    agree = specialists.agreement(gem_text, out.get("asr_text", "")) if gem_text else None
    if agree is not None:
        report.notes.append(f"Transcript check: Gemini's transcript and the Whisper model's transcript agree {agree:.0%} word for word."
                            + (" They differ noticeably, so quotes from the speech should be checked by ear." if agree < 0.6 else ""))
    elif out.get("asr_text") and not state.media:
        report.notes.append("The transcript shown comes from the Whisper model alone: Gemini's examination was unavailable.")
    gem_ocr = (state.news_image.extracted_text if state.news_image else "")
    agree_ocr = specialists.agreement(gem_ocr, out.get("ocr_text", "")) if gem_ocr else None
    if agree_ocr is not None:
        report.notes.append(f"Text check: Gemini's reading of the image and the OCR model's reading agree {agree_ocr:.0%} word for word.")
    elif out.get("ocr_text") and not state.news_image and mode == "news_claim":
        report.notes.append("The text shown was read by the OCR model alone: Gemini could not read the image.")
    if state.media_mime and not state.sampled_frames and kind == "video" and state.media:
        report.notes.append("Frame sampling was unavailable, so Gemini received the original video file.")
    if kind == "video" and state.sampled_frames:
        report.caveats.append(f"Only {state.sampled_frames} sampled still frames were examined: motion, flicker and "
                              "lip-sync between frames were not analysed")

    claim_axis = None
    if mode == "ai_generated":
        if kind == "image" and report.media_assessment:
            m = report.media_assessment
            report.assessment_axes = [AxisAssessment(heading="Synthetic / manipulation assessment", state=m.state,
                                                     label=m.label, summary=m.summary)]
            report.artifact_assessment = None
        if not report.verdict:
            report.confidence = None
    else:
        claim_axis = next((a for a in report.assessment_axes if a.heading == "Claim assessment"), None)
        if claim_axis is not None:
            conflict = any(n.startswith("Sources disagree") for n in report.notes)
            if not state.text.strip():
                if state.crew_error:
                    claim_axis.state, claim_axis.label = "INCONCLUSIVE", "Could not be read"
                    claim_axis.summary = "Gemini could not read the file, so no claim was extracted or checked."
                else:
                    claim_axis.state, claim_axis.label = "NOT_ASSESSED", "No checkable claim found"
                    claim_axis.summary = "No factual claim could be extracted from this file, so nothing was checked against sources."
                report.recommendation = ("No claim was verified. Treat any claim attached to this file as unverified "
                                         "and look for it in established news sources before sharing.")
            elif conflict:
                claim_axis.state, claim_axis.label = "INCONCLUSIVE", "Sources conflict"
                claim_axis.summary = "Listed sources disagree: some support the claim and some contradict it. Both sides are listed below."
            elif not report.evidence and (state.tool_errors or state.crew_error):
                claim_axis.state, claim_axis.label = "EVIDENCE_UNAVAILABLE", "Evidence unavailable"
                claim_axis.summary = ("The evidence search could not be completed. This says nothing about whether the "
                                      "claim is true or false.")
                report.recommendation = ("The claim could not be checked right now. Treat it as unverified and try "
                                         "again later; a failed search is not evidence that the claim is false.")
            claim_axis.confidence, claim_axis.basis = _claim_confidence(claim_axis.state, report.evidence)
            ctx = next((a for a in report.assessment_axes if a.heading == "Context consistency"), None)
            lead = ctx if (ctx is not None and ctx.state == "MISLEADING_CONTEXT") else claim_axis
            report.overall_assessment = Assessment(state=lead.state, label=lead.label, summary=claim_axis.summary)
            if ctx is not None:
                ctx.confidence = claim_axis.confidence if ctx.state in ("MISLEADING_CONTEXT", "SUPPORTED") else "low"
                ctx.basis = ("Follows from the claim assessment and the media findings." if ctx.confidence != "low"
                             or ctx.state in ("MISLEADING_CONTEXT", "SUPPORTED")
                             else "A file alone cannot establish when, where or by whom it was made.")

    for a in report.assessment_axes:
        if a is claim_axis or a.heading in ("Context consistency", "Spoken claims") or a.confidence:
            continue
        a.confidence, a.basis = _media_confidence(a, report.signals, detectors, gemini_ok)
    if report.overall_assessment and report.assessment_axes:
        match = next((a for a in report.assessment_axes if a.state == report.overall_assessment.state), None)
        if match:
            report.overall_assessment.confidence, report.overall_assessment.basis = match.confidence, match.basis

    ev: list[EvidenceSignal] = [_signal_evidence(i, s, kind, settings.GEMINI_MODEL)
                                for i, s in enumerate(report.signals, 1)]
    cues = (state.visual.authentic_cues if state.visual else [])[:4]
    for i, cue in enumerate(cues, 1):
        ev.append(EvidenceSignal(
            signal_id=f"cue-{i:02d}", category="visual_analysis", modality=kind, source_type="GEMINI",
            model=settings.GEMINI_MODEL, finding="Cue consistent with a genuine capture", direction="SUPPORTS",
            confidence="low", reliability="low: generators can reproduce such cues",
            relevance="whether the media itself is authentic", dimension="media_authenticity", evidence=cue))
    ev += [_source_evidence(i, e) for i, e in enumerate(report.evidence, 1)]
    for m in report.specialist_models:
        direction, conf, finding = "UNKNOWN", "", m.status
        if m.status == "RAN":
            finding, score = m.detail, None
            if m.slot == "image_synthetic":
                score = out.get("p_generated")
            elif m.slot == "audio_spoof":
                score = out.get("p_synthetic")
            elif m.slot == "video_deepfake" and out.get("frame_scores"):
                score = sum(p for _, p in out["frame_scores"]) / len(out["frame_scores"])
            if score is not None:
                direction = "CONTRADICTS" if score >= specialists.HIGH else "SUPPORTS" if score <= specialists.LOW else "NEUTRAL"
                conf = "low" if m.slot == "audio_spoof" or direction == "NEUTRAL" else "medium"
                if m.slot == "image_synthetic" and not image_det:
                    direction, conf = "NEUTRAL", "low"
            elif m.slot in ("asr", "ocr"):
                direction, conf = "NEUTRAL", "medium"
            elif m.slot in ("embedding", "nli"):
                direction, conf = "NEUTRAL", "medium"  # per-source results are on each EXTERNAL_SOURCE item
        ev.append(EvidenceSignal(
            signal_id=f"model-{m.slot}", category="specialist_model", modality=kind, source_type="MODEL",
            model=m.candidate, finding=finding, direction=direction, confidence=conf,
            reliability=("low: unproven for this kind of input" if m.slot == "audio_spoof" else
                         "medium: pretrained model, not calibrated on this data") if m.status == "RAN" else "",
            relevance=m.task, dimension="claim" if m.slot in ("embedding", "nli") else
            "content_risk" if m.slot in ("asr", "ocr") else "media_authenticity",
            evidence=m.detail if m.status == "RAN" else "",
            limitations=m.limitations if m.status == "RAN" else ([m.detail] if m.detail else [])))
    report.evidence_signals = ev
    report.change_factors = _change_factors(report, state, claim_axis)
    if mode == "ai_generated":
        report.confidence_boosters = report.change_factors
    return report
