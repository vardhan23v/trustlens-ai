"""Deterministic message rules (English + Hinglish). Each key fires at most once."""
import re
from dataclasses import dataclass, field

from app.models.report import Signal
from app.rules import domain_rules, url_rules
from app.rules.domain_rules import DomainContext
from app.rules.scoring import category_of
from app.utils.urls import ParsedUrl, extract_urls, parse_url

# key, severity, title, explanation, patterns
RULES: list[tuple[str, str, str, str, list[str]]] = [
    ("kyc_threat", "high", "KYC expiry threat",
     "KYC-expiry messages with a link are a common scam pattern; real KYC updates happen in the bank app or branch.",
     [r"kyc.{0,30}(expir|suspend|block|update|pending|complete|verif)", r"(update|complete|verify).{0,20}kyc",
      r"kyc.{0,20}(band|bandh|block)", r"kyc (karo|karein|kare)"]),
    ("threat", "high", "Threat of consequences",
     "Threatening to block an account or take legal action creates fear so the reader acts without checking.",
     [r"account.{0,25}(blocked|suspended|closed|deactivated|frozen|terminated)", r"legal action", r"\barrest",
      r"\bpenalty", r"court notice", r"(account|sim|number).{0,15}(band|block|suspend) ho jayega"]),
    ("credential_request", "high", "Asks for OTP or credentials",
     "Genuine organisations do not ask for an OTP, PIN, password or card details through a message or link.",
     [r"\botp\b", r"one[- ]time password", r"\bpin\b", r"\bcvv\b", r"password", r"passcode", r"\bmpin\b",
      r"aadhaar (number|no)", r"pan (number|no)", r"card (number|no)", r"otp (batao|share|bhejo)"]),
    ("financial_request", "high", "Payment request",
     "The content asks for money or directs a payment; confirm the payee through an official channel first.",
     [r"pay(ment)?.{0,25}(\bfee\b|charge|amount|₹|\brs\.?(?![a-z])|\binr\b)", r"(send|transfer).{0,20}(money|₹|\brs\.?(?![a-z])|amount)",
      r"processing fee", r"security deposit", r"refundable", r"\bupi (id|to)\b",
      r"@(okaxis|oksbi|okhdfcbank|okicici|ybl|paytm|upi)\b", r"(paise|paisa) (bhejo|bhej do)", r"payment (karo|karein)"]),
    ("registration_fee", "high", "Upfront fee request",
     "Asking for a fee before a job, registration or onboarding is a common advance-fee scam pattern.",
     [r"registration fee", r"joining fee", r"onboarding fee", r"training fee", r"document verification fee",
      r"laptop (fee|deposit)"]),
    ("urgency", "medium", "Urgency",
     "A tight deadline pressures the reader to act before checking.",
     [r"immediately", r"urgent(ly)?", r"within \d+ ?(hours?|hrs?|minutes?|mins?)", r"today only",
      r"last (chance|day)", r"expir(es|ing|ed) (today|tonight|in)", r"act now", r"right now",
      r"avoid (late fee|penalty|suspension)", r"\bturant\b", r"\babhi\b", r"\bjaldi\b", r"aaj hi"]),
    ("action_pressure", "medium", "Pressure to act",
     "The message pushes a specific action such as clicking, calling or forwarding.",
     [r"click(ing)? (here|the link|below|now|this)", r"tap (here|the link)", r"link par click", r"verify (now|your|immediately)",
      r"confirm (now|your)", r"download (now|the app|this app)", r"call (now|this number|immediately)",
      r"forward (this|to \d+)", r"share (with|to) \d+"]),
]
FAKE_AUTHORITY = [r"\brbi\b", r"reserve bank", r"income tax", r"cyber ?(cell|crime|police)", r"\bpolice\b", r"\bcourt\b",
                  r"government of india", r"\bministry\b", r"customs", r"\bcbi\b", r"enforcement directorate", r"\btrai\b"]
# Text addressed to an AI system. Content is data: this is reported, never obeyed.
INJECTION = [r"ignore (all |any |the |your )?(previous |prior |above |earlier )?(instructions|rules|prompts?)",
             r"ignore (all )?(rules|instructions) above", r"\b(ai|assistant|system|chatgpt|gemini|llm)\b\s*(assistant|model)?\s*:",
             r"(report|rate|mark|classify|label) this (message|content|text|image)? ?as (low|safe|genuine|no) ?(risk)?",
             r"disregard (the |all |any )?(above|previous|system)", r"you are now (a|an|in)\b"]
HIGH_RISK_KEYS = {"kyc_threat", "threat", "financial_request", "credential_request", "registration_fee"}


@dataclass
class RuleResult:
    signals: list[Signal] = field(default_factory=list)
    urls: list[ParsedUrl] = field(default_factory=list)
    domain: DomainContext = field(default_factory=DomainContext)


def _quote(text: str, m: re.Match) -> str:
    """The matched span, extended to whole words."""
    a, b = m.span()
    while a > 0 and text[a - 1].isalnum():
        a -= 1
    while b < len(text) and text[b].isalnum():
        b += 1
    return " ".join(text[a:b].split())


