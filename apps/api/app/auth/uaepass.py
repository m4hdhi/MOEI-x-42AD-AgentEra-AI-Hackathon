"""UAE PASS OAuth 2.0 client.

Implements the authorization-code flow per the UAE PASS Authentication Integration v2.0
toolkit. Defaults to the staging (QA) endpoints; flip the env vars below to point at
production once TDRA approves the entity.

Env vars (defaults are the public staging credentials from docs.uaepass.ae):

    UAEPASS_BASE_URL       https://qa-id.uaepass.ae   # or https://id.uaepass.ae for prod
    UAEPASS_CLIENT_ID      sandbox_stage
    UAEPASS_CLIENT_SECRET  sandbox_stage
    UAEPASS_REDIRECT_URI   https://han-ringleted-dubitatively.ngrok-free.dev/auth/uaepass/callback
    UAEPASS_SCOPE          urn:uae:digitalid:profile:general
    UAEPASS_ACR_VALUES     urn:safelayer:tws:policies:authentication:level:low
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from loguru import logger


@dataclass
class UaePassConfig:
    mode: str                  # "mock" | "staging" | "production"
    base_url: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str
    acr_values: str

    @classmethod
    def from_env(cls) -> "UaePassConfig":
        # Mode-aware defaults. Set UAEPASS_MODE in .env:
        #   mock       → local /auth/mock-uaepass/* endpoints (default for hackathon)
        #   staging    → real qa-id.uaepass.ae (needs entity-issued sandbox creds from TDRA)
        #   production → real id.uaepass.ae    (needs TDRA-approved prod creds)
        mode = (os.getenv("UAEPASS_MODE") or "mock").lower().strip()
        defaults = {
            "mock": {
                "base_url": os.getenv("HASSAN_PUBLIC_URL", "http://localhost:8000"),
                "client_id": "hassan-mock",
                "client_secret": "hassan-mock-secret",
            },
            "staging": {
                "base_url": "https://qa-id.uaepass.ae",
                "client_id": "sandbox_stage",
                "client_secret": "sandbox_stage",
            },
            "production": {
                "base_url": "https://id.uaepass.ae",
                "client_id": "",
                "client_secret": "",
            },
        }
        d = defaults.get(mode, defaults["mock"])
        # mock → localhost callback; staging/production → public ngrok callback
        default_redirect = (
            "http://localhost:8000/auth/uaepass/callback"
            if mode == "mock"
            else "https://han-ringleted-dubitatively.ngrok-free.dev/auth/uaepass/callback"
        )
        return cls(
            mode=mode,
            base_url=os.getenv("UAEPASS_BASE_URL", d["base_url"]),
            client_id=os.getenv("UAEPASS_CLIENT_ID", d["client_id"]),
            client_secret=os.getenv("UAEPASS_CLIENT_SECRET", d["client_secret"]),
            redirect_uri=os.getenv("UAEPASS_REDIRECT_URI", default_redirect),
            scope=os.getenv("UAEPASS_SCOPE", "urn:uae:digitalid:profile:general"),
            acr_values=os.getenv(
                "UAEPASS_ACR_VALUES",
                "urn:safelayer:tws:policies:authentication:level:low",
            ),
        )

    @property
    def is_mock(self) -> bool:
        return self.mode == "mock"

    @property
    def authorize_url(self) -> str:
        if self.is_mock:
            return f"{self.base_url}/auth/mock-uaepass/authorize"
        return f"{self.base_url}/trustedx-authserver/oauth/main-as"

    @property
    def token_url(self) -> str:
        if self.is_mock:
            return f"{self.base_url}/auth/mock-uaepass/token"
        return f"{self.base_url}/trustedx-authserver/oauth/main-as/token"

    @property
    def userinfo_url(self) -> str:
        if self.is_mock:
            return f"{self.base_url}/auth/mock-uaepass/userinfo"
        return f"{self.base_url}/trustedx-resources/openid/v1/users/me"

    @property
    def logout_url(self) -> str:
        if self.is_mock:
            return f"{self.base_url}/auth/mock-uaepass/logout"
        return f"{self.base_url}/trustedx-authserver/digitalid-idp/logout"


def build_authorize_url(cfg: UaePassConfig, *, state: str, ui_locale: str = "en") -> str:
    params = {
        "redirect_uri": cfg.redirect_uri,
        "client_id": cfg.client_id,
        "response_type": "code",
        "state": state,
        "scope": cfg.scope,
        "acr_values": cfg.acr_values,
        "ui_locales": ui_locale,
    }
    return f"{cfg.authorize_url}?{urlencode(params)}"


async def exchange_code_for_token(cfg: UaePassConfig, code: str) -> dict:
    """POST /token with Basic auth + form-encoded params. Per PDF §4.2."""
    creds = f"{cfg.client_id}:{cfg.client_secret}".encode()
    basic = base64.b64encode(creds).decode()
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            cfg.token_url,
            data={
                "grant_type": "authorization_code",
                "redirect_uri": cfg.redirect_uri,
                "code": code,
            },
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
        )
        if r.status_code >= 400:
            logger.warning(f"uaepass_token_error: {r.status_code} {r.text[:300]}")
            r.raise_for_status()
        return r.json()


async def fetch_userinfo(cfg: UaePassConfig, access_token: str) -> dict:
    """GET /users/me with Bearer token. Returns the user profile."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            cfg.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.status_code >= 400:
            logger.warning(f"uaepass_userinfo_error: {r.status_code} {r.text[:300]}")
            r.raise_for_status()
        return r.json()


def emirates_id_from_idn(idn: str) -> str:
    """UAE PASS returns the IDN as a 15-digit string (e.g. 784200400000001).
    Convert to the dashed display format 784-YYYY-XXXXXXX-X used elsewhere in Agent42.
    """
    s = "".join(c for c in idn if c.isdigit())
    if len(s) != 15:
        return idn
    return f"{s[0:3]}-{s[3:7]}-{s[7:14]}-{s[14]}"
