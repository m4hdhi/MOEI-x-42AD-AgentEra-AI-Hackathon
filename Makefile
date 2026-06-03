.DEFAULT_GOAL := help
SHELL := /bin/bash

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---- Infra ----
infra-up:  ## Bring up Postgres + Redis + Qdrant + Langfuse
	docker compose -f infra/docker-compose.yml up -d

infra-down:  ## Stop infra (keep volumes)
	docker compose -f infra/docker-compose.yml down

infra-nuke:  ## Stop infra and DROP volumes
	docker compose -f infra/docker-compose.yml down -v

infra-logs:  ## Tail infra logs
	docker compose -f infra/docker-compose.yml logs -f --tail=100

# ---- Python ----
sync:  ## uv sync (root + agents)
	uv sync
	uv pip install -e agents

api:  ## Run FastAPI on :8000
	uv run uvicorn app.main:app --reload --app-dir apps/api --port 8000

test:  ## Run pytest
	uv run pytest -q

lint:  ## Ruff
	uv run ruff check .
	uv run ruff format --check .

fmt:  ## Format with ruff
	uv run ruff format .
	uv run ruff check --fix .

# ---- Web ----
web:  ## Run Next.js on :3000
	cd apps/web && pnpm dev

web-install:  ## Install web deps
	cd apps/web && pnpm install

# ---- Ollama fallback ----
ollama-pull:  ## Pull local fallback models
	ollama pull qwen2.5:7b
	ollama pull nomic-embed-text

# ---- Demo data ----
synth:  ## Generate synthetic SZHP cases + salary slips
	uv run python scripts/gen_synthetic_data.py --cases 300 --slips 100

# ---- Smoke ----
smoke:  ## End-to-end smoke: curl the API across channels + Arabic
	@curl -s http://localhost:8000/healthz | python3 -m json.tool
	@echo "--- English housing (web) ---"
	@curl -s -X POST http://localhost:8000/chat/web \
		-H 'Content-Type: application/json' \
		-d '{"user_id":"784-1990-0000001-0","channel":"web","session_id":"s1","language":"auto","text":"I am 4 months behind on my SZHP housing loan, salary 15000 AED"}' \
		| python3 -m json.tool
	@echo "--- Arabic housing (whatsapp-shaped) ---"
	@curl -s -X POST http://localhost:8000/chat/web \
		-H 'Content-Type: application/json' \
		-d '{"user_id":"784-1990-0000001-0","channel":"whatsapp","session_id":"s2","language":"auto","text":"أحتاج تأجيل قسط السكن"}' \
		| python3 -m json.tool
	@echo "--- Exec KPIs ---"
	@curl -s http://localhost:8000/exec/kpis | python3 -m json.tool | head -20

.PHONY: help infra-up infra-down infra-nuke infra-logs sync api test lint fmt web web-install ollama-pull smoke
