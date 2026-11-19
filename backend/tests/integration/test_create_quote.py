from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db.models import Quote, QuoteCounter
from app.main import create_app
from tests.conftest import FIXED_NOW, FakeRenderer

CAR = {
    "product": "car",
    "inputs": {
        "driver_age": 23,
        "license_years": 1,
        "car_value": 100_000,
        "claims_last_3_years": 0,
        "coverage_type": "comprehensive",
    },
    "coverages": ["glass", "towing"],
    "agent_name": "  דנה כהן ",
    "client_full_name": "ישראל ישראלי",
    "client_phone": "050-1234567",
    "client_email": "",
}
APARTMENT = {
    "product": "apartment",
    "inputs": {"structure_value": 100_000, "contents_value": 0, "floor": 0, "has_alarm": True},
    "coverages": [],
    "agent_name": "דנה",
    "client_full_name": "לקוח",
}


@pytest.fixture
def env(tmp_path):
    renderer = FakeRenderer()
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'db' / 'test.db'}",
        storage_dir=tmp_path / "storage",
        frontend_origin="http://localhost:5173",
    )
    app = create_app(settings, renderer=renderer, clock=lambda: FIXED_NOW)
    with TestClient(app, raise_server_exceptions=False) as client:
        service = app.state.quote_service
        yield client, service, renderer, settings


def rows(service, model):
    with service.sessions() as session:
        return session.query(model).all()


def test_create_quote_persists_and_writes_pdf(env):
    client, service, renderer, settings = env
    response = client.post("/api/quotes", json=CAR)

    assert response.status_code == 201
    body = response.json()
    download_url = body.pop("download_url")
    assert body == {
        "quote_number": "Q-2026-000001",
        "product": "car",
        "premium": "7175",  # 3500 x 1.5 x 1.3 = 6825, + 200 + 150
        "issued_at": "2026-11-19T08:30:00Z",
        "valid_until": "2026-12-19T08:30:00Z",
    }

    [quote] = rows(service, Quote)
    assert download_url == f"/api/quotes/download/{quote.download_token}"
    assert quote.agent_name == "דנה כהן"  # trimmed
    assert quote.client_email is None  # blank -> None
    assert quote.coverages == ["towing", "glass"]  # catalog order
    assert str(quote.premium) == "7175"
    assert quote.issued_at == FIXED_NOW
    assert len(quote.download_token) >= 43
    assert quote.pdf_filename == f"{quote.id}.pdf"
    assert sum_lines(quote.breakdown) == quote.breakdown["premium_before_rounding"]

    pdf = settings.storage_dir / quote.pdf_filename
    assert pdf.read_bytes().startswith(b"%PDF")
    assert renderer.documents[0].quote_number == "Q-2026-000001"


def sum_lines(breakdown):
    from decimal import Decimal

    return str(sum((Decimal(line["amount"]) for line in breakdown["lines"]), Decimal("0")))


def test_numbers_are_sequential(env):
    client, *_ = env
    numbers = [client.post("/api/quotes", json=p).json()["quote_number"] for p in (CAR, APARTMENT)]
    assert numbers == ["Q-2026-000001", "Q-2026-000002"]


def test_pdf_content_comes_from_the_request(env):
    client, _service, renderer, _ = env
    client.post("/api/quotes", json=APARTMENT)
    document = renderer.documents[0]
    assert document.product_label_he == "ביטוח דירה"
    assert document.minimum_applied is True
    assert ("פקטור קומה", "1.1") in [(f.label_he, str(f.value)) for f in document.factors]
    fields = {f.label_he: f.value for f in document.fields}
    assert fields["שווי המבנה (₪)"] == "100,000 ₪"
    assert fields["יש אזעקה"] == "כן"


def test_render_failure_rolls_everything_back(env):
    client, service, renderer, settings = env
    renderer.fail_with = RuntimeError("boom")

    response = client.post("/api/quotes", json=CAR)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert rows(service, Quote) == []
    assert rows(service, QuoteCounter) == []
    assert list(settings.storage_dir.iterdir()) == []

    renderer.fail_with = None
    assert client.post("/api/quotes", json=CAR).json()["quote_number"] == "Q-2026-000001"


def test_storage_failure_rolls_back(env, monkeypatch):
    client, service, _renderer, settings = env

    def broken_save(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(service.storage, "save", broken_save)
    assert client.post("/api/quotes", json=CAR).status_code == 500
    assert rows(service, Quote) == []
    assert list(settings.storage_dir.iterdir()) == []


def test_pdf_unavailable_is_503(env):
    from app.services.pdf_renderer import PdfUnavailableError

    client, _service, renderer, _ = env
    renderer.fail_with = PdfUnavailableError("no pango")
    response = client.post("/api/quotes", json=CAR)
    assert response.status_code == 503
    assert response.json() == {
        "error": {"code": "pdf_unavailable", "message_he": "יצירת PDF אינה זמינה בשרת זה"}
    }


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"agent_name": ""}, "שם הסוכן: שדה חובה"),
        ({"agent_name": "   "}, "שם הסוכן: שדה חובה"),
        ({"client_full_name": "א" * 101}, "שם הלקוח: אורך מקסימלי 100 תווים"),
        ({"client_phone": "abc"}, "טלפון: פורמט לא תקין"),
        ({"client_email": "no-at-sign"}, 'דוא"ל: פורמט לא תקין'),
        ({"client_email": "a@b.co" + "m" * 100}, 'דוא"ל: אורך מקסימלי 100 תווים'),
    ],
)
def test_party_validation_in_hebrew(env, overrides, message):
    client, service, *_ = env
    response = client.post("/api/quotes", json={**CAR, **overrides})
    assert response.status_code == 422
    assert response.json()["error"]["message_he"] == message
    assert rows(service, Quote) == []


def test_missing_parties(env):
    client, *_ = env
    payload = {k: v for k, v in CAR.items() if k not in ("agent_name", "client_full_name")}
    message = client.post("/api/quotes", json=payload).json()["error"]["message_he"]
    assert message == "שם הסוכן: שדה חובה; שם הלקוח: שדה חובה"


def test_no_id_or_financial_fields_accepted(env):
    client, *_ = env
    response = client.post("/api/quotes", json={**CAR, "id_number": "123456789"})
    assert response.status_code == 422


def test_get_metadata_without_token(env):
    client, *_ = env
    client.post("/api/quotes", json=CAR)
    response = client.get("/api/quotes/Q-2026-000001")
    assert response.status_code == 200
    body = response.json()
    assert body["quote_number"] == "Q-2026-000001"
    assert body["premium"] == "7175"
    assert body["client_full_name"] == "ישראל ישראלי"
    for secret in ("download_token", "id", "pdf_filename"):
        assert secret not in body


@pytest.mark.parametrize(
    "number", ["Q-2026-000099", "Q-2026-1", "../../etc/passwd", "q-2026-000001", "Q-2026-000001x"]
)
def test_get_metadata_unknown_or_malformed_is_404(env, number):
    client, *_ = env
    client.post("/api/quotes", json=CAR)
    response = client.get(f"/api/quotes/{number}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_year_rollover_uses_israel_time(tmp_path):
    clock_value = datetime(2026, 12, 31, 23, 0, tzinfo=UTC)  # 01:00 on 1/1/2027 in Israel
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 't.db'}",
        storage_dir=tmp_path / "s",
        frontend_origin="http://localhost:5173",
    )
    app = create_app(settings, renderer=FakeRenderer(), clock=lambda: clock_value)
    with TestClient(app) as client:
        assert client.post("/api/quotes", json=CAR).json()["quote_number"] == "Q-2027-000001"
