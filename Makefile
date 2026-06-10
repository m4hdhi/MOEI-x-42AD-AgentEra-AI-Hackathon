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

# ---- WhatsApp setup ----
wa-profile:  ## Request WhatsApp display name approval + set business profile (run once after .env is filled)
	uv run python scripts/set_whatsapp_profile.py

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

# ---- One-command bootstrap ----

# Fails with a helpful message when .env is missing (Make runs this rule when the file doesn't exist)
.env:
	@printf '\n  ERROR: .env not found.\n  Run:  cp .env.example .env\n  Then fill in at least GROQ_API_KEY, DATABASE_URL, REDIS_URL.\n\n'; exit 1

db-up:  ## Start native Postgres + create hassan user/DB (WSL2-safe; idempotent)
	@echo "==> PostgreSQL..."
	@sudo service postgresql start 2>/dev/null || true
	@sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='hassan'" 2>/dev/null | grep -q 1 \
	    || sudo -u postgres psql -c "CREATE USER hassan WITH PASSWORD 'hassan_dev';"
	@sudo -u postgres psql -lqt 2>/dev/null | cut -d'|' -f1 | grep -qw hassan \
	    || sudo -u postgres createdb -O hassan hassan

db-migrate:  ## Apply all SQL migrations (safe to re-run — errors on existing objects are suppressed)
	@echo "==> DB migrations..."
	@for f in infra/postgres/init.sql infra/postgres/init_v2.sql infra/postgres/init_v3.sql \
	          infra/postgres/init_v4_knowledge.sql infra/postgres/init_v5_recordings.sql \
	          infra/postgres/init_v6_citizens.sql infra/postgres/init_v7_geo.sql \
	          infra/postgres/init_v8_dataset.sql infra/postgres/init_v9_whatsapp.sql; do \
	    PGPASSWORD=hassan_dev psql -h 127.0.0.1 -U hassan -d hassan -f "$$f" >/dev/null 2>&1 || true; \
	done

dataset:  ## Import demo dataset (idempotent — wipes and reloads)
	@echo "==> Demo data..."
	@uv run --extra dataset python scripts/import_dataset.py
	@$(MAKE) -s catalogue

catalogue:  ## Load the official MOEI service catalogue into the knowledge base (idempotent)
	@echo "==> Official service catalogue..."
	@uv run --extra dataset python scripts/import_services_catalog.py

up: .env  ## One command: bootstrap everything, then run API (:8000) + Web (:3000)
	@$(MAKE) -s db-up
	@echo "==> Docker infra (Redis + Langfuse)..."
	@docker compose -f infra/docker-compose.yml up -d redis langfuse
	@$(MAKE) -s db-migrate
	@echo "==> Python deps..."
	@uv sync -q && uv pip install -q -e agents
	@echo "==> Web deps..."
	@cd apps/web && pnpm install --silent
	@[ -f apps/web/.env.local ] || echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > apps/web/.env.local
	@$(MAKE) -s dataset
	@printf '\n  API      → http://localhost:8000\n  Web      → http://localhost:3000\n  Langfuse → http://localhost:3001\n  ngrok    → starting ... run "make webhook-url" in a second terminal once it is up\n\n'
	@uvx honcho start

down:  ## Stop all services (Docker infra + native Postgres)
	@echo "==> Stopping Docker infra..."
	@docker compose -f infra/docker-compose.yml down
	@echo "==> Stopping PostgreSQL..."
	@sudo service postgresql stop 2>/dev/null || true

webhook-url:  ## Print current ngrok tunnel URL to paste into Meta App Dashboard
	@python3 -c "\
import urllib.request, json, sys; \
d = json.loads(urllib.request.urlopen('http://localhost:4040/api/tunnels').read()); \
url = next((t['public_url'] for t in d['tunnels'] if t['proto']=='https'), None); \
sys.exit('ngrok not ready yet — try again in a few seconds') if not url else \
print('\n  Webhook URL (paste in Meta App Dashboard → Webhooks):\n\n    ' + url + '/whatsapp/webhook\n')"

.PHONY: help infra-up infra-down infra-nuke infra-logs sync api test lint fmt web web-install \
        ollama-pull wa-profile smoke db-up db-migrate dataset up down webhook-url
