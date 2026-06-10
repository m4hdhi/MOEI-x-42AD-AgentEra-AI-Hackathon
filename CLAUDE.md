# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

"Agent42" — a single agentic AI layer (the MOEI Smart Assistant) unifying customer engagement across
WhatsApp, voice, web, and mobile for the UAE Ministry of Energy and Infrastructure. One LangGraph
supervisor serves every channel; citizens get a continuous cross-channel conversation, staff get an
executive dashboard and agent co-pilot. Hackathon project (MOEI × 42 AgentEra, Challenge 3).

## Commands

Driven by the `Makefile` (run `make help` for the full list). Python uses `uv`, web uses `pnpm`.

```bash
make infra-up        # Postgres + Redis + Langfuse via infra/docker-compose.yml
make sync            # uv sync + editable install of the `hassan` agents package
make api             # FastAPI on :8000 (uvicorn app.main:app --app-dir apps/api)
make web-install     # pnpm install in apps/web
make web             # Next.js dev on :3000
make test            # pytest -q  (testpaths: apps/api/tests, agents/tests)
make lint            # ruff check + ruff format --check
make fmt             # ruff format + ruff check --fix
make smoke           # end-to-end curl across channels (EN/AR) — requires api + infra up
```

Run a single test: `uv run pytest agents/tests/test_szhp_rules.py -q` (or `-k <name>`).
Web type-check / lint: `cd apps/web && pnpm typecheck` / `pnpm lint`.

**Database schema is NOT auto-migrated.** Apply migrations in order (`init.sql`, `init_v2.sql` …
`init_v8_dataset.sql`) by piping each into `psql -h 127.0.0.1 -U hassan -d hassan` (or via
`docker exec -i hassan-postgres psql -U hassan -d hassan` if Docker Postgres is reachable). See
README "Running it locally" for the exact loop. Then load demo data with
`uv run python scripts/import_dataset.py` and optionally `make synth` / `scripts/crawl_moei.py`.

**WSL2 Postgres note:** Docker's Postgres container is not reachable from WSL2 via `localhost`.
Use the native system Postgres instead (`sudo service postgresql start`). The `hassan` user must
exist with password `hassan_dev` — create it with:

```bash
sudo -u postgres psql -c "CREATE USER hassan WITH PASSWORD 'hassan_dev';"
sudo -u postgres createdb -O hassan hassan
```

Copy `.env.example` → `.env` before running. Required keys: `GROQ_API_KEY` (primary LLM),
`DATABASE_URL`, `REDIS_URL`. For WhatsApp: `META_WHATSAPP_PHONE_NUMBER_ID`,
`META_WHATSAPP_ACCESS_TOKEN`, `META_WHATSAPP_VERIFY_TOKEN`, `META_APP_SECRET`.
For extra CORS origins (e.g. ngrok): set `CORS_EXTRA_ORIGINS=https://your-url.ngrok-free.app`.

## Architecture

Three top-level code roots in one repo, with a hard package boundary between them:

- **`agents/hassan/`** — installable Python package (`hassan`, editable-installed via `make sync`,
  `package-dir = agents` in pyproject). Contains all agent logic. The API imports it as
  `from hassan.supervisor.graph import run_supervisor`.
- **`apps/api/`** — FastAPI channel gateway. Routes normalize each channel's payload to a common
  shape (user_id, channel, session_id, language, correlation_id) and call into the `hassan` package.
- **`apps/web/`** — Next.js 15 (App Router, Tailwind, React 19). Citizen surfaces (`/`, `/chat`,
  `/call`, `/mobile`, `/csat`) and admin console (`/admin/*`).

### The supervisor (the core)

One LangGraph `StateGraph` in `agents/hassan/supervisor/graph.py` is the single brain for all
channels. `run_supervisor(...)` is the only entry point the API uses; it builds initial
`SupervisorState`, attaches Langfuse callbacks, and runs with a hard timeout
(`HASSAN_SUPERVISOR_TIMEOUT`, default 60s) that returns a graceful bilingual reply on hang.

Graph shape (see the module docstring — keep it in sync when editing nodes):

```
router → sentiment → memory_loader → policy_guardrails → dispatcher →[conditional]→ ... → persist_turn
```

Two conditional branches optimize latency:
- **Full path** (web/voice, or the housing-payment flow): `dispatcher → critic → escalation → composer → next_best_action → persist`.
- **Fast path** (everything else, incl. WhatsApp): skips the Critic and Composer LLM calls
  (`dispatcher → escalation → fast_compose → …`). The branch predicate is `_is_housing_payment_flow`
  (true only when the housing rules engine actually produced a `housing_decision`). Catalog-grounded
  answers are already polished + cited, so they skip the rewrite; only rules-engine math gets the
  Critic + Composer treatment. WhatsApp's 15s webhook timeout is handled by a background-task path in
  `routes/whatsapp.py`, not by shortening the graph.

Nodes live in `supervisor/nodes.py`; state in `state.py`; structured-output schemas in `schemas.py`;
prompts in `prompts.py`. Worker agents (the dispatcher's targets) are in `agents/hassan/workers/`
(housing, energy, transport/maritime/infra via `domain.py`, `general`, `crm`, `knowledge`, `postcall`).

### LLM access — by role, not by model

Never hardcode a model in node code. `agents/hassan/llm/client.py` exposes roles (`LLMRole.ROUTER`,
`REASONER`, `CRITIC`, `COMPOSER`, `ARABIC`, `LONGCTX`) and the routing/cascade policy lives there, so
a provider can be swapped without touching graph logic. Despite README phrasing, the configured
**primary is Groq Llama 3.3 70B** (`primary_llm` in `core/config.py`); Router uses the faster 8B;
Arabic → Jais; long-context → Gemini Flash. All cloud, OpenAI-compatible clients via LangChain.

### Data layer

- **PostgreSQL** is the system of record: `citizens`, `cases`, `interactions`, `recordings`,
  `knowledge_documents`, audit log. Cross-channel identity is keyed by **Customer ID** — this is what
  makes one conversation span channels (`GET /crm/identify?phone=…` resolves any channel to the
  unified profile).
- **Knowledge base / RAG uses Postgres full-text search** (bilingual EN/AR), *not* a vector DB —
  `$0` to run, swappable to pgvector later. (Qdrant/mem0 appear in deps but FTS is the live path.)
- **Redis** holds the short-term cross-channel conversation buffer (`hassan/memory/short_term.py`).
- A background **notification dispatcher** (`apps/api/app/core/dispatcher.py`) starts from the FastAPI
  lifespan, polls for due notifications, and sends via Twilio (WhatsApp/SMS) — separate from the
  LangGraph "dispatcher" node; don't confuse the two.

## Conventions

- Ruff is the linter/formatter (line length 100, py312, rules `E,F,I,B,UP,N,S,ASYNC,RUF`). Run
  `make fmt` before committing Python.
- `pytest` runs in `asyncio_mode = auto` — async test functions need no decorator.
- Python ≥ 3.12 required.
