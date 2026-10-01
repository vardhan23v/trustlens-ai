"""Optional PostgreSQL persistence for finished reports (Railway: DATABASE_URL).

Stores the report JSON only — never the uploaded file. Used for two things: an identical file in the
same mode returns the same report after a restart, and a report can be reopened by its id.
There is no listing endpoint: reports can contain personal text read from the upload.
Without DATABASE_URL, or if the database is unreachable, everything still works from RAM.
"""
import logging
import secrets

from app.config import settings
from app.models.report import TrustReport

log = logging.getLogger("trustlens.store")
NEWS_MAX_AGE_H = 24  # evidence changes: a stored news verdict is reused for a day, then re-run
_ready = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id           TEXT PRIMARY KEY,
    cache_key    TEXT UNIQUE NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    mode         TEXT NOT NULL,
    media_type   TEXT NOT NULL,
    state        TEXT,
    trust_score  INTEGER,
    model        TEXT,
    report       JSONB NOT NULL
)"""


def enabled() -> bool:
    return bool(settings.DATABASE_URL)


def _connect():
    import psycopg
    global _ready
    conn = psycopg.connect(settings.DATABASE_URL, connect_timeout=5, autocommit=True)
    if not _ready:
        conn.execute(SCHEMA)
        _ready = True
    return conn


def status() -> str:
    if not enabled():
        return "not_configured"
    try:
        with _connect() as conn:
            conn.execute("SELECT 1")
        return "connected"
    except Exception as e:
        log.warning("database unreachable: %s", type(e).__name__)
        return "unreachable"


def new_id() -> str:
    return "TL-" + secrets.token_hex(6).upper()


def save(cache_key: str, report: TrustReport) -> None:
    if not enabled() or report.gemini_error or not report.report_id:
        return
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO analyses (id, cache_key, mode, media_type, state, trust_score, model, report) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb) "
                "ON CONFLICT (cache_key) DO UPDATE SET id = EXCLUDED.id, created_at = now(), state = EXCLUDED.state, "
                "trust_score = EXCLUDED.trust_score, report = EXCLUDED.report",
                (report.report_id, cache_key, report.mode or "", report.media_type,
                 report.overall_assessment.state if report.overall_assessment else None, report.trust_score,
                 settings.GEMINI_MODEL, report.model_dump_json()))
    except Exception as e:  # persistence is best-effort: the analysis result is still returned
        log.warning("could not store report: %s", type(e).__name__)


def _load(sql: str, params: tuple) -> TrustReport | None:
    if not enabled():
        return None
    try:
        with _connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return TrustReport.model_validate(row[0]) if row else None
    except Exception as e:
        log.warning("could not read report: %s", type(e).__name__)
        return None


def by_key(cache_key: str) -> TrustReport | None:
    return _load("SELECT report FROM analyses WHERE cache_key = %s AND "
                 "(mode <> 'news_claim' OR created_at > now() - make_interval(hours => %s))",
                 (cache_key, NEWS_MAX_AGE_H))


def by_id(report_id: str) -> TrustReport | None:
    return _load("SELECT report FROM analyses WHERE id = %s", (report_id,))
