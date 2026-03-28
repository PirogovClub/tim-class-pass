"""Load frozen schema / contract version strings (Stage 6.1)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parent / "schema_versions.json"

REQUIRED_VERSION_KEYS = frozenset(
    {
        "knowledge_schema_version",
        "rule_schema_version",
        "evidence_schema_version",
        "concept_graph_version",
    }
)


@lru_cache
def load_schema_versions() -> dict[str, str]:
    data = json.loads(_VERSION_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("schema_versions.json must be a JSON object")
    return {str(k): str(v) for k, v in data.items()}


def validate_version_map(versions: dict[str, str], *, strict: bool = True) -> list[str]:
    """Return issues if required keys missing or values unknown (vs frozen file)."""
    issues: list[str] = []
    frozen = load_schema_versions()
    for key in REQUIRED_VERSION_KEYS:
        if key not in versions:
            issues.append(f"missing_schema_version_key:{key}")
        elif strict and versions.get(key) != frozen.get(key):
            issues.append(f"schema_version_mismatch:{key}={versions.get(key)!r} expected {frozen.get(key)!r}")
    return issues
