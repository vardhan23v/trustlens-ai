# TrustLens AI — Project Memory

Read this file at the start of every session. Update the **Status** and **Log** sections after each stage. Decisions here are settled; do not re-open them unless blocked.

## Context
- Event: ACM × MLH Hack Days 2026 (ACM NMAMIT × MLH, powered by Gemini), theme "Beyond Reality". Track 2 "Trust in a Synthetic World".
- Date: Thu 1 Oct 2026, NMAMIT Nitte. Hacking begins 9:00 AM · mentor check-in 11:00 · lunch 1:00 PM · **submission deadline 3:00 PM** · demos 3:15 · prizes 4:45.
- Effective build window ≈ 5 h (9:00–2:30) + 30 min for PPT/submission. Judges see four demos (see design.md §9).
- Product principle: Trust should be backed by evidence, not appearance. Show why.

## Event rules that constrain us (from the official guide)
- **Gemini compulsory and meaningfully incorporated** → agents' LLM is Gemini; vision + grounding are Gemini; say "Gemini" in UI and pitch.
- **Originality: developed during the hackathon; no pre-existing projects** → no application code before 9:00 AM. Planning docs (these files), accounts, API keys, installed toolchains are preparation, not code. Repo's first commit is at the venue.
- **One primary track** → Track 2 only. Map every feature to the track's verbs: Detect (manipulated media), Verify (documents/notices), Trace (viral claims), Secure (phishing/scam), Build Trust (transparent, evidence-backed AI). Protect (identity/SIM swap) is out of scope — say so if asked.
- **Bonus challenge announced on the day** → keep a 20-min slot at 2:00 PM; do not pre-commit to it.
- **Submission in the given PPT template** (QR in guide) → PPT is part of the deliverable; outline below.
- **Demo to judges is mandatory** → cached demo fixtures are the safety net; rehearse once at 2:30.
- **Judging: innovation, technical implementation, problem relevance, usability, presentation** → pitch structure below.
- Team size 2; public libraries/APIs/frameworks allowed (CrewAI OK).

## Day plan (2 people, both running Claude Code in separate sessions; API contract = models/report.py ↔ types/report.ts, fixed at 9:15)
| Time | Dev A (backend) | Dev B (frontend + demo + PPT) |
|---|---|---|
| 9:00–9:15 | repo init, .env, deps install, health endpoint; test `claims:search` on demo claims A/B | Vite/TS/Tailwind scaffold, types/report.ts from contract, mocks/scam_sms.json from D10 |
| 9:15–10:30 | Stage 1: Flow + text crew → rules → score → report | Stage 3: InputPanel, StageProgress, ReportView against mock JSON |
| 10:30–11:15 | Stage 2: EXIF/ELA/vision → Analyst | make_demos.py images; wire real API; DemoChips |
| 11:00 | mentor check-in (5 min, ask about bonus + judging) | |
| 11:15–12:30 | Stage 6: claim crew + tools + verdict | Stage 5: ElaCompare; polish; error/banner states |
| 12:30–1:00 | Stage 4: demo endpoints; `--record` fixtures | README; start PPT in template |
| 1:00–1:30 | lunch (fixtures recording can run) | lunch |
| 1:30–2:00 | Stage 9 Railway deploy (login handshake with user, `railway up`, variables, domain) — 25 min box | PPT content; screenshots for slides; public URL on slide |
| 2:00–2:20 | bonus challenge (if feasible) | bonus challenge slide |
| 2:20–2:45 | code freeze; final commit; run all four demos twice | rehearse 3-min pitch |
| 2:45–3:00 | submit | submit |

## Submission PPT outline (fill the organizers' template; ≤ 8 slides)
1. Title — TrustLens AI · "See Beyond the Digital Surface" · team · Track 2.
2. Problem — screenshots/forwards treated as proof; scams, edited notices, viral claims (1 stat + 1 local example).
3. Solution — upload/paste → evidence-backed Trust Report; principle "show them why".
4. How it works — Flow diagram: forensics → Gemini vision → rules → CrewAI agents (Gemini) → transparent score.
5. Gemini usage — vision extraction, agent reasoning, grounding; structured outputs; RULE vs GEMINI badges.
6. Demo — 4 screenshots (genuine, edited + ELA heatmap, scam SMS, claim).
7. Honesty & limits — risk indicator not proof; UNVERIFIED by design; prompt-injection guard; privacy (no storage).
8. Impact & next — Hindi/regional rules, WhatsApp bot, browser extension, org verification.

