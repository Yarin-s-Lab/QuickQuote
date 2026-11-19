"""Map every error to {"error": {"code": ..., "message_he": ...}} (SPEC section 5)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.pricing.catalog import field_labels_he
from app.services.pdf_renderer import PdfUnavailableError
from app.services.quote_service import (
    ComparisonRequestError,
    QuoteExpiredError,
    QuoteNotFoundError,
)

_STATUS_MESSAGES_HE = {
    404: ("not_found", "המשאב לא נמצא"),
    405: ("method_not_allowed", "שיטת הבקשה אינה נתמכת"),
}

_GENERIC_LABELS_HE = {
    "product": "מוצר",
    "inputs": "נתוני המוצר",
    "coverages": "כיסויים",
    "agent_name": "שם הסוכן",
    "client_full_name": "שם הלקוח",
    "client_phone": "טלפון",
    "client_email": 'דוא"ל',
    "tokens": "הצעות להשוואה",
}


def error_body(code: str, message_he: str) -> dict[str, Any]:
    return {"error": {"code": code, "message_he": message_he}}


def _field_label(loc: tuple[Any, ...], labels: dict[str, str]) -> str | None:
    for part in reversed(loc):
        if isinstance(part, str) and part in labels:
            return labels[part]
    return None


def _message_he(err: dict[str, Any], labels: dict[str, str]) -> str:
    kind = err.get("type", "")
    ctx = err.get("ctx") or {}
    label = _field_label(tuple(err.get("loc", ())), labels)

    if kind == "value_error":
        # Our own validators raise ValueError with a Hebrew message.
        return str(ctx.get("error", "ערך לא תקין"))
    if kind == "missing":
        text = "שדה חובה"
    elif kind in ("greater_than_equal", "greater_than"):
        text = f"הערך חייב להיות לפחות {ctx.get('ge', ctx.get('gt'))}"
    elif kind in ("less_than_equal", "less_than"):
        text = f"הערך חייב להיות לכל היותר {ctx.get('le', ctx.get('lt'))}"
    elif kind.startswith("int_"):
        text = "יש להזין מספר שלם"
    elif kind.startswith("bool"):
        text = "יש לבחור כן או לא"
    elif kind in ("literal_error", "enum"):
        text = "ערך שאינו מהרשימה"
    elif kind in ("union_tag_invalid", "union_tag_not_found"):
        return "מוצר לא מוכר"
    elif kind == "extra_forbidden":
        text = "שדה לא מוכר"
    elif kind == "string_too_short":
        text = "שדה חובה"
    elif kind == "string_pattern_mismatch":
        text = "פורמט לא תקין"
    elif kind == "string_type":
        text = "יש להזין טקסט"
    elif kind == "string_too_long":
        text = f"אורך מקסימלי {ctx.get('max_length')} תווים"
    else:
        text = "ערך לא תקין"
    return f"{label}: {text}" if label else text


def install_error_handlers(app: FastAPI) -> None:
    labels = {**_GENERIC_LABELS_HE, **field_labels_he()}

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        messages = list(dict.fromkeys(_message_he(e, labels) for e in exc.errors()))
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", "; ".join(messages) or "קלט לא תקין"),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _STATUS_MESSAGES_HE.get(exc.status_code, ("http_error", "שגיאה בבקשה"))
        return JSONResponse(status_code=exc.status_code, content=error_body(code, message))

    @app.exception_handler(PdfUnavailableError)
    async def _pdf_unavailable(_: Request, __: PdfUnavailableError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=error_body("pdf_unavailable", "יצירת PDF אינה זמינה בשרת זה"),
        )

    @app.exception_handler(QuoteExpiredError)
    async def _expired(_: Request, __: QuoteExpiredError) -> JSONResponse:
        return JSONResponse(
            status_code=410,
            content=error_body("quote_expired", "תוקף ההצעה פג ולא ניתן להוריד אותה"),
        )

    @app.exception_handler(QuoteNotFoundError)
    async def _quote_not_found(_: Request, __: QuoteNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content=error_body("not_found", "ההצעה לא נמצאה"))

    @app.exception_handler(ComparisonRequestError)
    async def _comparison(_: Request, exc: ComparisonRequestError) -> JSONResponse:
        return JSONResponse(status_code=422, content=error_body("validation_error", exc.message_he))

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content=error_body("internal_error", "שגיאת שרת"))
