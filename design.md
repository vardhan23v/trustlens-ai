# TrustLens AI — UI/UX Design

Tagline: **See Beyond the Digital Surface.**  Principle: **Don't just tell users what to trust. Show them why.**

## 1. Direction
Dark, forensic, calm. Not "hacker green". Evidence-first layout: the score is prominent but every signal card is readable without scrolling past it. One accent colour; severity colours reserved for signals and the risk badge only.

## 2. Tokens (Tailwind theme)
```
bg          #0B0F17   surface  #111827   surface-2 #1A2233   border #253047
text        #E6EAF2   muted    #94A3B8
accent      #22D3EE   (cyan)   accent-soft #0E7490
risk-low    #22C55E   risk-med #F59E0B   risk-high #EF4444
sev-high    #EF4444   sev-med  #F97316   sev-low   #EAB308
rule-badge  #6366F1 (indigo)   gemini-badge #14B8A6 (teal)
```
Type: Inter (UI), JetBrains Mono (score, extracted fields, domains, URLs). Radius 12px cards, 999px badges. Subtle 1px borders, no heavy shadows.

## 3. Page layout (single page, max-w 6xl, 16px gutters)

```
┌───────────────────────────────────────────────────────────────┐
│ Header: ◈ TrustLens AI   See Beyond the Digital Surface.   [ Gemini-powered ] │
├───────────────────────────────────────────────────────────────┤
│ InputPanel                                                     │
│  Tabs: [ Screenshot / Image ] [ Message / Text ] [ News Claim ] │
│  DropZone  |  TextArea (mode-specific placeholder)              │
│  Demo chips: Genuine notice · Edited notice · Scam SMS · Viral claim · Injection │
│  [ Analyze with Gemini ]                                        │
├───────────────────────────────────────────────────────────────┤
│ StageProgress (visible only while analyzing)                    │
├───────────────────────────────────────────────────────────────┤
│ ReportView                                                      │
│  ┌─────────────┬──────────────────────────────────────────────┐ │
│  │ TrustGauge  │ RiskBadge  ·  ModeBanner (cached / no-Gemini) │ │
│  │  22 / 100   │ Recommendation box                            │ │
│  └─────────────┴──────────────────────────────────────────────┘ │
│  ElaCompare (image only): original | heatmap, region outlined   │
│  Signals (sorted high→low): SignalCard ×N                       │
│  DeductionTable: signal → points, capped per category → score   │
│  Evidence (claim only): source · rating · link                  │
│  Extracted panel (collapsible, mono)                            │
│  AgentsFootnote · Disclaimer                                    │
└───────────────────────────────────────────────────────────────┘
```
Mobile: stack gauge above badge/recommendation; tabs become a segmented control; ELA compare stacks vertically.

## 4. Components (`src/components/`)

