"""The comparison PDF itself (Docker: WeasyPrint + poppler)."""

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

import pytest

from app.services.pdf_renderer import ComparisonDocument, ComparisonRow, PdfRenderer
from tests.conftest import FIXED_NOW, requires_pdf

pytestmark = [
    requires_pdf,
    pytest.mark.pdf,
    pytest.mark.skipif(shutil.which("pdftotext") is None, reason="needs poppler (Docker)"),
]

FIRST, SECOND = "Q-2026-000001", "Q-2026-000002"


def document(**overrides) -> ComparisonDocument:
    values = {
        "product": "car",
        "product_label_he": "ביטוח רכב",
        "generated_at": FIXED_NOW,
        "quote_numbers": (FIRST, SECOND),
        "rows": (
            ComparisonRow("לקוח", ("ישראל ישראלי", "משה לוי"), differs=True),
            ComparisonRow("תאריך הנפקה", ("19/11/2026", "20/11/2026"), ltr=True, differs=True),
            ComparisonRow("גיל הנהג", ("23", "35"), ltr=True, differs=True),
            ComparisonRow("סוג כיסוי", ("מקיף", "מקיף")),
            ComparisonRow("פרמיה שנתית", ("12,261 ₪", "8,150 ₪"), ltr=True, differs=True),
        ),
        "difference": Decimal("4111"),
        "cheaper": 1,
    }
    values.update(overrides)
    return ComparisonDocument(**values)


def word_boxes(pdf: bytes, tmp_path) -> dict[str, list[float]]:
    """x-centre of every word on page 1, from poppler's bounding boxes."""
    path = tmp_path / "compare.pdf"
    path.write_bytes(pdf)
    out = subprocess.run(
        ["pdftotext", "-bbox", "-f", "1", "-l", "1", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    boxes: dict[str, list[float]] = {}
    for x_min, x_max, word in re.findall(
        r'<word xMin="([\d.]+)" yMin="[\d.]+" xMax="([\d.]+)" yMax="[\d.]+">([^<]*)</word>', out
    ):
        boxes.setdefault(word, []).append((float(x_min) + float(x_max)) / 2)
    return boxes


def test_first_quote_is_on_the_right(tmp_path):
    pdf = PdfRenderer().render_comparison(document())
    boxes = word_boxes(pdf, tmp_path)
    # Each number appears in its column header (and the second also in the summary).
    first_x = boxes[FIRST][0]
    second_x = boxes[SECOND][0]
    assert first_x > second_x, f"first quote at x={first_x}, second at x={second_x}"

    # The same holds for a body row: the first quote's client is right of the second's.
    # (poppler reports Hebrew words in visual order, i.e. reversed.)
    def x_of(word: str) -> float:
        return (boxes.get(word) or boxes[word[::-1]])[0]

    assert x_of("ישראלי") > x_of("לוי")


def test_single_page_with_both_numbers_and_footer(tmp_path):
    from pypdf import PdfReader

    pdf = PdfRenderer().render_comparison(document())
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert FIRST in text and SECOND in text
    assert "1 / 1" in text


def test_only_our_fonts(tmp_path):
    out = tmp_path / "c.pdf"
    out.write_bytes(PdfRenderer().render_comparison(document()))
    fonts = subprocess.run(["pdffonts", str(out)], check=True, capture_output=True, text=True)
    names = [line.split()[0] for line in fonts.stdout.splitlines()[2:] if line.strip()]
    assert names and all("+QQ-" in name for name in names), names


def test_worst_case_fits_one_page():
    """Apartment has the fewest rows, car the most; use car with 100-char names."""
    from pypdf import PdfReader

    long_name = ("שם ארוך מאוד " * 10)[:100]
    rows = (
        ComparisonRow("לקוח", (long_name, long_name)),
        ComparisonRow("סוכן", (long_name, long_name)),
        ComparisonRow("תאריך הנפקה", ("19/11/2026", "19/11/2026"), ltr=True),
        ComparisonRow("בתוקף עד", ("19/12/2026", "19/12/2026"), ltr=True),
        *(ComparisonRow(f"שדה {i}", ("1,000,000 ₪", "999,999 ₪"), ltr=True) for i in range(5)),
        ComparisonRow("כיסויים נוספים", ("גרירה · שמשות · רכב חלופי",) * 2),
        ComparisonRow("פרמיה שנתית", ("12,261 ₪", "12,261 ₪"), ltr=True),
    )
    pdf = PdfRenderer().render_comparison(
        document(rows=rows, generated_at=FIXED_NOW + timedelta(days=1))
    )
    assert len(PdfReader(BytesIO(pdf)).pages) == 1
