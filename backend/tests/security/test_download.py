"""SPEC section 7: download only by token; no path ever comes from the request."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from decimal import Decimal
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db.models import Quote
from app.main import create_app
from tests.conftest import FIXED_NOW, FakeRenderer

CAR = {
    "product": "car",
    "inputs": {
        "driver_age": 40,
        "license_years": 10,
        "car_value": 100_000,
        "claims_last_3_years": 0,
        "coverage_type": "comprehensive",
    },
    "coverages": [],
    "agent_name": "דנה",
    "client_full_name": "ישראל",
}


class Clock:
    def __init__(self) -> None:
        self.now = FIXED_NOW

    def __call__(self):
        return self.now


@pytest.fixture
def env(tmp_path):
    clock = Clock()
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
        storage_dir=tmp_path / "storage",
        frontend_origin="http://localhost:5173",
    )
    app = create_app(settings, renderer=FakeRenderer(), clock=clock)
    with TestClient(app) as client:
        created = client.post("/api/quotes", json=CAR).json()
        yield app, client, clock, created, tmp_path


def raw_get(app, raw_path: str) -> tuple[int, dict[str, str], bytes]:
    """Send a request with the path exactly as given (no client-side normalization)."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": unquote(raw_path),
        "raw_path": raw_path.encode("latin-1"),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }
    messages: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(app(scope, receive, send))
    start = next(m for m in messages if m["type"] == "http.response.start")
    headers = {k.decode().lower(): v.decode() for k, v in start["headers"]}
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return start["status"], headers, body


def test_download_by_token(env):
    _app, client, _clock, created, tmp_path = env
    response = client.get(created["download_url"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'attachment; filename="Q-2026-000001.pdf"'
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    # Exactly one value each: duplicates let a browser pick a weaker policy.
    for header in ("referrer-policy", "x-content-type-options", "cache-control"):
        assert len(response.headers.get_list(header)) == 1, header

    [pdf] = (tmp_path / "storage").iterdir()
    assert response.content == pdf.read_bytes()
    assert response.content.startswith(b"%PDF")


def test_download_is_repeatable(env):
    _app, client, _clock, created, _ = env
    first = client.get(created["download_url"]).content
    second = client.get(created["download_url"]).content
    assert first == second


def test_valid_until_inclusive_then_410(env):
    _app, client, clock, created, _ = env
    clock.now = FIXED_NOW + timedelta(days=30)  # exactly valid_until
    assert client.get(created["download_url"]).status_code == 200

    clock.now = FIXED_NOW + timedelta(days=30, seconds=1)
    response = client.get(created["download_url"])
    assert response.status_code == 410
    assert response.json() == {
        "error": {"code": "quote_expired", "message_he": "תוקף ההצעה פג ולא ניתן להוריד אותה"}
    }
    # Metadata stays available after expiry; the token never appears in it.
    meta = client.get(f"/api/quotes/{created['quote_number']}")
    assert meta.status_code == 200
    assert created["download_url"].rsplit("/", 1)[1] not in meta.text


@pytest.mark.parametrize(
    "raw_path",
    [
        "/api/quotes/download/../../etc/passwd",
        "/api/quotes/download/..%2F..%2Fetc%2Fpasswd",
        "/api/quotes/download/%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        "/api/quotes/download/%2e%2e",
        "/api/quotes/download//etc/passwd",
        "/api/quotes/download/%2Fetc%2Fpasswd",
        "/api/quotes/download/C:%5CWindows%5Cwin.ini",
        "/api/quotes/download/token%00.pdf",
        "/api/quotes/download/%00",
        "/api/quotes/download/" + "A" * 42,  # wrong length
        "/api/quotes/download/" + "A" * 44,
        "/api/quotes/download/" + "A" * 43,  # well-formed but unknown
        "/api/quotes/download/" + "A" * 42 + "%2F",
        "/api/quotes/download/",
    ],
)
def test_malicious_or_unknown_tokens_are_404(env, raw_path):
    app, *_ = env
    status, headers, body = raw_get(app, raw_path)
    assert status == 404
    assert headers["content-type"].startswith("application/json")
    assert b"%PDF" not in body


def test_internal_id_and_filename_are_not_tokens(env):
    app, client, _clock, _created, _tmp = env
    meta_service = app.state.quote_service
    with meta_service.sessions() as session:
        quote = session.query(Quote).one()
    for guess in (quote.id, quote.pdf_filename, quote.quote_number):
        assert client.get(f"/api/quotes/download/{guess}").status_code == 404


def test_tampered_row_id_cannot_escape_storage(env):
    """Even a poisoned DB row cannot make the server read outside STORAGE_DIR."""
    app, client, _clock, _created, tmp_path = env
    secret = tmp_path / "secret.pdf"
    secret.write_bytes(b"%PDF-secret")
    token = "B" * 43
    service = app.state.quote_service
    with service.sessions() as session, session.begin():
        session.add(
            Quote(
                id="../secret",
                quote_number="Q-2026-999999",
                product="car",
                agent_name="x",
                client_full_name="y",
                client_phone=None,
                client_email=None,
                inputs={},
                coverages=[],
                premium=Decimal("500"),
                breakdown={},
                issued_at=FIXED_NOW,
                valid_until=FIXED_NOW + timedelta(days=30),
                download_token=token,
                pdf_filename="../secret.pdf",
            )
        )
    response = client.get(f"/api/quotes/download/{token}")
    assert response.status_code == 404
    assert b"secret" not in response.content


def test_missing_file_is_404(env):
    _app, client, _clock, created, tmp_path = env
    for pdf in (tmp_path / "storage").iterdir():
        pdf.unlink()
    assert client.get(created["download_url"]).status_code == 404
