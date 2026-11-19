"""The comparison document and compare.html (no PDF engine needed)."""

from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal

import pytest

from app.db.models import Quote
from app.services.pdf_renderer import (
    PRODUCT_STYLESHEETS,
    TEMPLATES_DIR,
    ComparisonDocument,
    ComparisonRow,
    PdfRenderer,
    UnknownProductError,
)
from app.services.quote_service import _comparison_document
from tests.conftest import FIXED_NOW


def quote(number, *, premium, age=30, coverages=(), client="ישראל", product="car", days=0):
    inputs = (
        {
            "driver_age": age,
            "license_years": 10,
            "car_value": 100_000,
            "claims_last_3_years": 0,
            "coverage_type": "comprehensive",
        }
        if product == "car"
        else {"structure_value": 1_000_000, "contents_value": 0, "floor": 2, "has_alarm": True}
    )
    issued = FIXED_NOW + timedelta(days=days)
    return Quote(
        id=f"00000000-0000-4000-8000-00000000000{number[-1]}",
        quote_number=number,
        product=product,
        agent_name="דנה כהן",
        client_full_name=client,
        client_phone=None,
        client_email=None,
        inputs=inputs,
        coverages=list(coverages),
        premium=Decimal(premium),
        breakdown={},
        issued_at=issued,
        valid_until=issued + timedelta(days=30),
        download_token="T" * 43,
        pdf_filename="x.pdf",
    )


def rows_by_label(doc):
    return {row.label_he: row for row in doc.rows}


def test_rows_values_and_differences():
    a = quote("Q-2026-000001", premium="5250", age=23, coverages=["towing"])
    b = quote("Q-2026-000002", premium="3700", age=40, coverages=["glass"], days=1)
    doc = _comparison_document(a, b, generated_at=FIXED_NOW)
    rows = rows_by_label(doc)

    assert doc.quote_numbers == ("Q-2026-000001", "Q-2026-000002")
    assert rows["גיל הנהג"].values == ("23", "40") and rows["גיל הנהג"].differs
    assert not rows["ותק נהיגה (שנים)"].differs
    assert rows["שווי הרכב (₪)"].values == ("100,000 ₪", "100,000 ₪")
    assert rows["כיסויים נוספים"].values == ("גרירה", "שמשות")
    assert rows["תאריך הנפקה"].values == ("19/11/2026", "20/11/2026")
    assert rows["פרמיה שנתית"].values == ("5,250 ₪", "3,700 ₪")
    assert rows["לקוח"].values == ("ישראל", "ישראל") and not rows["לקוח"].differs
    assert doc.cheaper == 1
    assert doc.difference == Decimal("1550")


def test_row_order_is_parties_dates_fields_coverages_premium():
    a = quote("Q-2026-000001", premium="5250")
    b = quote("Q-2026-000002", premium="5250")
    labels = [r.label_he for r in _comparison_document(a, b, generated_at=FIXED_NOW).rows]
    assert labels == [
        "לקוח",
        "סוכן",
        "תאריך הנפקה",
        "בתוקף עד",
        "גיל הנהג",
        "ותק נהיגה (שנים)",
        "שווי הרכב (₪)",
        "תביעות ב-3 השנים האחרונות",
        "סוג כיסוי",
        "כיסויים נוספים",
        "פרמיה שנתית",
    ]


def test_equal_premiums_and_no_coverages():
    a = quote("Q-2026-000001", premium="500", product="apartment")
    b = quote("Q-2026-000002", premium="500", product="apartment")
    doc = _comparison_document(a, b, generated_at=FIXED_NOW)
    assert doc.cheaper is None
    assert doc.difference == Decimal("0")
    assert rows_by_label(doc)["כיסויים נוספים"].values == ("ללא", "ללא")
    assert rows_by_label(doc)["יש אזעקה"].values == ("כן", "כן")


