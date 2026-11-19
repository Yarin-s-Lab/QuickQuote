"""Runtime settings, read from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

# Dates on the quote and the year in the quote number follow Israel time.
LOCAL_TZ = ZoneInfo("Asia/Jerusalem")
QUOTE_VALIDITY_DAYS = 30


@dataclass(frozen=True)
class Settings:
    database_url: str
    storage_dir: Path
    frontend_origin: str


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("DATABASE_URL", "sqlite:///./data/quickquote.db"),
        storage_dir=Path(os.environ.get("STORAGE_DIR", "./storage")),
        frontend_origin=os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173"),
    )
