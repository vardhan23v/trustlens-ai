# TrustLens AI — deployment

TrustLens deploys as **one Docker container** that serves the API and the built frontend. The repository supports two
paths: plain Docker, and Railway (which uses the same Dockerfile). There are no Kubernetes manifests, Helm charts or
compose files in the repository.

## What the image contains

`Dockerfile` has two stages:

1. `node:20-alpine` — `npm ci` and `npm run build` for the frontend.
2. `python:3.12-slim` — installs `libgl1` and `libglib2.0-0` (needed by OpenCV, which the OCR model uses), installs
   `backend/requirements.txt`, runs `python scripts/fetch_models.py` to download the pretrained model weights
   (about 0.9 GB), then copies the backend and the built frontend.

The container starts `uvicorn app.main:app` on `${PORT:-8000}`. FastAPI serves `/api/*` and, from the same origin,
the frontend.

Notes:

- Model weights are fetched at **build** time, never at request time. A download that fails during the build is
  reported in the build log and that model reports `MODEL_UNAVAILABLE` at runtime; the build itself still succeeds.
- The weights layer is rebuilt whenever anything under `backend/app/ml/` or `backend/scripts/fetch_models.py` changes.
- `.dockerignore` keeps `.env` files, local virtualenvs, local model weights, `docs/` and Markdown files out of the
  image.
- ffmpeg is not installed with apt; the `imageio-ffmpeg` package bundles a binary.

## Variables

| Variable | Default | Notes |
|---|---|---|
| `GEMINI_API_KEY` | — | Needed for full analysis. The service starts without it and returns deterministic and model-only results |
| `GEMINI_MODEL` | `gemini-3.6-flash` | |
| `FACTCHECK_API_KEY` | — | Enables Google Fact Check Tools lookups |
| `DATABASE_URL` | — | PostgreSQL connection string; enables stored reports |
| `OPENROUTER_API_KEY` | — | Optional PDF wording layer; needs `OPENROUTER_REPORT_MODEL` too |
| `OPENROUTER_REPORT_MODEL` | — | Must be a free OpenRouter model id ending in `:free` |
| `TRUSTLENS_ML` | `1` | `0` switches every pretrained model off |
| `TRUSTLENS_MODEL_DIR` | `backend/models` | Where the weights live inside the image |
| `MAX_UPLOAD_MB` | `10` | Image upload cap |
| `LLM_TIMEOUT_S` | `30` | Timeout for a single Gemini call |
| `FLOW_TIMEOUT_S` | `60` | Default per-request limit (longer limits are set per mode in `routes/analyze.py`) |
| `DEBUG` | `false` | |
| `PORT` | `8000` | Set by the platform |
| `RAILWAY_PUBLIC_DOMAIN` | — | Set by Railway; added to the CORS allow-list |

Never commit keys. Locally they go in `backend/.env`, which is git-ignored.

## Docker

```bash
docker build -t trustlens-ai .
docker run -d --name trustlens-ai -p 8000:8000 -e GEMINI_API_KEY="..." trustlens-ai
```

Open `http://localhost:8000`.

## Railway

`railway.json` tells Railway to build with the Dockerfile, health-check `/api/health` (120 s timeout) and restart on
failure. It is a build configuration, not a one-click template.

```bash
railway login
railway init                      # or: railway link
railway variables --set GEMINI_API_KEY=...
railway up
```

To store reports, add a PostgreSQL service and reference it from the app service:

```bash
railway add --database postgres
railway variables --service <app-service> --set 'DATABASE_URL=${{Postgres.DATABASE_URL}}'
```

The app creates its one table (`analyses`) on first use.

## Sizing

| Memory limit | What happens |
|---|---|
| ~1 GB | The app runs. Models are loaded one at a time and unloaded to make room. The speech detector (about 650 MB) is skipped and reports `MODEL_UNAVAILABLE` |
| 2 GB or more | Every model can load |

The memory guard reads the container's cgroup limit before loading a model, so a model that will not fit is skipped
rather than crashing the service. CPU threads per model follow the container's CPU quota (1 to 4).

Run a single replica. The result cache is in process memory, so several replicas would give inconsistent cache hits
unless a database is configured; a multi-replica setup has not been tested.

## Verifying a deployment

```bash
curl -s https://<host>/api/health            # process is up; shows whether a key and database are configured
curl -s https://<host>/api/models/selftest   # loads every model and runs it on bundled inputs
```

`/api/health` returning `{"status": "ok", ...}` only means the process is up: it does not contact Gemini.
`gemini_configured` says a key is set, and `database` is `connected`, `unreachable` or `not_configured`. Use the
self-test to see which models actually run on this host, and run one demo
(`curl -X POST https://<host>/api/analyze/demo/viral_post`) to exercise the pipeline.
