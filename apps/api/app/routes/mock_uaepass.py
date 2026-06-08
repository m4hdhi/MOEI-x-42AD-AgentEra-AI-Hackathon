"""Mock UAE PASS identity provider — runs locally inside Hassan's API.

Looks and behaves like the real qa-id.uaepass.ae:
  - Same OAuth 2.0 authorization-code grant
  - Same /authorize → login UI → callback flow
  - Same /token POST with Basic auth
  - Same /userinfo schema (sub, idn, fullnameEN, fullnameAR, userType, acr, mobile, email, …)

Two pre-configured citizens (both real customers from the MOEI dataset, so signing in lands
on a genuine cross-channel profile):
  - Ali Al Rumaithi           (Emirates ID 784-2002-1102000-2) — Gold tier, 3-channel history
  - Fatima Al Mansouri        (Emirates ID 784-1990-1181000-4) — repeat escalator, open cases

The mock is intentionally faithful so the SAME backend OAuth client works against either
the mock or the real UAE PASS. Switch by setting UAEPASS_MODE=staging in .env.
"""

from __future__ import annotations

import base64
import secrets
import time
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from loguru import logger

router = APIRouter(prefix="/auth/mock-uaepass", tags=["mock-uaepass"])

# ---- Pre-configured staging identities --------------------------------------
# Same shape as the real UAE PASS /users/me response (per integration toolkit v2.0)

_USERS: dict[str, dict] = {
    "784200211020002": {       # Ali Al Rumaithi — dataset customer UAE-001102 (Gold, 3 channels)
        "sub": "MOCKUUID-784200211020002",
        "userType": "SOP3",     # SOP3 = Verified UAE PASS identity (Emirates ID verified)
        "fullnameEN": "Ali Al Rumaithi",
        "fullnameAR": "علي الرميثي",
        "firstnameEN": "Ali",
        "firstnameAR": "علي",
        "lastnameEN": "Al Rumaithi",
        "lastnameAR": "الرميثي",
        "gender": "Male",
        "idn": "784200211020002",
        "idType": "ID",
        "nationalityEN": "UAE",
        "nationalityAR": "الإمارات",
        "mobile": "971515851616",
        "email": "ali.alrumaithi@example.ae",
        "titleEN": "",
        "titleAR": "",
        "acr": "urn:safelayer:tws:policies:authentication:level:high",
        "amr": [
            "urn:safelayer:tws:policies:authentication:adaptive:methods:mobileid",
            "urn:uae:authentication:method:verified",
        ],
    },
    "784199011810004": {       # Fatima Al Mansouri — dataset customer UAE-001181 (repeat escalator)
        "sub": "MOCKUUID-784199011810004",
        "userType": "SOP3",
        "fullnameEN": "Fatima Al Mansouri",
        "fullnameAR": "فاطمة المنصوري",
        "firstnameEN": "Fatima",
        "firstnameAR": "فاطمة",
        "lastnameEN": "Al Mansouri",
        "lastnameAR": "المنصوري",
        "gender": "Female",
        "idn": "784199011810004",
        "idType": "ID",
        "nationalityEN": "UAE",
        "nationalityAR": "الإمارات",
        "mobile": "971530843221",
        "email": "fatima.almansouri@example.ae",
        "titleEN": "",
        "titleAR": "",
        "acr": "urn:safelayer:tws:policies:authentication:level:high",
        "amr": ["urn:uae:authentication:method:verified"],
    },
}

# Short-lived store: code → (user_emirates_id, redirect_uri, state, expires_at)
_CODES: dict[str, dict] = {}
# Short-lived: access_token → (user_emirates_id, expires_at)
_TOKENS: dict[str, dict] = {}

CODE_TTL_SECONDS = 300
TOKEN_TTL_SECONDS = 3600


def _purge_expired(store: dict) -> None:
    now = time.time()
    for k in [k for k, v in store.items() if v.get("expires_at", 0) < now]:
        store.pop(k, None)


