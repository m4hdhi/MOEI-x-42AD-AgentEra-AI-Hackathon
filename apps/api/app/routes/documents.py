"""Document understanding (computer vision) — OCR + field extraction.

A citizen uploads a photo of an Emirates ID or salary slip; we send it to a vision model
(GPT-4o-mini) which reads the document and returns structured fields. This removes manual
data entry and feeds the case automatically.

PDPL note: extracted Emirates ID / salary numbers are masked in the response shown to the
citizen; the full values would go only to the secure case record in production.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger

from ..core.db import db_cursor
from .auth import get_authenticated_user_id

router = APIRouter(prefix="/documents", tags=["documents"])


def _ensure_documents_table() -> None:
    with db_cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_documents (
                id              UUID PRIMARY KEY,
                user_id         TEXT NOT NULL,
                case_number     TEXT,
                document_type   TEXT NOT NULL DEFAULT 'other',
                status          TEXT NOT NULL DEFAULT 'uploaded',
                original_name   TEXT,
                content_type    TEXT,
                file_size       BIGINT,
                storage_path    TEXT NOT NULL,
                sha256          TEXT NOT NULL,
                confidence      NUMERIC(4,2),
                extracted_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
                signals         JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_customer_documents_user_created "
            "ON customer_documents (user_id, created_at DESC)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_customer_documents_case "
            "ON customer_documents (case_number) WHERE case_number IS NOT NULL"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_customer_documents_type "
            "ON customer_documents (document_type)"
        )

_EXTRACT_PROMPT = (
    "You are a document-reading assistant for the UAE Ministry of Energy and Infrastructure. "
    "Read the attached document image and extract its fields as JSON. First classify it using "
    "visible layout and text cues. Emirates ID cards are plastic identity cards and commonly show "
    "Identity Card, Emirates ID, ID Number, name, nationality, date of birth, expiry date, a portrait, "
    "and a 15-digit UAE ID number in the 784-YYYY-NNNNNNN-C format. Salary certificates are usually "
    "employer letters/certificates and commonly show Salary Certificate, To whom it may concern, "
    "employee name, employer/company, designation, monthly/basic/gross salary, issue date, stamp, "
    "and signature. Detect the document type (one of: emirates_id, salary_certificate, "
    "bank_statement, passport, other). Return ONLY a JSON object with keys: "
    "document_type, full_name, id_number, employer, monthly_salary_aed, issue_date, expiry_date, "
    "designation, nationality, date_of_birth, and any other clearly visible key fields under 'other'. "
    "Use null for anything not present. "
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


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _digits(value: object) -> str:
    return re.sub(r"\D", "", _clean_text(value))


def _all_field_text(fields: dict, *, filename: str = "", hint: str = "") -> str:
    parts = [filename, hint]
    for value in fields.values():
        parts.append(_clean_text(value))
    return " ".join(parts).lower()


def _looks_like_emirates_id_number(value: object) -> bool:
    digits = _digits(value)
    return len(digits) == 15 and digits.startswith("784")


def classify_document(fields: dict, *, filename: str = "", doc_hint: str = "") -> dict:
    """Classify the document with deterministic checks after vision extraction.

    Vision reads the image; this guardrail checks UAE-specific text and field patterns so we do
    not rely on the model label alone.
    """
    text = _all_field_text(fields, filename=filename, hint=doc_hint)
    model_type = str(fields.get("document_type") or "").strip().lower()
    scores = {
        "emirates_id": 0,
        "salary_certificate": 0,
        "bank_statement": 0,
        "passport": 0,
        "other": 0,
    }
    signals: list[str] = []

    if model_type in scores:
        scores[model_type] += 2
        signals.append(f"vision_label:{model_type}")

    id_sources = [
        fields.get("id_number"),
        fields.get("emirates_id"),
        fields.get("idn"),
        fields.get("identity_number"),
        fields.get("other"),
        text,
    ]
    if any(_looks_like_emirates_id_number(value) for value in id_sources):
        scores["emirates_id"] += 5
        signals.append("uae_id_number_format:784-YYYY-NNNNNNN-C")
    if re.search(r"\b(emirates id|emirates identity|identity card|id card|id number|idn)\b", text):
        scores["emirates_id"] += 3
        signals.append("identity_card_keywords")
    if fields.get("nationality") or fields.get("date_of_birth") or fields.get("expiry_date"):
        scores["emirates_id"] += 1
        signals.append("identity_fields_present")

    if re.search(r"\b(salary certificate|salary slip|to whom it may concern|basic salary|gross salary|monthly salary|employee no|designation)\b", text):
        scores["salary_certificate"] += 4
        signals.append("salary_certificate_keywords")
    if fields.get("monthly_salary_aed"):
        scores["salary_certificate"] += 3
        signals.append("monthly_salary_field_present")
    if fields.get("employer") or fields.get("designation"):
        scores["salary_certificate"] += 2
        signals.append("employment_fields_present")
    if re.search(r"\b(stamp|signed|signature|hr department|human resources)\b", text):
        scores["salary_certificate"] += 1
        signals.append("letter_stamp_signature_cues")

    if re.search(r"\b(bank statement|account number|iban|opening balance|closing balance|transaction)\b", text):
        scores["bank_statement"] += 4
        signals.append("bank_statement_keywords")
    if re.search(r"\b(passport|place of birth|passport no|passport number|issuing authority)\b", text):
        scores["passport"] += 4
        signals.append("passport_keywords")

    doc_type, score = max(scores.items(), key=lambda item: item[1])
    if score <= 1:
        doc_type = "other"
    runner_up = max((v for k, v in scores.items() if k != doc_type), default=0)
    confidence = min(0.98, max(0.35, 0.45 + (score - runner_up) * 0.12 + score * 0.03))
    if doc_type == "other":
        confidence = min(confidence, 0.45)

    return {
        "document_type": doc_type,
        "confidence": round(confidence, 2),
        "signals": signals[:6],
    }


def _chat_summary(fields: dict, doc_type: str, confidence: float) -> str:
    label = {
        "emirates_id": "Emirates ID",
        "salary_certificate": "salary certificate",
        "bank_statement": "bank statement",
        "passport": "passport",
    }.get(doc_type, "supporting document")
    parts = [f"I uploaded a {label}. The document detector classified it with {round(confidence * 100)}% confidence."]
    if doc_type == "emirates_id":
        if fields.get("full_name"):
            parts.append(f"Name found: {fields['full_name']}.")
        if fields.get("expiry_date"):
            parts.append(f"Expiry date found: {fields['expiry_date']}.")
    elif doc_type == "salary_certificate":
        if fields.get("employer"):
            parts.append(f"Employer found: {fields['employer']}.")
        if fields.get("monthly_salary_aed"):
            parts.append(f"Monthly salary found: AED {fields['monthly_salary_aed']}.")
        if fields.get("issue_date"):
            parts.append(f"Issue date found: {fields['issue_date']}.")
    return " ".join(parts)


def _storage_root() -> Path:
    default = Path(__file__).resolve().parents[4] / "storage" / "customer-documents"
    return Path(os.getenv("DOCUMENT_STORAGE_DIR", str(default))).expanduser()


def _safe_suffix(filename: str | None, content_type: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".pdf"}:
        return suffix
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"
    if content_type == "application/pdf":
        return ".pdf"
    return ".jpg"


def _persist_document(
    *,
    user_id: str,
    data: bytes,
    file: UploadFile,
    doc_type: str,
    confidence: float,
    signals: list[str],
    fields: dict,
    case_number: str | None = None,
) -> dict | None:
    """Save the upload locally and store customer-linked metadata in Postgres.

    Local disk is the demo storage adapter. In production this should be replaced by S3/Azure Blob
    with the same DB row shape.
    """
    try:
        doc_id = str(uuid.uuid4())
        digest = hashlib.sha256(data).hexdigest()
        root = _storage_root()
        user_dir = root / re.sub(r"[^A-Za-z0-9_.-]", "_", user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        storage_path = user_dir / f"{doc_id}{_safe_suffix(file.filename, file.content_type)}"
        storage_path.write_bytes(data)

        _ensure_documents_table()
        with db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO customer_documents
                  (id, user_id, case_number, document_type, status, original_name, content_type,
                   file_size, storage_path, sha256, confidence, extracted_fields, signals)
                VALUES (%s,%s,%s,%s,'uploaded',%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
                RETURNING id, user_id, case_number, document_type, status, original_name,
                          content_type, file_size, sha256, confidence, created_at
                """,
                (
                    doc_id,
                    user_id,
                    case_number,
                    doc_type,
                    file.filename,
                    file.content_type,
                    len(data),
                    str(storage_path),
                    digest,
                    confidence,
                    json.dumps(fields, ensure_ascii=False),
                    json.dumps(signals, ensure_ascii=False),
                ),
            )
            row = cur.fetchone()
        return _serialize_document(row) if row else {"id": doc_id}
    except Exception as e:
        logger.warning(f"documents: persist failed for user={user_id}: {e}")
        return None


