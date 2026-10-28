FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.8
COPY apps/api/pyproject.toml apps/api/uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PATH=/app/.venv/bin:$PATH PYTHONPATH=/app/src:/app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN groupadd --system studio && useradd --system --gid studio --create-home studio
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY apps/api/src /app/src
COPY apps/api/alembic.ini /app/alembic.ini
COPY apps/api/migrations /app/migrations
COPY packages/contracts /packages/contracts
COPY workers /app/workers
RUN mkdir -p /app/local-data/assets && chown -R studio:studio /app
USER studio
EXPOSE 8000
CMD ["uvicorn", "studio_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

