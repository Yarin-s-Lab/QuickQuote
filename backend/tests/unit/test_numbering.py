from datetime import UTC, datetime

import pytest

from app.db.session import Database
from app.services.numbering import (
    QUOTE_NUMBER_RE,
    QuoteNumberExhaustedError,
    format_quote_number,
    next_quote_number,
    quote_year,
)


@pytest.fixture
def db(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'test.db'}")
    database.create_all()
    yield database
    database.dispose()


def take(db, year):
    with db.sessionmaker() as session, session.begin():
        return next_quote_number(session, year)


@pytest.mark.parametrize(
    ("year", "seq", "expected"),
    [(2026, 1, "Q-2026-000001"), (2026, 42, "Q-2026-000042"), (2027, 999_999, "Q-2027-999999")],
)
def test_format(year, seq, expected):
    assert format_quote_number(year, seq) == expected
    assert QUOTE_NUMBER_RE.fullmatch(expected)


@pytest.mark.parametrize("seq", [0, -1, 1_000_000])
def test_format_out_of_range(seq):
    with pytest.raises(QuoteNumberExhaustedError):
        format_quote_number(2026, seq)


def test_sequential_within_year(db):
    assert [take(db, 2026) for _ in range(3)] == [
        "Q-2026-000001",
        "Q-2026-000002",
        "Q-2026-000003",
    ]


def test_resets_each_year(db):
    take(db, 2026)
    take(db, 2026)
    assert take(db, 2027) == "Q-2027-000001"
    assert take(db, 2026) == "Q-2026-000003"


def test_rollback_returns_the_number(db):
    with db.sessionmaker() as session:
        session.begin()
        assert next_quote_number(session, 2026) == "Q-2026-000001"
        session.rollback()
    assert take(db, 2026) == "Q-2026-000001"


def test_year_follows_israel_time():
    # 31/12 23:30 UTC is already 01/01 in Israel (UTC+2)
    assert quote_year(datetime(2026, 12, 31, 23, 30, tzinfo=UTC)) == 2027
    assert quote_year(datetime(2026, 12, 31, 21, 59, tzinfo=UTC)) == 2026
