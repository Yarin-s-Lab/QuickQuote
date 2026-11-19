import re
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.services.pdf_renderer import (
    PRODUCT_TEMPLATES,
    TEMPLATES_DIR,
    DocumentField,
    DocumentLine,
    PdfRenderer,
    UnknownProductError,
    format_date_he,
    format_factor,
    format_ils,
    template_for,
)
from tests.conftest import PRODUCT_CODES, PRODUCT_FIELDS, PRODUCT_LABELS, make_document

SUBTITLES = {"car": "הצעת מחיר לביטוח רכב", "apartment": "הצעת מחיר לביטוח דירה"}
FIELD_GROUPS = {
    "car": [
        ("פרטי הנהג", ["driver_age", "license_years", "claims_last_3_years"]),
        ("פרטי הרכב", ["car_value", "coverage_type"]),
    ],
    "apartment": [
        ("שווי הנכס", ["structure_value", "contents_value"]),
        ("מאפייני הדירה", ["floor", "has_alarm"]),
    ],
}


@pytest.fixture(scope="module", params=PRODUCT_CODES)
def product(request):
    return request.param


@pytest.fixture(scope="module")
def html(product):
    return PdfRenderer().render_html(make_document(product))


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


@pytest.mark.parametrize("product", PRODUCT_CODES)
def test_negative_amount_kept_as_one_ltr_run(product):
    html = PdfRenderer().render_html(
        make_document(product, breakdown=(DocumentLine("הנחת אזעקה", Decimal("-100")),))
    )
    assert '<bdi dir="ltr">-100 ₪</bdi>' in html


def test_text_fields_keep_auto_direction(html):
    assert '<bdi class="agent-name">דנה כהן</bdi>' in html
    assert '<bdi class="client-name">ישראל ישראלי</bdi>' in html


def test_contains_required_sections(html, product):
    for text in [
        "QuickQuote",
        "דנה כהן",
        "ישראל ישראלי",
        "050-1234567",
        "client@example.com",
        PRODUCT_LABELS[product],
        "גרירה",
        "פירוט החישוב",
        "פרמיה שנתית",
        "הצעה לדוגמה — לא מחייבת",
    ]:
        assert text in html, text


@pytest.mark.parametrize("product", PRODUCT_CODES)
def test_optional_contact_details_omitted(product):
    html = PdfRenderer().render_html(make_document(product, client_phone=None, client_email=None))
    assert "client-phone" not in html
    assert "client-email" not in html


@pytest.mark.parametrize("product", PRODUCT_CODES)
def test_no_coverages_and_minimum_note(product):
    html = PdfRenderer().render_html(make_document(product, coverages=(), minimum_applied=True))
    assert re.search(r"כיסויים נוספים:\s*ללא", html)
    assert "הוחלה פרמיה מינימלית" in html


def test_stylesheets_are_local(html, product):
    head = html.split("<body", 1)[0]
    assert '<link rel="stylesheet" href="quote.css">' in head
    assert f'<link rel="stylesheet" href="quote_{product}.css">' in head
    assert "http" not in head


# ---------- template per product (SPEC bonus section 10) ----------


def test_fixed_mapping_covers_exactly_the_products():
    assert dict(PRODUCT_TEMPLATES) == {
        "car": "quote_car.html",
        "apartment": "quote_apartment.html",
    }
    for name in PRODUCT_TEMPLATES.values():
        assert (TEMPLATES_DIR / name).is_file()


def test_mapping_is_read_only():
    with pytest.raises(TypeError):
        PRODUCT_TEMPLATES["boat"] = "evil.html"  # type: ignore[index]


@pytest.mark.parametrize(
    "bad",
    ["boat", "", "Car", "base", "base.html", "quote_car.html", "../quote_car", None, 1],
)
def test_unknown_product_has_no_template(bad):
    with pytest.raises(UnknownProductError):
        template_for(bad)


def test_rendering_an_unknown_product_fails_instead_of_falling_back():
    with pytest.raises(UnknownProductError):
        PdfRenderer().render_html(make_document("boat"))


@pytest.mark.parametrize("product", PRODUCT_CODES)
def test_product_templates_extend_base(product):
    source = (TEMPLATES_DIR / template_for(product)).read_text(encoding="utf-8")
    assert source.lstrip().startswith('{% extends "base.html" %}')


def test_product_specific_look(html, product):
    assert f'<body class="product-{product}">' in html
    assert f'<div class="tagline">{SUBTITLES[product]}</div>' in html
    assert '<span class="product-icon"><svg class="icon"' in html
    other = next(p for p in PRODUCT_CODES if p != product)
    assert SUBTITLES[other] not in html
    assert f"quote_{other}.css" not in html


def test_every_field_appears_exactly_once(html, product):
    """Grouping fields per product must never drop or duplicate one."""
    rows = re.findall(r'<tr data-field="([^"]+)">', html)
    assert sorted(rows) == sorted(f.name for f in PRODUCT_FIELDS[product])


def test_field_groups_and_order(html, product):
    for title, names in FIELD_GROUPS[product]:
        section = html.split(f'<h3 class="field-group">{title}</h3>', 1)[1].split("</table>", 1)[0]
        assert re.findall(r'<tr data-field="([^"]+)">', section) == names


def test_missing_field_fails_loudly():
    fields = tuple(f for f in PRODUCT_FIELDS["car"] if f.name != "car_value")
    with pytest.raises(Exception, match="car_value"):
        PdfRenderer().render_html(make_document("car", fields=fields))


def test_car_badge_shows_coverage_type():
    html = PdfRenderer().render_html(make_document("car"))
    assert '<span class="badge coverage-type-badge">מקיף</span>' in html


@pytest.mark.parametrize(("has_alarm", "shown"), [("כן", True), ("לא", False)])
def test_apartment_alarm_badge(has_alarm, shown):
    fields = tuple(
        DocumentField(f.name, f.label_he, has_alarm) if f.name == "has_alarm" else f
        for f in PRODUCT_FIELDS["apartment"]
    )
    html = PdfRenderer().render_html(make_document("apartment", fields=fields))
    assert ('<span class="badge alarm-badge">יש אזעקה</span>' in html) is shown
