"""Main snapshot: the rendered HTML of each product. Runs everywhere (no PDF engine needed).

A failure means the quote's content or markup changed. If that is intended, run
`pytest tests/snapshot --snapshot-update`, review the diff, and say why in the commit.
"""

from __future__ import annotations

import difflib

import pytest

from tests.snapshot.conftest import SAMPLES, SNAPSHOT_DIR, missing_snapshot_message


def _normalize(text: str) -> str:
    # Git may check out snapshots with CRLF on Windows; compare logical lines only.
    return text.replace("\r\n", "\n")


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_rendered_html_matches_snapshot(name, render_sample, snapshot_update, failures_dir):
    actual = _normalize(render_sample(name).html)
    path = SNAPSHOT_DIR / f"{name}.html"

    if snapshot_update:
        path.write_text(actual, encoding="utf-8", newline="\n")
        return

    assert path.exists(), missing_snapshot_message(path)
    expected = _normalize(path.read_text(encoding="utf-8"))
    if actual != expected:
        (failures_dir / f"{name}.actual.html").write_text(actual, encoding="utf-8", newline="\n")
        diff = "".join(
            difflib.unified_diff(
                expected.splitlines(keepends=True),
                actual.splitlines(keepends=True),
                fromfile=f"snapshot/{name}.html",
                tofile=f"actual/{name}.html",
                n=2,
            )
        )
        pytest.fail(f"HTML snapshot mismatch for {name}:\n{diff[:4000]}")


def test_comparison_html_matches_snapshot(render_comparison, snapshot_update, failures_dir):
    actual = _normalize(render_comparison().html)
    path = SNAPSHOT_DIR / "compare.html"
    if snapshot_update:
        path.write_text(actual, encoding="utf-8", newline="\n")
        return
    assert path.exists(), missing_snapshot_message(path)
    expected = _normalize(path.read_text(encoding="utf-8"))
    if actual != expected:
        (failures_dir / "compare.actual.html").write_text(actual, encoding="utf-8", newline="\n")
        diff = "".join(
            difflib.unified_diff(
                expected.splitlines(keepends=True), actual.splitlines(keepends=True), n=2
            )
        )
        pytest.fail(f"HTML snapshot mismatch for compare:\n{diff[:4000]}")


def test_comparison_is_deterministic(render_comparison):
    assert render_comparison().html == render_comparison().html


def test_snapshots_are_deterministic(render_sample):
    """Two runs must be byte-identical, or the snapshot would be flaky."""
    assert render_sample("car").html == render_sample("car").html
