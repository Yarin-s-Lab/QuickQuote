"""PDF storage. Paths are built on the server from the internal UUID only (SPEC section 7)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path


class InvalidStoragePathError(ValueError):
    pass


class Storage:
    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve()

    @staticmethod
    def filename_for(quote_id: str) -> str:
        try:
            parsed = uuid.UUID(quote_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise InvalidStoragePathError("quote id must be a UUID") from exc
        if str(parsed) != quote_id:
            raise InvalidStoragePathError("quote id must be a canonical UUID")
        return f"{parsed}.pdf"

    def path_for(self, quote_id: str) -> Path:
        path = (self.root / self.filename_for(quote_id)).resolve()
        if not path.is_relative_to(self.root):
            raise InvalidStoragePathError("path escapes the storage directory")
        return path

    def save(self, quote_id: str, data: bytes) -> Path:
        """Write atomically: a crash never leaves a half-written PDF under the final name."""
        path = self.path_for(quote_id)
        tmp = path.with_name(path.name + ".tmp")
        try:
            tmp.write_bytes(data)
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
        return path

    def delete(self, quote_id: str) -> None:
        self.path_for(quote_id).unlink(missing_ok=True)
