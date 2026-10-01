"""Settings. Must be imported before crewai so telemetry is disabled first."""
import os
from pathlib import Path

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

from pydantic_settings import BaseSettings, SettingsConfigDict  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEMO_DIR = BACKEND_DIR / "app" / "demo"
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    FACTCHECK_API_KEY: str = ""
    MAX_UPLOAD_MB: int = 10
    DEBUG: bool = False
    LLM_TIMEOUT_S: int = 30
    FLOW_TIMEOUT_S: int = 60


settings = Settings()
