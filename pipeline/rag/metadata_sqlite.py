"""SQLite metadata mirror for Stage 6.3 retrieval units (portable alternative to Postgres)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.rag.store import InMemoryDocStore


def write_retrieval_metadata_sqlite(
    store: InMemoryDocStore,
    path: Path,
    *,
    corpus_contract_version: str,
    schema_versions_blob: dict[str, Any] | None,
    embedding_model_version: str,
) -> None:
    """Persist one row per retrieval doc with full JSON payload for audit/SQL queries."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    indexed_at = datetime.now(timezone.utc).isoformat()
    schema_json = json.dumps(schema_versions_blob or {}, ensure_ascii=False)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            """
            CREATE TABLE retrieval_unit (
                doc_id TEXT PRIMARY KEY,
                unit_type TEXT NOT NULL,
                lesson_id TEXT,
                corpus_contract_version TEXT,
                schema_versions_json TEXT,
                embedding_model_version TEXT,
                indexed_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX idx_retrieval_unit_type ON retrieval_unit(unit_type)")
        conn.execute("CREATE INDEX idx_retrieval_lesson ON retrieval_unit(lesson_id)")
        for doc in store.get_all():
            conn.execute(
                """
                INSERT INTO retrieval_unit (
                    doc_id, unit_type, lesson_id, corpus_contract_version,
                    schema_versions_json, embedding_model_version, indexed_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc["doc_id"],
                    doc.get("unit_type", ""),
                    doc.get("lesson_id") or "",
                    corpus_contract_version,
                    schema_json,
                    embedding_model_version,
                    indexed_at,
                    json.dumps(doc, ensure_ascii=False),
                ),
            )
        conn.commit()
    finally:
        conn.close()
