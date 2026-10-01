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
        source_type="RULE" if rule else "GEMINI", model="" if rule and len(s.sources) == 1 else gemini_model,
        finding=s.title, direction=direction, confidence=s.severity, reliability=reliability, relevance=rel,
        dimension=dim, evidence=s.evidence, limitations=[s.uncertainty] if s.uncertainty else [])


def _source_evidence(i: int, e: Evidence) -> EvidenceSignal:
    return EvidenceSignal(
        signal_id=f"src-{i:02d}", category="claim_evidence", modality="external", source_type="EXTERNAL_SOURCE",
        finding=e.title or e.quote, direction=STANCE.get(e.stance, "UNKNOWN"),
        confidence="medium" if e.rating not in ("", "none") else "low",
        reliability=TIER_RELIABILITY.get(e.source_type, TIER_RELIABILITY["other"]),
        relevance=f"atomic claim {e.claim_index}" if e.claim_index else "the claim as a whole", dimension="claim",
        evidence=e.quote, source_reference=e.url,
        limitations=["Stance was read from the source's headline by Gemini, not by an NLI model"]
        + ([] if e.published else ["Publication date unknown"]))


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
    return level, (f"{n} independent listed source(s) on this side"
                   + (", including an official source or fact-checker" if top else "")
                   + ". Copies from one site count once.")


def _media_confidence(axis: Assessment, signals: list[Signal], detectors: bool, gemini_ok: bool) -> tuple[str, str]:
    measured = [s for s in signals if s.category == "image_forensics" and "RULE" in s.sources and s.severity != "low"]
    if axis.state == "NOT_ASSESSED":
        return "", ""
    if not gemini_ok:
        return "low", "Gemini's examination was unavailable; only deterministic checks ran."
    if axis.state == "MANIPULATED" and measured:
        return "medium", "A measured forensic finding supports this, alongside Gemini's observations."
    if detectors:
        return "medium", "A specialist detector and Gemini's observations were both available."
    return "low", "Rests on Gemini's observations only: no specialist detector ran, and visual inspection is unreliable."


def _change_factors(report: TrustReport, state, claim_axis: AxisAssessment | None) -> list[str]:
    out: list[str] = []
    kind = report.media_type
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
    if any(m.status == "MODEL_UNAVAILABLE" and m.slot in ("image_synthetic", "video_deepfake", "audio_spoof")
           for m in report.specialist_models):
        out.append("A specialist synthetic-media detector run on the original file (none is installed on this deployment)")
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
        if claim_axis.state == "INCONCLUSIVE":
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
    report.specialist_models = [SpecialistModel(**m) for m in registry.status(mode, kind)]
    report.score_scope = SCORE_SCOPE[mode]
    report.notes = [n for n in report.notes if not n.startswith(("Specialist models:", "Semantic-retrieval and NLI"))]
    detectors = any(m.status == "AVAILABLE" and m.slot in ("image_synthetic", "video_deepfake", "audio_spoof")
                    for m in report.specialist_models)
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
        ev.append(EvidenceSignal(
            signal_id=f"model-{m.slot}", category="specialist_model", modality=kind, source_type="MODEL",
            model=m.candidate, finding=m.status, direction="UNKNOWN", relevance=m.task,
            dimension="claim" if m.slot in ("embedding", "nli") else "media_authenticity",
            limitations=[m.detail] if m.detail else []))
    report.evidence_signals = ev
    report.change_factors = _change_factors(report, state, claim_axis)
    if mode == "ai_generated":
        report.confidence_boosters = report.change_factors
    return report
