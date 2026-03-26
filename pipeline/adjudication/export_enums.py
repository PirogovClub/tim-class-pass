"""Stage 5.6 reviewed corpus export — stable identifiers and artifact names."""

from __future__ import annotations

from enum import Enum

# Bump when row shape or manifest contract changes incompatibly.
EXPORT_SCHEMA_VERSION = "export.v1"

# Exporter implementation version (not the tier policy version).
EXPORTER_VERSION = "stage5_6_exporter.v1"


class ExportArtifact(str, Enum):
    """Logical JSONL / JSON outputs under the export directory."""

    MANIFEST = "export_manifest.json"
    GOLD_RULES = "gold_rules.jsonl"
    GOLD_EVIDENCE_LINKS = "gold_evidence_links.jsonl"
    GOLD_RELATIONS = "gold_relations.jsonl"
    GOLD_CONCEPT_LINKS = "gold_concept_links.jsonl"
    GOLD_CANONICAL_FAMILIES = "gold_canonical_families.jsonl"
    SILVER_RULES = "silver_rules.jsonl"
    SILVER_EVIDENCE_LINKS = "silver_evidence_links.jsonl"
    SILVER_RELATIONS = "silver_relations.jsonl"
    SILVER_CONCEPT_LINKS = "silver_concept_links.jsonl"
    EVAL_RETRIEVAL_RULES = "eval_retrieval_rules.jsonl"
    EVAL_DUPLICATE_PAIRS = "eval_duplicate_pairs.jsonl"
    EVAL_EVIDENCE_SUPPORT = "eval_evidence_support.jsonl"
    EVAL_CANONICAL_ASSIGNMENTS = "eval_canonical_assignments.jsonl"


VOLATILE_MANIFEST_KEYS = frozenset({"export_timestamp"})
