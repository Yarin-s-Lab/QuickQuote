"""SQLAlchemy models (SPEC section 3)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


class DecimalString(TypeDecorator[Decimal]):
    """Exact Decimal storage. SQLite's NUMERIC goes through float, so store the text form."""

    impl = String(40)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if not isinstance(value, Decimal):
            raise TypeError("DecimalString accepts Decimal only")
        return str(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> Decimal | None:
        return None if value is None else Decimal(value)


class UTCDateTime(TypeDecorator[datetime]):
    """Store naive UTC, return aware UTC (SQLite drops tzinfo)."""

    impl = DateTime()
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime; pass an aware datetime")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    quote_number: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    product: Mapped[str] = mapped_column(String(20))
    agent_name: Mapped[str] = mapped_column(String(100))
    client_full_name: Mapped[str] = mapped_column(String(100))
    client_phone: Mapped[str | None] = mapped_column(String(100))
    client_email: Mapped[str | None] = mapped_column(String(100))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    coverages: Mapped[list[str]] = mapped_column(JSON)
    premium: Mapped[Decimal] = mapped_column(DecimalString())
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSON)
    issued_at: Mapped[datetime] = mapped_column(UTCDateTime())
    valid_until: Mapped[datetime] = mapped_column(UTCDateTime())
    download_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    pdf_filename: Mapped[str] = mapped_column(String(64))


class QuoteCounter(Base):
    __tablename__ = "quote_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_value: Mapped[int] = mapped_column(Integer)
