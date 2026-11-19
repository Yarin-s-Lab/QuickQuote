"""Real PDF output. Needs WeasyPrint + Pango: runs in Docker, skipped elsewhere."""

from io import BytesIO

import pytest

from app.services.pdf_renderer import PdfRenderer
from tests.conftest import PRODUCT_CODES, make_document, requires_pdf

pytestmark = [requires_pdf, pytest.mark.pdf]


@pytest.fixture(scope="module", params=PRODUCT_CODES)
def product(request):
    return request.param


@pytest.fixture(scope="module")
def pdf_bytes(product):
    return PdfRenderer().render(make_document(product))


@pytest.fixture(scope="module")
def reader(pdf_bytes):
    from pypdf import PdfReader

    return PdfReader(BytesIO(pdf_bytes))


def embedded_fonts(reader):
    names = set()
    for page in reader.pages:
        fonts = page["/Resources"].get_object().get("/Font", {})
        for ref in fonts.values():
            font = ref.get_object()
            names.add(str(font.get("/BaseFont", "")))
            for descendant in font.get("/DescendantFonts", []):
                descriptor = descendant.get_object().get("/FontDescriptor")
                if descriptor and any(
                    k in descriptor.get_object() for k in ("/FontFile", "/FontFile2", "/FontFile3")
                ):
                    names.add("embedded:" + str(descendant.get_object().get("/BaseFont", "")))
    return names


def test_is_a_pdf(pdf_bytes):
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 5_000


def test_single_a4_page(reader):
    assert len(reader.pages) == 1
    box = reader.pages[0].mediabox
    assert (round(float(box.width)), round(float(box.height))) == (595, 842)


def test_only_our_embedded_fonts_are_used(reader):
    """WeasyPrint names subsets after the @font-face family (QQ Hebrew / QQ Latin, see
    quote.css). Every font must be one of ours and embedded: no system fallback."""
    fonts = embedded_fonts(reader)
    embedded = {f.removeprefix("embedded:").split("+", 1)[-1] for f in fonts if "embedded:" in f}
    used = {f.split("+", 1)[-1] for f in fonts if not f.startswith("embedded:")}
    assert "QQ-Hebrew" in embedded, fonts
    assert "QQ-Latin" in embedded, fonts
    assert used <= embedded, f"non-embedded fonts: {used - embedded}"
    assert all(name.startswith("QQ-") for name in used), fonts


def test_text_contains_number_dates_and_hebrew(reader):
    text = reader.pages[0].extract_text()
    for expected in ("Q-2026-000042", "19/11/2026", "19/12/2026", "6,975"):
        assert expected in text, expected
    assert any("֐" <= ch <= "׿" for ch in text)


def test_no_missing_glyph_boxes(reader):
    # A .notdef glyph would show up as an empty box; pypdf yields U+FFFD or nothing for it.
    text = reader.pages[0].extract_text()
    assert "�" not in text


def test_product_subtitle_in_pdf(reader, product):
    # Hebrew-only runs extract in visual order, so look for a distinctive word.
    word = {"car": "רכב", "apartment": "דירה"}[product]
    assert word in reader.pages[0].extract_text() or word[::-1] in reader.pages[0].extract_text()


# Real maxima per product: car = base, value, factors + 3 add-ons (6 lines) and the
# minimum never applies (lowest car premium is 900); apartment = structure, contents,
# factors + 3 add-ons + minimum line (7) with the minimum note.
WORST_CASE = {"car": (6, False), "apartment": (7, True)}


@pytest.mark.parametrize("worst_product", PRODUCT_CODES)
def test_worst_case_still_fits_one_page(worst_product):
    """Longest allowed texts (100 chars, incl. an unbreakable email), every contact field
    and the most breakdown lines the product can produce: still one page, footer 1 / 1.
    (Before the fix, a long email widened the client box past the page edge.)"""
    from decimal import Decimal

    from pypdf import PdfReader

    from app.services.pdf_renderer import DocumentLine

    lines, minimum = WORST_CASE[worst_product]
    long_name = ("שם ארוך מאוד " * 10)[:100]
    long_email = ("a" * 88) + "@example.com"
    pdf = PdfRenderer().render(
        make_document(
            worst_product,
            agent_name=long_name,
            client_full_name=long_name,
            client_phone="+972 50-123-4567",
            client_email=long_email,
            coverages=("גרירה", "שמשות", "רכב חלופי"),
            breakdown=tuple(DocumentLine(f"שורת פירוט {i}", Decimal("100")) for i in range(lines)),
            minimum_applied=minimum,
        )
    )
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "1 / 1" in text
    assert "@example.com" in text
