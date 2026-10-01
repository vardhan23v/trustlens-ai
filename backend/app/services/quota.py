"""When a Gemini model's quota is exhausted, switch to the next configured model and try again.

Free-tier quotas are per model and per day, so a 429 on one model usually does not affect another.
The switch is process-wide (later requests start on the working model) and is reported by /api/health.
"""
import functools
import logging

from app.config import settings

log = logging.getLogger("trustlens.quota")
_MARKERS = ("429", "resource_exhausted", "quota")


def is_quota_error(err: BaseException) -> bool:
    text = str(err).lower()
    return any(m in text for m in _MARKERS)


def _next_model() -> str | None:
    chain = [m.strip() for m in settings.GEMINI_FALLBACK_MODELS.split(",") if m.strip()]
    tried = getattr(settings, "_exhausted", set()) | {settings.GEMINI_MODEL}
    object.__setattr__(settings, "_exhausted", tried)
    return next((m for m in chain if m not in tried), None)


def with_fallback(fn):
    """Retry `fn` on the next model each time the current one reports an exhausted quota."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        while True:
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                nxt = _next_model() if is_quota_error(e) else None
                if nxt is None:
                    raise
                log.warning("quota exhausted on %s; switching to %s", settings.GEMINI_MODEL, nxt)
                settings.GEMINI_MODEL = nxt
    return wrapper
