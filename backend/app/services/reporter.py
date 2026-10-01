"""Merge + dedupe signals, enforce safeguards, score, compute the claim verdict → TrustReport.

Safeguards live here (not in prompts): the LLM can add signals or raise severity, never remove or
downgrade a RULE signal; score and verdict are computed in Python only.
"""
import re
from urllib.parse import urlparse

from app.models.llm_outputs import SIGNAL_KEYS, Extracted, LLMSignal
from app.models.report import CategoryBreakdown, Evidence, Signal, TrustReport
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
    signals = merge(rule_signals, llm.signals if llm else [])

    if state.all_urls_match_claimed:  # known-org attenuation: a real bank SMS is not a scam for sounding urgent
        signals = [s for s in signals if s.key != "url_shortener"]
        for s in signals:
            if s.key in ("urgency", "action_pressure") and "injection" not in s.title.lower():
                s.severity = "low"
        notes.append("URLs match the claimed organisation; urgency signals were capped at low.")

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
    signals.sort(key=lambda s: (-SEVERITY_RANK[s.severity], -s.penalty))

    if state.input_type == "claim":
        recommendation = CLAIM_RECOMMENDATION[verdict_value]
        caveats = (["No fact-check source was found; absence of evidence is not evidence of falsehood"]
                   if not evidence else
                   ["The verdict reflects published fact-checks found at analysis time, not an independent investigation"])
        caveats.append("The trust score reflects message-level signals only, not whether the claim is true")
    else:
        recommendation = RECOMMENDATION[risk]
        if risk != "LOW" and llm and llm.recommendation.strip():
            recommendation = f"{recommendation} {llm.recommendation.strip()}"
        caveats = (["Sender identity cannot be verified from text alone"] if state.input_type == "text" else
                   ["EXIF and ELA indicate editing risk, not proof either way",
                    "Absence of metadata is normal for screenshots"])
        if risk == "LOW":
            caveats.append("A well-made forgery with no scam markers would also show no risk signals")

    if state.crew_error:
        notes.append(_error_note(state.crew_error))

    return TrustReport(
        analysis_mode=state.analysis_mode, input_type=state.input_type,
        classification=extracted.classification or "other", trust_score=trust_score, risk_level=risk,
        verdict=verdict_value, confidence=confidence, extracted=extracted, signals=signals,
        score_breakdown=breakdown, evidence=evidence, recommendation=recommendation,
        what_to_verify=what_to_verify[:5], inconsistencies=inconsistencies[:6], notes=notes, ela=state.ela,
        gemini_error="gemini_unavailable" if state.crew_error else None,
        agents_used=state.agents_used, caveats=caveats,
    )
