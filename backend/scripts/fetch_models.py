"""Download the pretrained specialist models into backend/models (run once locally and at Docker build).

    python scripts/fetch_models.py            # all
    python scripts/fetch_models.py nli asr    # some

The app never downloads at request time: a slot whose files are missing reports MODEL_UNAVAILABLE.
A failed download is reported and skipped, so one unreachable repository does not break the build.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from huggingface_hub import hf_hub_download, snapshot_download  # noqa: E402

from app.ml.registry import MODEL_DIR, SOURCES  # noqa: E402


def fetch(slot: str) -> None:
    src = SOURCES[slot]
    dest = MODEL_DIR / slot
    dest.mkdir(parents=True, exist_ok=True)
    if src.get("fastembed"):
        from fastembed import TextEmbedding
        TextEmbedding(model_name=src["fastembed"], cache_dir=str(dest))
    elif src.get("snapshot"):
        snapshot_download(src["repo"], local_dir=str(dest))
    else:
        for name in src["files"]:
            hf_hub_download(src["repo"], name, local_dir=str(dest))
    size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) / 1e6
    print(f"ok   {slot:16s} {size:7.1f} MB  <- {src.get('repo') or src.get('fastembed')}")


if __name__ == "__main__":
    wanted = sys.argv[1:] or list(SOURCES)
    failed = []
    for slot in wanted:
        try:
            fetch(slot)
        except Exception as e:  # keep going: the slot simply stays unavailable
            failed.append(slot)
            print(f"FAIL {slot:16s} {type(e).__name__}: {str(e)[:160]}")
    print("done;", "all present" if not failed else f"missing: {', '.join(failed)}")
