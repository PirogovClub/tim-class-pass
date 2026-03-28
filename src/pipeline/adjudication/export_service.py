"""Read-only reviewed corpus export (Stage 5.6)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.adjudication.enums import CanonicalFamilyStatus, QualityTier, ReviewTargetType
from pipeline.adjudication.export_enums import EXPORT_SCHEMA_VERSION, EXPORTER_VERSION, ExportArtifact
from pipeline.adjudication.export_models import (
    EvalCanonicalAssignmentRow,
    EvalDuplicatePairRow,
    EvalEvidenceSupportRow,
    EvalRetrievalRuleRow,
    ExportManifest,
    GoldCanonicalFamilyExportRow,
    GoldLinkExportRow,
    GoldRuleExportRow,
    SilverLinkExportRow,
    SilverRuleExportRow,
)
from pipeline.adjudication.export_policy import (
    EXCLUDED_CATEGORIES,
    INCLUSION_RULES_GOLD,
    INCLUSION_RULES_SILVER,
    gold_non_rule_allowed,
    gold_rule_card_allowed,
    silver_non_rule_allowed,
    silver_rule_card_allowed,
    tier_policy_version_label,
)
from pipeline.adjudication.repository import AdjudicationRepository
from pipeline.adjudication.time_utils import utc_now_iso

if TYPE_CHECKING:
    from pipeline.explorer.service import ExplorerService


def _jsonl_dumps(obj: BaseModel | dict[str, Any]) -> str:
    if isinstance(obj, BaseModel):
        data = obj.model_dump(mode="json")
    else:
        data = obj
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _write_jsonl(path: Path, rows: list[Any]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(_jsonl_dumps(row))
            f.write("\n")
    return len(rows)


def _write_json(path: Path, obj: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _rule_lesson_and_evidence(
    explorer: ExplorerService | None, rule_id: str
) -> tuple[str | None, list[str], str | None]:
    if explorer is None:
        return None, [], "no_explorer_context"
    try:
        detail = explorer.get_rule_detail(rule_id)
        lesson = getattr(detail, "lesson_id", None)
        ev: list[str] = []
        for ref in detail.evidence_refs or []:
            did = getattr(ref, "doc_id", None)
            if did:
                ev.append(str(did))
        return (str(lesson) if lesson else None, ev, None)
    except Exception:
        return None, [], "explorer_fetch_failed"


@dataclass
class ExportStats:
    excluded: dict[str, int] = field(default_factory=dict)

    def add(self, key: str, n: int = 1) -> None:
        self.excluded[key] = self.excluded.get(key, 0) + n


def _manifest_db_counts(repo: AdjudicationRepository) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    decision_summary: dict[str, Any] = {}
    proposal_summary: dict[str, Any] = {}
    family_counts: dict[str, int] = {}
    with repo.connect() as conn:
        cur = conn.execute("SELECT COUNT(*) AS c FROM review_decisions")
        decision_summary["total_decisions"] = int(cur.fetchone()["c"])
        cur = conn.execute(
            """
            SELECT proposal_status, COUNT(*) AS c
            FROM adjudication_proposal
            GROUP BY proposal_status
            """
        )
        proposal_summary["by_status"] = {str(r["proposal_status"]): int(r["c"]) for r in cur.fetchall()}
        cur = conn.execute("SELECT COUNT(*) AS c FROM adjudication_proposal")
        proposal_summary["total_proposals"] = int(cur.fetchone()["c"])
        cur = conn.execute(
            "SELECT status, COUNT(*) AS c FROM canonical_rule_families GROUP BY status"
        )
        family_counts = {str(r["status"]): int(r["c"]) for r in cur.fetchall()}
    return decision_summary, proposal_summary, family_counts


def run_export(
    repo: AdjudicationRepository,
    output_dir: Path,
    *,
    tiers: set[QualityTier],
    corpus_index: CorpusTargetIndex | None,
    explorer: ExplorerService | None = None,
    write_eval_subsets: bool = True,
) -> ExportManifest:
    """Write gold/silver JSONL, manifest, and optional eval subsets. Read-only on adjudication DB."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = utc_now_iso()
    stats = ExportStats()

    gold_rules: list[GoldRuleExportRow] = []
    gold_ev: list[GoldLinkExportRow] = []
    gold_con: list[GoldLinkExportRow] = []
    gold_rel: list[GoldLinkExportRow] = []
    silver_rules: list[SilverRuleExportRow] = []
    silver_ev: list[SilverLinkExportRow] = []
    silver_con: list[SilverLinkExportRow] = []
    silver_rel: list[SilverLinkExportRow] = []

    if QualityTier.GOLD in tiers:
        for rec in repo.list_all_materialized_tiers(tier=QualityTier.GOLD):
            if rec.target_type == ReviewTargetType.RULE_CARD:
                st = repo.get_rule_card_state(rec.target_id)
                if not gold_rule_card_allowed(rec, st, corpus_index=corpus_index):
                    if st and st.is_unsupported:
                        stats.add("excluded_unsupported_rule_card")
                    elif st is None:
                        stats.add("excluded_missing_rule_state")
                    elif not rec.is_eligible_for_downstream_use:
                        stats.add("excluded_ineligible_materialized")
                    elif corpus_index is not None and not corpus_index.contains(
                        rec.target_type, rec.target_id
                    ):
                        stats.add("excluded_not_in_corpus")
                    else:
                        stats.add("excluded_other_gold_rule")
                    continue
                lesson_id, ev_ids, prov_note = _rule_lesson_and_evidence(explorer, rec.target_id)
                assert st is not None
                gold_rules.append(
                    GoldRuleExportRow(
                        tier="gold",
                        target_id=rec.target_id,
                        tier_policy_version=rec.policy_version,
                        materialized_resolved_at=rec.resolved_at,
                        lesson_id=lesson_id,
                        provenance_note=prov_note,
                        canonical_family_id=st.canonical_family_id,
                        duplicate_of_rule_id=st.duplicate_of_rule_id,
                        is_duplicate=bool(st.is_duplicate),
                        evidence_ref_ids=ev_ids,
                        latest_decision_type=(
                            st.latest_decision_type.value if st.latest_decision_type else None
                        ),
                    )
                )
            else:
                if not gold_non_rule_allowed(rec, corpus_index=corpus_index):
                    stats.add("excluded_gold_non_rule")
                    continue
                st_row = _link_state(repo, rec.target_type, rec.target_id)
                row = GoldLinkExportRow(
                    tier="gold",
                    target_type=rec.target_type.value,
                    target_id=rec.target_id,
                    tier_policy_version=rec.policy_version,
                    materialized_resolved_at=rec.resolved_at,
                    support_or_link_or_relation_status=_link_status_value(st_row),
                    latest_decision_type=_link_decision_type(st_row),
                )
                if rec.target_type == ReviewTargetType.EVIDENCE_LINK:
                    gold_ev.append(row)
                elif rec.target_type == ReviewTargetType.CONCEPT_LINK:
                    gold_con.append(row)
                else:
                    gold_rel.append(row)

    if QualityTier.SILVER in tiers:
        for rec in repo.list_all_materialized_tiers(tier=QualityTier.SILVER):
            if rec.target_type == ReviewTargetType.RULE_CARD:
                st = repo.get_rule_card_state(rec.target_id)
                if not silver_rule_card_allowed(rec, st, corpus_index=corpus_index):
                    stats.add("excluded_silver_rule_policy")
                    continue
                lesson_id, ev_ids, prov_note = _rule_lesson_and_evidence(explorer, rec.target_id)
                assert st is not None
                silver_rules.append(
                    SilverRuleExportRow(
                        tier="silver",
                        target_id=rec.target_id,
                        tier_policy_version=rec.policy_version,
                        materialized_resolved_at=rec.resolved_at,
                        lesson_id=lesson_id,
                        provenance_note=prov_note,
                        canonical_family_id=st.canonical_family_id,
                        duplicate_of_rule_id=st.duplicate_of_rule_id,
                        is_duplicate=bool(st.is_duplicate),
                        evidence_ref_ids=ev_ids,
                        latest_decision_type=(
                            st.latest_decision_type.value if st.latest_decision_type else None
                        ),
                    )
                )
            else:
                if not silver_non_rule_allowed(rec, corpus_index=corpus_index):
                    stats.add("excluded_silver_non_rule")
                    continue
                st_row = _link_state(repo, rec.target_type, rec.target_id)
                row = SilverLinkExportRow(
                    tier="silver",
                    target_type=rec.target_type.value,
                    target_id=rec.target_id,
                    tier_policy_version=rec.policy_version,
                    materialized_resolved_at=rec.resolved_at,
                    support_or_link_or_relation_status=_link_status_value(st_row),
                    latest_decision_type=_link_decision_type(st_row),
                )
                if rec.target_type == ReviewTargetType.EVIDENCE_LINK:
                    silver_ev.append(row)
                elif rec.target_type == ReviewTargetType.CONCEPT_LINK:
                    silver_con.append(row)
                else:
                    silver_rel.append(row)

    gold_rule_ids = {r.target_id for r in gold_rules}
    gold_families: list[GoldCanonicalFamilyExportRow] = []
    if QualityTier.GOLD in tiers:
        for fam in repo.list_canonical_families_by_status(CanonicalFamilyStatus.ACTIVE):
            members = repo.list_family_members(fam.family_id)
            mids = [m.rule_id for m in members]
            if any(rid in gold_rule_ids for rid in mids):
                gold_families.append(
                    GoldCanonicalFamilyExportRow(
                        family_id=fam.family_id,
                        canonical_title=fam.canonical_title,
                        family_status=fam.status.value,
                        member_rule_ids=sorted(mids),
                        tier_policy_version=tier_policy_version_label(),
                    )
                )

    files_written: list[str] = []
    exported_rows: dict[str, int] = {}

    if QualityTier.GOLD in tiers:
        n = _write_jsonl(output_dir / ExportArtifact.GOLD_RULES.value, gold_rules)
        exported_rows[ExportArtifact.GOLD_RULES.value] = n
        files_written.append(ExportArtifact.GOLD_RULES.value)
        n = _write_jsonl(output_dir / ExportArtifact.GOLD_EVIDENCE_LINKS.value, gold_ev)
        exported_rows[ExportArtifact.GOLD_EVIDENCE_LINKS.value] = n
        files_written.append(ExportArtifact.GOLD_EVIDENCE_LINKS.value)
        n = _write_jsonl(output_dir / ExportArtifact.GOLD_CONCEPT_LINKS.value, gold_con)
        exported_rows[ExportArtifact.GOLD_CONCEPT_LINKS.value] = n
        files_written.append(ExportArtifact.GOLD_CONCEPT_LINKS.value)
        n = _write_jsonl(output_dir / ExportArtifact.GOLD_RELATIONS.value, gold_rel)
        exported_rows[ExportArtifact.GOLD_RELATIONS.value] = n
        files_written.append(ExportArtifact.GOLD_RELATIONS.value)
        n = _write_jsonl(output_dir / ExportArtifact.GOLD_CANONICAL_FAMILIES.value, gold_families)
        exported_rows[ExportArtifact.GOLD_CANONICAL_FAMILIES.value] = n
        files_written.append(ExportArtifact.GOLD_CANONICAL_FAMILIES.value)

    if QualityTier.SILVER in tiers:
        n = _write_jsonl(output_dir / ExportArtifact.SILVER_RULES.value, silver_rules)
        exported_rows[ExportArtifact.SILVER_RULES.value] = n
        files_written.append(ExportArtifact.SILVER_RULES.value)
        n = _write_jsonl(output_dir / ExportArtifact.SILVER_EVIDENCE_LINKS.value, silver_ev)
        exported_rows[ExportArtifact.SILVER_EVIDENCE_LINKS.value] = n
        files_written.append(ExportArtifact.SILVER_EVIDENCE_LINKS.value)
        n = _write_jsonl(output_dir / ExportArtifact.SILVER_CONCEPT_LINKS.value, silver_con)
        exported_rows[ExportArtifact.SILVER_CONCEPT_LINKS.value] = n
        files_written.append(ExportArtifact.SILVER_CONCEPT_LINKS.value)
        n = _write_jsonl(output_dir / ExportArtifact.SILVER_RELATIONS.value, silver_rel)
        exported_rows[ExportArtifact.SILVER_RELATIONS.value] = n
        files_written.append(ExportArtifact.SILVER_RELATIONS.value)

    if write_eval_subsets and QualityTier.GOLD in tiers:
        eval_retrieval = [
            EvalRetrievalRuleRow(target_id=r.target_id, lesson_id=r.lesson_id) for r in gold_rules
        ]
        eval_dups: list[EvalDuplicatePairRow] = []
        seen: set[tuple[str, str]] = set()
        for r in gold_rules:
            if r.is_duplicate and r.duplicate_of_rule_id:
                a, b = sorted((r.target_id, r.duplicate_of_rule_id))
                key = (a, b)
                if key not in seen:
                    seen.add(key)
                    eval_dups.append(
                        EvalDuplicatePairRow(
                            rule_id=r.target_id, duplicate_of_rule_id=r.duplicate_of_rule_id
                        )
                    )
        eval_evi = [
            EvalEvidenceSupportRow(
                evidence_link_target_id=r.target_id,
                support_status=r.support_or_link_or_relation_status,
            )
            for r in gold_ev
        ]
        eval_canon: list[EvalCanonicalAssignmentRow] = []
        for r in gold_rules:
            if r.canonical_family_id:
                eval_canon.append(
                    EvalCanonicalAssignmentRow(
                        rule_id=r.target_id, canonical_family_id=r.canonical_family_id
                    )
                )
        _write_jsonl(output_dir / ExportArtifact.EVAL_RETRIEVAL_RULES.value, eval_retrieval)
        files_written.append(ExportArtifact.EVAL_RETRIEVAL_RULES.value)
        exported_rows[ExportArtifact.EVAL_RETRIEVAL_RULES.value] = len(eval_retrieval)
        _write_jsonl(output_dir / ExportArtifact.EVAL_DUPLICATE_PAIRS.value, eval_dups)
        files_written.append(ExportArtifact.EVAL_DUPLICATE_PAIRS.value)
        exported_rows[ExportArtifact.EVAL_DUPLICATE_PAIRS.value] = len(eval_dups)
        _write_jsonl(output_dir / ExportArtifact.EVAL_EVIDENCE_SUPPORT.value, eval_evi)
        files_written.append(ExportArtifact.EVAL_EVIDENCE_SUPPORT.value)
        exported_rows[ExportArtifact.EVAL_EVIDENCE_SUPPORT.value] = len(eval_evi)
        _write_jsonl(output_dir / ExportArtifact.EVAL_CANONICAL_ASSIGNMENTS.value, eval_canon)
        files_written.append(ExportArtifact.EVAL_CANONICAL_ASSIGNMENTS.value)
        exported_rows[ExportArtifact.EVAL_CANONICAL_ASSIGNMENTS.value] = len(eval_canon)

    decision_summary, proposal_summary, family_counts = _manifest_db_counts(repo)
    raw_counts = repo.materialized_tier_counts()
    by_tt: dict[str, dict[str, int]] = {
        tt: dict(tiers_d) for tt, tiers_d in raw_counts["by_target_type"].items()
    }

    inclusion_rules: list[str] = []
    if QualityTier.GOLD in tiers:
        inclusion_rules.extend(INCLUSION_RULES_GOLD)
    if QualityTier.SILVER in tiers:
        inclusion_rules.extend(INCLUSION_RULES_SILVER)

    files_written_sorted = sorted(files_written)
    manifest = ExportManifest(
        export_timestamp=ts,
        export_schema_version=EXPORT_SCHEMA_VERSION,
        exporter_version=EXPORTER_VERSION,
        included_tiers=[t.value for t in sorted(tiers, key=lambda x: x.value)],
        inclusion_rules=inclusion_rules,
        excluded_categories=list(EXCLUDED_CATEGORIES),
        source_artifact_versions={
            "tier_policy": tier_policy_version_label(),
            "export_schema": EXPORT_SCHEMA_VERSION,
            "exporter": EXPORTER_VERSION,
        },
        decision_coverage_summary=decision_summary,
        proposal_coverage_summary=proposal_summary,
        canonical_family_counts=family_counts,
        counts_by_target_type=by_tt,
        counts_by_tier_in_db=dict(raw_counts["totals_by_tier"]),
        exported_rows_by_file=exported_rows,
        excluded_row_counts=dict(stats.excluded),
        files_written=sorted({*files_written_sorted, ExportArtifact.MANIFEST.value}),
    )
    _write_json(output_dir / ExportArtifact.MANIFEST.value, manifest)
    return manifest


