SHELL := /bin/sh
API_DIR := apps/api
WEB_DIR := apps/studio-web
COMPOSE_FILE := infra/compose/local/docker-compose.yml
ENV_FILE := infra/compose/local/.env

.PHONY: bootstrap up automation dev-infra down api-dev web-dev test lint typecheck contracts check

bootstrap:
	uv sync --project $(API_DIR) --extra dev
	npm ci

up:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE) up -d --build studio-web worker-dispatcher worker-cpu worker-beat

automation:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE) up -d n8n

dev-infra:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE) up -d postgres redis minio minio-setup

down:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE) down

api-dev:
	uv run --project $(API_DIR) uvicorn studio_api.main:app --reload --host 0.0.0.0 --port 8000

web-dev:
	npm run dev --prefix $(WEB_DIR)

test:
	uv run --project $(API_DIR) pytest $(API_DIR)/tests
	npm run test --prefix $(WEB_DIR)

lint:
	uv run --project $(API_DIR) ruff check $(API_DIR) workers
	npm run lint --prefix $(WEB_DIR)

typecheck:
	uv run --project $(API_DIR) mypy $(API_DIR)/src
	npm run typecheck --prefix $(WEB_DIR)

contracts:
	uv run --project $(API_DIR) python scripts/verify/validate_contracts.py

check: contracts lint typecheck test

