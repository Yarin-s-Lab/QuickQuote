"""Secondary snapshot: page 1 of the PDF as PNG, compared with a small tolerance.

Runs only inside the Docker image (QQ_IN_DOCKER=1), where fonts, Pango and poppler
are pinned. Anywhere else the rendering can legitimately differ, so it is skipped.
"""

from __future__ import annotations

import os
import subprocess
from io import BytesIO
from pathlib import Path

import pytest

from tests.snapshot.conftest import SAMPLES, SNAPSHOT_DIR, missing_snapshot_message

pytestmark = [
    pytest.mark.pdf,
    pytest.mark.skipif(
        os.environ.get("QQ_IN_DOCKER") != "1",
        reason="PNG snapshot runs only inside the backend Docker image",
    ),
]

DPI = 72
PIXEL_THRESHOLD = 32  # per-pixel grey-level difference that counts as "changed"
MAX_CHANGED_RATIO = 0.005  # at most 0.5% of pixels may change


def pdf_page1_png(pdf: bytes, workdir: Path) -> bytes:
    pdf_path = workdir / "quote.pdf"
    pdf_path.write_bytes(pdf)
    out = workdir / "page"
    subprocess.run(
        ["pdftoppm", "-r", str(DPI), "-png", "-singlefile", "-f", "1", "-l", "1", pdf_path, out],
        check=True,
        capture_output=True,
    )
    return out.with_suffix(".png").read_bytes()


def compare(expected_png: bytes, actual_png: bytes):
    """Fraction of pixels whose largest per-channel (R, G or B) difference exceeds the
    threshold. Compared in RGB, not greyscale: a colour change with similar brightness
    (e.g. the blue total box turning red) would otherwise go unnoticed."""
    from PIL import Image, ImageChops

    expected = Image.open(BytesIO(expected_png)).convert("RGB")
    actual = Image.open(BytesIO(actual_png)).convert("RGB")
    if expected.size != actual.size:
        return 1.0, None
    red, green, blue = ImageChops.difference(expected, actual).split()
    diff = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    changed = sum(diff.point(lambda v: 255 if v > PIXEL_THRESHOLD else 0).histogram()[255:])
    ratio = changed / (expected.width * expected.height)
    return ratio, diff


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_pdf_page1_matches_png_snapshot(
    name, render_sample, snapshot_update, failures_dir, tmp_path
):
    pdf = render_sample(name, real_pdf=True).pdf
    assert pdf is not None
    actual = pdf_page1_png(pdf, tmp_path)
    path = SNAPSHOT_DIR / f"{name}.png"

    if snapshot_update:
        path.write_bytes(actual)
        return

    assert path.exists(), missing_snapshot_message(path)
    ratio, diff = compare(path.read_bytes(), actual)
    if ratio > MAX_CHANGED_RATIO:
        (failures_dir / f"{name}.actual.png").write_bytes(actual)
        if diff is not None:
            diff.point(lambda v: 255 if v > PIXEL_THRESHOLD else 0).save(
                failures_dir / f"{name}.diff.png"
            )
        pytest.fail(
            f"PNG snapshot mismatch for {name}: {ratio:.2%} of pixels changed "
            f"(limit {MAX_CHANGED_RATIO:.2%}). See {failures_dir}."
        )
