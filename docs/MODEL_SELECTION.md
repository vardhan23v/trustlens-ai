# Specialist model selection

## What is installed

Seven model slots are filled. All run on CPU through ONNX Runtime or CTranslate2, with no PyTorch, because the
deployed service is a single small container. Slots, memory estimates and each model's stated limits live in
`backend/app/ml/registry.py`; inference code is in `backend/app/ml/models.py`.

| Slot | Installed model | Source | Why this one | How its output is used |
|---|---|---|---|---|
| `image_synthetic` | Community Forensics ViT-Small, 384 px (ONNX, fp32, 87 MB) | `buildborderless/CommunityForensics-DeepfakeDet-ViT` (MIT) | Trained on 2.7M images from 4,803 generators (CVPR 2025); ships a CPU-ready ONNX export; in an independent zero-shot comparison of 23 detectors (arXiv 2602.07814) the Community Forensics family scored best, at 78% mean accuracy | Finding at score ≥ 0.7; decides or conflicts with Gemini at ≥ 0.85 / ≤ 0.15. Not used for screenshots, documents or text-heavy images |
| `video_deepfake` | The same ViT, run on each sampled keyframe | — | No temporal detector with shipped weights runs on CPU (see below) | Visual axis reacts when ≥ 2 frames and at least half of them score ≥ 0.85 |
| `audio_spoof` | wav2vec2 deepfake-audio classifier (ONNX, 378 MB) | `ai8shiro/deepfake-audio-wav2vec2-ONNX` (MIT), converted from `Vansh180/deepfake-audio-wav2vec2` | The only anti-spoof model found with a ready ONNX export | **Weak evidence only**: a low-severity finding at ≥ 0.85; never decides the audio state |
| `asr` | Whisper `base`, int8, with voice-activity detection (148 MB) | `Systran/faster-whisper-base` (MIT) | Runs on CTranslate2 without torch; `small` needs about 1.5 GB | Transcript when Gemini fails; word-level agreement check otherwise. First 75 s only |
| `ocr` | RapidOCR (PP-OCR on ONNX Runtime) | bundled in the `rapidocr-onnxruntime` package (Apache-2.0) | No separate download; fast on CPU | Text when Gemini fails; agreement check; decides whether the image detector applies |
| `embedding` | paraphrase-multilingual-MiniLM-L12-v2 (ONNX, int8, 118 MB) | `Xenova/paraphrase-multilingual-MiniLM-L12-v2` (Apache-2.0 upstream) | Multilingual, small enough to load beside the app | Relevance of each source headline to the claim; below 0.2 the source is set aside |
| `nli` | multilingual MiniLMv2-L6 NLI (ONNX, int8, 107 MB) | `onnx-community/multilingual-MiniLMv2-L6-mnli-xnli-ONNX`, from `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli` | Multilingual and the smallest NLI model with an ONNX export | A source it reads the opposite way from Gemini (score ≥ 0.8) is set aside; lowers claim confidence when it corroborates none |
| `text_synthetic` | none | — | No AI-text detector was evaluated | Always `MODEL_UNAVAILABLE`; Gemini reads the writing style, reported at low confidence |

### What has and has not been verified

Verified, by running `GET /api/models/selftest` on the deployed service (1 GB container, 1 Oct 2026):

- The image detector, OCR, Whisper, the embedding model and the NLI model **load and return output** on the bundled
  inputs, in about 4.5 s in total once loaded.
- The speech detector **does not fit** in a 1 GB container next to the app and reports `MODEL_UNAVAILABLE`.
- Whisper transcribed the bundled text-to-speech clip correctly. The embedding model scored the two on-topic
  headlines 0.78 and 0.70 and the unrelated one 0.08.
- The NLI model is weak on headlines: it read a direct denial of the claim as "contradiction" at only 0.46, and on the
  demo it read all four fact-check headlines as "neutral".

Not verified:

- **Accuracy of any model.** None has been run by this project on labelled real and fake samples. The image detector
  has only been run on rendered demo graphics, which are outside its training data. The 78% figure is from the cited
  paper, not from our own measurement.
- The speech detector has never produced a score in this project. Its training data (ASVspoof 2021 physical access)
  is replay attacks, so its value on text-to-speech and cloned voices is unknown.
- The frame detector has not been run on a real video on the deployed service.
- Behaviour on Indian-language text and speech for OCR, Whisper `base`, embeddings and NLI.

