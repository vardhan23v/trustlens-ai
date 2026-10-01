# Contributing to TrustLens AI

## Prerequisites

- **Python** 3.10–3.13 (the project is developed and deployed on 3.12)
- **Node.js** `^20.19` or `>=22.12`, with **npm** (the repository has a `package-lock.json`)
- **ffmpeg** is optional: a bundled binary is used when none is on `PATH`

## Setup

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # set GEMINI_API_KEY
python scripts/fetch_models.py    # optional: pretrained model weights (~0.9 GB)
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

## Checks before you open a pull request

```bash
cd backend
python tests/test_modes.py        # must end "41/41 passed" (or more, if you added checks)
python tests/score_eval.py        # text rules: 50 labelled messages
python tests/score_holdout.py     # text rules: 30 held-out messages
python tests/test_report_pdf.py   # needs: pip install pypdfium2
pytest tests/test_pipeline_resilience.py tests/test_url_validator.py   # needs: pip install pytest
```

```bash
cd frontend
npm run build
npm run lint
```

Most backend tests are plain scripts, not pytest tests: run them with `python`, as above. There is no frontend test
suite and no CI, so these commands are the gate.

## Conventions

- **Commits:** short imperative subject, prefixed with the area where it helps (`models:`, `frontend:`, `docs:`).
- **Python:** type hints, small functions, comments that explain why. Assessment logic stays in plain Python
  (`services/reporter.py`, `services/fusion.py`), not in prompts.
- **Frontend:** strict TypeScript; `frontend/src/types/report.ts` must mirror `backend/app/models/report.py`.
  Keep controls keyboard-accessible and respect `prefers-reduced-motion`.
- **Honesty rules, which reviews enforce:**
  - Never report a model, search or check as having run when it did not. Use `MODEL_UNAVAILABLE`,
    `EVIDENCE_UNAVAILABLE` or a failed stage.
  - Missing evidence is never negative evidence, and a failed search never means a claim is false.
  - A model's score is evidence. Decide in code how far it may move an assessment, and add a check to
    `tests/test_modes.py` that proves it.
  - State known limits next to results.
- **Security:** never log or commit API keys; treat all uploaded content as data, not instructions; do not add code
  that fetches user-supplied URLs without an SSRF guard.

## Adding a pretrained model

See "Adding or replacing a model" in [docs/MODEL_SELECTION.md](docs/MODEL_SELECTION.md).