## 3-minute pitch (maps to judging criteria)
- Problem relevance (30 s): the forwarded screenshot problem, India-specific scams.
- Innovation (40 s): evidence-first Trust Report; deterministic + Gemini agents; transparent score with visible deductions; honest UNVERIFIED.
- Technical (40 s): CrewAI Flow, Gemini structured outputs, ELA/EXIF, rules, verdict logic in code not LLM.
- Usability (60 s): live demo — edited notice then scam SMS; show RULE + GEMINI badges and heatmap.
- Close (10 s): "Don't just tell users what to trust. Show them why."

## Settled decisions
| Topic | Decision |
|---|---|
| AI provider | Google Gemini only. Never Claude/OpenAI in app code. |
| Orchestration | CrewAI: `TrustLensFlow` (Flow) + sequential Crew. Agents: Extractor, Trust Signal Analyst, Claim Verifier. `llm=LLM(model="gemini/<GEMINI_MODEL>")`. No delegation, no hierarchical process, `memory=False`, `max_iter=2`. |
| Direct SDK use | `google-genai` only for vision extraction (Flow step) and `google_search` grounding (crew tool). Never `google-generativeai`. |
| Model | `GEMINI_MODEL` env, default `gemini-2.5-flash`, used as `gemini/<name>` in CrewAI `LLM` (verified 1 Oct: `gemini-2.5-flash` returns 404 "no longer available to new users"; using **`gemini-3.6-flash`**, thinking_level=low). |
| Structured output | Crew tasks: `output_pydantic=` (`Extracted`, `SignalSet`, `ClaimEvidence`); vision: `response_schema=Extracted`. Fallback: parse `result.raw` after stripping fences; retry once; then `gemini_error`. |
| Grounding | Only in `GroundedSearchTool` (claim crew); separate google-genai call without schema (cannot combine with tools). |
| Telemetry | `CREWAI_DISABLE_TELEMETRY=true`, `OTEL_SDK_DISABLED=true` set in `config.py` before importing crewai. |
| Timeouts | LLM 30 s; whole Flow 60 s via `asyncio.wait_for` in executor. |
| Verdicts | Computed in Python from `ClaimEvidence`; VERIFIED/DEBUNKED only from a fact-check outlet with explicit rating; else UNVERIFIED. Agent never asserts one. |
| Scoring | One file `rules/scoring.py`; dedupe by key; category caps; bands 75/45. |
| Severity | Exactly three: high 🔴, medium 🟠, low 🟡. |
| ELA | JPEG/WebP only; heatmap returned as b64; never claimed as proof. |
| EXIF | Absence is never a signal. |
| Demos | Generated by `scripts/make_demos.py`; Gemini output pre-recorded with `--record`; served with `analysis_mode: demo_cached`. |
| Fallback | On crew/vision failure return rule+forensics report + `gemini_error`; never fabricate. |
| Stages UI | Timed frontend animation, no SSE. |
| Frontend | TypeScript, Tailwind v4 via `@tailwindcss/vite`, Vite proxy `/api`. |
| Safeguards | LLM can add but never remove/downgrade RULE signals; known-org URL attenuation; unknown keys → misleading_claim; LOW = "No risk signals found"; `caveats[]` always present; never fetch user URLs; privacy line in UI. |
| Content source | Agent prompts, rules, org list, demo text, sample report: `content_kit.md` (Appendix D). Do not rewrite them from memory. |
| Hosting | Railway, one service (FastAPI serves built frontend), Dockerfile, healthcheck `/api/health`. New Railway account: `railway login` requires the user in the browser — Claude Code stops and asks; never `railway link` to the existing project; `railway init` new project only after the user confirms `whoami`. Time-box 25 min, after demos work. |
| Storage | None. Stateless. |
| Auth | None. |

## Never do
- Hardcode or log the API key; put it in frontend; commit `.env`.
- Add auth, DB, queues, microservices, SSE, multi-file upload.
- Use CrewAI hierarchical process, delegation, memory/knowledge, or `multimodal=True` beyond a 10-min spike.
- Let an agent compute the trust score or the verdict (Python does both).
- Let Gemini's opinion set a fact-check verdict.
- Output "fake"/"real" as a verdict.
- Rewrite working code for style.
- Spend >20 min on any polish item before the cut line is done.