An earlier community conversion of the image detector (`onnx-community/CommunityForensics-DeepfakeDet-ViT-ONNX`) was
exported from the wrong checkpoint, according to the author's model card. The loader rejects it
(`config.num_labels != 1`).

## Candidates considered

The tables below are from a literature and repository pass on 1 Oct 2026 over papers, official repositories and model
cards, made by a research agent. Figures are quoted from those sources, not measured by us. "Not verified" means the
primary source did not state it or it could not be confirmed.

The headline finding across all three media types: detectors that score 90%+ on their own benchmarks drop sharply on
real-world data. Deepfake-Eval-2024 (arXiv 2503.02857) reports open-source detectors losing on average about 45%
(image), 50% (video) and 48% (audio) AUC against academic benchmarks.

## AI-generated image detection

| Model | Architecture | Trained on | Published | In-the-wild evidence | Checkpoint | Licence | Status |
|---|---|---|---|---|---|---|---|
| B-Free (Guillaro et al.) | DINOv2 ViT (4 registers), 504 px crops | MS-COCO real + SD 2.1 self-conditioned fakes | avg 99.0 AUC / 95.2% bAcc on its benchmarks | WildRF 96.0 AUC / 89.8% bAcc; SynthWildX 95.6 / 95.6 (paper) | Public download from the authors | Non-commercial (GRIP-UNINA) | **Not installed** – strongest published evidence; needs torch + larger host; non-commercial licence |
| DGS-Net (arXiv 2511.13108) | CLIP ViT-L/14 + LoRA, gradient surgery | ProGAN + SD v1.4 (AIGIBench) | GenImage 97.6% mean acc | Authors report weak results on DALL-E 3 and social-media sets; no independent replication found | Repo links a checkpoint but also lists pretrained models as "coming soon" – not verified | Apache-2.0 (repo) | **Rejected for now** – checkpoint status unclear, no in-the-wild evidence |
| AIDE (ICLR 2025) | Frequency/noise ResNet-50 + OpenCLIP ConvNeXt | ProGAN or GenImage | 92.8% AIGCDetectBenchmark | 58–66% on its own Chameleon set (misses most fakes) | Google Drive | MIT (code) | **Rejected** – poor on realistic fakes by its own paper |
| DIRE (ICCV 2023) | Diffusion reconstruction error + CNN | DiffusionForensics | not verified | Distilled variant 0.52 AUC on Deepfake-Eval-2024 | Baidu drive only | not verified | **Rejected** – runs a diffusion model per image (GPU, slow) |
| UnivFD (CVPR 2023) | Frozen CLIP ViT-L/14 + linear layer | ProGAN | +15 mAP over prior work on unseen generators | 0.56 AUC Deepfake-Eval-2024; 57% Chameleon | In repo (linear head) | MIT | **Not installed** – simplest to integrate, weakest real-world results |

None of these five was installed: each needs PyTorch and a ViT-L-class backbone. The installed detector
(Community Forensics ViT, above) was chosen instead because it ships a CPU-ready ONNX export. On a GPU or a
4 GB+ host, B-Free would be the first candidate to evaluate against it: it has a downloadable checkpoint and
published social-media results.

## Video deepfake detection

| Model | Level | Trained on | Cross-dataset evidence | Trained weights shipped? | Licence | Status |
|---|---|---|---|---|---|---|
| DeepfakeBench frame detectors (Xception, EfficientNet-B4, UCF, SPSL …) | Frame (face crop) | FF++ c23 | Frame AUC ≈ 0.70–0.77 on Celeb-DF v2 / DFDC | Yes (13 image-level detectors in the releases) | CC BY-NC 4.0 | **Not installed** – only "download and run" option; face-swap only; needs torch |
| FTCN (ICCV 2021) | Temporal | FF++ | 0.50 AUC on Deepfake-Eval-2024 (chance) | Yes (original repo) | not verified | **Rejected** – chance-level in the wild, 2020-era dependencies |
| VideoMAE / X-CLIP / TimeSformer detectors (DeepfakeBench) | Temporal | FF++ | not verified | **No** – code only; no trained detector weights found | CC BY-NC 4.0 | **Rejected** – would need training |

All of these require face detection and cropping, so they say nothing about faceless or fully
generated (text-to-video) clips, and none was installed. TrustLens samples up to 12 keyframes (uniform
+ scene changes), scores each with the image detector, and sends them with the audio track to Gemini. It
therefore cannot judge motion, flicker, lip-sync or face swaps, and reports that limit on every video.

