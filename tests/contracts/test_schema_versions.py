from __future__ import annotations

from pathlib import Path

from pipeline.contracts.versioning import (
    REQUIRED_VERSION_KEYS,
    load_schema_versions,
    validate_version_map,
)


def test_schema_versions_file_exists() -> None:
    p = Path(__file__).resolve().parents[2] / "src" / "pipeline" / "contracts" / "schema_versions.json"
    assert p.is_file()


def test_expected_keys_present() -> None:
    v = load_schema_versions()
    for key in REQUIRED_VERSION_KEYS:
        assert key in v
        assert v[key]
        parts = str(v[key]).split(".")
        assert len(parts) >= 2


def test_validate_version_map_missing_key() -> None:
    issues = validate_version_map({"knowledge_schema_version": "1.0.0"}, strict=True)
    assert any("missing_schema_version_key" in i for i in issues)


def test_validate_version_map_mismatch_strict() -> None:
    frozen = load_schema_versions()
    bad = {k: frozen[k] for k in REQUIRED_VERSION_KEYS}
    bad["knowledge_schema_version"] = "0.0.0"
    issues = validate_version_map(bad, strict=True)
    assert any("schema_version_mismatch" in i for i in issues)


def test_validate_version_map_mismatch_lenient() -> None:
    frozen = load_schema_versions()
    bad = {k: frozen[k] for k in REQUIRED_VERSION_KEYS}
    bad["knowledge_schema_version"] = "0.0.0"
    issues = validate_version_map(bad, strict=False)
    assert not any("schema_version_mismatch" in i for i in issues)
