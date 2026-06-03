"""UAE PASS authentication routes.

Endpoints:
  GET  /auth/uaepass/login    → 302 redirect to UAE PASS authorize URL
  GET  /auth/uaepass/callback → handles OAuth code, sets HttpOnly session cookie, 302 back to /chat
  GET  /auth/me               → JSON of the logged-in citizen profile (or 401)
  POST /auth/logout           → clear cookie + redirect to UAE PASS logout

Session storage: signed JWT in an HttpOnly cookie. Self-contained — no DB needed.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, TimestampSigner
from loguru import logger

from ..auth.uaepass import (
    UaePassConfig,
    build_authorize_url,
    emirates_id_from_idn,
    exchange_code_for_token,
    fetch_userinfo,
)
from ..core.db import db_cursor

router = APIRouter(prefix="/auth", tags=["auth"])


def _persist_citizen(session: dict) -> None:
    """Upsert the authenticated citizen into the master `citizens` table.

    Called on every UAE PASS login so staff can browse everyone who has interacted.
    Best-effort: never block login on a DB hiccup.
    """
    user_id = session.get("emirates_id") or session.get("idn_raw")
    if not user_id:
        return
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO citizens
                  (user_id, full_name_en, full_name_ar, emirates_id, uae_pass_sub,
                   user_type, nationality_en, gender, mobile, email, verified, last_seen_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                  full_name_en = COALESCE(NULLIF(EXCLUDED.full_name_en,''), citizens.full_name_en),
                  full_name_ar = COALESCE(NULLIF(EXCLUDED.full_name_ar,''), citizens.full_name_ar),
                  emirates_id  = COALESCE(NULLIF(EXCLUDED.emirates_id,''), citizens.emirates_id),
                  uae_pass_sub = COALESCE(EXCLUDED.uae_pass_sub, citizens.uae_pass_sub),
                  user_type    = COALESCE(EXCLUDED.user_type, citizens.user_type),
                  nationality_en = COALESCE(EXCLUDED.nationality_en, citizens.nationality_en),
                  gender       = COALESCE(EXCLUDED.gender, citizens.gender),
                  mobile       = COALESCE(EXCLUDED.mobile, citizens.mobile),
                  email        = COALESCE(EXCLUDED.email, citizens.email),
                  verified     = TRUE,
                  last_seen_at = NOW()
                """,
                (user_id, session.get("full_name_en"), session.get("full_name_ar"),
                 session.get("emirates_id"), session.get("sub"), session.get("user_type"),
                 session.get("nationality_en"), session.get("gender"),
                 session.get("mobile"), session.get("email")),
            )
        logger.info(f"citizens: upserted {user_id} ({session.get('full_name_en')!r})")
    except Exception as e:
        logger.warning(f"citizens: upsert failed for {user_id}: {e}")

_COOKIE_NAME = "hassan_session"
_STATE_COOKIE = "hassan_oauth_state"
_COOKIE_MAX_AGE = 60 * 60 * 8     # 8h
_SESSION_SECRET = os.getenv("HASSAN_SESSION_SECRET", "dev-secret-change-me-32chars-xx")


def _signer() -> TimestampSigner:
    return TimestampSigner(_SESSION_SECRET)


def _sign(payload: dict) -> str:
    return _signer().sign(json.dumps(payload).encode()).decode()


def _unsign(value: str, max_age: int) -> dict | None:
    try:
        raw = _signer().unsign(value, max_age=max_age)
        return json.loads(raw.decode())
    except BadSignature:
        return None
    except Exception:
        return None


def _redirect_after_login() -> str:
    return os.getenv("HASSAN_FRONTEND_URL", "http://localhost:3000") + "/chat?logged_in=1"


@router.get("/uaepass/login")
async def uaepass_login(request: Request, locale: str = "en") -> Response:
    """Kick off the OAuth flow — generate state, redirect to UAE PASS."""
    cfg = UaePassConfig.from_env()
    state = secrets.token_urlsafe(24)

    target = build_authorize_url(cfg, state=state, ui_locale=locale if locale in ("en", "ar") else "en")
    logger.info(f"uaepass_login: redirecting to {cfg.authorize_url} (state={state[:8]}…)")
    resp = RedirectResponse(url=target, status_code=302)
    # Store state in a short-lived cookie so we can verify on callback (CSRF guard)
    resp.set_cookie(
        _STATE_COOKIE,
        _sign({"state": state, "ts": int(time.time())}),
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https",
    )
    return resp