## Conventions
- Backend: Python 3.11–3.13 (CrewAI bound), FastAPI, Pydantic v2, CrewAI, google-genai, Pillow, piexif, httpx. Type hints, `ruff`-clean.
- Crew code lives in `services/crew/` (llm, agents, tasks, tools, crews); Flow in `services/flow.py`. Agent goals/backstories ≤ 3 sentences each.
- Signal keys: snake_case from the shared enum in `models/gemini.py`.
- Every signal has `sources` (list) and `explanation` in plain language.
- Frontend types in `src/types/report.ts` mirror `models/report.py` exactly.
- Commit after each build stage with message `stage N: <what>`.

## Build order (cut line — stop cleanly wherever time runs out)
- [ ] 1 Backend skeleton, config (telemetry off), health, Flow + text crew (Extractor → Analyst) → rules → score → report
- [ ] 2 Image analyze: EXIF, ELA (+heatmap), Gemini vision step, rules on extracted_text → Analyst
- [ ] 3 Frontend: InputPanel, StageProgress, ReportView (gauge, badge, signals, source badges)
- [ ] 4 Demo generation script, fixtures recorded, demo endpoints, DemoChips
- [ ] 5 ElaCompare in UI
- [ ] 6 Claim crew: Claim Verifier + GroundedSearchTool + Python verdict rule + EvidenceList
- [ ] 7 FactCheckSearchTool (Fact Check Tools API key path)
- [ ] 8 README, `.env.example`, final verification
- [ ] 9 Railway deploy (Dockerfile, railway.json, login handshake with user, variables, domain, health + demo check) — only after 4, before 2:00 PM

## Verification checklist (run before calling any stage done)
- `GET /api/health` → 200 with `{"gemini_model": ..., "gemini_configured": true, "crewai_version": ...}`.
- Backend startup logs no telemetry/OTEL warnings; no outbound calls except Gemini/LiteLLM and fact-check.
- `POST /api/analyze/text` response has `agents_used: ["extractor","analyst"]` and GEMINI-sourced signals with non-empty `evidence` quotes.
- Text analyze completes < 20 s on flash; image < 25 s.
- `POST /api/analyze/text` with scam SMS → HIGH, signals include `urgency`, `kyc_threat`, `suspicious_url` with mixed sources.
- `POST /api/analyze/image` with `demo_notice_edited.jpg` → HIGH, `editing_software_exif` + `ela_anomaly` present, `ela.heatmap_b64` non-empty.
- `POST /api/analyze/image` with `demo_notice_genuine.jpg` → LOW.
- PNG upload → `ela.status == "not_applicable_lossless"`, no ELA signal.
- Bad key → crew fails fast; text analyze still returns a report with `gemini_error` set; UI shows banner.
- Demo endpoints return `analysis_mode: "demo_cached"`; live uploads return `"live"`.
- `grep -r "AIza" frontend/dist` → no matches.
- Deployed: `https://<railway-domain>/api/health` 200; one cached demo chip renders; `.env` not in image (`docker history`/`.dockerignore`).
- Score dedupe: same key from RULE and GEMINI counted once.

## Commands
```
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
python scripts/make_demos.py            # images + txt
python scripts/make_demos.py --record   # vision + crew fixtures (needs key)
uvicorn app.main:app --reload --port 8000
# frontend
cd frontend && npm i && npm run dev     # http://localhost:5173
```

## Known risks
- Gemini API free tier has per-minute and per-day request caps (check ai.google.dev/gemini-api/docs/rate-limits on the day). Each crew request = 2–6 model calls. Mitigate: fixtures for demos, no retry loops in tests, `gemini-2.5-flash-lite` for dev iterations if caps bite. Ask organisers at check-in whether Gemini credits/keys are provided.
- CrewAI + Gemini via LiteLLM: `output_pydantic` may come back None → parse `result.raw`. If still failing after 45 min in stage 1, last resort = direct google-genai structured call behind the same function; log it here.
- CrewAI adds latency (1–3 LLM calls per agent). Keep `max_iter=2`, no tools on Extractor/Analyst, short backstories.
- CrewAI install is heavy; pin a recent 1.x in requirements.txt and install first thing.
- Model name drift → check ai.google.dev once; set env.
- Fact Check Tools API needs a Google Cloud key with the API enabled; treat as optional.
- Gemini may over-flag genuine notice → tune `ANALYSIS_SYSTEM` to require quoted evidence per signal; keep genuine demo LOW.
- ELA thresholds need calibration against the two demo images; set so genuine < medium, edited ≥ high.

