# Specialist model selection

**Decision for this build: no pretrained specialist model is enabled.** Every slot in
`backend/app/ml/registry.py` reports `MODEL_UNAVAILABLE`, and each report says so. Perception is done
by Gemini (visual/audio examination, OCR, transcription, stance reading) plus deterministic checks
(EXIF, ELA, ffmpeg container metadata, text rules, source-tier and independence rules).

Why: the deployed service is one small CPU container with no `torch`. Every detector below needs
torch plus a ViT-L-class or wav2vec-class backbone, most need a GPU, and none was run or validated by
us. Enabling an unvalidated detector would add a confident-looking number with no evidence behind it.

How this table was made: a literature and repository pass on 1 Oct 2026 over the papers, official
repos and model cards. Figures are quoted from those sources, not measured by us. "Not verified"
means the primary source did not state it or we could not confirm it. Nothing here was downloaded or
run.

The headline finding across all three media types: detectors that score 90%+ on their own benchmarks
drop sharply on real-world data. Deepfake-Eval-2024 (arXiv 2503.02857) reports open-source detectors
losing on average about 45% (image), 50% (video) and 48% (audio) AUC against academic benchmarks.

## AI-generated image detection

| Model | Architecture | Trained on | Published | In-the-wild evidence | Checkpoint | Licence | Status |
|---|---|---|---|---|---|---|---|
| B-Free (Guillaro et al.) | DINOv2 ViT (4 registers), 504 px crops | MS-COCO real + SD 2.1 self-conditioned fakes | avg 99.0 AUC / 95.2% bAcc on its benchmarks | WildRF 96.0 AUC / 89.8% bAcc; SynthWildX 95.6 / 95.6 (paper) | Public download from the authors | Non-commercial (GRIP-UNINA) | **Deferred** – best candidate; needs torch + larger host; licence must be respected |
| DGS-Net (arXiv 2511.13108) | CLIP ViT-L/14 + LoRA, gradient surgery | ProGAN + SD v1.4 (AIGIBench) | GenImage 97.6% mean acc | Authors report weak results on DALL-E 3 and social-media sets; no independent replication found | Repo links a checkpoint but also lists pretrained models as "coming soon" – not verified | Apache-2.0 (repo) | **Rejected for now** – checkpoint status unclear, no in-the-wild evidence |
| AIDE (ICLR 2025) | Frequency/noise ResNet-50 + OpenCLIP ConvNeXt | ProGAN or GenImage | 92.8% AIGCDetectBenchmark | 58–66% on its own Chameleon set (misses most fakes) | Google Drive | MIT (code) | **Rejected** – poor on realistic fakes by its own paper |
| DIRE (ICCV 2023) | Diffusion reconstruction error + CNN | DiffusionForensics | not verified | Distilled variant 0.52 AUC on Deepfake-Eval-2024 | Baidu drive only | not verified | **Rejected** – runs a diffusion model per image (GPU, slow) |
| UnivFD (CVPR 2023) | Frozen CLIP ViT-L/14 + linear layer | ProGAN | +15 mAP over prior work on unseen generators | 0.56 AUC Deepfake-Eval-2024; 57% Chameleon | In repo (linear head) | MIT | **Deferred** – simplest to integrate, weakest real-world results |

If a GPU or a 4 GB+ CPU host were available: B-Free first, as the only candidate with a downloadable
checkpoint *and* published social-media results. One detector plus Gemini's observations is
complementary; stacking several CLIP-based classifiers would be redundant.

## Video deepfake detection

| Model | Level | Trained on | Cross-dataset evidence | Trained weights shipped? | Licence | Status |
|---|---|---|---|---|---|---|
| DeepfakeBench frame detectors (Xception, EfficientNet-B4, UCF, SPSL …) | Frame (face crop) | FF++ c23 | Frame AUC ≈ 0.70–0.77 on Celeb-DF v2 / DFDC | Yes (13 image-level detectors in the releases) | CC BY-NC 4.0 | **Deferred** – only "download and run" option; face-swap only |
| FTCN (ICCV 2021) | Temporal | FF++ | 0.50 AUC on Deepfake-Eval-2024 (chance) | Yes (original repo) | not verified | **Rejected** – chance-level in the wild, 2020-era dependencies |
| VideoMAE / X-CLIP / TimeSformer detectors (DeepfakeBench) | Temporal | FF++ | not verified | **No** – code only; no trained detector weights found | CC BY-NC 4.0 | **Rejected** – would need training |

