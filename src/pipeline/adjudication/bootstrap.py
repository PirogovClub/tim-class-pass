"""Idempotent SQLite schema initialization for adjudication."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from pipeline.adjudication.storage import ADJUDICATION_SCHEMA_SQL

logger = logging.getLogger(__name__)


def initialize_adjudication_storage(db_path: str | Path) -> None:
    """Create adjudication tables if missing. Safe to call repeatedly. No import side effects."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(ADJUDICATION_SCHEMA_SQL)
        conn.commit()
        logger.info("Adjudication storage initialized at %s", path)
    finally:
        conn.close()
