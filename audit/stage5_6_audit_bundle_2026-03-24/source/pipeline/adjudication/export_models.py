"""Pydantic models for export rows and manifest (Stage 5.6)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from pipeline.adjudication.export_enums import EXPORT_SCHEMA_VERSION, EXPORTER_VERSION


class BaseExportRow(BaseModel):
    """Common fields on every JSONL export row."""

    schema_version: str = Field(default=EXPORT_SCHEMA_VERSION)
    exporter_version: str = Field(default=EXPORTER_VERSION)
    tier: Literal["gold", "silver"]
    target_type: str
    target_id: str
    tier_policy_version: str
    materialized_resolved_at: str
    lesson_id: str | None = None
    provenance_note: str | None = Field(
        default=None,
        description="Optional human note (e.g. lesson_id unavailable without explorer).",
    )


class GoldRuleExportRow(BaseExportRow):
    tier: Literal["gold"] = "gold"
    target_type: Literal["rule_card"] = "rule_card"
    canonical_family_id: str | None = None
    duplicate_of_rule_id: str | None = None
    is_duplicate: bool = False
    evidence_ref_ids: list[str] = Field(default_factory=list)
    latest_decision_type: str | None = None


class SilverRuleExportRow(BaseExportRow):
    tier: Literal["silver"] = "silver"
    target_type: Literal["rule_card"] = "rule_card"
    canonical_family_id: str | None = None
    duplicate_of_rule_id: str | None = None
    is_duplicate: bool = False
    evidence_ref_ids: list[str] = Field(default_factory=list)
    latest_decision_type: str | None = None


class GoldLinkExportRow(BaseExportRow):
    tier: Literal["gold"] = "gold"
    support_or_link_or_relation_status: str | None = None
    latest_decision_type: str | None = None


class SilverLinkExportRow(BaseExportRow):
    tier: Literal["silver"] = "silver"
    support_or_link_or_relation_status: str | None = None
    latest_decision_type: str | None = None


class GoldCanonicalFamilyExportRow(BaseModel):
    schema_version: str = Field(default=EXPORT_SCHEMA_VERSION)
    exporter_version: str = Field(default=EXPORTER_VERSION)
    tier: Literal["gold"] = "gold"
    artifact_kind: Literal["canonical_rule_family"] = "canonical_rule_family"
    family_id: str
    canonical_title: str
    family_status: str
    member_rule_ids: list[str] = Field(default_factory=list)
    tier_policy_version: str


class EvalRetrievalRuleRow(BaseModel):
    """High-trust rule targets for retrieval-style eval (derived from gold rule export)."""

    schema_version: str = Field(default=EXPORT_SCHEMA_VERSION)
    subset: Literal["eval_retrieval_rules"] = "eval_retrieval_rules"
    target_id: str
    lesson_id: str | None = None


class EvalDuplicatePairRow(BaseModel):
    schema_version: str = Field(default=EXPORT_SCHEMA_VERSION)
    subset: Literal["eval_duplicate_pairs"] = "eval_duplicate_pairs"
    rule_id: str
    duplicate_of_rule_id: str


class EvalEvidenceSupportRow(BaseModel):
    schema_version: str = Field(default=EXPORT_SCHEMA_VERSION)
    subset: Literal["eval_evidence_support"] = "eval_evidence_support"
    evidence_link_target_id: str
    support_status: str | None = None


class EvalCanonicalAssignmentRow(BaseModel):
    schema_version: str = Field(default=EXPORT_SCHEMA_VERSION)
    subset: Literal["eval_canonical_assignments"] = "eval_canonical_assignments"
    rule_id: str
    canonical_family_id: str


class ExportManifest(BaseModel):
    export_timestamp: str
    export_schema_version: str = EXPORT_SCHEMA_VERSION
    exporter_version: str = EXPORTER_VERSION
    included_tiers: list[str]
    inclusion_rules: list[str]
    excluded_categories: list[str]
    source_artifact_versions: dict[str, str]
    decision_coverage_summary: dict[str, Any]
    proposal_coverage_summary: dict[str, Any]
    canonical_family_counts: dict[str, int]
    counts_by_target_type: dict[str, dict[str, int]]
    counts_by_tier_in_db: dict[str, int]
    exported_rows_by_file: dict[str, int]
    excluded_row_counts: dict[str, int]
    files_written: list[str]
