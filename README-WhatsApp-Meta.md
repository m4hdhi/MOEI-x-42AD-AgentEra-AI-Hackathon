# WhatsApp Meta Cloud API — Setup & Testing Guide

This document covers the changes introduced on branch `feat/whatsapp-meta-cloud-api` and how to
get the WhatsApp chatbot running on a fresh device.

---

## What changed

The WhatsApp chatbot is now served through **Meta WhatsApp Cloud API** (display name:
"MOEI Assistant (Demo)"). Twilio remains in place as a dormant fallback for SMS and legacy
WhatsApp sandbox usage.

| | Before | After |
|---|---|---|
| Chatbot channel | Twilio WhatsApp sandbox | Meta Cloud API (real number) |
| Join code needed | Yes (`join nose-bell`) | No |
| Webhook path | `POST /whatsapp/inbound` | `POST /whatsapp/webhook` |
| Verification | Twilio signature | HMAC-SHA256 (`X-Hub-Signature-256`) |
| Scheduled notifications | Twilio | Still Twilio (deferred; needs Meta-approved templates) |

New files:
- `apps/api/app/core/whatsapp_meta.py` — Meta client (webhook verify, signature check, send)
- `apps/api/app/routes/whatsapp.py` — added `GET /whatsapp/webhook` + `POST /whatsapp/webhook`
- `apps/api/tests/test_whatsapp_meta.py` — 8 unit tests (all pass)
- `apps/web/src/components/WhatsAppTryCard.tsx` — hides join-code step when empty

---

## Prerequisites

