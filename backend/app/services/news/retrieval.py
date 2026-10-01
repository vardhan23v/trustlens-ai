"""Evidence retrieval for claim verification without scraping: Google News RSS search.

Only the fixed host news.google.com is contacted. Each hit carries publisher, publisher site,
publication date and headline exactly as the feed gives them; nothing is inferred.
"""
import json
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from app.utils.urls import parse_url

RSS_URL = "https://news.google.com/rss/search"
REGISTRY: dict[str, list[str]] = {
    k: v for k, v in json.loads(
        (Path(__file__).resolve().parents[2] / "rules" / "source_registry.json").read_text(encoding="utf-8")).items()
    if not k.startswith("_")
}
_TIER_OF = {d: tier for tier, domains in REGISTRY.items() for d in domains}
_cache: dict[str, tuple[float, list[dict]]] = {}
CACHE_S = 15 * 60


def registrable(url_or_host: str) -> str:
    return parse_url(url_or_host).registrable if url_or_host else ""


def source_tier(url_or_host: str) -> str:
    """official | wire | established | factcheck | other — from the registry file, by site."""
    if not url_or_host:
        return "other"
    p = parse_url(url_or_host)
    return _TIER_OF.get(p.host.removeprefix("www.")) or _TIER_OF.get(p.registrable) or "other"


def search(query: str, limit: int = 10) -> list[dict]:
    """[{title, source, source_url, published (YYYY-MM-DD or ""), link, tier}] — empty on no hits."""
    q = " ".join(query.split())[:200]
    hit = _cache.get(q)
    if hit and time.time() - hit[0] < CACHE_S:
        return hit[1]
    r = httpx.get(RSS_URL, params={"q": q, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"}, timeout=10,
                  follow_redirects=True, headers={"User-Agent": "TrustLensAI/1.0 (claim verification)"})
    r.raise_for_status()
    out: list[dict] = []
    for item in ET.fromstring(r.content).findall("./channel/item"):
        src = item.find("source")
        link = (item.findtext("link") or "").strip()
        if src is None or not link:
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "").date().isoformat()
        except (TypeError, ValueError):
            published = ""  # unknown stays unknown: dates are never guessed
        name = (src.text or "").strip()
        title = (item.findtext("title") or "").strip()
        if name and title.endswith(f" - {name}"):
            title = title[: -len(name) - 3]
        site = src.get("url") or ""
        out.append({"title": title, "source": name, "source_url": site, "published": published, "link": link,
                    "tier": source_tier(site)})
    # listed sources first, then newest; the model only ever sees this short list
    rank = {"factcheck": 0, "official": 0, "wire": 1, "established": 1, "other": 2}
    out.sort(key=lambda h: (rank[h["tier"]], ), )
    out = out[:limit]
    _cache[q] = (time.time(), out)
    return out
