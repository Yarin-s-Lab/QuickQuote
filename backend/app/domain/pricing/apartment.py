"""Apartment premium (demo formula, SPEC section 4)."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import (
    BreakdownLine,
    Coverage,
    Factor,
    PricingResult,
    check_coverages,
    factors_adjustment,
    finalize,
)

ApartmentCoverageCode = Literal["earthquake", "plumbing", "jewelry"]

STRUCTURE_RATE = Decimal("0.001")
CONTENTS_RATE = Decimal("0.003")
EARTHQUAKE_RATE = Decimal("0.0005")
PLUMBING_PRICE = Decimal("120")
JEWELRY_PRICE = Decimal("300")

APARTMENT_COVERAGES: dict[str, Coverage] = {
    "earthquake": Coverage("earthquake", "רעידת אדמה", "0.05% משווי המבנה"),
    "plumbing": Coverage("plumbing", "צנרת", "+120 ₪"),
    "jewelry": Coverage("jewelry", "תכשיטים", "+300 ₪"),
}

AT_LEAST_ONE_VALUE_HE = "יש להזין שווי מבנה או שווי תכולה גדול מ-0"


class ApartmentInputs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    structure_value: int = Field(
        ge=0, le=5_000_000, strict=True, title="שווי המבנה (₪)", json_schema_extra={"unit": "ILS"}
    )
    contents_value: int = Field(
        ge=0, le=2_000_000, strict=True, title="שווי התכולה (₪)", json_schema_extra={"unit": "ILS"}
    )
    floor: int = Field(ge=0, le=60, strict=True, title="קומה")
    has_alarm: bool = Field(strict=True, title="יש אזעקה")

    @model_validator(mode="after")
    def _at_least_one_value(self) -> Self:
        if self.structure_value == 0 and self.contents_value == 0:
            raise ValueError(AT_LEAST_ONE_VALUE_HE)
        return self


def floor_factor(floor: int) -> Decimal:
    return Decimal("1.1") if floor == 0 else Decimal("1.0")


def alarm_factor(has_alarm: bool) -> Decimal:
    return Decimal("0.9") if has_alarm else Decimal("1.0")


def price_apartment(inputs: ApartmentInputs, coverages: Iterable[str]) -> PricingResult:
    selected = check_coverages(coverages, APARTMENT_COVERAGES)

    structure_part = Decimal(inputs.structure_value) * STRUCTURE_RATE
    contents_part = Decimal(inputs.contents_value) * CONTENTS_RATE
    lines = [
        BreakdownLine("structure_part", "רכיב מבנה (0.1%)", structure_part),
        BreakdownLine("contents_part", "רכיב תכולה (0.3%)", contents_part),
    ]
    subtotal = structure_part + contents_part

    factors = (
        Factor("floor_factor", "פקטור קומה", floor_factor(inputs.floor)),
        Factor("alarm_factor", "פקטור אזעקה", alarm_factor(inputs.has_alarm)),
    )
    lines.append(factors_adjustment(subtotal, factors))

    addon_prices = {
        "earthquake": Decimal(inputs.structure_value) * EARTHQUAKE_RATE,
        "plumbing": PLUMBING_PRICE,
        "jewelry": JEWELRY_PRICE,
    }
    for code in selected:
        lines.append(BreakdownLine(code, APARTMENT_COVERAGES[code].label_he, addon_prices[code]))

    return finalize(lines, factors)