1. **A Meta developer app** with WhatsApp product added
   - [developers.facebook.com](https://developers.facebook.com) → Create App → Business → Add WhatsApp
2. **A public HTTPS URL** for the webhook — use [ngrok](https://ngrok.com) in development
   - Free account gives one static domain: `ngrok.com/dashboard/domains/new`
3. **Python ≥ 3.12** and **uv** installed on the machine
4. **PostgreSQL** and **Redis** running locally (see below)
5. **Node.js ≥ 20** and **pnpm** for the web frontend (optional — API-only test skips this)

---

## Step 0.5 — Set the WhatsApp display name (one-time, needs Meta approval)

By default, recipients see the raw phone number until Meta approves a **Display Name** for the
business number. Once approved, every user sees "MOEI Assistant (Demo)" automatically — no contact
saving required.

**Fastest path (Meta Dashboard):**

1. [business.facebook.com](https://business.facebook.com) → **WhatsApp Manager** → **Phone Numbers**
2. Three-dot menu next to +971 54 184 1533 → **Edit profile**
3. Set **Display Name** to `MOEI Assistant (Demo)` → Submit
4. Meta reviews within 1–3 business days (often same-day for test apps)

> **Note:** The display name itself can **only** be set in the WhatsApp Manager dashboard —
> there is no Cloud API endpoint to request it. `make wa-profile` only *reports* the current
> verified name; it cannot change it.

**Helper script:**

```bash
make wa-profile   # requires META_WHATSAPP_ACCESS_TOKEN + META_WHATSAPP_PHONE_NUMBER_ID in .env
```

This prints the current verified display name and sets the business profile About text, category,
and website immediately (no review needed).

> **Hackathon demo tip:** If approval hasn't arrived yet, pre-save the contact as
> "MOEI Assistant (Demo)" on every demo device. The chatbot logic is unaffected either way.

---

## Step 1 — Clone and configure

```bash
git clone https://github.com/m4hdhi/MOEI-x-42AD-AgentEra-AI-Hackathon.git
cd MOEI-x-42AD-AgentEra-AI-Hackathon
git checkout feat/whatsapp-meta-cloud-api

cp .env.example .env
```

Open `.env` and fill in the required values:

```env
# LLM
GROQ_API_KEY=gsk_...            # https://console.groq.com

# WhatsApp — Meta Cloud API
META_WHATSAPP_PHONE_NUMBER_ID=  # WhatsApp > API Setup (the number ID, not the display number)
META_WHATSAPP_ACCESS_TOKEN=     # System User permanent token from Meta Business Suite
META_WHATSAPP_VERIFY_TOKEN=     # Any random string — you'll paste this into the Meta dashboard too
META_APP_SECRET=                # App > Settings > Basic > App Secret
META_GRAPH_API_VERSION=v22.0
META_WHATSAPP_NUMBER=+971...    # The E.164 number shown in API Setup

# Database + cache
DATABASE_URL=postgresql+psycopg://hassan:hassan_dev@localhost:5432/hassan
REDIS_URL=redis://localhost:6379/0

# Your public URL (ngrok or similar) — needed so CORS allows your frontend/webhook host
CORS_EXTRA_ORIGINS=https://your-domain.ngrok-free.app
```

Leave all other values at their defaults for a local test.

---

## Step 2 — Start infrastructure

**PostgreSQL (native, WSL2-compatible):**

```bash
sudo service postgresql start
sudo -u postgres psql -c "CREATE USER hassan WITH PASSWORD 'hassan_dev';" 2>/dev/null || true
sudo -u postgres createdb -O hassan hassan 2>/dev/null || true
```

Apply database migrations in order:

```bash
for sql in infra/postgres/init*.sql; do
  psql -h 127.0.0.1 -U hassan -d hassan < "$sql"
done
```

Load demo data:

```bash
uv run python scripts/import_dataset.py
```

**Redis:**

```bash
sudo service redis-server start   # or: redis-server --daemonize yes
```

---

## Step 3 — Install and start the API

```bash
uv sync
uv run uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000
```

Confirm it's healthy:

```bash
curl http://localhost:8000/healthz
# → {"status":"ok","agent":"Agent42"}
```

---

## Step 4 — Expose the API via ngrok

```bash
ngrok http 8000 --domain your-reserved-domain.ngrok-free.app
```

With a random URL (no reserved domain):

```bash
ngrok http 8000
# Copy the https://xxxx.ngrok-free.app URL shown
# Update CORS_EXTRA_ORIGINS in .env and restart the API
```

Verify the tunnel:

```bash
curl https://your-domain.ngrok-free.app/healthz
# → {"status":"ok","agent":"Agent42"}
```

---

## Step 5 — Register the webhook in Meta

1. [developers.facebook.com](https://developers.facebook.com) → your app → **WhatsApp → Configuration**
2. **Webhook** → **Edit**
   - **Callback URL**: `https://your-domain.ngrok-free.app/whatsapp/webhook`
   - **Verify token**: the value you set for `META_WHATSAPP_VERIFY_TOKEN`
3. Click **Verify and Save** — Meta calls your `GET /whatsapp/webhook`; you should see a `200` in API logs
4. Under **Webhook Fields**, enable the **`messages`** subscription

---

## Step 6 — Add your phone to the test allowlist

> Only needed on a dev (unverified) Meta app. Skip once the app is approved for production.

1. **WhatsApp → API Setup** → **To** field → **Manage phone number list**
2. Add your WhatsApp number in E.164 format (e.g. `+971501234567`)
3. Confirm the OTP sent to your phone
4. Maximum 5 numbers per dev app

---

## Step 7 — Send a test message

Open WhatsApp and message **+971541841533** (or tap the link from `/whatsapp/sandbox-info`):

```
Hello, how do I apply for housing support?
```

```
ما هي رسوم الكهرباء؟
```

You should receive a reply from **"MOEI Assistant (Demo)"** within ~10 seconds.

**Watch the logs to confirm the full flow:**

```
whatsapp_in(meta): from=whatsapp:+<your number> name='...' text='...'
wa_bg: supervisor for whatsapp:+<your number> → whatsapp:+<your number>
wa_bg: sent reply (N chars) to whatsapp:+<your number>
```

---

## Step 8 — Start the web frontend (optional)

```bash
cd apps/web
pnpm install
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000):

| Page | URL | Description |
|---|---|---|
| Home | `/` | Citizen portal landing + UAE PASS (mock) login |
| Web Chat | `/chat` | Same Agent42 LangGraph brain via browser |
| Voice | `/call` | LiveKit voice session (needs mic) |
| Mobile | `/mobile` | Mobile-optimised citizen chat |
| CSAT | `/csat` | Post-interaction satisfaction survey |
| Admin Login | `/admin/login` | Staff console entry point |
| Exec Dashboard | `/admin/exec` | KPIs, volumes, sentiment, escalation risk |
| Citizens | `/admin/citizens` | Unified cross-channel citizen profiles |

---

## Running the unit tests

```bash
uv run --with pytest python -m pytest apps/api/tests/test_whatsapp_meta.py -v
# 8 passed
```

Full test suite:

```bash
uv run --with pytest python -m pytest -q
```

---

## Cross-channel continuity test

1. Send a WhatsApp message: *"My name is Ahmed and I have a housing complaint"*
2. In another browser tab, open `/chat` and log in as the same citizen (matched by phone via `GET /crm/identify?phone=+971...`)
3. The conversation history from WhatsApp is loaded automatically — Agent42 greets Ahmed by name and picks up where WhatsApp left off

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `403` on `POST /whatsapp/webhook` | HMAC signature mismatch — check `META_APP_SECRET` matches the value in Meta App Settings → Basic |
| Meta "Verify and Save" fails | ngrok not running, or wrong callback URL / verify token |
| No reply received | Check API logs for `wa_bg: sent reply` — if absent, the supervisor timed out; check `GROQ_API_KEY` |
| `relation "whatsapp_identities" does not exist` | Run all `infra/postgres/init*.sql` migrations in order |
| CORS error from browser | Add your ngrok URL to `CORS_EXTRA_ORIGINS` in `.env` and restart the API |
| Router LLM `json_schema` error | Known Groq limitation on llama-3.3-70b; keyword fallback fires automatically, no user impact |