## Status
Current stage: 1–6 + 8 done; 7 coded but untested (no FACTCHECK_API_KEY); 9 (Railway) pending user login   Last verified: 1 Oct 11:10

## Log
<!-- append: [time] stage N — what changed, what was verified, open issues -->
- [10:35] stages 1–3, 5, 8 (code) — backend Flow/rules/scoring/forensics/crew/tools/demo endpoints, frontend (all design.md components), README, Dockerfile, railway.json. Verified without a key: health 200, scam SMS → 25 HIGH (rule-only, `gemini_error` set), injection → 25 HIGH, edited notice ELA region on the two altered lines + EXIF signals, genuine notice → 100, PNG → `not_applicable_lossless`, non-image → 415, UI renders reports from the real API. crewai 1.15.23 (native Gemini provider), google-genai 2.26.0, Python 3.12.
- Deviations from content_kit (all deliberate, small):
  - ELA: single q90 re-save could not separate the demo images (text edges dominate; genuine and edited both ≈2.2×). Now a re-save sweep over q95…60 (JPEG-ghost style), hottest block vs median content block; thresholds high ≥4.0, medium ≥3.0 (genuine peaks 2.5, edited 4.7).
  - Edited demo pipeline: genuine → forwarded copy q75 → two lines re-typed → editor export q98 + Photoshop EXIF (spec said save q75; a final low-quality save erases every ELA trace, so no honest ELA hit was possible).
  - `urgency` pattern `last (chance|date|day)` → `last (chance|day)`: "Last date for payment" on a genuine notice is not urgency.
  - `financial_request`: word boundaries on `rs`/`inr`/`fee`.
  - WEAK_ALIASES (upi, aadhaar, meta, apple, axis, …) never establish a claimed organisation on their own.
  - Deterministic "Prompt injection attempt" rule (key `action_pressure`, high) in addition to the Analyst's — the injection demo holds even rule-only.
  - Claim Verifier `max_iter=4` (needs up to 3 tool calls + answer); other agents 2.
  - Evidence URLs must appear in the per-run tool ledger or they are dropped; grounding redirect links are resolved to the real source URL.
  - Risk floor: a high-severity signal is never shown as LOW (image-forensics cap of 25 alone would give 75 = LOW).
  - Report contract additions: `score_breakdown`, `what_to_verify`, `inconsistencies`, `notes`, `ela.width/height`, signal `uncertainty`.
