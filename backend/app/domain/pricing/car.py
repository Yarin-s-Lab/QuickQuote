"""Car premium (demo formula, SPEC section 4)."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import (
    BreakdownLine,
    Coverage,
    Factor,
    PricingResult,
    check_coverages,
    factors_adjustment,
    finalize,
)

CoverageType = Literal["comprehensive", "third_party"]
CarCoverageCode = Literal["towing", "glass", "replacement_car"]

COVERAGE_TYPE_LABELS_HE: dict[str, str] = {
    "comprehensive": "מקיף",
    "third_party": "צד ג'",
}

BASE: dict[str, Decimal] = {
    "comprehensive": Decimal("1500"),
    "third_party": Decimal("900"),
}
VALUE_RATE = Decimal("0.02")

ADDON_PRICES: dict[str, Decimal] = {
    "towing": Decimal("150"),
    "glass": Decimal("200"),
    "replacement_car": Decimal("250"),
}

CAR_COVERAGES: dict[str, Coverage] = {
    "towing": Coverage("towing", "גרירה", "+150 ₪"),
    "glass": Coverage("glass", "שמשות", "+200 ₪"),
    "replacement_car": Coverage("replacement_car", "רכב חלופי", "+250 ₪"),
}


class CarInputs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    driver_age: int = Field(ge=17, le=90, strict=True, title="גיל הנהג")
    license_years: int = Field(ge=0, le=70, strict=True, title="ותק נהיגה (שנים)")
    car_value: int = Field(
        ge=10_000,
        le=1_000_000,
        strict=True,
        title="שווי הרכב (₪)",
        json_schema_extra={"unit": "ILS"},
    )
    claims_last_3_years: int = Field(ge=0, le=5, strict=True, title="תביעות ב-3 השנים האחרונות")
    coverage_type: CoverageType = Field(
        title="סוג כיסוי",
        json_schema_extra={"options_he": COVERAGE_TYPE_LABELS_HE},
    )


def age_factor(driver_age: int) -> Decimal:
    if driver_age < 24:
        return Decimal("1.5")
    if driver_age <= 29:
        return Decimal("1.2")
    return Decimal("1.0")


def license_factor(license_years: int) -> Decimal:
    return Decimal("1.3") if license_years < 2 else Decimal("1.0")


def claims_factor(claims: int) -> Decimal:
    return Decimal("1") + Decimal("0.15") * claims


def price_car(inputs: CarInputs, coverages: Iterable[str]) -> PricingResult:
    selected = check_coverages(coverages, CAR_COVERAGES)

    base = BASE[inputs.coverage_type]
    lines = [
        BreakdownLine(
            "base", f"פרמיית בסיס ({COVERAGE_TYPE_LABELS_HE[inputs.coverage_type]})", base
        )
    ]
    subtotal = base

    if inputs.coverage_type == "comprehensive":
        value_part = Decimal(inputs.car_value) * VALUE_RATE
        lines.append(BreakdownLine("value_part", "רכיב שווי הרכב (2%)", value_part))
        subtotal += value_part

    factors = (
        Factor("age_factor", "פקטור גיל", age_factor(inputs.driver_age)),
        Factor("license_factor", "פקטור ותק", license_factor(inputs.license_years)),
        Factor("claims_factor", "פקטור תביעות", claims_factor(inputs.claims_last_3_years)),
    )
    lines.append(factors_adjustment(subtotal, factors))

    for code in selected:
        lines.append(BreakdownLine(code, CAR_COVERAGES[code].label_he, ADDON_PRICES[code]))

    return finalize(lines, factors)
