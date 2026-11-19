"""Quote numbers: Q-YYYY-NNNNNN, running per year, reset every year (SPEC section 8)."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import LOCAL_TZ
from app.db.models import QuoteCounter

MAX_SEQUENCE = 999_999
QUOTE_NUMBER_RE = re.compile(r"^Q-\d{4}-\d{6}$")


class QuoteNumberExhaustedError(RuntimeError):
    pass


def quote_year(issued_at: datetime) -> int:
    """The numbering year follows Israel time, not UTC."""
    return issued_at.astimezone(LOCAL_TZ).year


def format_quote_number(year: int, sequence: int) -> str:
    if not 1 <= sequence <= MAX_SEQUENCE:
        raise QuoteNumberExhaustedError(f"sequence {sequence} out of range for {year}")
    return f"Q-{year:04d}-{sequence:06d}"


def next_quote_number(session: Session, year: int) -> str:
    """Advance the year's counter inside the caller's transaction and return the new number.

    One atomic upsert statement, so the counter row is write-locked until the caller
    commits or rolls back. A rollback gives the number back.
    """
    stmt = (
        sqlite_insert(QuoteCounter)
        .values(year=year, last_value=1)
        .on_conflict_do_update(
            index_elements=[QuoteCounter.year],
            set_={"last_value": QuoteCounter.last_value + 1},
        )
        .returning(QuoteCounter.last_value)
    )
    sequence = session.execute(stmt).scalar_one()
    return format_quote_number(year, sequence)
