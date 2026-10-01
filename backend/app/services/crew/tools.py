"""Claim Verifier tools. Every URL a tool returns is recorded so that Python can later drop
any evidence item whose URL did not come from a tool (the agent cannot invent sources)."""
import json

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from app.services import factcheck
from app.services.news import retrieval


class ToolLedger:
    """URLs (and their publishers/ratings) actually returned by tools during one crew run."""

    def __init__(self) -> None:
        self.items: dict[str, dict] = {}
        self.errors: list[str] = []

    def add(self, url: str, **meta: str) -> None:
        self.items.setdefault(url.strip(), meta)


class QueryArgs(BaseModel):
    query: str = Field(..., description="A concise search query: the claim, or its key entities.")


class FactCheckSearchTool(BaseTool):
    name: str = "FactCheckSearchTool"
    description: str = ("Search published fact-checks (Google Fact Check Tools). Returns a JSON list of "
                        "{source, url, rating, claim_text}, or NO_RESULTS.")
    args_schema: type[BaseModel] = QueryArgs
    _ledger: ToolLedger = PrivateAttr()

    def __init__(self, ledger: ToolLedger, **kw):
        super().__init__(**kw)
        self._ledger = ledger

    def _run(self, query: str) -> str:
        try:
            hits = factcheck.search_claims(query)
        except Exception as e:
            self._ledger.errors.append(f"factcheck: {str(e)[:120]}")
            return "NO_RESULTS"
        if not hits:
            return "NO_RESULTS"
        for h in hits:
            self._ledger.add(h["url"], source=h["source"], rating=h["rating"], origin="factcheck")
        return json.dumps(hits[:8], ensure_ascii=False)


class GroundedSearchTool(BaseTool):
    name: str = "GroundedSearchTool"
    description: str = ("Search the web for fact-checks of a claim using Gemini with Google Search grounding. "
                        "Returns a summary followed by a SOURCES: list of title and url.")
    args_schema: type[BaseModel] = QueryArgs
    _ledger: ToolLedger = PrivateAttr()

    def __init__(self, ledger: ToolLedger, **kw):
        super().__init__(**kw)
        self._ledger = ledger

    def _run(self, query: str) -> str:
        try:
            text, sources = factcheck.grounded_search(query)
        except Exception as e:
            self._ledger.errors.append(f"grounding: {str(e)[:120]}")
            return "NO_RESULTS"
        if not sources:
            return (text or "NO_RESULTS") + "\nSOURCES: none"
        for s in sources:
            self._ledger.add(s["url"], source=s["title"], rating="none", origin="grounding")
        lines = "\n".join(f"- {s['title']} — {s['url']}" for s in sources)
        return f"{text}\nSOURCES:\n{lines}"


class NewsSearchTool(BaseTool):
    name: str = "NewsSearchTool"
    description: str = ("Search news coverage and fact-checks of a claim (Google News RSS). Returns a JSON list of "
                        "{title, source, published, tier, url}, or NO_RESULTS. tier is official | wire | established | "
                        "factcheck | other.")
    args_schema: type[BaseModel] = QueryArgs
    _ledger: ToolLedger = PrivateAttr()

    def __init__(self, ledger: ToolLedger, **kw):
        super().__init__(**kw)
        self._ledger = ledger

    def _run(self, query: str) -> str:
        try:
            hits = retrieval.search(query)
        except Exception as e:
            self._ledger.errors.append(f"news: {str(e)[:120]}")
            return "NO_RESULTS"
        if not hits:
            return "NO_RESULTS"
        for h in hits:
            self._ledger.add(h["link"], source=h["source"], rating="none", origin="news", title=h["title"],
                             published=h["published"], site=h["source_url"])
        return json.dumps([{"title": h["title"], "source": h["source"], "published": h["published"] or "unknown",
                            "tier": h["tier"], "url": h["link"]} for h in hits], ensure_ascii=False)
