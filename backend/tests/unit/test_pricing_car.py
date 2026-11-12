from decimal import Decimal
from itertools import product

import pytest
from pydantic import ValidationError

from app.domain.pricing.car import CarInputs, price_car
from app.domain.pricing.common import InvalidCoverageError

BASELINE = {
    "driver_age": 40,
    "license_years": 10,
    "car_value": 100_000,
    "claims_last_3_years": 0,
    "coverage_type": "comprehensive",
}
# comprehensive baseline: 1500 + 100,000 x 2% = 3500, all factors 1.0


def car(**overrides):
    return CarInputs(**{**BASELINE, **overrides})


def premium(coverages=(), **overrides) -> Decimal:
    return price_car(car(**overrides), coverages).premium


def factor(result, code) -> Decimal:
    return next(f.value for f in result.factors if f.code == code)


def test_baseline_comprehensive():
    result = price_car(car(), [])
    assert result.premium == Decimal("3500")
    assert [line.code for line in result.breakdown] == ["base", "value_part", "factors_adjustment"]


def test_third_party_has_no_value_part():
    result = price_car(car(coverage_type="third_party", car_value=1_000_000), [])
    assert result.premium == Decimal("900")
    assert "value_part" not in [line.code for line in result.breakdown]


@pytest.mark.parametrize(
    ("age", "expected_factor", "expected_premium"),
    [
        (17, "1.5", "5250"),
        (23, "1.5", "5250"),
        (24, "1.2", "4200"),
        (29, "1.2", "4200"),
        (30, "1.0", "3500"),
        (90, "1.0", "3500"),
    ],
)
def test_age_factor_thresholds(age, expected_factor, expected_premium):
    result = price_car(car(driver_age=age), [])
    assert factor(result, "age_factor") == Decimal(expected_factor)
    assert result.premium == Decimal(expected_premium)


@pytest.mark.parametrize(
    ("years", "expected_factor", "expected_premium"),
    [(0, "1.3", "4550"), (1, "1.3", "4550"), (2, "1.0", "3500"), (70, "1.0", "3500")],
)
def test_license_factor_thresholds(years, expected_factor, expected_premium):
    result = price_car(car(license_years=years), [])
    assert factor(result, "license_factor") == Decimal(expected_factor)
    assert result.premium == Decimal(expected_premium)


@pytest.mark.parametrize(
    ("claims", "expected_factor", "expected_premium"),
    [(0, "1.00", "3500"), (1, "1.15", "4025"), (2, "1.30", "4550"), (5, "1.75", "6125")],
)
def test_claims_factor(claims, expected_factor, expected_premium):
    result = price_car(car(claims_last_3_years=claims), [])
    assert factor(result, "claims_factor") == Decimal(expected_factor)
    assert result.premium == Decimal(expected_premium)


def test_factors_combine_multiplicatively():
    # 3500 x 1.5 x 1.3 x 1.15 = 7848.75 -> 7849
    result = price_car(car(driver_age=20, license_years=1, claims_last_3_years=1), [])
    assert result.premium_before_rounding == Decimal("7848.75")
    assert result.premium == Decimal("7849")


@pytest.mark.parametrize(
    ("coverage", "price"), [("towing", "150"), ("glass", "200"), ("replacement_car", "250")]
)
def test_each_addon(coverage, price):
    assert premium([coverage]) == Decimal("3500") + Decimal(price)


def test_addons_are_not_multiplied_by_factors():
    # (3500 x 1.5) + 150 + 200 + 250
    assert premium(["towing", "glass", "replacement_car"], driver_age=20) == Decimal("5850")


def test_addons_on_third_party():
    assert premium(["towing", "glass", "replacement_car"], coverage_type="third_party") == Decimal(
        "1500"
    )


def test_rounding_exact_half_goes_up():
    # 1500 + 10,025 x 2% = 1700.5
    result = price_car(car(car_value=10_025), [])
    assert result.premium_before_rounding == Decimal("1700.5")
    assert result.premium == Decimal("1701")


@pytest.mark.parametrize(
    "overrides",
    [
        {"driver_age": 16},
        {"driver_age": 91},
        {"license_years": -1},
        {"license_years": 71},
        {"car_value": 9_999},
        {"car_value": 1_000_001},
        {"claims_last_3_years": -1},
        {"claims_last_3_years": 6},
        {"coverage_type": "full"},
        {"car_value": 100_000.5},
        {"driver_age": "40"},
        {"unexpected": 1},
    ],
)
def test_out_of_range_input_rejected(overrides):
    with pytest.raises(ValidationError):
        car(**overrides)


def test_boundaries_accepted():
    car(driver_age=17, license_years=0, car_value=10_000, claims_last_3_years=0)
    car(driver_age=90, license_years=70, car_value=1_000_000, claims_last_3_years=5)


@pytest.mark.parametrize("coverages", [["sunroof"], ["glass", "glass"], ["earthquake"]])
def test_invalid_coverages_rejected(coverages):
    with pytest.raises(InvalidCoverageError):
        price_car(car(), coverages)


@pytest.mark.parametrize(
    ("age", "years", "value", "claims", "ctype", "coverages"),
    list(
        product(
            [17, 23, 24, 29, 30, 90],
            [0, 1, 2],
            [10_000, 10_025, 333_333, 1_000_000],
            [0, 3, 5],
            ["comprehensive", "third_party"],
            [(), ("towing", "glass", "replacement_car")],
        )
    ),
)
def test_breakdown_sums_exactly_to_premium_before_rounding(
    age, years, value, claims, ctype, coverages
):
    result = price_car(
        CarInputs(
            driver_age=age,
            license_years=years,
            car_value=value,
            claims_last_3_years=claims,
            coverage_type=ctype,
        ),
        coverages,
    )
    total = sum((line.amount for line in result.breakdown), Decimal("0"))
    assert total == result.premium_before_rounding
    assert all(isinstance(line.amount, Decimal) for line in result.breakdown)
    assert result.premium == result.premium_before_rounding.quantize(Decimal("1"), "ROUND_HALF_UP")
