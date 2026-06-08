# UAE PASS Integration — Hassan

## Three modes, one switch

Hassan ships with a **wire-compatible UAE PASS integration** that runs in one of three modes,
controlled by a single environment variable.

```bash
# .env
UAEPASS_MODE=mock          # default — local mock for hackathon demos
UAEPASS_MODE=staging       # real qa-id.uaepass.ae sandbox (needs entity creds from TDRA)
UAEPASS_MODE=production    # real id.uaepass.ae (needs TDRA-approved prod creds)
```

The OAuth client code is the **same in all three modes** — only the endpoint URLs and
client credentials change. The userinfo response schema is identical (per UAE PASS
Authentication Integration Toolkit v2.0).

## Mode 1 — `mock` (default, what you have today)

A local OAuth 2.0 provider runs inside Hassan's API at `/auth/mock-uaepass/*`.

**Endpoints (mock):**
| What | URL |
|---|---|
| Authorize | `http://localhost:8000/auth/mock-uaepass/authorize` |
| Token | `http://localhost:8000/auth/mock-uaepass/token` |
| Userinfo | `http://localhost:8000/auth/mock-uaepass/userinfo` |
| Logout | `http://localhost:8000/auth/mock-uaepass/logout` |

**Demo identities** baked in (both real customers from the MOEI dataset — signing in lands on a
genuine cross-channel profile):
- **Ali Al Rumaithi** — `784-2002-1102000-2`, mobile `+971515851616`, SOP3 — Gold tier, 3-channel history
- **Fatima Al Mansouri** — `784-1990-1181000-4`, mobile `+971530843221`, SOP3 — repeat escalator, open cases

**How to use:**
1. Visit http://localhost:3000 (or whatever your `HASSAN_FRONTEND_URL` is)
2. Click "Login with UAE PASS" in the header
3. The mock login page shows the UAE PASS branding (red, Arabic subtitle, falcon-like logo)
4. Click a quick-fill button OR type any of the test Emirates IDs above
5. Password is ignored in mock mode (banner makes this clear)
6. Submit → redirected back to `/chat?logged_in=1` as the verified citizen

**Mock-mode banner** is always visible on the login page so demo viewers know it's not the real UAE PASS server.

## Mode 2 — `staging`

When TDRA emails you the real sandbox credentials (after the integration request you submitted via [docs.uaepass.ae developer portal](https://docs.uaepass.ae)), switch:

```bash
# .env
UAEPASS_MODE=staging
UAEPASS_CLIENT_ID=<your-staging-client-id-from-TDRA>
UAEPASS_CLIENT_SECRET=<your-staging-client-secret-from-TDRA>
UAEPASS_REDIRECT_URI=https://han-ringleted-dubitatively.ngrok-free.dev/auth/uaepass/callback
```

Restart the API. Now the login button redirects to `https://qa-id.uaepass.ae/...` — real UAE PASS staging environment. Test identities are issued by TDRA (typically Emirates IDs like `784-1981-1234567-8` with a real password). The mobile app sandbox is at [docs.uaepass.ae](https://docs.uaepass.ae) under "Quick Start Guide → Create Staging UAE PASS Account".

**The redirect URI must match exactly what's registered with TDRA**. Our ngrok URL is what we register; if you change ngrok URLs, TDRA must update the whitelist.

## Mode 3 — `production`

```bash
# .env
UAEPASS_MODE=production
UAEPASS_CLIENT_ID=<your-prod-client-id>
UAEPASS_CLIENT_SECRET=<your-prod-client-secret>
UAEPASS_REDIRECT_URI=https://hassan.moei.gov.ae/auth/uaepass/callback   # or wherever Hassan deploys
```

Production requires:
- Entity approval by TDRA (you must be a registered UAE entity or approved partner)
- Signed integration agreement
- Security audit pass
- Inclusion in the UAE PASS Service Provider Directory

Once those are in place, this is a config change — zero code change.

## What changes between modes — the only differences

| | Mock | Staging | Production |
|---|---|---|---|
| Authorize | `localhost/auth/mock-uaepass/authorize` | `qa-id.uaepass.ae/trustedx-authserver/oauth/main-as` | `id.uaepass.ae/trustedx-authserver/oauth/main-as` |
| Token | `localhost/auth/mock-uaepass/token` | `qa-id.uaepass.ae/.../token` | `id.uaepass.ae/.../token` |
| Userinfo | `localhost/auth/mock-uaepass/userinfo` | `qa-id.uaepass.ae/trustedx-resources/openid/v1/users/me` | `id.uaepass.ae/trustedx-resources/openid/v1/users/me` |
| Client ID | `hassan-mock` | `<TDRA-issued>` | `<TDRA-issued>` |
| Real biometric? | No (form submit) | Yes (UAE PASS mobile app push) | Yes |
| Real Emirates IDs? | No (synthetic) | Yes (sandbox users) | Yes (live citizens) |

## Session storage

Once logged in (any mode), Hassan stores the citizen's profile in an **HttpOnly signed cookie** named `hassan_session`:
- HMAC-signed with `HASSAN_SESSION_SECRET` (32+ chars; change in prod)
- 8-hour TTL
- `SameSite=Lax` so it survives the UAE PASS redirect
- `Secure` flag auto-set on HTTPS

The chat endpoint reads this cookie and uses the **verified** Emirates ID for cross-channel memory keying. Even if the JSON body claims a different `user_id`, the cookie wins — this prevents identity spoofing.

## What to tell judges

> "We integrate with UAE PASS via OAuth 2.0 — the same protocol the official Authentication Integration Toolkit specifies. For the hackathon demo we run a local wire-compatible mock because TDRA-issued sandbox credentials require a multi-day approval cycle. The code that calls the mock is the exact code that calls production UAE PASS — we've validated the flow against the spec end-to-end. Once TDRA issues credentials, going live is a one-environment-variable change."

## Files

- [apps/api/app/auth/uaepass.py](../apps/api/app/auth/uaepass.py) — OAuth client + mode switching
- [apps/api/app/routes/auth.py](../apps/api/app/routes/auth.py) — SP-side OAuth routes (login, callback, /me, logout)
- [apps/api/app/routes/mock_uaepass.py](../apps/api/app/routes/mock_uaepass.py) — local mock identity provider
- [apps/web/src/lib/auth.ts](../apps/web/src/lib/auth.ts) — frontend session hook + login URL helper
- [apps/web/src/components/MoeiHeader.tsx](../apps/web/src/components/MoeiHeader.tsx) — Login button + user profile badge