def _first_hit(text: str, patterns: list[str]) -> tuple[str, int] | None:
    first, count = None, 0
    for p in patterns:
        hits = list(re.finditer(p, text, re.I))
        count += len(hits)
        if hits and (first is None or hits[0].start() < first.start()):
            first = hits[0]
    return (_quote(text, first), count) if first else None


def _injection_quote(text: str) -> str:
    starts = [m.start() for p in INJECTION for m in re.finditer(p, text, re.I)]
    a = min(starts)
    while a > 0 and text[a - 1] not in "\n.[(":
        a -= 1
    return " ".join(text[a:a + 120].split()).strip("[]() ")


# Safety advice ("never share your OTP", "we will never ask for your PIN") is the opposite of a request.
_WARNING = re.compile(
    r"[^.!?\n]*\b(never|do not|don't|dont|not to|will not|won't|does not|doesn't|kabhi nahi|na karein|mat)\b"
    r"[^.!?\n]{0,60}\b(shar(e|es|ing)|asks?|asking|disclos(e|ing)|reveal|giv(e|ing)|tell|enter|batao|bataye)\b[^.!?\n]*"
    r"|[^.!?\n]*\b(share|batao|bataye|bhejo)\s+(mat|na|nahi|nahin)\b[^.!?\n]*", re.I)


def _without_warnings(text: str) -> str:
    return _WARNING.sub(lambda m: " " * len(m.group(0)), text)


def soften_for_document(signals: list[Signal]) -> list[Signal]:
    """Image mode: genuine documents routinely mention fees, penalties or passwords. A keyword hit with
    no link or impersonation problem behind it is therefore medium, not high (Gemini can still raise it)."""
    if any(s.category == "url_domain" or s.key == "impersonation" for s in signals):
        return signals
    for s in signals:
        if s.key in HIGH_RISK_KEYS and s.severity == "high":
            s.severity = "medium"
    return signals


def _mk(key: str, severity: str, title: str, explanation: str, evidence: str) -> Signal:
    return Signal(key=key, title=title, severity=severity, category=category_of(key), sources=["RULE"],
                  explanation=explanation, evidence=evidence)


def _unusual_language(text: str) -> str | None:
    hits = []
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 20 and sum(c.isupper() for c in letters) / len(letters) > 0.35:
        hits.append("heavy use of capital letters")
    if re.search(r"!{2,}", text) or text.count("!") >= 3:
        hits.append("repeated exclamation marks")
    m = re.search(r"dear (customer|user|sir|madam|winner)", text, re.I)
    if m:
        hits.append(f"generic greeting \"{m.group(0)}\"")
    if re.search(r"kindly do the needful", text, re.I):
        hits.append("stock phrase \"kindly do the needful\"")
    m = re.search(r"\b(sb1|hdfc-bank|1cici|hdfc1|payt[mn]\d)\b", text, re.I)
    if m:
        hits.append(f"organisation name spelt oddly (\"{m.group(0)}\")")
    return "; ".join(hits) if len(hits) >= 2 else None


def run(text: str) -> RuleResult:
    """Run text, URL and domain rules on raw text (text mode) or extracted_text (image mode)."""
    res = RuleResult()
    if not text.strip():
        return res
    fired: dict[str, Signal] = {}
    for key, sev, title, expl, patterns in RULES:
        hit = _first_hit(_without_warnings(text) if key == "credential_request" else text, patterns)
        if hit:
            quote, count = hit
            more = f" ({count} matching phrases found.)" if count > 1 else ""
            fired[key] = _mk(key, sev, title, expl + more, quote)

    if fired.keys() & {"threat", "financial_request", "credential_request", "urgency"}:
        hit = _first_hit(text, FAKE_AUTHORITY)
        if hit:
            fired["fake_authority"] = _mk(
                "fake_authority", "medium", "Authority name-dropping",
                "An official body is named alongside pressure or a request; scammers borrow authority to seem credible.",
                hit[0])

    hit = _first_hit(text, INJECTION)
    if hit:  # replaces any ordinary action_pressure hit: same key, counted once
        fired["action_pressure"] = _mk(
            "action_pressure", "high", "Prompt injection attempt",
            "The content contains text addressed to an AI system, trying to steer the analysis. It is treated as "
            "data and ignored; the score is computed in code.", _injection_quote(text))

    odd = _unusual_language(text)
    if odd:
        fired["unusual_language"] = _mk("unusual_language", "low", "Unusual language",
                                        "The wording has traits common in mass-sent scam messages.", odd)

    res.urls = [parse_url(u) for u in extract_urls(text)]
    url_signals = url_rules.run(res.urls)
    domain_signals, res.domain = domain_rules.run(text, res.urls)

    risky = fired.keys() & HIGH_RISK_KEYS
    if res.domain.claimed and risky:
        for c in res.domain.claimed:
            if not any(u.registrable in c.org["domains"] for u in res.urls):
                fired["impersonation"] = _mk(
                    "impersonation", "high", "Possible impersonation",
                    f"Message claims to be from {c.org['name']} and makes a high-risk request through a channel "
                    f"that cannot be verified.", c.alias)
                break

    res.signals = list(fired.values()) + url_signals + domain_signals
    return res


def summarize(signals: list[Signal]) -> str:
    """Rule findings rendered for the analyst prompt."""
    if not signals:
        return "- none"
    return "\n".join(f"- key={s.key} severity={s.severity} evidence=\"{s.evidence}\"" for s in signals)
