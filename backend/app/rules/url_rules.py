"""Per-URL heuristics. Pure string analysis: the app never fetches user-supplied URLs."""
import re

from app.models.report import Signal
from app.rules.domain_rules import ALL_ORG_DOMAINS, ORGS, host_alias_hits
from app.rules.scoring import SEVERITY_RANK
from app.utils.urls import ParsedUrl

SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "cutt.ly", "rb.gy", "is.gd", "tiny.cc", "shorturl.at",
    "rebrand.ly", "s.id", "t.ly", "buff.ly", "ow.ly", "short.io", "tiny.one", "v.gd", "clck.ru", "surl.li",
}
RISKY_TLDS = {"xyz", "top", "club", "online", "site", "live", "info", "buzz", "icu", "tk", "ml", "ga", "cf",
              "gq", "work", "rest", "cam", "vip", "win"}
RISKY_PATH = re.compile(r"login|verify|kyc|update|secure|otp", re.I)
_DIGIT_SWAP = str.maketrans({"1": "i", "0": "o", "3": "e", "5": "s"})
_COMPACT_ALIASES = {a.replace(" ", ""): o for o in ORGS for a in o["aliases"] if len(a.replace(" ", "")) >= 3}


def _digit_lookalike(host: str) -> str | None:
    for tok in re.split(r"[^a-z0-9]+", host):
        if not re.search(r"\d", tok) or tok in _COMPACT_ALIASES:
            continue
        for cand in {tok.translate(_DIGIT_SWAP), tok.replace("1", "l").replace("0", "o")}:
            if cand in _COMPACT_ALIASES:
                return f"{tok} ≈ {cand}"
    return None


def _check(u: ParsedUrl) -> list[tuple[str, str, str, str]]:
    """Return (key, severity, title, explanation) tuples for one URL."""
    out = []
    known = u.registrable in ALL_ORG_DOMAINS
    if u.is_ip:
        out.append(("ip_url", "high", "Link uses raw IP address",
                    "The link points to a numeric IP address instead of a named website, which legitimate organisations rarely do."))
    if u.registrable in SHORTENERS and not known:
        out.append(("url_shortener", "medium", "Shortened link",
                    "A shortener hides the real destination of the link."))
    if u.explicit_http:
        out.append(("http_not_https", "low", "Unencrypted link",
                    "The link uses http:// rather than https://, so the connection is not encrypted."))

    lookalike = host_alias_hits(u) if not known and not u.is_ip else []
    digit = _digit_lookalike(u.host) if not known else None
    if "xn--" in u.host:
        out.append(("suspicious_url", "high", "Disguised link characters",
                    "The address uses punycode (xn--), which can make a look-alike domain appear genuine."))
    elif digit:
        out.append(("suspicious_url", "high", "Look-alike link",
                    f"The address imitates a known name using digits in place of letters ({digit})."))
    elif lookalike and u.registrable not in SHORTENERS and any(
        a.replace(" ", "") in u.host for _, a in lookalike
    ):
        org, alias = lookalike[0]
        out.append(("suspicious_url", "high", "Look-alike link",
                    f"The address contains \"{alias}\" but {u.registrable} is not an official {org['name']} domain."))
    elif not known and not u.is_ip:
        reasons = []
        if u.suffix.split(".")[-1] in RISKY_TLDS:
            reasons.append(f"an uncommon .{u.suffix} ending often used for throwaway sites")
        if u.host.count("-") >= 3:
            reasons.append("many hyphens in the address")
        if len(u.host.split(".")) > 4:
            reasons.append("an unusually deep chain of sub-domains")
        if RISKY_PATH.search(u.path):
            reasons.append("login/verification wording in the link on a domain that is not a known organisation")
        if reasons:
            out.append(("suspicious_url", "medium", "Suspicious link pattern",
                        "The link has " + "; ".join(reasons) + "."))
    return out


def run(urls: list[ParsedUrl]) -> list[Signal]:
    best: dict[str, Signal] = {}
    for u in urls:
        for key, sev, title, expl in _check(u):
            cur = best.get(key)
            if cur is None or SEVERITY_RANK[sev] > SEVERITY_RANK[cur.severity]:
                best[key] = Signal(key=key, title=title, severity=sev, category="url_domain",
                                   sources=["RULE"], explanation=expl, evidence=u.raw)
    return list(best.values())
