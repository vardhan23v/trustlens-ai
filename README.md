# TrustLens AI — See Beyond the Digital Surface

[![Live demo](https://img.shields.io/badge/Live%20demo-Railway-0B0D0E?logo=railway&logoColor=white)](https://trustlens-ai-production-5b04.up.railway.app)
![Powered by Gemini](https://img.shields.io/badge/Powered%20by-Gemini%203.6%20Flash-8E75B2?logo=googlegemini&logoColor=white)
![CrewAI](https://img.shields.io/badge/Agents-CrewAI%201.15-FF5A50)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/UI-React%2019%20%2B%20Vite-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-6-3178C6?logo=typescript&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-v4-06B6D4?logo=tailwindcss&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Deploy-Docker-2496ED?logo=docker&logoColor=white)
![Hackathon](https://img.shields.io/badge/ACM%20%C3%97%20MLH%20Hack%20Days%202026-Track%202%3A%20Trust-22D3EE)

**Live:** https://trustlens-ai-production-5b04.up.railway.app

**Gemini-powered Trust Checker.** Upload a screenshot or document image, or paste a suspicious message or a viral
claim, and get an explainable **Trust Report**: every signal shows what was found, the quoted evidence, and whether it
came from a deterministic **RULE** or from **GEMINI** reasoning. The score is computed in code and every deducted point
is listed.

> Trust should be backed by evidence, not appearance. *Don't just tell users what to trust. Show them why.*

Built at **ACM × MLH Hack Days 2026 — "Build with Gemini"**, Track 2: *Trust in a Synthetic World*.

![Architecture](docs/system_architecture.png)

## How Gemini is used

| Where | What Gemini does | How |
|---|---|---|
| Vision extraction (image mode) | Reads the image: full text, sender, URLs, amounts, plus visual notes on odd regions | `google-genai`, structured output (`response_schema=Extracted`) |
| **Extractor** agent | Classifies the content and extracts structured fields | CrewAI agent, `LLM(model="gemini/<GEMINI_MODEL>")`, `output_pydantic=Extracted` |
| **Trust Signal Analyst** agent | Finds what rules cannot see: inconsistencies, tone mismatch, implausible authority, manipulation, prompt injection | CrewAI agent on Gemini, `output_pydantic=SignalSet` |
| **Claim Verifier** agent | Extracts the checkable claim and gathers evidence with tools | CrewAI agent on Gemini + `FactCheckSearchTool` + `GroundedSearchTool` |
| Grounded search | Finds published fact-checks with cited sources | Gemini `google_search` grounding (separate call, no schema) |

Model: `GEMINI_MODEL` (default `gemini-3.6-flash`; `gemini-2.5-flash` is no longer offered to new API keys). Orchestration: a CrewAI **Flow** (`TrustLensFlow`):

```
forensics (EXIF + ELA) → Gemini vision → deterministic rules → CrewAI crew (Gemini) → score + verdict in Python → Trust Report
```

The browser never talks to Gemini: Frontend → FastAPI → CrewAI/Gemini. The API key lives only in `backend/.env`.

## Run locally

```bash
# backend (Python 3.11–3.13)
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then set GEMINI_API_KEY (and optionally FACTCHECK_API_KEY)
python scripts/make_demos.py    # builds the demo images + texts
python scripts/make_demos.py --record   # records real Gemini outputs for the demo chips (needs the key)
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
npm install
npm run dev                     # http://localhost:5173  (proxies /api → :8000)
```

API: `GET /api/health` · `POST /api/analyze/image` (multipart `file`) · `POST /api/analyze/text` ·
`POST /api/analyze/claim` (JSON `{"text"}`) · `GET /api/demos` · `POST /api/analyze/demo/{id}`.

Deploy: one container (`Dockerfile`) — FastAPI serves the built frontend; `railway.json` sets the health check.
Deployed on Railway: https://trustlens-ai-production-5b04.up.railway.app

## Trust score — auditable by design

Start at 100. Each de-duplicated signal subtracts `PENALTIES[key] × severity` (high 1.0 · medium 0.6 · low 0.3).
Deductions are capped per category (image forensics 25 · URL/domain 30 · message content 45 · claim evidence 40).
Bands: **75–100 LOW · 45–74 MEDIUM · 0–44 HIGH**. Everything is in one file: `backend/app/rules/scoring.py`.
The report shows the full deduction table, so the number can be checked by hand.

The same signal found by a rule *and* by Gemini counts once and shows both badges.

**The Trust Score is a risk indicator, not proof of authenticity or fraud.**

## Honesty & limits

- **Score and verdict are computed in Python, never by the model.** Gemini can add signals or raise severity; it can
  never remove or downgrade a rule finding.
- **UNVERIFIED is a first-class answer.** A claim is `VERIFIED/DEBUNKED BY SOURCE` only when a fact-check outlet with an
  explicit rating says so, and only for links that actually came from a search tool.
- **Prompt-injection guard.** Content is wrapped as data in every prompt; text addressed to an AI is itself reported as a
  high-severity "Prompt injection attempt" signal.
- **ELA and EXIF are signals, not proof.** ELA runs only on JPEG/WebP (PNG ⇒ "not applicable"); missing EXIF is never a signal.
- **A clean fake passes.** LOW is shown as "No risk signals found — not verified as authentic", never as "safe".
- **Known-organisation attenuation.** If every link is on the claimed organisation's own domain, urgency is capped at
  low, so a real bank SMS is not flagged HIGH for sounding urgent.
- **Graceful degradation.** If Gemini is unavailable, the report still returns rule + forensics signals with a banner; nothing is fabricated.
- **Privacy.** Nothing is stored; uploads are processed in memory and sent to Gemini for analysis only. The backend never fetches user-supplied URLs.
- Rules cover English + Hinglish patterns; other languages rely on Gemini.

## Track 2 mapping

- **Detect** — manipulated images: EXIF editor traces + multi-quality Error Level Analysis with a heatmap.
- **Verify** — notices, offer letters and documents: Gemini vision extraction + inconsistency analysis.
- **Trace** — viral claims: fact-check search + Google-Search grounding with source links.
- **Secure** — phishing/scam messages: URL, domain-mismatch and impersonation rules against ~30 known organisations.
- **Build Trust** — transparent, evidence-backed AI: source badges, quoted evidence, auditable score, honest caveats.

## Demos

`Genuine notice` · `Edited notice` · `Scam SMS` · `Viral claim` · `Injection` — the chips run forensics and rules live and
use pre-recorded Gemini outputs (`backend/app/demo/*.crew.json`, badge **CACHED DEMO**). Anything you upload or paste
yourself is always analysed live. The demo notice uses a fictional institution.

## Stack

React + Vite + TypeScript + Tailwind v4 · FastAPI + Pydantic v2 · CrewAI (Flow + sequential Crew) · google-genai ·
Pillow / piexif / NumPy · no database, no auth, stateless.

Planning docs: `architecture.md`, `design.md`, `memory.md`, `content_kit.md`.