def test_numeric_rows_are_ltr():
    a = quote("Q-2026-000001", premium="5250")
    b = quote("Q-2026-000002", premium="3700")
    rows = rows_by_label(_comparison_document(a, b, generated_at=FIXED_NOW))
    for label in ("גיל הנהג", "שווי הרכב (₪)", "תאריך הנפקה", "פרמיה שנתית"):
        assert rows[label].ltr, label
    for label in ("לקוח", "סוג כיסוי", "כיסויים נוספים"):
        assert not rows[label].ltr, label


# ---------- compare.html ----------


def make_doc(**overrides) -> ComparisonDocument:
    values = {
        "product": "car",
        "product_label_he": "ביטוח רכב",
        "generated_at": FIXED_NOW,
        "quote_numbers": ("Q-2026-000001", "Q-2026-000002"),
        "rows": (
            ComparisonRow("לקוח", ("ישראל", "משה"), differs=True),
            ComparisonRow("גיל הנהג", ("23", "23"), ltr=True),
            ComparisonRow("פרמיה שנתית", ("5,250 ₪", "3,700 ₪"), ltr=True, differs=True),
        ),
        "difference": Decimal("1550"),
        "cheaper": 1,
    }
    values.update(overrides)
    return ComparisonDocument(**values)


@pytest.fixture
def html():
    return PdfRenderer().render_comparison_html(make_doc())


def test_extends_base(html):
    source = (TEMPLATES_DIR / "compare.html").read_text(encoding="utf-8")
    assert source.lstrip().startswith('{% extends "base.html" %}')
    assert '<html lang="he" dir="rtl">' in html
    assert "QuickQuote" in html
    assert "הצעה לדוגמה — לא מחייבת" in html  # shell from base.html


def test_first_quote_column_comes_first_so_it_renders_on_the_right(html):
    # In an RTL table, source order is right-to-left: label, first quote, second quote.
    assert html.index("quote-number-a") < html.index("quote-number-b")
    assert '<bdi dir="ltr" class="quote-number-a">Q-2026-000001</bdi>' in html
    assert '<bdi dir="ltr" class="quote-number-b">Q-2026-000002</bdi>' in html
    row = re.search(
        r"<th>לקוח</th>\s*<td><bdi>([^<]*)</bdi></td>\s*<td><bdi>([^<]*)</bdi></td>", html
    )
    assert row and row.groups() == ("ישראל", "משה")


def test_differing_rows_are_highlighted(html):
    assert re.search(r'<tr class="differs">\s*<th>לקוח</th>', html)
    assert re.search(r'<tr class="differs">\s*<th>פרמיה שנתית</th>', html)
    assert re.search(r"<tr>\s*<th>גיל הנהג</th>", html)


def test_summary_names_the_cheaper_quote(html):
    assert "הזולה יותר: הצעה ב'" in html
    assert '<bdi dir="ltr" class="cheaper-number">Q-2026-000002</bdi>' in html
    assert '<bdi dir="ltr" class="difference">1,550 ₪</bdi>' in html


def test_summary_when_equal():
    html = PdfRenderer().render_comparison_html(make_doc(cheaper=None, difference=Decimal("0")))
    assert "הפרמיות זהות" in html
    assert "הזולה יותר" not in html


def test_every_numeric_bdi_is_ltr(html):
    for attrs, text in re.findall(r"<bdi([^>]*)>([^<]*)</bdi>", html):
        if re.search(r"\d", text) and not re.search(r"[A-Za-z֐-׿]", text):
            assert 'dir="ltr"' in attrs, text


@pytest.mark.parametrize("product", sorted(PRODUCT_STYLESHEETS))
def test_product_accent_stylesheet(product):
    html = PdfRenderer().render_comparison_html(make_doc(product=product))
    head = html.split("<body", 1)[0]
    assert sorted(re.findall(r'href="([^"]*)"', head)) == sorted(
        ["quote.css", PRODUCT_STYLESHEETS[product]]
    )
    assert f'<body class="product-{product} compare">' in html


@pytest.mark.parametrize("bad", ["boat", "", "../quote_car", None])
def test_unknown_product_fails(bad):
    with pytest.raises(UnknownProductError):
        PdfRenderer().render_comparison_html(make_doc(product=bad))
