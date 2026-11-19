"""SPEC section 8: no duplicate quote numbers under parallel requests."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db.models import Quote, QuoteCounter
from app.main import create_app
from tests.conftest import FIXED_NOW, FakeRenderer

REQUESTS = 20

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


class SlowRenderer(FakeRenderer):
    """Holds the transaction open for a while so requests really overlap."""

    def __init__(self, fail_every: int = 0) -> None:
        super().__init__()
        self.fail_every = fail_every
        self.calls = 0
        self._lock = threading.Lock()

    def render_pdf(self, html: str) -> bytes:
        with self._lock:
            self.calls += 1
            call = self.calls
        time.sleep(0.02)
        if self.fail_every and call % self.fail_every == 0:
            raise RuntimeError(f"render failure #{call}")
        return super().render_pdf(html)


class InFlight:
    """Counts requests that are inside the endpoint at the same time."""

    def __init__(self) -> None:
        self.current = 0
        self.peak = 0
        self._lock = threading.Lock()

    def __enter__(self):
        with self._lock:
            self.current += 1
            self.peak = max(self.peak, self.current)

    def __exit__(self, *exc):
        with self._lock:
            self.current -= 1


@pytest.fixture
def make_env(tmp_path):
    def factory(renderer):
        settings = Settings(
            database_url=f"sqlite:///{tmp_path / 'concurrency.db'}",
            storage_dir=tmp_path / "storage",
            frontend_origin="http://localhost:5173",
        )
        return create_app(settings, renderer=renderer, clock=lambda: FIXED_NOW)

    return factory


def fire(app, count):
    in_flight = InFlight()
    start = threading.Barrier(count)

    def one(_):
        start.wait()  # release all threads at once
        with in_flight:
            return client.post("/api/quotes", json=CAR)

    with TestClient(app, raise_server_exceptions=False) as client:
        with ThreadPoolExecutor(max_workers=count) as pool:
            responses = list(pool.map(one, range(count)))
        service = app.state.quote_service
        with service.sessions() as session:
            stored = sorted(q.quote_number for q in session.query(Quote).all())
            counters = {c.year: c.last_value for c in session.query(QuoteCounter).all()}
    return responses, stored, counters, in_flight.peak


def test_parallel_requests_get_unique_consecutive_numbers(make_env):
    responses, stored, counters, peak = fire(make_env(SlowRenderer()), REQUESTS)

    assert peak > 1, "requests did not overlap; the test would prove nothing"
    assert [r.status_code for r in responses] == [201] * REQUESTS
    numbers = sorted(r.json()["quote_number"] for r in responses)
    expected = [f"Q-2026-{n:06d}" for n in range(1, REQUESTS + 1)]
    assert numbers == expected  # unique and gap-free
    assert stored == expected
    assert counters == {2026: REQUESTS}


def test_failed_requests_do_not_consume_numbers(make_env):
    responses, stored, counters, peak = fire(make_env(SlowRenderer(fail_every=3)), REQUESTS)

    assert peak > 1
    ok = [r for r in responses if r.status_code == 201]
    failed = [r for r in responses if r.status_code != 201]
    assert len(failed) == REQUESTS // 3
    assert {r.status_code for r in failed} == {500}

    numbers = sorted(r.json()["quote_number"] for r in ok)
    expected = [f"Q-2026-{n:06d}" for n in range(1, len(ok) + 1)]
    assert numbers == expected  # still gap-free: rolled-back numbers are reused
    assert stored == expected
    assert counters == {2026: len(ok)}
