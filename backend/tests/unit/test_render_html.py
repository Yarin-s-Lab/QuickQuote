import re
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.services.pdf_renderer import (
    DocumentLine,
    PdfRenderer,
    format_date_he,
    format_factor,
    format_ils,
)
from tests.conftest import make_document


@pytest.fixture(scope="module")
def html():
    return PdfRenderer().render_html(make_document())


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("1234", "1,234 ₪"),
        ("6975.000000", "6,975 ₪"),
        ("500", "500 ₪"),
        ("1700.5", "1,700.50 ₪"),
        ("0.004", "0 ₪"),
        ("-100.00", "-100 ₪"),
        ("1000000", "1,000,000 ₪"),
    ],
)
def test_format_ils(amount, expected):
    assert format_ils(Decimal(amount)) == expected


def test_format_ils_rejects_float():
    with pytest.raises(TypeError):
        format_ils(1234.5)


def test_format_date_is_israel_local():
    # 22:30 UTC on 31/12 is 00:30 on 01/01 in Israel
    assert format_date_he(datetime(2026, 12, 31, 22, 30, tzinfo=UTC)) == "01/01/2027"
    assert format_date_he(datetime(2026, 7, 5, 9, 0, tzinfo=UTC)) == "05/07/2026"


def test_format_date_rejects_naive():
    with pytest.raises(ValueError):
        format_date_he(datetime(2026, 1, 1))


@pytest.mark.parametrize(("value", "expected"), [("1.5", "×1.5"), ("1.00", "×1"), ("0.9", "×0.9")])
def test_format_factor(value, expected):
    assert format_factor(Decimal(value)) == expected


def test_rtl_hebrew_document(html):
    assert '<html lang="he" dir="rtl">' in html
    assert '<meta charset="utf-8">' in html


def test_quote_number_and_dates_in_ltr_bdi(html):
    assert '<bdi dir="ltr" class="quote-number">Q-2026-000042</bdi>' in html
    assert '<bdi dir="ltr" class="issued-at">19/11/2026</bdi>' in html
    assert '<bdi dir="ltr" class="valid-until">19/12/2026</bdi>' in html


def test_amounts_formatted_and_forced_ltr(html):
    # dir="ltr" is required: with dir=auto a run with no letters inherits RTL,
    # which flips "-100 ₪" to "100-" and "+972 50..." to "50... 972+".
    assert '<bdi dir="ltr" class="premium">6,975 ₪</bdi>' in html
    assert '<bdi dir="ltr">3,325 ₪</bdi>' in html
    assert '<bdi dir="ltr">×1.5</bdi>' in html
    assert '<bdi dir="ltr" class="client-phone">050-1234567</bdi>' in html


def test_every_amount_and_number_is_ltr(html):
    for match in re.finditer(r"<bdi([^>]*)>([^<]*)</bdi>", html):
        attrs, text = match.groups()
        has_letters = re.search(r"[A-Za-z\u0590-\u05FF]", text)
        if re.search(r"\d", text) and not has_letters:
            assert 'dir="ltr"' in attrs, f"numeric bdi without dir=ltr: {text!r}"


def test_negative_amount_kept_as_one_ltr_run():
    html = PdfRenderer().render_html(
        make_document(breakdown=(DocumentLine("הנחת אזעקה", Decimal("-100")),))
    )
    assert '<bdi dir="ltr">-100 ₪</bdi>' in html


def test_text_fields_keep_auto_direction(html):
    assert '<bdi class="agent-name">דנה כהן</bdi>' in html
    assert '<bdi class="client-name">ישראל ישראלי</bdi>' in html


def test_contains_required_sections(html):
    for text in [
        "QuickQuote",
        "דנה כהן",
        "ישראל ישראלי",
        "050-1234567",
        "client@example.com",
        "ביטוח רכב",
        "גרירה",
        "פירוט החישוב",
        "פרמיה שנתית",
        "הצעה לדוגמה — לא מחייבת",
    ]:
        assert text in html, text


def test_optional_contact_details_omitted():
    html = PdfRenderer().render_html(make_document(client_phone=None, client_email=None))
    assert "client-phone" not in html
    assert "client-email" not in html


def test_no_coverages_and_minimum_note():
    html = PdfRenderer().render_html(make_document(coverages=(), minimum_applied=True))
    assert re.search(r"כיסויים נוספים:\s*ללא", html)
    assert "הוחלה פרמיה מינימלית" in html


def test_stylesheet_and_fonts_are_local():
    html = PdfRenderer().render_html(make_document())
    assert '<link rel="stylesheet" href="quote.css">' in html
    assert "http" not in html.split("<body>")[0]
