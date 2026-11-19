"""SPEC section 7 applied to POST /api/quotes/compare: tokens only, no paths, no injection."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db.models import Quote
from app.main import create_app
from tests.conftest import FIXED_NOW, FakeRenderer


def car(client_name: str, agent_name: str = "דנה כהן", age: int = 30):
    return {
        "product": "car",
        "inputs": {
            "driver_age": age,
            "license_years": 10,
            "car_value": 100_000,
            "claims_last_3_years": 0,
            "coverage_type": "comprehensive",
        },
        "coverages": [],
        "agent_name": agent_name,
        "client_full_name": client_name,
    }


@pytest.fixture
def env(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
        storage_dir=tmp_path / "storage",
        frontend_origin="http://localhost:5173",
    )
    app = create_app(settings, renderer=FakeRenderer(), clock=lambda: FIXED_NOW)
    with TestClient(app) as client:

        def create(payload):
            body = client.post("/api/quotes", json=payload).json()
            return body["download_url"].rsplit("/", 1)[1]

        yield app, client, create


def compare(client, tokens):
    return client.post("/api/quotes/compare", json={"tokens": tokens})


@pytest.mark.parametrize(
    "evil",
    [
        "../../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "%2e%2e%2f%2e%2e%2f",
        "/etc/passwd",
        "C:\\Windows\\win.ini",
        "token\x00.pdf",
        "\x00",
        "../" + "A" * 40,
        "A" * 42 + "/",
        "A" * 42 + "\n",
        " " + "A" * 42,
    ],
)
def test_traversal_and_junk_tokens_are_404(env, evil):
    _app, client, create = env
    good = create(car("ישראל"))
    for tokens in ([good, evil], [evil, good]):
        response = compare(client, tokens)
        assert response.status_code == 404, (tokens, response.text)
        assert not response.content.startswith(b"%PDF")


def test_internal_identifiers_are_not_tokens(env):
    app, client, create = env
    good = create(car("ישראל"))
    create(car("משה"))
    with app.state.quote_service.sessions() as session:
        other = session.query(Quote).order_by(Quote.quote_number).all()[1]
    for guess in (other.id, other.pdf_filename, other.quote_number):
        assert compare(client, [good, guess]).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        "{{7*7}}",
        "{% for x in range(3) %}X{% endfor %}",
        "<script>alert(1)</script>",
        '<img src="file:///etc/passwd">',
        '<link rel="stylesheet" href="http://attacker.example/x.css">',
        '"><b onmouseover=alert(1)>',
    ],
)
def test_names_are_escaped_in_comparison(env, payload):
    _app, client, create = env
    token_a = create(car(payload, agent_name=payload, age=23))
    token_b = create(car("ישראל", age=40))
    response = compare(client, [token_a, token_b])
    assert response.status_code == 200
    html = response.content.decode("utf-8").split("\n", 1)[1]  # FakeRenderer: %PDF-fake + HTML
    body = html.split("<body", 1)[1]
    for raw in ("<script", "<img", "<b ", "XXX"):
        assert raw not in body, raw
    assert ">49<" not in body
    # head: only our two stylesheets
    head = html.split("<body", 1)[0]
    assert sorted(re.findall(r'href="([^"]*)"', head)) == ["quote.css", "quote_car.css"]


def test_tokens_never_appear_in_the_document(env):
    _app, client, create = env
    token_a = create(car("ישראל", age=23))
    token_b = create(car("משה", age=40))
    html = compare(client, [token_a, token_b]).content.decode("utf-8")
    assert token_a not in html
    assert token_b not in html
