"""Gemini as the LLM for every CrewAI agent."""
from app.config import settings  # noqa: F401  (must load before crewai: disables telemetry)

from crewai import LLM


def gemini_llm() -> LLM:
    return LLM(
        model=f"gemini/{settings.GEMINI_MODEL}",
        api_key=settings.GEMINI_API_KEY,
        temperature=0.2,
        timeout=settings.LLM_TIMEOUT_S,
        max_tokens=4096,
    )
