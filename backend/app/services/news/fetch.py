"""Fetch one article the user asked to verify. This is the only place a user-supplied URL is
requested, and only after SSRF checks: public http(s) hosts only, short timeout, size cap, robots.txt.
A failure means SOURCE_UNAVAILABLE — never evidence that the claim is false."""
import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import httpx

MAX_BYTES = 1_500_000
TIMEOUT_S = 8
MAX_REDIRECTS = 3
UA = "TrustLensAI/1.0 (claim verification; respects robots.txt)"
URL_ONLY = re.compile(r"^https?://\S+$", re.I)


class SourceUnavailable(RuntimeError):
    pass


def _assert_public(url: str) -> None:
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise SourceUnavailable("only http(s) links can be fetched")
    if u.port not in (None, 80, 443):
        raise SourceUnavailable("non-standard port")
    try:
        infos = socket.getaddrinfo(u.hostname, None)
    except OSError as e:
        raise SourceUnavailable("host could not be resolved") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise SourceUnavailable("address is not on the public internet")


def _allowed_by_robots(url: str) -> bool:
    u = urlparse(url)
    try:
        r = httpx.get(f"{u.scheme}://{u.netloc}/robots.txt", timeout=4, headers={"User-Agent": UA})
        if r.status_code >= 400:
            return True
        rp = robotparser.RobotFileParser()
        rp.parse(r.text.splitlines())
        return rp.can_fetch(UA, url)
    except Exception:
        return True


class _Extract(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self.paragraphs: list[str] = []
        self.jsonld: list[str] = []
        self._stack: list[str] = []
        self._buf: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content"):
                self.meta.setdefault(key, a["content"].strip())
        if tag in ("script", "style", "noscript", "nav", "footer", "aside", "form"):
            self._skip += 1
            if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
                self._stack.append("jsonld")
                self._buf = []
                return
        if tag in ("p", "title", "h1"):
            self._stack.append(tag)
            self._buf = []

    def handle_endtag(self, tag):
        if tag == "script" and self._stack and self._stack[-1] == "jsonld":
            self.jsonld.append("".join(self._buf))
            self._stack.pop()
        if tag in ("script", "style", "noscript", "nav", "footer", "aside", "form"):
            self._skip = max(0, self._skip - 1)
        if tag in ("p", "title", "h1") and self._stack and self._stack[-1] == tag:
            text = " ".join("".join(self._buf).split())
            self._stack.pop()
            if tag == "p" and len(text) > 60 and self._skip == 0:
                self.paragraphs.append(text)
            elif tag in ("title", "h1") and text and not self.title:
                self.title = text

    def handle_data(self, data):
        if self._stack:
            self._buf.append(data)


def _from_jsonld(blocks: list[str]) -> dict:
    out: dict[str, str] = {}
    for raw in blocks:
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        nodes = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for n in nodes:
            if not isinstance(n, dict) or "Article" not in str(n.get("@type", "")):
                continue
            out.setdefault("headline", str(n.get("headline") or ""))
            out.setdefault("published", str(n.get("datePublished") or "")[:10])
            pub = n.get("publisher")
            out.setdefault("publisher", str(pub.get("name") if isinstance(pub, dict) else pub or ""))
            au = n.get("author")
            au = au[0] if isinstance(au, list) and au else au
            out.setdefault("author", str(au.get("name") if isinstance(au, dict) else au or ""))
    return out


def fetch_article(url: str) -> dict:
    """{url, headline, description, publisher, author, published, text} or raises SourceUnavailable."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        _assert_public(current)
        if not _allowed_by_robots(current):
            raise SourceUnavailable("the site's robots.txt does not allow fetching this page")
        try:
            with httpx.stream("GET", current, timeout=TIMEOUT_S, follow_redirects=False,
                              headers={"User-Agent": UA, "Accept": "text/html"}) as r:
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                    current = urljoin(current, r.headers["location"])
                    continue
                if r.status_code != 200:
                    raise SourceUnavailable(f"the site answered HTTP {r.status_code}")
                if "html" not in r.headers.get("content-type", ""):
                    raise SourceUnavailable("the link is not a web page")
                body = b""
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        break
        except httpx.HTTPError as e:
            raise SourceUnavailable(f"request failed ({type(e).__name__})") from e
        break
    else:
        raise SourceUnavailable("too many redirects")

    p = _Extract()
    try:
        p.feed(body.decode("utf-8", "ignore"))
    except Exception as e:
        raise SourceUnavailable("the page could not be parsed") from e
    ld = _from_jsonld(p.jsonld)
    headline = ld.get("headline") or p.meta.get("og:title") or p.title
    text = " ".join(p.paragraphs)[:6000]
    if not headline and len(text) < 200:
        raise SourceUnavailable("no article text could be extracted (paywall or script-rendered page)")
    return {
        "url": current, "headline": headline.strip(),
        "description": (p.meta.get("og:description") or p.meta.get("description") or "").strip(),
        "publisher": (ld.get("publisher") or p.meta.get("og:site_name") or urlparse(current).hostname or "").strip(),
        "author": (ld.get("author") or p.meta.get("author") or "").strip(),
        "published": (ld.get("published") or p.meta.get("article:published_time", "")[:10]).strip(),
        "text": text,
    }
