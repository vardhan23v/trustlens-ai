"""Claimed organisation vs. URL domain, using known_orgs.json."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.models.report import Signal
from app.utils.urls import ParsedUrl, strip_urls

ORGS: list[dict] = json.loads((Path(__file__).parent / "known_orgs.json").read_text(encoding="utf-8"))
ALL_ORG_DOMAINS: set[str] = {d for o in ORGS for d in o["domains"]}

# Aliases that are also everyday words / payment methods: they never establish a claimed
# organisation on their own (e.g. "pay by UPI" is not a claim to be NPCI).
WEAK_ALIASES = {"upi", "bhim", "aadhaar", "aadhar", "meta", "apple", "axis", "post office",
                "provident fund", "outlook", "income tax", "e-filing", "speed post", "canara"}


def _alias_re(alias: str) -> re.Pattern:
    return re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", re.I)


_ALIAS_RES = [(o, a, _alias_re(a)) for o in ORGS for a in o["aliases"]]


@dataclass
class Claimed:
    org: dict
    alias: str  # as it appeared


@dataclass
class DomainContext:
    claimed: list[Claimed] = field(default_factory=list)
    claimed_domains: set[str] = field(default_factory=set)
    all_urls_match_claimed: bool = False


def org_of_domain(registrable: str) -> dict | None:
    for o in ORGS:
        if registrable in o["domains"]:
            return o
    return None


def host_alias_hits(url: ParsedUrl) -> list[tuple[dict, str]]:
    """Org aliases embedded in a URL (host or path) whose registrable domain is NOT that org's."""
    hits = []
    hay = f"{url.host}{url.path}".lower()
    tokens = set(re.split(r"[^a-z0-9]+", hay))
    for o in ORGS:
        if url.registrable in o["domains"]:
            continue
        for a in o["aliases"]:
            compact = a.replace(" ", "")
            if a in WEAK_ALIASES:
                continue
            if compact in tokens or (len(compact) >= 5 and compact in url.host):
                hits.append((o, a))
                break
    return hits


def find_claimed(text: str, urls: list[ParsedUrl]) -> list[Claimed]:
    plain = strip_urls(text)
    out: dict[str, Claimed] = {}
    for o, a, rx in _ALIAS_RES:
        if a in WEAK_ALIASES or o["name"] in out:
            continue
        m = rx.search(plain)
        if m:
            out[o["name"]] = Claimed(o, m.group(0))
    for u in urls:
        for o, a in host_alias_hits(u):
            out.setdefault(o["name"], Claimed(o, a))
    return list(out.values())


def run(text: str, urls: list[ParsedUrl]) -> tuple[list[Signal], DomainContext]:
    ctx = DomainContext(claimed=find_claimed(text, urls))
    ctx.claimed_domains = {d for c in ctx.claimed for d in c.org["domains"]}
    signals: list[Signal] = []
    if not ctx.claimed or not urls:
        return signals, ctx
    mismatched = [u for u in urls if u.registrable not in ctx.claimed_domains]
    ctx.all_urls_match_claimed = not mismatched
    if mismatched:
        u = mismatched[0]
        other = org_of_domain(u.registrable)
        c = ctx.claimed[0]
        if other:
            sev, expl = "medium", (
                f"The message mentions {c.org['name']}, but the link belongs to {other['name']} ({u.registrable})."
            )
        else:
            sev, expl = "high", (
                f"The message claims to be from {c.org['name']}, but the link goes to {u.registrable}, "
                f"which is not one of its official domains."
            )
        signals.append(Signal(
            key="domain_mismatch", title=f"Link does not match {c.alias.upper() if len(c.alias) <= 5 else c.org['name']}"[:60],
            severity=sev, category="url_domain", sources=["RULE"], explanation=expl,
            evidence=f"\"{c.alias}\" vs {u.registrable}",
        ))
    return signals, ctx
