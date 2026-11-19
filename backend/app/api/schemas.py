"""Request/response contracts for /api (SPEC section 5)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
)

from app.domain.pricing.apartment import ApartmentCoverageCode, ApartmentInputs
from app.domain.pricing.car import CarCoverageCode, CarInputs

DUPLICATE_COVERAGE_HE = "כיסוי נבחר יותר מפעם אחת"


def _unique(codes: list[str]) -> list[str]:
    if len(set(codes)) != len(codes):
        raise ValueError(DUPLICATE_COVERAGE_HE)
    return codes


class CarPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: Literal["car"]
    inputs: CarInputs
    coverages: Annotated[list[CarCoverageCode], AfterValidator(_unique)] = []


class ApartmentPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: Literal["apartment"]
    inputs: ApartmentInputs
    coverages: Annotated[list[ApartmentCoverageCode], AfterValidator(_unique)] = []


PreviewRequest = Annotated[
    CarPreviewRequest | ApartmentPreviewRequest, Field(discriminator="product")
]


MAX_TEXT = 100
PHONE_RE = r"^\+?\d[\d -]{6,18}\d$"
EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


RequiredText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT)
]
Phone = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_TEXT, pattern=PHONE_RE)]
    | None,
    BeforeValidator(_blank_to_none),
]
Email = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_TEXT, pattern=EMAIL_RE)]
    | None,
    BeforeValidator(_blank_to_none),
]


class PartiesIn(BaseModel):
    """Agent and client details. No ID numbers or financial details (SPEC section 3)."""

    agent_name: RequiredText
    client_full_name: RequiredText
    client_phone: Phone = None
    client_email: Email = None


class CarQuoteRequest(CarPreviewRequest, PartiesIn):
    pass


class ApartmentQuoteRequest(ApartmentPreviewRequest, PartiesIn):
    pass


CreateQuoteRequest = Annotated[
    CarQuoteRequest | ApartmentQuoteRequest, Field(discriminator="product")
]


class CreateQuoteResponse(BaseModel):
    quote_number: str
    product: str
    premium: Decimal
    issued_at: datetime
    valid_until: datetime
    download_url: str | None = None  # secure download arrives in level 3


class QuoteMetadata(BaseModel):
    """GET /quotes/{quote_number}. Never includes the download token or file name."""

    quote_number: str
    product: str
    agent_name: str
    client_full_name: str
    client_phone: str | None
    client_email: str | None
    inputs: dict[str, Any]
    coverages: list[str]
    premium: Decimal
    breakdown: dict[str, Any]
    issued_at: datetime
    valid_until: datetime


class CompareRequest(BaseModel):
    """POST /quotes/compare. Tokens travel in the body so they stay out of URLs and logs.
    Count, duplicates and token format are checked by the service (404/410/422 rules)."""

    model_config = ConfigDict(extra="forbid")

    tokens: list[Annotated[str, StringConstraints(max_length=100)]] = Field(max_length=10)


class BreakdownLineOut(BaseModel):
    code: str
    label_he: str
    amount: Decimal


class FactorOut(BaseModel):
    code: str
    label_he: str
    value: Decimal


class PreviewResponse(BaseModel):
    product: str
    currency: Literal["ILS"] = "ILS"
    premium: Decimal
    premium_before_rounding: Decimal
    minimum_applied: bool
    breakdown: list[BreakdownLineOut]
    factors: list[FactorOut]


class FieldOption(BaseModel):
    value: str
    label_he: str


class ProductField(BaseModel):
    name: str
    label_he: str
    type: Literal["integer", "money", "boolean", "enum"]
    required: bool
    min: int | None
    max: int | None
    options: list[FieldOption] | None


class CoverageOut(BaseModel):
    code: str
    label_he: str
    price_rule_he: str


class ProductOut(BaseModel):
    code: str
    label_he: str
    fields: list[ProductField]
    coverages: list[CoverageOut]


class ProductsResponse(BaseModel):
    min_premium: Decimal
    products: list[ProductOut]
