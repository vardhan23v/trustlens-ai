"""Evidence lookups for claim mode: Google Fact Check Tools + Gemini google_search grounding."""
from concurrent.futures import ThreadPoolExecutor

import httpx
from google.genai import types

from app.config import settings
from app.services import gemini_vision

FACTCHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
GROUNDED_PROMPT = (
    "Search for fact-checks of this claim: \"{claim}\". Return a bullet list; each bullet: publisher — rating or "
    "verdict as stated — one-sentence summary. Include only sources you actually retrieved."
)


def search_claims(query: str) -> list[dict]:
    """Fact Check Tools claims:search → [{source, url, rating, claim_text}]. Empty when no key or no hits."""
    if not settings.FACTCHECK_API_KEY:
        return []
    r = httpx.get(FACTCHECK_URL, timeout=10, params={
        "query": query, "languageCode": "en", "pageSize": 10, "key": settings.FACTCHECK_API_KEY})
    r.raise_for_status()
    out = []
    for claim in r.json().get("claims", []):
        for review in claim.get("claimReview", []):
            if review.get("url"):
                out.append({
                    "source": (review.get("publisher") or {}).get("name") or (review.get("publisher") or {}).get("site", ""),
                    "url": review["url"],
                    "rating": review.get("textualRating", "none"),
                    "claim_text": claim.get("text", ""),
                })
    return out


def _resolve(uri: str) -> str:
    """Grounding returns Google redirect links; read the Location header to show the real source URL.
    (This follows a Google-issued link, never a user-supplied URL.)"""
    if "grounding-api-redirect" not in uri:
        return uri
    try:
        r = httpx.head(uri, timeout=4, follow_redirects=False)
        return r.headers.get("location") or uri
    except Exception:
        return uri


def grounded_search(claim: str) -> tuple[str, list[dict]]:
    """Gemini with google_search grounding (no response schema). Returns (text, [{title, url}])."""
    resp = gemini_vision.client().models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=GROUNDED_PROMPT.format(claim=claim.replace('"', "'")[:600]),
        config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.1),
    )
    chunks = []
    try:
        meta = resp.candidates[0].grounding_metadata
        chunks = [c.web for c in (meta.grounding_chunks or []) if c.web and c.web.uri]
    except (AttributeError, IndexError, TypeError):
        pass
    chunks = chunks[:8]
    with ThreadPoolExecutor(max_workers=8) as pool:
        urls = list(pool.map(_resolve, [c.uri for c in chunks]))
    sources, seen = [], set()
    for c, url in zip(chunks, urls):
        if url not in seen:
            seen.add(url)
            sources.append({"title": c.title or "", "url": url})
    return resp.text or "", sources