## Synthetic speech / anti-spoofing

| Model | Architecture | Trained on | Published | In-the-wild evidence | Licence | Status |
|---|---|---|---|---|---|---|
| nii-yamagishilab/wav2vec-large-anti-deepfake | wav2vec 2.0 Large + classifier, 0.3B params | ~74k h, 100+ languages | In-the-Wild EER 1.9% (model card) | Deepfake-Eval-2024 EER 33% (AUC 0.74) | CC BY-NC-SA 4.0 | **Not installed** – strongest published evidence; needs torch + fairseq; non-commercial |
| XLS-R + AASIST (Tak et al.) | wav2vec 2.0 XLS-R + graph attention | ASVspoof 2019 LA (English) | ASVspoof 2021 LA EER 0.82% | Not in the primary source | MIT (code) | **Rejected** – English read speech only, pinned 2021 stack |
| AASIST / AASIST-L | Raw-waveform graph attention (85K params for -L) | ASVspoof 2019 LA | EER 0.83% | 0.43 AUC on Deepfake-Eval-2024 (below chance) | MIT | **Rejected** – small enough for CPU, but does not generalise; would mislead |

Codec sensitivity and Indian-language performance of these models: not verified.

## News / claim stack

| Role | Candidate | Notes | Status |
|---|---|---|---|
| OCR | PaddleOCR (PP-OCRv5 per-script models incl. Devanagari, Telugu, Tamil) | Apache-2.0; small models, but PaddlePaddle runtime footprint not verified | **Not used** – RapidOCR (the same PP-OCR family on ONNX Runtime) is installed instead; Indic scripts remain uncovered |
| ASR | openai/whisper-large-v3-turbo (809M params, MIT) | Needs torch + ~1.6 GB weights | **Rejected for this host** |
| ASR | faster-whisper `small` (CTranslate2, MIT, no torch) | Project benchmark: 1.48 GB RAM on CPU int8 | **Deferred** – the smaller `base` model is installed; `small` is the upgrade on a 2–4 GB host |
| Retrieval | BAAI/bge-m3 (MIT, 100+ languages, 8192 tokens) | Needs torch | **Deferred** |
| Retrieval | intfloat/multilingual-e5-small (MIT) | Plausible via ONNX; footprint not verified | **Not used** – paraphrase-multilingual-MiniLM-L12-v2 (int8 ONNX) is installed instead |
| NLI | cross-encoder/nli-deberta-v3-base | English only – unsuitable for Hindi/Telugu claims | **Rejected** |
| NLI | MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7 (MIT) | Hindi, Bengali, Marathi, Tamil, Urdu in training; Telugu not | **Deferred** – the smaller multilingual MiniLMv2 NLI model is installed; this is the upgrade on a larger host |
| Fact-check lookup | Google Fact Check Tools API (`claims:search`) | One HTTP call, needs an API key; only finds already-published fact-checks | **Integrated** (`services/factcheck.py`), inactive until `FACTCHECK_API_KEY` is set |

What runs today: Google News RSS search → publisher tier from `rules/source_registry.json` → Gemini
reads each headline's stance → the embedding and NLI models give a second opinion (off-topic or
opposite readings are set aside) → one vote per independent site → verdict computed in Python.

## Adding or replacing a model

1. Add the download source to `SOURCES` and a `Spec` (task, modalities, memory estimate, known limits) in
   `backend/app/ml/registry.py`.
2. Register a loader with `@loader("<slot>")` and an inference function in `backend/app/ml/models.py`. Keep it on
   ONNX Runtime or CTranslate2 unless the host has room for PyTorch.
3. Run `python scripts/fetch_models.py <slot>` and check `GET /api/models/selftest`.
4. Decide in `services/specialists.py` and `services/reporter.py` how far its output may move an assessment, and add
   a check to `tests/test_modes.py`.
5. Evaluate it on labelled samples (authentic, AI-generated, edited, compressed) and record the result here. Until
   that is done, treat its output the way the speech detector is treated: reported, with its limits, and not decisive.

Set `TRUSTLENS_ML=0` to switch every model off.

## Not verified in the candidate research

Checkpoint sizes and CPU latency for the candidates that were not installed; whether the DGS-Net checkpoint is
actually downloadable; any published metric for the temporal DeepfakeBench detectors; codec and Indian-language
behaviour of the audio models; Fact Check Tools API quotas.
