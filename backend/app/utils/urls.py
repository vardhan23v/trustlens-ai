"""URL / phone / email extraction and registrable-domain parsing. Never fetches anything."""
import ipaddress
import re
from dataclasses import dataclass

import tldextract

_extract = tldextract.TLDExtract(suffix_list_urls=())  # offline: bundled suffix snapshot only

_TRAIL = ".,;:!?"
# URL characters are ASCII only: text in another script glued to a link ("uidai.gov.inలో") is not part of it.
_STOP = r"""[^\s<>"')\]\u0080-\U0010ffff]"""
_BARE_TLDS = (
    r"com|in|co\.in|net|org|gov\.in|ac\.in|edu|xyz|top|info|club|online|site|live|ly|gy|cc|me|io|app|link|"
    r"buzz|icu|tk|ml|ga|cf|gq|work|rest|cam|shop|store|vip|win"
)
# re.A: with plain re.I the non-ASCII exclusion would also swallow i/k/s (their Unicode case variants).
HTTP_RE = re.compile(rf"https?://{_STOP}+", re.I | re.A)
WWW_RE = re.compile(rf"\bwww\.{_STOP}+", re.I | re.A)
BARE_RE = re.compile(
    rf"\b[a-z0-9][a-z0-9-]{{1,62}}(?:\.[a-z0-9-]{{1,63}})*\.(?:{_BARE_TLDS})(?![a-z0-9-])(?:/{_STOP}*)?", re.I | re.A
)
IP_RE = re.compile(rf"\b\d{{1,3}}(?:\.\d{{1,3}}){{3}}(?::\d+)?/{_STOP}*")
EMAIL_RE = re.compile(r"[a-z0-9._%+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+91[\-\s]?)?[6-9]\d{9}\b")


@dataclass(frozen=True)
class ParsedUrl:
    raw: str
    host: str
    path: str
    registrable: str  # e.g. "sbi.co.in"; the IP itself for IP hosts
    suffix: str  # public suffix, e.g. "co.in"
    is_ip: bool
    explicit_http: bool


def _blank(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for a, b in spans:
        chars[a:b] = " " * (b - a)
    return "".join(chars)


def extract_urls(text: str) -> list[str]:
    """Return URLs in order of appearance, de-duplicated (case-insensitive)."""
    found: list[tuple[int, str]] = []
    work = text
    for rx in (HTTP_RE,):
        spans = []
        for m in rx.finditer(work):
            found.append((m.start(), m.group(0)))
            spans.append(m.span())
        work = _blank(work, spans)
    work = _blank(work, [m.span() for m in EMAIL_RE.finditer(work)])
    for rx in (WWW_RE, IP_RE, BARE_RE):
        spans = []
        for m in rx.finditer(work):
            if m.start() > 0 and work[m.start() - 1] in "@.":
                continue
            found.append((m.start(), m.group(0)))
            spans.append(m.span())
        work = _blank(work, spans)
    out, seen = [], set()
    for _, raw in sorted(found):
        url = raw.rstrip(_TRAIL)
        if url.lower() not in seen and len(url) > 3:
            seen.add(url.lower())
            out.append(url)
    return out


def strip_urls(text: str) -> str:
    """Text with every URL and email blanked out (used to find org names outside links)."""
    work = text
    for u in sorted(extract_urls(text), key=len, reverse=True):
        work = re.sub(re.escape(u), " ", work, flags=re.I)
    return EMAIL_RE.sub(" ", work)


def parse_url(raw: str) -> ParsedUrl:
    explicit_http = raw.lower().startswith("http://")
    rest = re.sub(r"^https?://", "", raw, flags=re.I)
    hostport, _, path = rest.partition("/")
    hostport = hostport.split("@")[-1]
    host = hostport.strip("[]") if hostport.startswith("[") else hostport.split(":")[0]
    host = host.lower().rstrip(".")
    is_ip = False
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        pass
    if is_ip:
        return ParsedUrl(raw, host, "/" + path, host, "", True, explicit_http)
    ext = _extract(host)
    registrable = f"{ext.domain}.{ext.suffix}" if ext.domain and ext.suffix else host
    return ParsedUrl(raw, host, "/" + path, registrable.lower(), ext.suffix.lower(), False, explicit_http)


def extract_phones(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0) for m in PHONE_RE.finditer(text)))


def extract_emails(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0) for m in EMAIL_RE.finditer(text)))
