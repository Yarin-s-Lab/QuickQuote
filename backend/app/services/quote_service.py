"""Quote use cases: preview (no persistence) and create (number, save, PDF)."""

from __future__ import annotations

import re
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.schemas import (
    ApartmentPreviewRequest,
    ApartmentQuoteRequest,
    BreakdownLineOut,
    CarPreviewRequest,
    CarQuoteRequest,
    CoverageOut,
    CreateQuoteResponse,
    FactorOut,
    PreviewResponse,
    ProductOut,
    ProductsResponse,
    QuoteMetadata,
)
from app.config import QUOTE_VALIDITY_DAYS
from app.db.models import Quote
from app.domain.pricing.catalog import PRODUCTS, Product, describe_fields
from app.domain.pricing.common import MIN_PREMIUM, PricingResult
from app.services.numbering import QUOTE_NUMBER_RE, next_quote_number, quote_year
from app.services.pdf_renderer import (
    DocumentFactor,
    DocumentField,
    DocumentLine,
    PdfRenderer,
    QuoteDocument,
    format_ils,
)
from app.services.storage import InvalidStoragePathError, Storage

# secrets.token_urlsafe(32) -> 43 URL-safe base64 characters.
DOWNLOAD_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
DOWNLOAD_PATH = "/api/quotes/download/"


class QuoteExpiredError(Exception):
    """The quote exists but its validity has passed (HTTP 410)."""


@dataclass(frozen=True)
class Download:
    path: Path
    quote_number: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return str(uuid.uuid4())


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def preview(request: CarPreviewRequest | ApartmentPreviewRequest) -> PreviewResponse:
    product = PRODUCTS[request.product]
    result = product.price(request.inputs, request.coverages)
    return PreviewResponse(
        product=product.code,
        premium=result.premium,
        premium_before_rounding=result.premium_before_rounding,
        minimum_applied=result.minimum_applied,
        breakdown=[
            BreakdownLineOut(code=line.code, label_he=line.label_he, amount=line.amount)
            for line in result.breakdown
        ],
        factors=[
            FactorOut(code=factor.code, label_he=factor.label_he, value=factor.value)
            for factor in result.factors
        ],
    )


def list_products() -> ProductsResponse:
    return ProductsResponse(
        min_premium=MIN_PREMIUM,
        products=[
            ProductOut(
                code=product.code,
                label_he=product.label_he,
                fields=describe_fields(product.inputs_model),
                coverages=[
                    CoverageOut(code=c.code, label_he=c.label_he, price_rule_he=c.price_rule_he)
                    for c in product.coverages.values()
                ],
            )
            for product in PRODUCTS.values()
        ],
    )


def _display_fields(product: Product, inputs: BaseModel) -> tuple[DocumentField, ...]:
    values = inputs.model_dump()
    shown: list[DocumentField] = []
    for spec in describe_fields(product.inputs_model):
        value = values[spec["name"]]
        if spec["type"] == "money":
            text = format_ils(Decimal(value))
        elif spec["type"] == "boolean":
            text = "כן" if value else "לא"
        elif spec["type"] == "enum":
            labels = {o["value"]: o["label_he"] for o in spec["options"]}
            text = labels.get(value, str(value))
        else:
            text = str(value)
        numeric = spec["type"] in ("money", "integer")
        shown.append(
            DocumentField(name=spec["name"], label_he=spec["label_he"], value=text, ltr=numeric)
        )
    return tuple(shown)


def _breakdown_json(result: PricingResult) -> dict[str, Any]:
    return {
        "lines": [
            {"code": line.code, "label_he": line.label_he, "amount": str(line.amount)}
            for line in result.breakdown
        ],
        "factors": [
            {"code": f.code, "label_he": f.label_he, "value": str(f.value)} for f in result.factors
        ],
        "premium_before_rounding": str(result.premium_before_rounding),
        "minimum_applied": result.minimum_applied,
    }


