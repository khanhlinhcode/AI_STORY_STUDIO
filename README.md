# AI Story Studio

Local-first studio for producing Vietnamese children's story videos from recent science and nature articles or a manually entered topic. The implementation uses a Next.js studio, a FastAPI modular monolith, durable PostgreSQL workflow state, Celery workers, content-addressed assets, and replaceable AI adapters. Current readiness is **internal alpha**: sourced MP4 previews work end to end, while generated facts still require human review before publication.

## Current delivery scope

- Automation and Studio execution modes
- Versioned JSON contracts and deterministic fake adapters for development/CI
- Authentication, workspace isolation, projects, episodes, scripts, characters, jobs, quality review, and exports
- Local Docker stack for PostgreSQL, Redis, Silo (MinIO-compatible S3), MLflow, n8n, Prometheus, Grafana, and Jaeger
- Browser workflow from registration to storyboard, job preview, asset browsing, and QC-gated ZIP export
- NASA Earth Observatory discovery, source provenance, one-click production and per-project daily scheduling at 07:00 Asia/Ho_Chi_Minh
- On macOS, optional Apple Linh Vietnamese narration and NASA article photography in sourced video previews
- Independent story and media backends; runtime model/LoRA status is visible in **Models**

## Quick start

Requirements: Docker Desktop, Node 22+, Python 3.12+, and `uv`.

```bash
cp infra/compose/local/.env.example infra/compose/local/.env
make bootstrap
make up
```

API docs: http://localhost:8000/docs. Studio: http://localhost:3000. Use **Tạo workspace** on the login page to create the first account. `make up` starts the studio, API, workers, and their dependencies; `make down` stops them without deleting volumes. The API runs Alembic migrations before it starts.

The example environment defaults to `AI_STORY_MODE=fake`, `AI_ADAPTER_MODE=fake`, and `AI_VOICE_MODE=fake` for a light setup. On this Mac, the local ignored `.env` selects `AI_STORY_MODE=ollama`, `OLLAMA_MODEL=qwen3:4b`, and `AI_VOICE_MODE=macos`. To reproduce it, install Ollama, run `ollama pull qwen3:4b`, run `python3 scripts/start_voice_bridge.py` after `make bootstrap`, set those three variables, and restart the API and workers. The launch agent starts the voice bridge on login. The model writes a Vietnamese six-scene script using the article's main text, publication date and source URL. Autopilot uses the NASA article's primary photograph in all six scenes and Apple Linh system speech in its MP4 preview; it does not yet generate six distinct AI illustrations. Manual topics still use fixture images unless a native image backend is configured. All exports remain QC-blocked pending media rights, factual, voice, and child-safety review. No LoRA checkpoint is installed or trained. The **Models** page reports the running story model, image/voice backend and LoRA state.

After registering or logging in at http://localhost:3000, use **Bật Autopilot & tạo video** on the dashboard. The app creates a science/nature project if needed, enables the daily run, selects a recent unused NASA Earth Observatory article, writes a story and queues an MP4 render. Its project page shows the original article, publication time, model and job status. You can also press **Lấy tin mới & sản xuất** in any project. New articles are picked once per project; if the feed has no suitable unused article, the API returns a clear error instead of silently reusing one.

The old `minio/minio` and `minio/mc` images are unavailable from Docker Hub. Compose uses versioned [Silo](https://github.com/pgsty/silo) and [Silo client](https://github.com/pgsty/mc) images with the same local S3 endpoint. Review these dependencies before any production deployment.

## Verification

```bash
make check
docker compose --env-file infra/compose/local/.env.example \
  -f infra/compose/local/docker-compose.yml config --quiet
```

The end-to-end fixture render can be run with SQLite and local assets:

```bash
DATABASE_URL=sqlite+aiosqlite:///./local-data/smoke.db \
PYTHONPATH=.:apps/api/src AI_ADAPTER_MODE=fake ENVIRONMENT=test \
uv run --project apps/api python scripts/verify/smoke_pipeline.py
```

With the core Docker stack running, verify the real web/API/worker/S3 path:

```bash
uv run --project apps/api python scripts/verify/live_stack.py
npm run test:e2e --prefix apps/studio-web
```

With Ollama and the macOS voice bridge running, check the complete sourced-media path and save both video previews:

```bash
uv run --project apps/api python scripts/verify/live_stack.py \
  --autopilot --output-dir local-data/exports
```

The Playwright command requires Chromium once: `npx playwright install chromium` from `apps/studio-web`. Each live stack check creates a fresh test workspace. The QC report intentionally blocks export until review. The export API creates a downloadable ZIP only when the latest episode job and QC pass, and Studio mode also requires script and human review approval.

See [machine audit](docs/architecture/RUNTIME_COMPATIBILITY.md) and [implementation status](docs/IMPLEMENTATION_STATUS.md) before installing large models.

