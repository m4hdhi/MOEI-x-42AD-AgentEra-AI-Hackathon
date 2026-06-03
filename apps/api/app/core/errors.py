"""Unified error envelope. Federal-grade error responses include correlation_id for audit.

Citizens never see raw stack traces; auditors get full traceability through correlation_id.
"""

from __future__ import annotations

import traceback
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger


def _envelope(*, status: int, code: str, message: str, correlation_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "correlation_id": correlation_id,
            }
        },
        headers={"X-Correlation-Id": correlation_id},
    )


async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    cid = request.headers.get("X-Correlation-Id", uuid4().hex)
    return _envelope(
        status=422,
        code="VALIDATION_ERROR",
        message="; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()),
        correlation_id=cid,
    )


async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    cid = request.headers.get("X-Correlation-Id", uuid4().hex)
    logger.error(f"[{cid}] unhandled: {exc}\n{traceback.format_exc()}")
    return _envelope(
        status=500,
        code="INTERNAL_ERROR",
        message="An internal error occurred. Quote the correlation_id when contacting support.",
        correlation_id=cid,
    )
