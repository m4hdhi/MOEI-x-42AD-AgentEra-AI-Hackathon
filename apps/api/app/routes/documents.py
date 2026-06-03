"""Document understanding (computer vision) — OCR + field extraction.

A citizen uploads a photo of an Emirates ID or salary slip; we send it to a vision model
(GPT-4o-mini) which reads the document and returns structured fields. This removes manual
data entry and feeds the case automatically.

PDPL note: extracted Emirates ID / salary numbers are masked in the response shown to the
citizen; the full values would go only to the secure case record in production.
"""

from __future__ import annotations

import base64
import json
import os

import httpx
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger

router = APIRouter(prefix="/documents", tags=["documents"])

_EXTRACT_PROMPT = (
    "You are a document-reading assistant for the UAE Ministry of Energy and Infrastructure. "
    "Read the attached document image and extract its fields as JSON. "
    "Detect the document type (one of: emirates_id, salary_certificate, bank_statement, "
    "passport, other). Return ONLY a JSON object with keys: "
    "document_type, full_name, id_number, employer, monthly_salary_aed, issue_date, expiry_date, "
    "and any other clearly visible key fields under 'other'. Use null for anything not present. "
    "Do not invent values."
)


def _mask(val: str | None) -> str | None:
    if not val or not isinstance(val, str):
        return val
    digits = [c for c in val if c.isdigit()]
    if len(digits) >= 6:
        # keep last 3 digits visible
        out, kept = [], 0
        for c in reversed(val):
            if c.isdigit() and kept < 3:
                out.append(c); kept += 1
            elif c.isdigit():
                out.append("•")
            else:
                out.append(c)
        return "".join(reversed(out))
    return val


@router.post("/extract")
async def extract_document(
    file: UploadFile = File(...),
    doc_hint: str = Form(""),
) -> JSONResponse:
    """OCR + structured extraction from an uploaded document image."""
    api_key = os.getenv("OPENAI_API_KEY")
    data = await file.read()
    if not data:
        return JSONResponse({"error": "empty file"}, status_code=400)
    if len(data) > 8 * 1024 * 1024:
        return JSONResponse({"error": "file too large (max 8MB)"}, status_code=413)

    mime = file.content_type or "image/jpeg"
    b64 = base64.b64encode(data).decode()
    data_uri = f"data:{mime};base64,{b64}"

    if not api_key:
        return JSONResponse({
            "ok": False,
            "reason": "vision model not configured (set OPENAI_API_KEY)",
        }, status_code=503)

    body = {
        "model": os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": _EXTRACT_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": f"Document hint: {doc_hint or 'unknown'}. Extract the fields."},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ]},
        ],
        "max_tokens": 600,
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
            )
        if r.status_code != 200:
            logger.warning(f"documents: vision API {r.status_code}: {r.text[:200]}")
            return JSONResponse({"ok": False, "reason": f"vision API error {r.status_code}"}, status_code=502)
        content = r.json()["choices"][0]["message"]["content"]
        fields = json.loads(content)
    except Exception as e:
        logger.warning(f"documents: extraction failed: {e}")
        return JSONResponse({"ok": False, "reason": str(e)}, status_code=502)

    # Mask sensitive identifiers in the response.
    masked = dict(fields)
    if masked.get("id_number"):
        masked["id_number"] = _mask(str(masked["id_number"]))

    return JSONResponse({
        "ok": True,
        "document_type": fields.get("document_type"),
        "fields": masked,
        "note": "Sensitive identifiers are masked here; full values go only to the secure case record.",
    })