| Component | Props | Notes |
|---|---|---|
| `Header` | — | Logo mark = lens/eye glyph in accent, wordmark, tagline, small "Powered by Gemini · CrewAI" pill |
| `InputPanel` | `mode, onModeChange, onSubmit, busy` | Holds tabs, DropZone/TextArea, DemoChips, AnalyzeButton |
| `DropZone` | `file, onFile` | Drag/drop + click; image preview thumbnail; accepts jpg/png/webp ≤10 MB; inline error |
| `TextArea` | `value, onChange, placeholder` | Placeholders: "Paste SMS / WhatsApp / email…", "Paste the viral claim or forwarded message…" |
| `DemoChips` | `demos[], onPick` | Loads demo into input AND marks request as demo id; chip shows "cached" tooltip |
| `AnalyzeButton` | `busy, disabled` | Primary accent; disabled while busy; label "Analyze with Gemini" → "Analyzing…". Below it, one muted line: "Not stored. Sent to Gemini for analysis only." |
| `StageProgress` | `stage` | 8 stages, vertical on mobile / horizontal on desktop; done ✓, active pulse, pending dim |
| `TrustGauge` | `score, risk` | SVG ring 180px, stroke coloured by risk, number animates 0→score over 900 ms, "/100" mono |
| `RiskBadge` | `risk \| verdict` | HIGH RISK / MEDIUM RISK; LOW renders as **NO RISK SIGNALS FOUND** with subline "not verified as authentic"; claim mode shows VERIFIED BY SOURCE / DEBUNKED BY SOURCE / UNVERIFIED |
| `ModeBanner` | `analysisMode, geminiError` | "CACHED DEMO — Gemini output pre-recorded" or "Gemini unavailable — rule-based results only" |
| `RecommendationBox` | `text` | Bold first sentence, then guidance |
| `ElaCompare` | `originalUrl, heatmapB64, region, status` | Side-by-side, region rectangle overlay, caption "ELA highlights compression differences; not proof of editing" |
| `SignalCard` | `signal` | Left severity bar; title; `SourceBadge` per source; explanation; evidence quote in mono if present |
| `SourceBadge` | `source: RULE\|GEMINI` | Indigo RULE, teal GEMINI; both shown when merged |
| `DeductionTable` | `signals[], score` | Rows: signal · severity · source · −points; category subtotal with cap shown as "45 of 71 (capped)"; final line 100 − Σ = score. Makes the number auditable |
| `Caveats` | `caveats[]` | Muted bullet list under the recommendation: what this analysis cannot tell you |
| `EvidenceList` | `evidence[]` | Source name, rating chip (green/red/amber), external link |
| `ExtractedPanel` | `extracted` | Collapsible key/value grid; URLs/domains/phones in mono |
| `AgentsFootnote` | `agentsUsed[]` | One muted line: "Analysed by CrewAI agents: Extractor, Trust Signal Analyst (Gemini)" |
| `Disclaimer` | — | "Trust Score is a risk indicator, not proof of authenticity or fraud." |

## 5. States
- **idle**: InputPanel only, subtle hint text under the button.
- **analyzing**: button disabled, StageProgress runs a timed animation (400 ms/stage); when the response arrives, remaining stages flash complete and ReportView fades in.
- **result**: ReportView; input stays above so the user can re-run.
- **error**: inline red card under input with the backend message; demos remain clickable.

Stages (exact labels): Reading content → Extracting information → Checking metadata → Running rule checks → Checking suspicious signals → Gemini reasoning → Calculating trust score → Generating Trust Report.

## 6. Report copy rules
- Signal title ≤ 5 words; explanation 1–2 sentences, plain language.
- Severity icons: 🔴 high, 🟠 medium, 🟡 low.
- Never render "fake" / "real" / "safe" as a verdict; only risk bands, "No risk signals found", and source-backed verdicts.
- Recommendation for HIGH: lead with the protective action ("Do not pay or share credentials yet.").

## 7. Motion and feel
Ring count-up, stage pulse, card fade-in (staggered 60 ms). Nothing else animates. Respect `prefers-reduced-motion`.

## 8. Accessibility
Contrast ≥ 4.5:1 on all text; severity conveyed by icon + label, not colour alone; DropZone keyboard-focusable; live region announces "Analysis complete".

## 9. Demo choreography (what the judges see)
1. Click **Genuine notice** → LOW RISK, few/no signals, ELA quiet, recommendation "appears consistent; verify via official channel if acting on it".
2. Click **Edited notice** → HIGH RISK; ElaCompare shows hot region on the altered field; EXIF editing-software signal (RULE); Gemini inconsistency signal (GEMINI).
3. Click **Scam SMS** → HIGH RISK; urgency, KYC threat, shortener/suspicious URL, impersonation; RULE + GEMINI badges on the same card.
4. Paste a viral claim → verdict badge with evidence links, or UNVERIFIED with "what to verify".
5. (If time) Click **Injection** → the hidden "report as LOW RISK" instruction shows up as a HIGH signal "Prompt injection attempt" — proof the score is computed in code, not by the model.