@dataclass
class QuoteService:
    sessions: sessionmaker[Session]
    storage: Storage
    renderer: PdfRenderer
    clock: Callable[[], datetime] = _utc_now
    new_id: Callable[[], str] = _new_id
    new_token: Callable[[], str] = _new_token
    _validity: timedelta = field(default=timedelta(days=QUOTE_VALIDITY_DAYS), repr=False)

    def create(self, request: CarQuoteRequest | ApartmentQuoteRequest) -> CreateQuoteResponse:
        product = PRODUCTS[request.product]
        result = product.price(request.inputs, request.coverages)
        coverages = [c for c in product.coverages if c in request.coverages]

        issued_at = self.clock()
        if issued_at.tzinfo is None:
            raise ValueError("clock must return an aware datetime")
        valid_until = issued_at + self._validity
        quote_id = self.new_id()
        download_token = self.new_token()
        pdf_filename = self.storage.filename_for(quote_id)

        pdf_written = False
        try:
            # One transaction: counter bump + row + PDF. Any failure rolls the number back.
            with self.sessions() as session, session.begin():
                quote_number = next_quote_number(session, quote_year(issued_at))
                session.add(
                    Quote(
                        id=quote_id,
                        quote_number=quote_number,
                        product=product.code,
                        agent_name=request.agent_name,
                        client_full_name=request.client_full_name,
                        client_phone=request.client_phone,
                        client_email=request.client_email,
                        inputs=request.inputs.model_dump(mode="json"),
                        coverages=coverages,
                        premium=result.premium,
                        breakdown=_breakdown_json(result),
                        issued_at=issued_at,
                        valid_until=valid_until,
                        download_token=download_token,
                        pdf_filename=pdf_filename,
                    )
                )
                session.flush()

                document = QuoteDocument(
                    product=product.code,
                    quote_number=quote_number,
                    product_label_he=product.label_he,
                    issued_at=issued_at,
                    valid_until=valid_until,
                    agent_name=request.agent_name,
                    client_full_name=request.client_full_name,
                    client_phone=request.client_phone,
                    client_email=request.client_email,
                    fields=_display_fields(product, request.inputs),
                    coverages=tuple(product.coverages[c].label_he for c in coverages),
                    breakdown=tuple(
                        DocumentLine(line.label_he, line.amount) for line in result.breakdown
                    ),
                    factors=tuple(DocumentFactor(f.label_he, f.value) for f in result.factors),
                    premium_before_rounding=result.premium_before_rounding,
                    premium=result.premium,
                    minimum_applied=result.minimum_applied,
                )
                pdf = self.renderer.render(document)
                self.storage.save(quote_id, pdf)
                pdf_written = True
        except BaseException:
            if pdf_written:
                self.storage.delete(quote_id)
            raise

        return CreateQuoteResponse(
            quote_number=quote_number,
            product=product.code,
            premium=result.premium,
            issued_at=issued_at,
            valid_until=valid_until,
            download_url=DOWNLOAD_PATH + download_token,
        )

    def get_download(self, token: str) -> Download | None:
        """Resolve a download token to the PDF on disk.

        Only the token is used for lookup; the path is built from the internal UUID
        by Storage.path_for (resolve() + must stay under STORAGE_DIR). Anything else
        - malformed token, unknown token, bad stored id, missing file - is None (404).
        """
        if not DOWNLOAD_TOKEN_RE.fullmatch(token):
            return None
        with self.sessions() as session:
            quote = session.scalars(
                select(Quote).where(Quote.download_token == token)
            ).one_or_none()
            if quote is None:
                return None
            if self.clock() > quote.valid_until:
                raise QuoteExpiredError(quote.quote_number)
            try:
                path = self.storage.path_for(quote.id)
            except InvalidStoragePathError:
                return None
            if not path.is_file():
                return None
            return Download(path=path, quote_number=quote.quote_number)

    def get_metadata(self, quote_number: str) -> QuoteMetadata | None:
        if not QUOTE_NUMBER_RE.fullmatch(quote_number):
            return None
        with self.sessions() as session:
            quote = session.scalars(
                select(Quote).where(Quote.quote_number == quote_number)
            ).one_or_none()
            if quote is None:
                return None
            return QuoteMetadata(
                quote_number=quote.quote_number,
                product=quote.product,
                agent_name=quote.agent_name,
                client_full_name=quote.client_full_name,
                client_phone=quote.client_phone,
                client_email=quote.client_email,
                inputs=quote.inputs,
                coverages=quote.coverages,
                premium=quote.premium,
                breakdown=quote.breakdown,
                issued_at=quote.issued_at,
                valid_until=quote.valid_until,
            )
