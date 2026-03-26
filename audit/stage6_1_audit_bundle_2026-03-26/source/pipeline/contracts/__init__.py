"""Frozen lesson contract v1: versions, registry, corpus validation (Stage 6.1)."""

from __future__ import annotations

from pipeline.contracts.contract_models import (
    ARTIFACT_KEY_BY_FILENAME,
    OPTIONAL_MARKDOWN_ARTIFACTS,
    REQUIRED_ARTIFACT_FILENAMES,
)
from pipeline.contracts.corpus_validator import (
    lesson_record_from_registry_entry,
    validate_corpus,
    validate_intermediate_dir,
    validate_lesson_record_v1,
    validate_registry_v1,
)
from pipeline.contracts.lesson_registry import (
    build_registry_v1,
    load_registry_v1,
    save_registry_v1,
)
from pipeline.contracts.registry_models import (
    LessonArtifacts,
    LessonRegistryEntryV1,
    LessonRegistryFileV1,
)
from pipeline.contracts.versioning import (
    REQUIRED_VERSION_KEYS,
    load_schema_versions,
    validate_version_map,
)

__all__ = [
    "ARTIFACT_KEY_BY_FILENAME",
    "OPTIONAL_MARKDOWN_ARTIFACTS",
    "REQUIRED_ARTIFACT_FILENAMES",
    "LessonArtifacts",
    "LessonRegistryEntryV1",
    "LessonRegistryFileV1",
    "REQUIRED_VERSION_KEYS",
    "build_registry_v1",
    "load_registry_v1",
    "load_schema_versions",
    "save_registry_v1",
    "lesson_record_from_registry_entry",
    "validate_corpus",
    "validate_intermediate_dir",
    "validate_lesson_record_v1",
    "validate_registry_v1",
    "validate_version_map",
]