- [11:10] Gemini key added. Live text crew verified once on gemini-3.6-flash (Extractor → Analyst, valid `Extracted` + `SignalSet` via output_pydantic, GEMINI signals merged with RULE). Default thinking made a run take 64 s; `thinking_level="low"` brings a call to ~2–3 s.
- **Quota: this key's free tier is 20 requests/day per model** (quotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier); failed 503 attempts count. 3.6-flash, 3.5-flash and 3.5-flash-lite are exhausted for today. Live analysis will return rule-only reports until the quota resets or a billed/second key is used.
- Fixtures recorded from real Gemini output: scam_sms (3.6-flash), injection, edited_notice, genuine_notice (3.5-flash), viral_claim (3.5-flash-lite). Cached demo results: genuine 94 LOW, edited 30 HIGH, scam SMS 25 HIGH, injection 25 HIGH, claim UNVERIFIED.
- Open: claim demo has NO evidence — Google Search grounding returned 429 on the free tier and no FACTCHECK_API_KEY is set, so the Claim Verifier tools have never returned a source; verdict logic (DEBUNKED/VERIFIED) is untested against live data. Live image path (vision + analyst through the HTTP endpoint) was exercised only via the recorder script, not via /api/analyze/image.
- [12:10] Accuracy pass after a user report that a real image was flagged. Built an ELA test set from 30 unedited system photos x 5 compression histories + 17 others (167 negatives) and 19 edited images. Before: 12/167 unedited flagged (10 high). Cause: the sweep included the file's own save quality, where saturated blocks look like outliers. Now the own quality is skipped and "high" needs a compact region (box <= 12% of image): 4/167 flagged (1 high, 3 medium); all 19 edited still flagged (15 high, 4 medium). WebP no longer produces an ELA signal.
- Also: editor EXIF tag high -> medium; safety advice ("never share your OTP") no longer counts as a credential request; in image mode keyword-only hits with no link or impersonation problem are medium, not high (Gemini can raise); Analyst prompt now says ordinary document features are not signals. The prompt change is NOT tested live (quota exhausted); fixtures were recorded with the older prompt.
- [13:10] Image analysis now has two user-selected intents, sent as form field `analysis_mode` on POST /api/analyze/image (`synthetic_detection` | `artifact_authenticity`, default artifact) and echoed in the report as `analysis_intent` (the report's existing `analysis_mode` still means live vs demo_cached). Report adds `overall_assessment`, `media_assessment`, `artifact_assessment` ({state,label,summary}, computed in Python) and `confidence_boosters`.
  - synthetic_detection: forensics + ONE Gemini vision call (`VisualAssessment`, google-genai structured) whose indicators become GEMINI signals (new keys ai_generation_indicator / manipulation_indicator / visual_inconsistency, category visual_analysis, cap 45). No text rules, no CrewAI agent (a text-only agent cannot see the image).
  - artifact_authenticity: existing pipeline; vision prompt and Analyst task get an artifact-specific addendum.
  - Verified live once each on gemini-3.1-flash-lite (3.6-flash quota exhausted): genuine notice in synthetic mode -> LIKELY_AUTHENTIC; edited notice in artifact mode -> MANIPULATED. NOT tested on a real AI-generated image or a real fake-payment screenshot. No "EXTERNAL SOURCE" provenance exists for images (only claim mode has external sources).
- [13:50] Trust-score accuracy pass on text rules, measured with `backend/tests/score_eval.py` (25 legitimate + 25 scam messages written for this test; rules only, no Gemini). Before: 30/50 in the right band (legit 23 LOW / 2 MEDIUM; scams 7 HIGH / 16 MEDIUM / 2 LOW). After: 44/50 (legit 25 LOW; scams 19 HIGH / 6 MEDIUM / 0 LOW). Changes: message_content cap 45 -> 60 (a link-less scam could never reach HIGH); threat 10 -> 15; wider threat/urgency/callback/credential patterns; new rule "Prize or easy-money bait" (misleading_claim); transaction alerts ("debited ... via UPI to X") no longer a payment request; fake_authority is high when combined with a threat and a demand; look-alike hosts now catch spelt-out weak aliases (incometax-refund.online); official-domain attenuation also caps kyc_threat/threat. Demo scores moved: scam SMS 25 -> 10, injection 25 -> 14, edited notice 32 -> 31. The set was written by the same author as the rules, so it over-states real-world accuracy.
- [14:25] PDF Trust Report: POST /api/report/pdf takes the TrustReport JSON, returns a ReportLab PDF built in memory (services/pdf_report_service.py, services/report_writer.py, routes/report.py; frontend PdfButton). Default wording is "direct" (deterministic, from the analysis). Optional OpenRouter wording layer (env OPENROUTER_API_KEY + OPENROUTER_REPORT_MODEL, id must end ":free") is implemented but has NEVER been called against the real OpenRouter API: no key was provided; it is tested only with mocked responses (tests/test_report_pdf.py: facts pinned, invented signal dropped, malformed/404/timeout/over-claim/invented URL -> direct fallback, paid model never called, tampered score -> 422). Note: an OpenRouter model is a non-Gemini LLM in app code, which the kit's "Gemini only" rule forbids; it is off unless the env vars are set, and it never analyses anything. No image preview in the PDF (the endpoint does not receive the image).
- [15:00] Repeatability fix for image/screenshot analysis (user saw different scores for the same image). Gemini calls now run at temperature 0, top_k 1 (vision also fixed seed); one retry on a brief 503 in the vision step; identical input + same intent + same model reuses the completed report from a RAM-only cache (64 items, 30 min, never caches a Gemini-unavailable result, never written to disk). UI privacy line changed from "Not stored" to "Not saved to disk" because of that cache. Verified live on gemini-3.1-flash-lite with the cache bypassed: edited notice twice per mode -> identical (synthetic 57 MANIPULATED both runs; artifact 42 LIKELY_FABRICATED both runs). The two modes still give different scores for one image by design (they answer different questions). A run where Gemini is unavailable will still differ from a run where it works.