def _serialize_document(row: dict | None) -> dict:
    if not row:
        return {}
    out = dict(row)
    for key, value in list(out.items()):
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        elif hasattr(value, "hex") and not isinstance(value, (bytes, str)):
            out[key] = str(value)
        elif key == "confidence" and value is not None:
            out[key] = float(value)
    out.pop("storage_path", None)
    return out


@router.post("/extract")
async def extract_document(
    request: Request,
    file: UploadFile = File(...),
    doc_hint: str = Form(""),
    case_number: str = Form(""),
) -> JSONResponse:
    """OCR + structured extraction from an uploaded document image."""
    api_key = os.getenv("OPENAI_API_KEY")
    user_id = get_authenticated_user_id(request)
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

    detected = classify_document(fields, filename=file.filename or "", doc_hint=doc_hint)
    fields["document_type"] = detected["document_type"]

    saved = None
    if user_id:
        saved = _persist_document(
            user_id=user_id,
            data=data,
            file=file,
            doc_type=detected["document_type"],
            confidence=detected["confidence"],
            signals=detected["signals"],
            fields=fields,
            case_number=case_number or None,
        )

    # Mask sensitive identifiers in the response.
    masked = dict(fields)
    if masked.get("id_number"):
        masked["id_number"] = _mask(str(masked["id_number"]))

    return JSONResponse({
        "ok": True,
        "document_type": detected["document_type"],
        "confidence": detected["confidence"],
        "signals": detected["signals"],
        "saved": bool(saved),
        "document": saved,
        "document_id": saved.get("id") if saved else None,
        "fields": masked,
        "chat_summary": _chat_summary(masked, detected["document_type"], detected["confidence"]),
        "note": (
            "Saved under your customer profile; sensitive identifiers are masked here."
            if saved
            else "Sensitive identifiers are masked here. Sign in to save documents under your profile."
        ),
    })


@router.get("")
def list_documents(request: Request, limit: int = 20) -> dict:
    """List uploaded documents for the signed-in customer."""
    uid = get_authenticated_user_id(request)
    if not uid:
        raise HTTPException(401, "sign in required")
    _ensure_documents_table()
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT id, user_id, case_number, document_type, status, original_name, content_type,
                   file_size, sha256, confidence, signals, created_at, updated_at
            FROM customer_documents
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (uid, max(1, min(limit, 100))),
        )
        rows = cur.fetchall()
    return {"user_id": uid, "count": len(rows), "documents": [_serialize_document(r) for r in rows]}


@router.get("/{document_id}")
def get_document(document_id: str, request: Request) -> dict:
    uid = get_authenticated_user_id(request)
    if not uid:
        raise HTTPException(401, "sign in required")
    _ensure_documents_table()
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT id, user_id, case_number, document_type, status, original_name, content_type,
                   file_size, sha256, confidence, extracted_fields, signals, created_at, updated_at
            FROM customer_documents
            WHERE id = %s
            """,
            (document_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "document not found")
    if row.get("user_id") != uid:
        raise HTTPException(403, "document belongs to another customer")
    return _serialize_document(row)
