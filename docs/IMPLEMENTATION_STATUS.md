# Implementation status (2026-10-28)

Plan v2.0 is the implementation target. The current deliverable is an **internal alpha / technical MVP**: the local stack runs a one-click NASA article-to-video preview, but generated facts still need human review. The plan places P12–P13 after the earlier workflow is stable and at least 20 videos have been published; that trigger has not been reached.

| Prompt | Current status | Verified here / remaining work |
| --- | --- | --- |
| P01 | Baseline complete | Monorepo, schemas, ADRs, Compose, CI. Core infrastructure started locally. |
| P02–P04 | Baseline complete | FastAPI modules, roles, adapters, PostgreSQL schema and migrations. Live PostgreSQL smoke passed. Initial migration still uses metadata-based table creation. |
| P05–P06 | Baseline complete | Script/scene/character history, durable job steps, outbox and retry. Fake-mode production and scene variant tests passed. |
| P07–P08 | Preview path complete | MinIO-compatible S3 assets, FFmpeg render, H.264/AAC MP4 in 16:9 and 9:16, SRT, thumbnail, QC. Autopilot can use the NASA article's primary photograph and local Apple Linh speech. Generative image and motion backends remain unverified. |
| P09 | Partial | Batch and internal webhook APIs, idempotency, status, cancel, Telegram hook and three inactive n8n templates. NASA Earth Observatory discovery, source provenance, idempotent one-click production and a 07:00 daily per-project schedule are implemented. Google Sheets status updates, credentials and delivery acceptance remain pending. |
| P10 | Baseline complete | Dashboard, project/episode flow, storyboard image variants, Job Center with preview/download and registration. Dashboard and project pages expose source discovery and model status. |
| P11 | Partial | FFmpeg checks, SRT validation, blocking QC report, browser script/review decisions, and QC-gated ZIP export with metadata/download are implemented. Automatic child-safety/image-quality evaluation remains pending. Fake assets are deliberately blocked from publishing. |
| P12 | Deferred by plan gate | No LoRA training, checkpoint or MLflow/DVC training run; requires the ADR-007 trigger and published baseline. Runtime explicitly reports that LoRA is absent. |
| P13 | Partial / deferred by plan gate | Authentication, workspace roles, metrics endpoint and monitoring config exist. Alerting, load tests, and security hardening still need validation. |

The machine has Apple M1/8 GiB, FFmpeg 9.0.2 and Ollama 0.40.11 with `qwen3:4b` selected. A direct Qwen3 4B structured-output call generated six Vietnamese scenes in about 90 seconds. The live one-click flow selected a current NASA article; PostgreSQL/S3/Celery used its primary NASA photo, produced six Apple Linh WAV clips and H.264/AAC previews in both aspect ratios. The latest successful run completed all 14 job steps and wrote 360×640 and 640×360 H.264/AAC MP4s of about 59 seconds. Frame checks show the photo and captions fit both aspects. The six scenes reuse one NASA source photograph; they are not six distinct AI-generated illustrations or motion scenes.

The factual gate now rejects unsupported long timelines, seasons absent from the source, Arctic/Antarctic confusion, and a reversed northward route. A Docker interruption was recovered by marking abandoned source generation failed, allowing retry. **These rules are partial:** the latest accepted script still contains inaccurate or awkward geography (for example, “điểm cực Nam của Nam Cực” and “Bắc - Bắc Tây Nam Cực”). The MP4s are unreviewed previews and must not be published. QC blocks public export pending source-fact, image rights, voice, image-quality, and child-safety review. Production deployment also needs dependable factual grounding, distinct scene visuals, and security/operations validation. No LoRA is active.

