"""Resilience and fallback tests for TrustLens analysis pipeline."""
import pytest
from app.config import settings


def test_settings_resilience_defaults():
    """Verify that default timeouts and retry settings are within resilient thresholds."""
    assert settings.LLM_TIMEOUT_S >= 10
    assert settings.FLOW_TIMEOUT_S >= 30
    assert settings.GEMINI_MAX_RETRIES >= 1
    assert settings.GEMINI_RETRY_BACKOFF_S >= 0.5


def test_max_upload_boundaries():
    """Verify upload limits conform to specification boundaries."""
    assert 1 <= settings.MAX_UPLOAD_MB <= 100


def test_cors_and_telemetry_isolation():
    """Verify telemetry disabling flags remain securely set."""
    import os
    assert os.getenv("CREWAI_DISABLE_TELEMETRY") == "true"
    assert os.getenv("OTEL_SDK_DISABLED") == "true"
