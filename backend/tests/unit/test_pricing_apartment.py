from decimal import Decimal
from itertools import product

import pytest
from pydantic import ValidationError

from app.domain.pricing.apartment import ApartmentInputs, price_apartment
from app.domain.pricing.common import InvalidCoverageError

BASELINE = {"structure_value": 1_000_000, "contents_value": 0, "floor": 3, "has_alarm": False}
# baseline: 1,000,000 x 0.1% = 1000, all factors 1.0


def apt(**overrides):
    return ApartmentInputs(**{**BASELINE, **overrides})


def factor(result, code) -> Decimal:
    return next(f.value for f in result.factors if f.code == code)


def test_baseline():
    result = price_apartment(apt(), [])
    assert result.premium == Decimal("1000")
    assert not result.minimum_applied


def test_contents_part():
    # 1000 + 200,000 x 0.3% = 1600
    assert price_apartment(apt(contents_value=200_000), []).premium == Decimal("1600")


def test_contents_only():
    result = price_apartment(apt(structure_value=0, contents_value=500_000), [])
    assert result.premium == Decimal("1500")


@pytest.mark.parametrize(
    ("floor", "expected_factor", "expected_premium"),
    [(0, "1.1", "1100"), (1, "1.0", "1000"), (60, "1.0", "1000")],
)
def test_floor_factor_threshold(floor, expected_factor, expected_premium):
    result = price_apartment(apt(floor=floor), [])
    assert factor(result, "floor_factor") == Decimal(expected_factor)
    assert result.premium == Decimal(expected_premium)


@pytest.mark.parametrize(
    ("has_alarm", "expected_factor", "expected_premium"),
    [(True, "0.9", "900"), (False, "1.0", "1000")],
)
def test_alarm_factor(has_alarm, expected_factor, expected_premium):
    result = price_apartment(apt(has_alarm=has_alarm), [])
    assert factor(result, "alarm_factor") == Decimal(expected_factor)
    assert result.premium == Decimal(expected_premium)


def test_floor_and_alarm_combined():
    assert price_apartment(apt(floor=0, has_alarm=True), []).premium == Decimal("990")


def test_earthquake_is_percent_of_structure():
    # 1000 + 1,000,000 x 0.05% = 1500
    assert price_apartment(apt(), ["earthquake"]).premium == Decimal("1500")


def test_earthquake_with_zero_structure_is_zero():
    result = price_apartment(apt(structure_value=0, contents_value=500_000), ["earthquake"])
    line = next(line for line in result.breakdown if line.code == "earthquake")
    assert line.amount == Decimal("0")
    assert result.premium == Decimal("1500")


@pytest.mark.parametrize(("coverage", "price"), [("plumbing", "120"), ("jewelry", "300")])
def test_fixed_addons(coverage, price):
    assert price_apartment(apt(), [coverage]).premium == Decimal("1000") + Decimal(price)


def test_addons_not_multiplied_by_factors():
    # 1000 x 0.9 + 500 + 120 + 300
    result = price_apartment(apt(has_alarm=True), ["earthquake", "plumbing", "jewelry"])
    assert result.premium == Decimal("1820")


def test_minimum_premium_enforced_with_breakdown_line():
    result = price_apartment(apt(structure_value=100_000), [])
    assert result.premium == Decimal("500")
    assert result.minimum_applied
    line = result.breakdown[-1]
    assert line.code == "minimum_adjustment"
    assert line.amount == Decimal("400")


def test_minimum_counts_addons():
    # 100 + 300 + 120 = 520 >= 500, so no minimum
    result = price_apartment(apt(structure_value=100_000), ["jewelry", "plumbing"])
    assert result.premium == Decimal("520")
    assert not result.minimum_applied


def test_minimum_with_half_below():
    # 499.5 is below the minimum, even though it would round to 500
    result = price_apartment(apt(structure_value=499_500), [])
    assert result.minimum_applied
    assert result.premium == Decimal("500")


@pytest.mark.parametrize(
    ("structure", "before", "after"),
    [(500_500, "500.5", "501"), (500_490, "500.49", "500"), (1_234_500, "1234.5", "1235")],
)
def test_rounding_half_up(structure, before, after):
    result = price_apartment(apt(structure_value=structure), [])
    assert result.premium_before_rounding == Decimal(before)
    assert result.premium == Decimal(after)
    assert not result.minimum_applied


@pytest.mark.parametrize(
    "overrides",
    [
        {"structure_value": -1},
        {"structure_value": 5_000_001},
        {"contents_value": -1},
        {"contents_value": 2_000_001},
        {"floor": -1},
        {"floor": 61},
        {"has_alarm": "yes"},
        {"has_alarm": 1},
        {"structure_value": 0, "contents_value": 0},
    ],
)
def test_invalid_input_rejected(overrides):
    with pytest.raises(ValidationError):
        apt(**overrides)


def test_boundaries_accepted():
    apt(structure_value=5_000_000, contents_value=2_000_000, floor=60)
    apt(structure_value=0, contents_value=1, floor=0)


@pytest.mark.parametrize("coverages", [["towing"], ["jewelry", "jewelry"]])
def test_invalid_coverages_rejected(coverages):
    with pytest.raises(InvalidCoverageError):
        price_apartment(apt(), coverages)


@pytest.mark.parametrize(
    ("structure", "contents", "floor", "alarm", "coverages"),
    [
        combo
        for combo in product(
            [0, 1, 100_000, 499_500, 1_234_567, 5_000_000],
            [0, 333, 2_000_000],
            [0, 1],
            [True, False],
            [(), ("earthquake", "plumbing", "jewelry")],
        )
        if combo[0] or combo[1]  # both zero is rejected input
    ],
)
def test_breakdown_sums_exactly_to_premium_before_rounding(
    structure, contents, floor, alarm, coverages
):
    result = price_apartment(
        ApartmentInputs(
            structure_value=structure, contents_value=contents, floor=floor, has_alarm=alarm
        ),
        coverages,
    )
    total = sum((line.amount for line in result.breakdown), Decimal("0"))
    assert total == result.premium_before_rounding
    assert result.premium >= Decimal("500")
