"""Shared building blocks for the premium engine.

All money math is done in Decimal. Rounding happens exactly once, at the end.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

MIN_PREMIUM = Decimal("500")
_WHOLE_SHEKEL = Decimal("1")


@dataclass(frozen=True)
class BreakdownLine:
    """One additive line of the calculation. All lines sum to the pre-rounding premium."""

    code: str
    label_he: str
    amount: Decimal


@dataclass(frozen=True)
class Factor:
    """A multiplicative factor, shown for information only (its effect is in a breakdown line)."""

    code: str
    label_he: str
    value: Decimal


@dataclass(frozen=True)
class Coverage:
    code: str
    label_he: str
    price_rule_he: str


@dataclass(frozen=True)
class PricingResult:
    premium: Decimal
    premium_before_rounding: Decimal
    minimum_applied: bool
    breakdown: tuple[BreakdownLine, ...]
    factors: tuple[Factor, ...]


class InvalidCoverageError(ValueError):
    pass


def round_shekel(amount: Decimal) -> Decimal:
    """Round to a whole shekel, half up (0.5 -> 1)."""
    if not isinstance(amount, Decimal):
        raise TypeError("amount must be a Decimal")
    return amount.quantize(_WHOLE_SHEKEL, rounding=ROUND_HALF_UP)


def factors_adjustment(subtotal: Decimal, factors: Iterable[Factor]) -> BreakdownLine:
    """The amount that applying all factors adds to (or removes from) the subtotal."""
    multiplier = Decimal("1")
    for factor in factors:
        multiplier *= factor.value
    return BreakdownLine(
        code="factors_adjustment",
        label_he="התאמה לפי פקטורים",
        amount=subtotal * multiplier - subtotal,
    )


def check_coverages(selected: Iterable[str], allowed: dict[str, Coverage]) -> list[str]:
    """Return the selected coverage codes in catalog order; reject unknown or duplicate codes."""
    selected = list(selected)
    unknown = [code for code in selected if code not in allowed]
    if unknown:
        raise InvalidCoverageError(f"unknown coverage: {', '.join(unknown)}")
    if len(set(selected)) != len(selected):
        raise InvalidCoverageError("duplicate coverage")
    return [code for code in allowed if code in selected]


def finalize(lines: list[BreakdownLine], factors: tuple[Factor, ...]) -> PricingResult:
    """Apply the minimum premium (as its own line) and round once."""
    total = sum((line.amount for line in lines), Decimal("0"))
    minimum_applied = total < MIN_PREMIUM
    if minimum_applied:
        lines = [
            *lines,
            BreakdownLine(
                code="minimum_adjustment",
                label_he="השלמה לפרמיה מינימלית",
                amount=MIN_PREMIUM - total,
            ),
        ]
        total = MIN_PREMIUM
    return PricingResult(
        premium=round_shekel(total),
        premium_before_rounding=total,
        minimum_applied=minimum_applied,
        breakdown=tuple(lines),
        factors=factors,
    )
