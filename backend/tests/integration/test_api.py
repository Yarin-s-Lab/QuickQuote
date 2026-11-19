from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

# Explicit settings: independent of FRONTEND_ORIGIN etc. in the environment (e.g. compose).
app = create_app(
    Settings(
        database_url="sqlite:///:memory:",
        storage_dir=Path("unused-storage"),
        frontend_origin="http://localhost:5173",
    )
)
client = TestClient(app)

CAR = {
    "product": "car",
    "inputs": {
        "driver_age": 23,
        "license_years": 1,
        "car_value": 100_000,
        "claims_last_3_years": 0,
        "coverage_type": "comprehensive",
    },
    "coverages": ["towing"],
}
APARTMENT = {
    "product": "apartment",
    "inputs": {"structure_value": 100_000, "contents_value": 0, "floor": 2, "has_alarm": False},
    "coverages": [],
}


def assert_error_shape(response, status, code="validation_error"):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert body["error"]["message_he"]
    return body["error"]["message_he"]


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/api/health", "/api/products", "/api/nope"])
def test_nosniff_on_every_api_response(path):
    response = client.get(path)
    assert response.headers.get_list("x-content-type-options") == ["nosniff"]


def test_products_lists_both_products_with_fields_and_coverages():
    body = client.get("/api/products").json()
    assert body["min_premium"] == "500"
    products = {p["code"]: p for p in body["products"]}
    assert set(products) == {"car", "apartment"}

    car_fields = {f["name"]: f for f in products["car"]["fields"]}
    assert car_fields["driver_age"]["min"] == 17
    assert car_fields["driver_age"]["max"] == 90
    assert car_fields["car_value"]["type"] == "money"
    assert [o["value"] for o in car_fields["coverage_type"]["options"]] == [
        "comprehensive",
        "third_party",
    ]
    assert {c["code"] for c in products["car"]["coverages"]} == {
        "towing",
        "glass",
        "replacement_car",
    }
    apt_fields = {f["name"]: f for f in products["apartment"]["fields"]}
    assert apt_fields["has_alarm"]["type"] == "boolean"
    assert apt_fields["floor"]["max"] == 60


def test_preview_car():
    response = client.post("/api/quotes/preview", json=CAR)
    assert response.status_code == 200
    body = response.json()
    # 3500 x 1.5 x 1.3 + 150 = 6975
    assert body["premium"] == "6975"
    assert body["currency"] == "ILS"
    assert body["minimum_applied"] is False
    assert [line["code"] for line in body["breakdown"]] == [
        "base",
        "value_part",
        "factors_adjustment",
        "towing",
    ]
    assert {f["code"] for f in body["factors"]} == {"age_factor", "license_factor", "claims_factor"}


def test_preview_apartment_minimum():
    body = client.post("/api/quotes/preview", json=APARTMENT).json()
    assert body["premium"] == "500"
    assert body["minimum_applied"] is True
    assert body["breakdown"][-1]["code"] == "minimum_adjustment"


def test_preview_amounts_are_strings_not_floats():
    body = client.post("/api/quotes/preview", json=CAR).json()
    assert all(isinstance(line["amount"], str) for line in body["breakdown"])


def test_out_of_range_returns_hebrew_error():
    payload = {**CAR, "inputs": {**CAR["inputs"], "driver_age": 16}}
    message = assert_error_shape(client.post("/api/quotes/preview", json=payload), 422)
    assert "גיל הנהג" in message
    assert "17" in message


def test_errors_only_mention_the_selected_product():
    payload = {**APARTMENT, "inputs": {**APARTMENT["inputs"], "floor": 61}}
    message = assert_error_shape(client.post("/api/quotes/preview", json=payload), 422)
    assert message == "קומה: הערך חייב להיות לכל היותר 60"


def test_unknown_product_message():
    message = assert_error_shape(
        client.post("/api/quotes/preview", json={"product": "boat", "inputs": {}}), 422
    )
    assert message == "מוצר לא מוכר"


def test_duplicate_coverage_message():
    message = assert_error_shape(
        client.post("/api/quotes/preview", json={**CAR, "coverages": ["glass", "glass"]}), 422
    )
    assert message == "כיסוי נבחר יותר מפעם אחת"


def test_apartment_both_values_zero():
    payload = {**APARTMENT, "inputs": {**APARTMENT["inputs"], "structure_value": 0}}
    message = assert_error_shape(client.post("/api/quotes/preview", json=payload), 422)
    assert "גדול מ-0" in message


@pytest.mark.parametrize(
    "payload",
    [
        {**CAR, "coverages": ["earthquake"]},
        {**CAR, "coverages": ["glass", "glass"]},
        {**CAR, "product": "boat"},
        {"product": "car"},
        {**CAR, "inputs": {**CAR["inputs"], "car_value": "100000"}},
        {**CAR, "agent_name": "x"},
    ],
)
def test_invalid_requests_rejected(payload):
    assert_error_shape(client.post("/api/quotes/preview", json=payload), 422)


def test_malformed_json():
    response = client.post(
        "/api/quotes/preview", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert_error_shape(response, 422)


def test_unknown_route_uses_error_format():
    assert_error_shape(client.get("/api/nope"), 404, code="not_found")


def test_cors_allows_frontend_origin_only():
    allowed = client.options(
        "/api/quotes/preview",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    denied = client.options(
        "/api/quotes/preview",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in denied.headers