def _link_state(repo: AdjudicationRepository, tt: ReviewTargetType, tid: str) -> Any:
    if tt == ReviewTargetType.EVIDENCE_LINK:
        return repo.get_evidence_link_state(tid)
    if tt == ReviewTargetType.CONCEPT_LINK:
        return repo.get_concept_link_state(tid)
    return repo.get_related_rule_relation_state(tid)


def _link_status_value(st: Any) -> str | None:
    if st is None:
        return None
    for attr in ("support_status", "link_status", "relation_status"):
        v = getattr(st, attr, None)
        if v is not None:
            return v.value if hasattr(v, "value") else str(v)
    return None


def _link_decision_type(st: Any) -> str | None:
    if st is None:
        return None
    _ = st
    return None


def normalize_export_for_repro_compare(output_dir: Path, *, tiers: set[QualityTier]) -> str:
    """Concatenate normalized JSONL (sorted lines) for hashing; omit manifest timestamp."""
    parts: list[str] = []
    root = Path(output_dir)
    artifacts: list[ExportArtifact] = []
    if QualityTier.GOLD in tiers:
        artifacts.extend(
            [
                ExportArtifact.GOLD_RULES,
                ExportArtifact.GOLD_EVIDENCE_LINKS,
                ExportArtifact.GOLD_CONCEPT_LINKS,
                ExportArtifact.GOLD_RELATIONS,
                ExportArtifact.GOLD_CANONICAL_FAMILIES,
            ]
        )
    if QualityTier.SILVER in tiers:
        artifacts.extend(
            [
                ExportArtifact.SILVER_RULES,
                ExportArtifact.SILVER_EVIDENCE_LINKS,
                ExportArtifact.SILVER_CONCEPT_LINKS,
                ExportArtifact.SILVER_RELATIONS,
            ]
        )
    for art in (
        ExportArtifact.EVAL_RETRIEVAL_RULES,
        ExportArtifact.EVAL_DUPLICATE_PAIRS,
        ExportArtifact.EVAL_EVIDENCE_SUPPORT,
        ExportArtifact.EVAL_CANONICAL_ASSIGNMENTS,
    ):
        p = root / art.value
        if p.is_file():
            artifacts.append(art)
    for art in artifacts:
        p = root / art.value
        if not p.is_file():
            continue
        lines = sorted(p.read_text(encoding="utf-8").splitlines())
        parts.append(art.value + "\n" + "\n".join(lines))
    mpath = root / ExportArtifact.MANIFEST.value
    if mpath.is_file():
        m = json.loads(mpath.read_text(encoding="utf-8"))
        m.pop("export_timestamp", None)
        parts.append("manifest_normalized\n" + json.dumps(m, sort_keys=True, separators=(",", ":")))
    return "\n\n".join(parts)
