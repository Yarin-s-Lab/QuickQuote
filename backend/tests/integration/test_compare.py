"""POST /api/quotes/compare (SPEC section 5, bonus section 10)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.quote_service import COMPARE_COUNT_HE, COMPARE_PRODUCTS_HE, COMPARE_SAME_HE
from tests.conftest import FIXED_NOW, FakeRenderer


def car(age: int, *, coverages=(), client="ישראל ישראלי"):
    return {
        "product": "car",
        "inputs": {
            "driver_age": age,
            "license_years": 10,
            "car_value": 100_000,
            "claims_last_3_years": 0,
            "coverage_type": "comprehensive",
        },
        "coverages": list(coverages),
        "agent_name": "דנה כהן",
        "client_full_name": client,
    }


APARTMENT = {
    "product": "apartment",
    "inputs": {"structure_value": 1_000_000, "contents_value": 0, "floor": 2, "has_alarm": False},
    "coverages": [],
    "agent_name": "דנה כהן",
    "client_full_name": "ישראל ישראלי",
}


class Clock:
    def __init__(self) -> None:
        self.now = FIXED_NOW

    def __call__(self):
        return self.now


@pytest.fixture
def env(tmp_path):
    clock = Clock()
    renderer = FakeRenderer()
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
        storage_dir=tmp_path / "storage",
        frontend_origin="http://localhost:5173",
    )
    app = create_app(settings, renderer=renderer, clock=clock)
    with TestClient(app) as client:

        def create(payload):
            body = client.post("/api/quotes", json=payload).json()
            return body["download_url"].rsplit("/", 1)[1], body["quote_number"]

        yield client, create, clock, tmp_path


def compare(client, tokens):
    return client.post("/api/quotes/compare", json={"tokens": tokens})


def assert_error(response, status, code, message=None):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["error"]["code"] == code
    if message is not None:
        assert body["error"]["message_he"] == message


def test_compare_returns_pdf_with_both_numbers(env):
    client, create, _clock, _ = env
    token_a, number_a = create(car(23))  # 3500 x 1.5 = 5250
    token_b, number_b = create(car(40, coverages=["glass"]))  # 3500 + 200 = 3700

    response = compare(client, [token_a, token_b])

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="compare-{number_a}-{number_b}.pdf"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.content.startswith(b"%PDF")
    html = response.content.decode("utf-8")  # FakeRenderer embeds the HTML
    assert number_a in html and number_b in html
    assert "הזולה יותר: הצעה ב'" in html
    assert "1,550 ₪" in html  # 5250 - 3700


def test_order_follows_the_request(env):
    client, create, _clock, _ = env
    token_a, number_a = create(car(23))
    token_b, number_b = create(car(40))
    response = compare(client, [token_b, token_a])
    assert (
        f'filename="compare-{number_b}-{number_a}.pdf"' in response.headers["content-disposition"]
    )


def test_equal_premiums(env):
    client, create, _clock, _ = env
    token_a, _ = create(car(40, client="אבי"))
    token_b, _ = create(car(40, client="בני"))
    html = compare(client, [token_a, token_b]).content.decode()
    assert "הפרמיות זהות" in html


def test_comparison_pdf_is_not_stored(env):
    client, create, _clock, tmp_path = env
    token_a, _ = create(car(23))
    token_b, _ = create(car(40))
    before = sorted(p.name for p in (tmp_path / "storage").iterdir())
    assert compare(client, [token_a, token_b]).status_code == 200
    assert sorted(p.name for p in (tmp_path / "storage").iterdir()) == before


@pytest.mark.parametrize("count", [0, 1, 3])
def test_wrong_number_of_tokens_is_422(env, count):
    client, create, _clock, _ = env
    tokens = [create(car(30 + i))[0] for i in range(count)]
    assert_error(compare(client, tokens), 422, "validation_error", COMPARE_COUNT_HE)


def test_same_token_twice_is_422(env):
    client, create, _clock, _ = env
    token, _ = create(car(23))
    assert_error(compare(client, [token, token]), 422, "validation_error", COMPARE_SAME_HE)


def test_different_products_is_422(env):
    client, create, _clock, _ = env
    token_car, _ = create(car(23))
    token_apartment, _ = create(APARTMENT)
    assert_error(
        compare(client, [token_car, token_apartment]), 422, "validation_error", COMPARE_PRODUCTS_HE
    )


@pytest.mark.parametrize("bad", ["A" * 43, "A" * 42, "short", ""])
def test_unknown_or_malformed_token_is_404(env, bad):
    client, create, _clock, _ = env
    token, _ = create(car(23))
    assert_error(compare(client, [token, bad]), 404, "not_found", "ההצעה לא נמצאה")
    assert_error(compare(client, [bad, token]), 404, "not_found")


def test_expired_quote_is_410(env):
    client, create, clock, _ = env
    old, _ = create(car(23))
    clock.now = FIXED_NOW + timedelta(days=20)
    fresh, _ = create(car(40))
    clock.now = FIXED_NOW + timedelta(days=30, seconds=1)  # only `old` has expired
    assert_error(compare(client, [old, fresh]), 410, "quote_expired")
    assert_error(compare(client, [fresh, old]), 410, "quote_expired")


def test_expiry_boundary_is_inclusive(env):
    client, create, clock, _ = env
    token_a, _ = create(car(23))
    token_b, _ = create(car(40))
    clock.now = FIXED_NOW + timedelta(days=30)
    assert compare(client, [token_a, token_b]).status_code == 200


def test_precedence_404_before_410_before_product_mismatch(env):
    """A caller with one valid token learns nothing about the other quote."""
    client, create, clock, _ = env
    expired_car, _ = create(car(23))
    clock.now = FIXED_NOW + timedelta(days=20)
    fresh_apartment, _ = create(APARTMENT)
    clock.now = FIXED_NOW + timedelta(days=31)
    # unknown + expired -> 404
    assert_error(compare(client, ["A" * 43, expired_car]), 404, "not_found")
    # expired + other product -> 410 (expiry checked before product)
    assert_error(compare(client, [expired_car, fresh_apartment]), 410, "quote_expired")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"tokens": "abc"},
        {"tokens": [1, 2]},
        {"tokens": ["a" * 101, "b"]},
        {"tokens": ["a"] * 11},
        {"tokens": ["a", "b"], "extra": 1},
    ],
)
def test_malformed_body_is_422(env, body):
    client, *_ = env
    response = client.post("/api/quotes/compare", json=body)
    assert_error(response, 422, "validation_error")


def test_tokens_are_not_echoed_in_errors(env):
    client, create, _clock, _ = env
    token, _ = create(car(23))
    response = compare(client, [token, "A" * 43])
    assert token not in response.text


def test_get_is_not_allowed(env):
    client, *_ = env
    assert client.get("/api/quotes/compare").status_code in (404, 405)
