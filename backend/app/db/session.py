"""Engine and session factory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

SQLITE_BUSY_TIMEOUT_MS = 30_000


class Database:
    def __init__(self, url: str) -> None:
        parsed = make_url(url)
        connect_args: dict[str, Any] = {}
        if parsed.get_backend_name() == "sqlite":
            connect_args["check_same_thread"] = False
            if parsed.database and parsed.database != ":memory:":
                Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)

        self.engine: Engine = create_engine(url, connect_args=connect_args)
        if parsed.get_backend_name() == "sqlite":
            event.listen(self.engine, "connect", _sqlite_pragmas)
        self.sessionmaker: sessionmaker[Session] = sessionmaker(self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def dispose(self) -> None:
        self.engine.dispose()


def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    # Concurrent writers wait for the lock instead of failing immediately.
    cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()
