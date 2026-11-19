"""Real PDF output. Needs WeasyPrint + Pango: runs in Docker, skipped elsewhere."""

from io import BytesIO

import pytest

from app.services.pdf_renderer import PdfRenderer
from tests.conftest import make_document, requires_pdf

pytestmark = [requires_pdf, pytest.mark.pdf]


@pytest.fixture(scope="module")
def pdf_bytes():
    return PdfRenderer().render(make_document())


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