All of these require face detection and cropping, so they say nothing about faceless or fully
generated (text-to-video) clips. TrustLens today samples keyframes (uniform + scene changes) and
sends them with the audio track to Gemini; it therefore cannot judge motion, flicker or lip-sync,
and reports that limit on every video.

## Synthetic speech / anti-spoofing

| Model | Architecture | Trained on | Published | In-the-wild evidence | Licence | Status |
|---|---|---|---|---|---|---|
| nii-yamagishilab/wav2vec-large-anti-deepfake | wav2vec 2.0 Large + classifier, 0.3B params | ~74k h, 100+ languages | In-the-Wild EER 1.9% (model card) | Deepfake-Eval-2024 EER 33% (AUC 0.74) | CC BY-NC-SA 4.0 | **Deferred** – best candidate; needs torch + fairseq, non-commercial |
| XLS-R + AASIST (Tak et al.) | wav2vec 2.0 XLS-R + graph attention | ASVspoof 2019 LA (English) | ASVspoof 2021 LA EER 0.82% | Not in the primary source | MIT (code) | **Rejected** – English read speech only, pinned 2021 stack |
| AASIST / AASIST-L | Raw-waveform graph attention (85K params for -L) | ASVspoof 2019 LA | EER 0.83% | 0.43 AUC on Deepfake-Eval-2024 (below chance) | MIT | **Rejected** – small enough for CPU, but does not generalise; would mislead |

Codec sensitivity and Indian-language performance of these models: not verified.

## News / claim stack

| Role | Candidate | Notes | Status |
|---|---|---|---|
| OCR | PaddleOCR (PP-OCRv5 per-script models incl. Devanagari, Telugu, Tamil) | Apache-2.0; small models, but PaddlePaddle runtime footprint not verified | **Deferred** – Gemini reads the text today |
| ASR | openai/whisper-large-v3-turbo (809M params, MIT) | Needs torch + ~1.6 GB weights | **Rejected for this host** |
| ASR | faster-whisper `small` (CTranslate2, MIT, no torch) | Project benchmark: 1.48 GB RAM on CPU int8 | **Deferred** – first pick on a 2–4 GB host; Gemini transcribes today |
| Retrieval | BAAI/bge-m3 (MIT, 100+ languages, 8192 tokens) | Needs torch | **Deferred** |
| Retrieval | intfloat/multilingual-e5-small (MIT) | Plausible via ONNX; footprint not verified | **Deferred** – measure first |
| NLI | cross-encoder/nli-deberta-v3-base | English only – unsuitable for Hindi/Telugu claims | **Rejected** |
| NLI | MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7 (MIT) | Hindi, Bengali, Marathi, Tamil, Urdu in training; Telugu not | **Deferred** – Gemini reads headline stance today |
| Fact-check lookup | Google Fact Check Tools API (`claims:search`) | One HTTP call, needs an API key; only finds already-published fact-checks | **Integrated** (`services/factcheck.py`), inactive until `FACTCHECK_API_KEY` is set |

What runs instead today: Google News RSS search → publisher tier from `rules/source_registry.json`
→ one vote per independent site → verdict computed in Python. Stance of each headline is read by
Gemini, which is weaker than an NLI model and is stated in the report.

## Enabling a detector later

1. Install the runtime (`requirements-ml.txt`) on a host with enough memory and set `TRUSTLENS_ML=1`.
2. Add a loader for the slot in `app/ml/registry.py` (`_LOADERS`); it is loaded once and cached.
3. Run it on a held-out sample set (authentic, AI-generated, edited, compressed) and record the
   result here before letting it influence any assessment.
4. Its output enters reports as a `MODEL` evidence signal with its known limits attached; a softmax
   score is not presented as a calibrated probability.

## Not verified

Checkpoint sizes and CPU latency for every detector; whether the DGS-Net checkpoint is actually
downloadable; any published metric for the temporal DeepfakeBench detectors; codec and
Indian-language behaviour of the audio models; Fact Check Tools API quotas.
