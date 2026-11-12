from decimal import Decimal

import pytest

from app.domain.pricing.common import (
    MIN_PREMIUM,
    BreakdownLine,
    Factor,
    factors_adjustment,
    finalize,
    round_shekel,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.5", "1"),
        ("500.5", "501"),
        ("1234.5", "1235"),
        ("1234.49", "1234"),
        ("1234.51", "1235"),
        ("1234.4999999", "1234"),
        ("1000", "1000"),
    ],
)
def test_round_shekel_half_up(value, expected):
    assert round_shekel(Decimal(value)) == Decimal(expected)


@pytest.mark.parametrize("bad", [1234.5, 1234, "1234.5"])
def test_round_shekel_rejects_non_decimal(bad):
    with pytest.raises(TypeError):
        round_shekel(bad)


def test_min_premium_value():
    assert Decimal("500") == MIN_PREMIUM


def test_finalize_below_minimum_adds_line():
    result = finalize([BreakdownLine("x", "x", Decimal("123.45"))], ())
    assert result.minimum_applied
    assert result.premium == Decimal("500")
    assert result.breakdown[-1].amount == Decimal("376.55")
    assert sum(line.amount for line in result.breakdown) == result.premium_before_rounding


def test_finalize_exactly_minimum_no_line():
    result = finalize([BreakdownLine("x", "x", Decimal("500"))], ())
    assert not result.minimum_applied
    assert len(result.breakdown) == 1


def test_factors_adjustment_is_exact():
    factors = (Factor("a", "a", Decimal("1.5")), Factor("b", "b", Decimal("1.3")))
    line = factors_adjustment(Decimal("3500"), factors)
    assert line.amount == Decimal("3325")  # 3500 x 1.95 - 3500


def test_factors_adjustment_negative_for_discount():
    line = factors_adjustment(Decimal("1000"), (Factor("a", "a", Decimal("0.9")),))
    assert line.amount == Decimal("-100")
