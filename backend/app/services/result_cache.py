"""Small in-memory cache so the SAME input gives the SAME report.

Gemini is not perfectly repeatable even at temperature 0, and a second run of an identical image
could score a few points differently. A completed report is therefore reused for an identical
input (same bytes, same intent, same model). RAM only, bounded, short-lived; never written to disk.
Reports produced while Gemini was unavailable are NOT cached, so a later run can get the full analysis.
"""
import hashlib
import threading
import time
from collections import OrderedDict

from app.config import settings
from app.models.report import TrustReport

MAX_ITEMS = 64
TTL_S = 30 * 60

_lock = threading.Lock()
_items: "OrderedDict[str, tuple[float, TrustReport]]" = OrderedDict()


def key(kind: str, payload: bytes, intent: str = "") -> str:
    h = hashlib.sha256()
    for part in (kind, intent, settings.GEMINI_MODEL):
        h.update(part.encode() + b"\0")
    h.update(payload)
    return h.hexdigest()


def get(k: str) -> TrustReport | None:
    with _lock:
        hit = _items.get(k)
        if hit is None:
            return None
        if time.time() - hit[0] > TTL_S:
            del _items[k]
            return None
        _items.move_to_end(k)
        return hit[1].model_copy(deep=True)


def put(k: str, report: TrustReport) -> None:
    if report.gemini_error:  # partial result: do not freeze it
        return
    with _lock:
        _items[k] = (time.time(), report.model_copy(deep=True))
        _items.move_to_end(k)
        while len(_items) > MAX_ITEMS:
            _items.popitem(last=False)
