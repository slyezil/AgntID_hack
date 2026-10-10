from __future__ import annotations

import sqlite3
from pathlib import Path


class ConnectorDatabase:
    """Connector-owned SQLite store. The public API must never import this module."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, isolation_level=None, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def migrate(self, schema_path: Path) -> None:
        with self.connect() as connection:
            connection.executescript(schema_path.read_text(encoding="utf-8"))
