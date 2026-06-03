"""Simple admin login.

For the hackathon: any email + password 'admin'. Sets a signed HttpOnly cookie
`hassan_admin` so the Next.js middleware can protect /admin/* without a separate session
store. Production would integrate with MOEI's federated SSO.
"""

from __future__ import annotations

import json
import os
import time

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, TimestampSigner

router = APIRouter(prefix="/admin-auth", tags=["admin-auth"])

_COOKIE = "hassan_admin"
_TTL = 60 * 60 * 8     # 8h
_SECRET = os.getenv("HASSAN_SESSION_SECRET", "dev-secret-change-me-32chars-xx")
_ADMIN_PASSWORD = os.getenv("HASSAN_ADMIN_PASSWORD", "admin")


def _signer() -> TimestampSigner:
    return TimestampSigner(_SECRET)


def _sign(payload: dict) -> str:
    return _signer().sign(json.dumps(payload).encode()).decode()


def _unsign(value: str, max_age: int = _TTL) -> dict | None:
    try:
        return json.loads(_signer().unsign(value, max_age=max_age).decode())
    except (BadSignature, Exception):
        return None


@router.post("/login")
async def login(payload: dict, request: Request) -> JSONResponse:
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if not email:
        raise HTTPException(400, "email required")
    if password != _ADMIN_PASSWORD:
        raise HTTPException(401, "invalid password (hint: 'admin' for the hackathon)")

    role = "supervisor" if email.startswith("supervisor") else "agent"
    session = {"email": email, "role": role, "iat": int(time.time())}
    resp = JSONResponse({"authenticated": True, "email": email, "role": role})
    resp.set_cookie(
        _COOKIE,
        _sign(session),
        max_age=_TTL,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https",
    )
    return resp


@router.get("/me")
async def me(request: Request) -> JSONResponse:
    cookie = request.cookies.get(_COOKIE)
    if not cookie:
        return JSONResponse({"authenticated": False}, status_code=401)
    s = _unsign(cookie)
    if not s:
        return JSONResponse({"authenticated": False, "error": "session expired"}, status_code=401)
    return JSONResponse({"authenticated": True, **s})


@router.post("/logout")
async def logout() -> Response:
    resp = RedirectResponse("/admin/login", status_code=302)
    resp.delete_cookie(_COOKIE)
    return resp


def is_admin_authenticated(request: Request) -> dict | None:
    cookie = request.cookies.get(_COOKIE)
    if not cookie:
        return None
    return _unsign(cookie)
