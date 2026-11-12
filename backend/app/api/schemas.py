"""Request/response contracts for /api (SPEC section 5)."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

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
