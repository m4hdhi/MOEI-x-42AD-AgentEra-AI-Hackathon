"""Correlation-ID middleware. Every request gets one in header + response."""

from __future__ import annotations

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-Id") or uuid4().hex
        request.state.correlation_id = cid
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = cid
        return response
