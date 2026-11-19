from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.services.pdf_renderer import (
    DocumentFactor,
    DocumentField,
    DocumentLine,
    PdfRenderer,
    QuoteDocument,
)

FIXED_NOW = datetime(2026, 11, 19, 8, 30, tzinfo=UTC)


def pytest_addoption(parser):
    parser.addoption(
        "--snapshot-update",
        action="store_true",
        default=False,
        help="Rewrite snapshot files. Only for intentional design changes; explain in the commit.",
    )


def weasyprint_available() -> bool:
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


requires_pdf = pytest.mark.skipif(
    not weasyprint_available(),
    reason="WeasyPrint/Pango not available here; PDF tests run in Docker",
)


class FakeRenderer(PdfRenderer):
    """Real HTML rendering, fake PDF bytes. Lets API tests run without Pango."""

    def __init__(self) -> None:
        super().__init__()
        self.documents: list[QuoteDocument] = []
        self.fail_with: BaseException | None = None

    def render_pdf(self, html: str) -> bytes:
        if self.fail_with is not None:
            raise self.fail_with
        return b"%PDF-fake\n" + html.encode("utf-8")

    def render(self, document: QuoteDocument) -> bytes:
        self.documents.append(document)
        return super().render(document)


PRODUCT_CODES = ("car", "apartment")

# Every input field of each product, as the service builds them (name, label, value, ltr).
PRODUCT_FIELDS = {
    "car": (
        DocumentField("driver_age", "גיל הנהג", "23", ltr=True),
        DocumentField("license_years", "ותק נהיגה (שנים)", "1", ltr=True),
        DocumentField("car_value", "שווי הרכב (₪)", "100,000 ₪", ltr=True),
        DocumentField("claims_last_3_years", "תביעות ב-3 השנים האחרונות", "0", ltr=True),
        DocumentField("coverage_type", "סוג כיסוי", "מקיף"),
    ),
    "apartment": (
        DocumentField("structure_value", "שווי המבנה (₪)", "1,000,000 ₪", ltr=True),
        DocumentField("contents_value", "שווי התכולה (₪)", "200,000 ₪", ltr=True),
        DocumentField("floor", "קומה", "3", ltr=True),
        DocumentField("has_alarm", "יש אזעקה", "כן"),
    ),
}
PRODUCT_LABELS = {"car": "ביטוח רכב", "apartment": "ביטוח דירה"}


def make_document(product: str = "car", **overrides) -> QuoteDocument:
    values = {
        "product": product,
        "quote_number": "Q-2026-000042",
        "product_label_he": PRODUCT_LABELS.get(product, "?"),
        "issued_at": FIXED_NOW,
        "valid_until": datetime(2026, 12, 19, 8, 30, tzinfo=UTC),
        "agent_name": "דנה כהן",
        "client_full_name": "ישראל ישראלי",
        "client_phone": "050-1234567",
        "client_email": "client@example.com",
        "fields": PRODUCT_FIELDS.get(product, ()),
        "coverages": ("גרירה",),
        "breakdown": (
            DocumentLine("פרמיית בסיס (מקיף)", Decimal("1500")),
            DocumentLine("רכיב שווי הרכב (2%)", Decimal("2000.00")),
            DocumentLine("התאמה לפי פקטורים", Decimal("3325.000000")),
            DocumentLine("גרירה", Decimal("150")),
        ),
        "factors": (DocumentFactor("פקטור גיל", Decimal("1.5")),),
        "premium_before_rounding": Decimal("6975.000000"),
        "premium": Decimal("6975"),
        "minimum_applied": False,
    }
    values.update(overrides)
    return QuoteDocument(**values)
