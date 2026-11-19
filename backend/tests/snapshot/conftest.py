"""Deterministic quote rendering for snapshot tests (SPEC section 8).

Frozen clock, fixed UUID and token, fixed inputs: the same code must always
produce the same HTML (main snapshot) and the same page image (secondary).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.api.schemas import CreateQuoteRequest
from app.db.session import Database
from app.services.pdf_renderer import PdfRenderer, QuoteDocument
from app.services.quote_service import QuoteService
from app.services.storage import Storage
from tests.conftest import FIXED_NOW

SNAPSHOT_DIR = Path(__file__).parent / "__snapshots__"
FIXED_ID = "00000000-0000-4000-8000-000000000001"
FIXED_TOKEN = "T" * 43

SAMPLES = {
    # Mixed Hebrew/English name and a phone number: the cases that broke bidi before.
    "car": {
        "product": "car",
        "inputs": {
            "driver_age": 23,
            "license_years": 1,
            "car_value": 185_000,
            "claims_last_3_years": 1,
            "coverage_type": "comprehensive",
        },
        "coverages": ["towing", "glass", "replacement_car"],
        "agent_name": "דנה כהן",
        "client_full_name": "John Smith ג'ון סמית'",
        "client_phone": "+972 50-123-4567",
        "client_email": "john.smith@example.com",
    },
    # Minimum premium, a negative adjustment line, no add-ons.
    "apartment": {
        "product": "apartment",
        "inputs": {
            "structure_value": 100_000,
            "contents_value": 0,
            "floor": 0,
            "has_alarm": True,
        },
        "coverages": [],
        "agent_name": 'סוכנות אלפא בע"מ',
        "client_full_name": "ישראל ישראלי",
    },
}

_REQUEST = TypeAdapter(CreateQuoteRequest)


class CapturingRenderer(PdfRenderer):
    """Records the document and HTML; produces the real PDF only when asked."""

    def __init__(self, real_pdf: bool) -> None:
        super().__init__()
        self.real_pdf = real_pdf
        self.document: QuoteDocument | None = None
        self.html: str | None = None
        self.pdf: bytes | None = None

    def render(self, document: QuoteDocument) -> bytes:
        self.document = document
        self.html = self.render_html(document)
        self.pdf = self.render_pdf(self.html) if self.real_pdf else b"%PDF-snapshot"
        return self.pdf


@dataclass
class RenderedQuote:
    html: str
    pdf: bytes | None


@pytest.fixture
def render_sample(tmp_path):
    """Run the full create() flow for a named sample with everything pinned."""

    runs = iter(range(1_000))

    def render(name: str, *, real_pdf: bool = False) -> RenderedQuote:
        # A fresh DB and storage per run, so every run is quote number 1.
        run_dir = tmp_path / f"run-{next(runs)}-{name}"
        db = Database(f"sqlite:///{run_dir / 'quotes.db'}")
        db.create_all()
        renderer = CapturingRenderer(real_pdf=real_pdf)
        service = QuoteService(
            sessions=db.sessionmaker,
            storage=Storage(run_dir / "storage"),
            renderer=renderer,
            clock=lambda: FIXED_NOW,
            new_id=lambda: FIXED_ID,
            new_token=lambda: FIXED_TOKEN,
        )
        try:
            service.create(_REQUEST.validate_python(SAMPLES[name]))
        finally:
            db.dispose()
        assert renderer.html is not None
        return RenderedQuote(html=renderer.html, pdf=renderer.pdf if real_pdf else None)

    return render


@pytest.fixture
def snapshot_update(request) -> bool:
    return bool(request.config.getoption("--snapshot-update"))


@pytest.fixture
def failures_dir() -> Path:
    """Where mismatching output is written for inspection (uploaded by CI)."""
    path = Path(os.environ.get("SNAPSHOT_FAILURES_DIR", Path(__file__).parent / ".failures"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def missing_snapshot_message(path: Path) -> str:
    return (
        f"snapshot {path.name} does not exist. Create it on purpose with "
        "`pytest tests/snapshot --snapshot-update` and review the result."
    )
