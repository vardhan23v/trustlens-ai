from importlib.metadata import version

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "gemini_model": settings.GEMINI_MODEL,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "factcheck_configured": bool(settings.FACTCHECK_API_KEY),
        "crewai_version": version("crewai"),
    }