@router.get("/uaepass/callback")
async def uaepass_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> Response:
    """Handle the redirect from UAE PASS. Exchange code → token → userinfo → session."""
    if error:
        logger.warning(f"uaepass_callback: error={error} desc={error_description}")
        return RedirectResponse(
            url=f"{os.getenv('HASSAN_FRONTEND_URL', 'http://localhost:3000')}/chat?auth_error={error}",
            status_code=302,
        )
    if not code or not state:
        raise HTTPException(status_code=400, detail="missing code or state")

    # Verify state
    state_cookie = request.cookies.get(_STATE_COOKIE)
    if not state_cookie:
        raise HTTPException(status_code=400, detail="missing state cookie (CSRF guard)")
    state_data = _unsign(state_cookie, max_age=600)
    if not state_data or state_data.get("state") != state:
        raise HTTPException(status_code=400, detail="state mismatch — possible CSRF")

    cfg = UaePassConfig.from_env()
    try:
        token = await exchange_code_for_token(cfg, code)
    except Exception as e:
        logger.exception(f"uaepass_callback: token exchange failed: {e}")
        return RedirectResponse(
            url=f"{os.getenv('HASSAN_FRONTEND_URL', 'http://localhost:3000')}/chat?auth_error=token_exchange",
            status_code=302,
        )

    access_token = token.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="no access_token in UAE PASS response")

    try:
        profile = await fetch_userinfo(cfg, access_token)
    except Exception as e:
        logger.exception(f"uaepass_callback: userinfo failed: {e}")
        return RedirectResponse(
            url=f"{os.getenv('HASSAN_FRONTEND_URL', 'http://localhost:3000')}/chat?auth_error=userinfo",
            status_code=302,
        )

    # Build the Hassan session payload from the UAE PASS profile
    idn = profile.get("idn") or ""
    session = {
        "iss": "uaepass-stage" if "qa-" in cfg.base_url else "uaepass",
        "sub": profile.get("sub"),
        "user_type": profile.get("userType"),                # SOP1 / SOP2 / SOP3
        "emirates_id": emirates_id_from_idn(idn) if idn else "",
        "idn_raw": idn,
        "full_name_en": profile.get("fullnameEN") or "",
        "full_name_ar": profile.get("fullnameAR") or "",
        "first_name_en": profile.get("firstnameEN") or "",
        "gender": profile.get("gender"),
        "nationality_en": profile.get("nationalityEN"),
        "mobile": profile.get("mobile"),
        "email": profile.get("email"),
        "acr": profile.get("acr"),
        "iat": int(time.time()),
    }
    logger.info(
        f"uaepass_callback: authenticated user_type={session['user_type']} "
        f"name={session['full_name_en']!r} eid={session['emirates_id']!r}"
    )
    _persist_citizen(session)

    resp = RedirectResponse(url=_redirect_after_login(), status_code=302)
    resp.set_cookie(
        _COOKIE_NAME,
        _sign(session),
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https",
    )
    resp.delete_cookie(_STATE_COOKIE)
    return resp


@router.get("/me")
async def me(request: Request) -> JSONResponse:
    """Return the authenticated citizen profile, or 401 if not logged in."""
    cookie = request.cookies.get(_COOKIE_NAME)
    if not cookie:
        return JSONResponse({"authenticated": False}, status_code=401)
    session = _unsign(cookie, max_age=_COOKIE_MAX_AGE)
    if not session:
        return JSONResponse({"authenticated": False, "error": "session expired"}, status_code=401)
    return JSONResponse({"authenticated": True, **session})


@router.post("/logout")
async def logout(request: Request) -> Response:
    """Clear the Hassan session cookie + redirect to UAE PASS logout."""
    cfg = UaePassConfig.from_env()
    frontend = os.getenv("HASSAN_FRONTEND_URL", "http://localhost:3000")
    logout_target = f"{cfg.logout_url}?{urlencode({'redirect_uri': frontend})}"
    resp = RedirectResponse(url=logout_target, status_code=302)
    resp.delete_cookie(_COOKIE_NAME)
    return resp


# ---- Helper for other routes ------------------------------------------------

def _read_session(request: Request) -> dict | None:
    cookie = request.cookies.get(_COOKIE_NAME)
    if not cookie:
        return None
    return _unsign(cookie, max_age=_COOKIE_MAX_AGE)


def get_authenticated_user_id(request: Request) -> str | None:
    """Read the session cookie and return the citizen's Emirates ID (dashed) if logged in."""
    s = _read_session(request)
    return s.get("emirates_id") if s else None


def get_authenticated_user_name(request: Request) -> str | None:
    """Read the session cookie and return the citizen's full English name if logged in."""
    s = _read_session(request)
    return s.get("full_name_en") if s else None