# ---------------------------------------------------------------------------
# /authorize → renders the mock UAE PASS login page
# ---------------------------------------------------------------------------

@router.get("/authorize", response_class=HTMLResponse)
async def authorize(
    request: Request,
    redirect_uri: str,
    client_id: str = "",
    response_type: str = "code",
    state: str = "",
    scope: str = "",
    acr_values: str = "",
    ui_locales: str = "en",
) -> HTMLResponse:
    """Mock the UAE PASS /authorize endpoint. Renders a login page that looks like the real one."""
    if response_type != "code":
        raise HTTPException(400, "unsupported response_type")

    is_arabic = ui_locales == "ar"
    dir_attr = "rtl" if is_arabic else "ltr"
    title_h = "تسجيل الدخول إلى UAE PASS" if is_arabic else "Login to UAE PASS"
    page_title = "UAE PASS"
    eid_placeholder = (
        "الهوية الإماراتية أو البريد أو الهاتف"
        if is_arabic else "Emirates ID, email, or phone eg. 971500000000"
    )
    remember = "تذكرني" if is_arabic else "Remember me"
    login_btn = "تسجيل الدخول" if is_arabic else "Login"
    no_account = "ليس لديك حساب UAEPASS؟" if is_arabic else "Don't have UAEPASS account?"
    create = "إنشاء حساب جديد" if is_arabic else "Create new account"
    recover = "استرجاع الحساب" if is_arabic else "Recover your account"
    foot_links = (
        [("الرئيسية", "#"), ("حول", "#"), ("الدعم", "#"), ("الأسئلة", "#"),
         ("مواقع الأكشاك", "#"), ("مزود الخدمة", "#")]
        if is_arabic else
        [("Home", "#"), ("About", "#"), ("Support", "#"), ("FAQ", "#"),
         ("Kiosk Locations", "#"), ("Service Provider", "#")]
    )
    copyright_line = (
        "حقوق النشر © 2026 UAE PASS جميع الحقوق محفوظة."
        if is_arabic else "Copyright © 2026 UAE PASS All rights reserved."
    )

    # Quick-fill buttons (hidden by default; revealed by tiny help text under the form)
    quick_fills = "".join(
        f"""
        <button type="button" class="quick" data-eid="{idn}">
          <div class="qname">{u['fullnameEN']}</div>
          <div class="qmeta">{idn[:3]}-{idn[3:7]}-{idn[7:14]}-{idn[14]}</div>
        </button>
        """ for idn, u in _USERS.items()
    )

    html = f"""<!DOCTYPE html>
<html lang="{ui_locales}" dir="{dir_attr}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{page_title}</title>
  <link rel="icon" href="/static/pass.png" type="image/png">
  <link rel="shortcut icon" href="/static/pass.png" type="image/png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+Arabic:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      /* Exact palette from user feedback */
      --text-dark: #455165;       /* primary text */
      --text-soft: #6b7585;
      --text-light: #97a0b0;
      --line: #d6dbe1;
      --link: #00b890;            /* green link, matches real UAE PASS */
      --btn-disabled: #97a0b3;
      --btn-active: #2d3a52;
      /* Gradient (from user-shared color picker): green → teal → blue-teal */
      --grad-1: #42e098;
      --grad-2: #28bfa8;
      --grad-3: #10a0b6;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      background: #fff;
      min-height: 100vh;
      color: var(--text-dark);
      -webkit-font-smoothing: antialiased;
    }}
    [dir="rtl"] body {{ font-family: 'Noto Sans Arabic', 'Inter', sans-serif; }}

    /* Gradient strip at the top — green to teal to blue-teal */
    .top-strip {{
      height: 6px;
      background: linear-gradient(90deg,
        var(--grad-1) 0%, var(--grad-2) 50%, var(--grad-3) 100%);
    }}

    /* Thin gradient line near the bottom of the viewport */
    .bottom-rule {{
      position: fixed;
      bottom: 90px;
      left: 0;
      right: 0;
      height: 2px;
      background: linear-gradient(90deg,
        var(--grad-1) 0%, var(--grad-2) 50%, var(--grad-3) 100%);
      z-index: 0;
    }}

    .page {{
      min-height: calc(100vh - 6px);
      display: flex;
      flex-direction: column;
    }}

    .main {{
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 40px 20px 140px;
    }}

    .login-box {{
      width: 100%;
      max-width: 420px;
      text-align: center;
    }}

    .logo {{
      width: 80px;
      height: 80px;
      margin: 0 auto 32px;
      object-fit: contain;
    }}

    h1 {{
      font-size: 22px;
      font-weight: 600;
      color: var(--text-dark);
      margin-bottom: 36px;
      letter-spacing: 0.1px;
    }}

    .input-wrap {{
      margin-bottom: 18px;
    }}

    input[type=text], input[type=email], input[type=tel] {{
      width: 100%;
      padding: 14px 18px;
      font-size: 14px;
      font-weight: 500;
      border: 1px solid var(--line);
      border-radius: 14px;
      transition: border-color .15s;
      font-family: inherit;
      color: var(--text-dark);
      background: white;
    }}
    input::placeholder {{ color: var(--text-light); font-weight: 400; }}
    input:focus {{
      outline: none;
      border-color: var(--grad-2);
      box-shadow: 0 0 0 3px rgba(40, 191, 168, 0.12);
    }}

    .remember-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 18px;
      font-size: 14px;
      font-weight: 500;
      color: var(--text-dark);
    }}
    .remember-row input[type=checkbox] {{
      width: 16px; height: 16px;
      accent-color: var(--grad-2);
      cursor: pointer;
    }}

    .login-btn {{
      width: 100%;
      padding: 14px;
      font-size: 16px;
      font-weight: 600;
      background: var(--btn-disabled);
      color: white;
      border: none;
      border-radius: 14px;
      cursor: pointer;
      transition: background .15s;
      font-family: inherit;
      letter-spacing: 0.2px;
    }}
    .login-btn:hover {{ background: #7e8898; }}
    .login-btn.active {{ background: var(--btn-active); }}
    .login-btn.active:hover {{ background: #1f2a3c; }}

    .links {{
      margin-top: 32px;
      font-size: 15px;
      font-weight: 500;
      color: var(--text-dark);
    }}
    .links a {{
      color: var(--link);
      text-decoration: none;
      font-weight: 600;
      margin-left: 4px;
    }}
    .links a:hover {{ text-decoration: underline; }}
    .recover-link {{
      display: block;
      margin-top: 18px;
      color: var(--link);
      text-decoration: none;
      font-weight: 600;
      font-size: 15px;
    }}
    .recover-link:hover {{ text-decoration: underline; }}

    /* Hidden developer toggle */
    .dev-toggle {{
      margin-top: 40px;
      font-size: 11px;
      color: var(--text-light);
      cursor: pointer;
      user-select: none;
    }}
    .quick-panel {{
      display: none;
      margin-top: 12px;
      padding: 12px;
      border: 1px dashed var(--line);
      border-radius: 12px;
      background: #fafbfc;
    }}
    .quick-panel.open {{ display: block; }}
    .quick-list {{
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin-top: 6px;
    }}
    .quick {{
      width: 100%;
      text-align: left;
      background: white;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 8px 12px;
      cursor: pointer;
      font-family: inherit;
      transition: border-color .15s;
    }}
    .quick:hover {{ border-color: var(--grad-2); }}
    .qname {{ font-size: 13px; font-weight: 600; color: var(--text-dark); }}
    .qmeta {{ font-size: 11px; color: var(--text-soft); font-family: monospace; margin-top: 2px; }}

    /* Footer */
    footer {{
      background: white;
      padding: 18px 20px 16px;
      font-size: 14px;
      font-weight: 500;
      color: var(--text-soft);
      text-align: center;
      position: relative;
      z-index: 1;
    }}
    .foot-links {{
      display: flex;
      justify-content: center;
      gap: 36px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}
    .foot-links a {{
      color: var(--text-soft);
      text-decoration: none;
      font-weight: 500;
    }}
    .foot-links a:hover {{ color: var(--grad-2); }}
    .copyright {{
      font-size: 14px;
      font-weight: 600;
      color: var(--text-dark);
    }}

    @media (max-width: 600px) {{
      .foot-links {{ gap: 18px; font-size: 12px; }}
      h1 {{ font-size: 24px; }}
      .logo {{ width: 120px; height: 120px; }}
    }}
  </style>
</head>
<body>
  <div class="top-strip"></div>
  <div class="bottom-rule"></div>
  <div class="page">
    <div class="main">
      <div class="login-box">
        <img src="/static/pass.png" alt="UAE PASS" class="logo" />
        <h1>{title_h}</h1>

        <form method="POST" action="/auth/mock-uaepass/login" autocomplete="off" id="loginForm">
          <input type="hidden" name="redirect_uri" value="{redirect_uri}">
          <input type="hidden" name="state" value="{state}">
          <input type="hidden" name="scope" value="{scope}">
          <input type="hidden" name="acr_values" value="{acr_values}">
          <input type="hidden" name="password" value="ignored">

          <div class="input-wrap">
            <input id="eid" name="emirates_id" type="text"
                   placeholder="{eid_placeholder}" required
                   autocomplete="off" inputmode="numeric">
          </div>

          <div class="remember-row">
            <input type="checkbox" id="remember" checked>
            <label for="remember">{remember}</label>
          </div>

          <button type="submit" class="login-btn" id="loginBtn">{login_btn}</button>
        </form>

        <div class="links">
          {no_account} <a href="#">{create}</a>
        </div>
        <a href="#" class="recover-link">{recover}</a>

        <div class="dev-toggle" id="devToggle">— demo identities —</div>
        <div class="quick-panel" id="quickPanel">
          <div class="quick-list">{quick_fills}</div>
        </div>
      </div>
    </div>

    <footer>
      <div class="foot-links">
        {"".join(f'<a href="{href}">{label}</a>' for label, href in foot_links)}
      </div>
      <div class="copyright">{copyright_line}</div>
    </footer>
  </div>

  <script>
    const eidInput = document.getElementById('eid');
    const loginBtn = document.getElementById('loginBtn');
    function digitsOnly(s) {{ return (s || '').replace(/[^0-9]/g, ''); }}
    function syncBtn() {{
      const d = digitsOnly(eidInput.value);
      if (d.length >= 9) loginBtn.classList.add('active');
      else loginBtn.classList.remove('active');
    }}
    eidInput.addEventListener('input', syncBtn);

    document.getElementById('devToggle').addEventListener('click', () => {{
      document.getElementById('quickPanel').classList.toggle('open');
    }});
    document.querySelectorAll('.quick').forEach(b => {{
      b.addEventListener('click', () => {{
        eidInput.value = b.dataset.eid;
        syncBtn();
        document.getElementById('loginForm').requestSubmit();
      }});
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# /login → handles the form submit, issues a code, redirects back to SP
# ---------------------------------------------------------------------------

@router.post("/login")
async def login_submit(
    emirates_id: str = Form(...),
    redirect_uri: str = Form(...),
    state: str = Form(""),
    scope: str = Form(""),
    acr_values: str = Form(""),
    password: str = Form(""),
) -> RedirectResponse:
    """Validate the chosen identity, issue an auth code, redirect to SP callback."""
    # Normalize the Emirates ID — accept both dashed (784-2004-6541442-1) and raw (784200465414421)
    digits = "".join(c for c in emirates_id if c.isdigit())
    if len(digits) != 15:
        return _redirect_with_error(redirect_uri, state, "access_denied", "InvalidEmiratesId")

    if digits not in _USERS:
        # Unknown identity — issue an access_denied like real UAE PASS would
        logger.info(f"mock-uaepass: unknown identity {digits[:3]}…{digits[-2:]}")
        return _redirect_with_error(redirect_uri, state, "access_denied", "UserNotFound")

    code = secrets.token_urlsafe(24)
    _CODES[code] = {
        "idn": digits,
        "redirect_uri": redirect_uri,
        "state": state,
        "expires_at": time.time() + CODE_TTL_SECONDS,
    }
    _purge_expired(_CODES)
    logger.info(f"mock-uaepass: issued code for idn={digits[:3]}…{digits[-2:]}")

    # 302 back to SP callback with code + original state (per OAuth 2.0)
    qs = urlencode({"code": code, "state": state})
    return RedirectResponse(f"{redirect_uri}?{qs}", status_code=302)


def _redirect_with_error(redirect_uri: str, state: str, error: str, desc: str) -> RedirectResponse:
    qs = urlencode({"error": error, "error_description": desc, "state": state})
    return RedirectResponse(f"{redirect_uri}?{qs}", status_code=302)


# ---------------------------------------------------------------------------
# /token → exchange code for access_token
# ---------------------------------------------------------------------------

@router.post("/token")
async def token(request: Request) -> JSONResponse:
    """Mock the UAE PASS /token endpoint. Verifies Basic auth + exchanges code for access_token."""
    # Basic auth: client_id:client_secret  (mock accepts hassan-mock:hassan-mock-secret)
    auth = request.headers.get("authorization", "")
    if auth.startswith("Basic "):
        try:
            creds = base64.b64decode(auth.removeprefix("Basic ")).decode()
            cid, csec = creds.split(":", 1)
        except Exception:
            return JSONResponse({"error": "invalid_client", "error_description": "unsupportedAuthenticationScheme"}, status_code=401)
        if cid != "hassan-mock" or csec != "hassan-mock-secret":
            return JSONResponse({"error": "invalid_client", "error_description": "invalidCredentials"}, status_code=401)

    form = await request.form()
    grant_type = form.get("grant_type")
    code = form.get("code")
    redirect_uri = form.get("redirect_uri")

    if grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
    if not code or code not in _CODES:
        return JSONResponse({"error": "invalid_grant", "error_description": "invalidOrExpiredCode"}, status_code=400)

    entry = _CODES.pop(code)        # codes are single-use
    if entry["expires_at"] < time.time():
        return JSONResponse({"error": "invalid_grant", "error_description": "expiredCode"}, status_code=400)
    if entry["redirect_uri"] != redirect_uri:
        return JSONResponse({"error": "invalid_grant", "error_description": "redirectUriMismatch"}, status_code=400)

    access_token = secrets.token_urlsafe(32)
    _TOKENS[access_token] = {
        "idn": entry["idn"],
        "expires_at": time.time() + TOKEN_TTL_SECONDS,
    }
    _purge_expired(_TOKENS)

    return JSONResponse({
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": TOKEN_TTL_SECONDS,
        "scope": "urn:uae:digitalid:profile:general",
    })


# ---------------------------------------------------------------------------
# /userinfo → return the same shape as the real UAE PASS /users/me
# ---------------------------------------------------------------------------

@router.get("/userinfo")
async def userinfo(request: Request) -> JSONResponse:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    tok = auth.removeprefix("Bearer ").strip()
    entry = _TOKENS.get(tok)
    if not entry or entry["expires_at"] < time.time():
        return JSONResponse({"error": "invalid_token"}, status_code=401)
    return JSONResponse(_USERS[entry["idn"]])


# ---------------------------------------------------------------------------
# /logout → clear the SP's redirect target
# ---------------------------------------------------------------------------

@router.get("/logout")
async def logout(redirect_uri: str | None = None) -> RedirectResponse:
    target = redirect_uri or "/"
    return RedirectResponse(target, status_code=302)
