"""Gemini as the LLM for every CrewAI agent."""
from app.config import settings  # noqa: F401  (must load before crewai: disables telemetry)

from crewai import LLM
from google.genai import types


def gemini_llm() -> LLM:
    return LLM(
        model=f"gemini/{settings.GEMINI_MODEL}",
        api_key=settings.GEMINI_API_KEY,
        temperature=0.2,
        timeout=settings.LLM_TIMEOUT_S,
        max_tokens=4096,
        # low thinking keeps each agent call to a few seconds (default thinking took 20-30 s per call)
        thinking_config=types.ThinkingConfig(thinking_level="low"),
    )
