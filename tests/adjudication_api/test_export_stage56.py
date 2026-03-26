"""Stage 5.6 reviewed corpus export — gold/silver, manifest, validation, reproducibility, eval subsets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    DecisionType,
    MembershipRole,
    QualityTier,
    ReviewTargetType,
    ReviewerKind,
    RuleCardCoarseStatus,
)
from pipeline.adjudication.export_enums import ExportArtifact
from pipeline.adjudication.export_models import ExportManifest
from pipeline.adjudication.export_service import normalize_export_for_repro_compare, run_export
from pipeline.adjudication.export_validation import validate_export_dir
from pipeline.adjudication.models import NewCanonicalFamily, NewMembership, NewReviewer
from pipeline.adjudication.repository import AdjudicationRepository
from pipeline.adjudication.time_utils import utc_now_iso

from tests.adjudication_api.corpus_index_fixtures import STANDARD_TEST_CORPUS_INDEX


def _upsert_rule_state_and_tier(
    repo: AdjudicationRepository,
    rule_id: str,
    *,
    tier: QualityTier,
    unsupported: bool = False,
    is_duplicate: bool = False,
    duplicate_of: str | None = None,
    family_id: str | None = None,
) -> None:
    now = utc_now_iso()
    with repo.connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO rule_card_reviewed_state (
                target_id, current_status, latest_decision_type, canonical_family_id,
                is_duplicate, duplicate_of_rule_id, is_ambiguous, is_deferred, is_unsupported,
                last_reviewed_at, last_reviewer_id, last_decision_id, notes_summary
            ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?, 'u1', 'd-test', NULL)
            """,
            (
                rule_id,
                RuleCardCoarseStatus.APPROVED.value,
                DecisionType.APPROVE.value,
                family_id,
                1 if is_duplicate else 0,
                duplicate_of,
                1 if unsupported else 0,
                now,
            ),
        )
        eligible = 1 if tier in (QualityTier.GOLD, QualityTier.SILVER) else 0
        conn.execute(
            """
            INSERT OR REPLACE INTO materialized_tier_state (
                target_type, target_id, tier, tier_reasons_json, blocker_codes_json,
                is_eligible, is_promotable_to_gold, resolved_at, policy_version
            ) VALUES (?, ?, ?, '[]', '[]', ?, 0, ?, 'export_test')
            """,
            (ReviewTargetType.RULE_CARD.value, rule_id, tier.value, eligible, now),
        )


def _upsert_evidence_gold(repo: AdjudicationRepository, target_id: str) -> None:
    now = utc_now_iso()
    with repo.connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO evidence_link_reviewed_state (
                target_id, support_status, last_reviewed_at, last_reviewer_id, last_decision_id
            ) VALUES (?, 'strong', ?, 'u1', 'd-ev')
            """,
            (target_id, now),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO materialized_tier_state (
                target_type, target_id, tier, tier_reasons_json, blocker_codes_json,
                is_eligible, is_promotable_to_gold, resolved_at, policy_version
            ) VALUES (?, ?, 'gold', '[]', '[]', 1, 0, ?, 'export_test')
            """,
            (ReviewTargetType.EVIDENCE_LINK.value, target_id, now),
        )


@pytest.fixture
def export_repo(tmp_path: Path) -> AdjudicationRepository:
    db = tmp_path / "export56.sqlite"
    initialize_adjudication_storage(db)
    r = AdjudicationRepository(db)
    r.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="T"))
    return r


def test_gold_export_rules_schema_and_tier(export_repo: AdjudicationRepository, tmp_path: Path) -> None:
    rid = "rule:http:1"
    _upsert_rule_state_and_tier(export_repo, rid, tier=QualityTier.GOLD)
    out = tmp_path / "exp1"
    man = run_export(
        export_repo,
        out,
        tiers={QualityTier.GOLD},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=True,
    )
    assert man.exported_rows_by_file[ExportArtifact.GOLD_RULES.value] == 1
    line = (out / ExportArtifact.GOLD_RULES.value).read_text(encoding="utf-8").strip()
    row = json.loads(line)
    assert row["tier"] == "gold"
    assert row["target_type"] == "rule_card"
    assert row["target_id"] == rid
    assert row["schema_version"]


def test_gold_excludes_unsupported_rule(export_repo: AdjudicationRepository, tmp_path: Path) -> None:
    rid = "rule:http:1"
    _upsert_rule_state_and_tier(export_repo, rid, tier=QualityTier.GOLD, unsupported=True)
    out = tmp_path / "exp2"
    run_export(
        export_repo,
        out,
        tiers={QualityTier.GOLD},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=False,
    )
    assert (out / ExportArtifact.GOLD_RULES.value).read_text(encoding="utf-8").strip() == ""


def test_silver_separate_from_gold(export_repo: AdjudicationRepository, tmp_path: Path) -> None:
    _upsert_rule_state_and_tier(export_repo, "rule:http:1", tier=QualityTier.GOLD)
    _upsert_rule_state_and_tier(export_repo, "rule:a:1", tier=QualityTier.SILVER)
    out = tmp_path / "exp3"
    run_export(
        export_repo,
        out,
        tiers={QualityTier.GOLD, QualityTier.SILVER},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=False,
    )
    g = [json.loads(ln) for ln in (out / ExportArtifact.GOLD_RULES.value).read_text().splitlines() if ln.strip()]
    s = [json.loads(ln) for ln in (out / ExportArtifact.SILVER_RULES.value).read_text().splitlines() if ln.strip()]
    assert all(r["tier"] == "gold" for r in g)
    assert all(r["tier"] == "silver" for r in s)
    g_ids = {r["target_id"] for r in g}
    s_ids = {r["target_id"] for r in s}
    assert not (g_ids & s_ids)


def test_manifest_counts_match_files(export_repo: AdjudicationRepository, tmp_path: Path) -> None:
    _upsert_rule_state_and_tier(export_repo, "rule:http:1", tier=QualityTier.GOLD)
    _upsert_evidence_gold(export_repo, "ev:1")
    out = tmp_path / "exp4"
    run_export(
        export_repo,
        out,
        tiers={QualityTier.GOLD},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=True,
    )
    raw = json.loads((out / ExportArtifact.MANIFEST.value).read_text(encoding="utf-8"))
    m = ExportManifest.model_validate(raw)
    for fname, expected in m.exported_rows_by_file.items():
        lines = [ln for ln in (out / fname).read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == expected, (fname, len(lines), expected)


def test_validation_passes(export_repo: AdjudicationRepository, tmp_path: Path) -> None:
    _upsert_rule_state_and_tier(export_repo, "rule:http:1", tier=QualityTier.GOLD)
    out = tmp_path / "exp5"
    run_export(
        export_repo,
        out,
        tiers={QualityTier.GOLD},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=True,
    )
    res = validate_export_dir(out)
    assert res.ok, res.errors


def test_validation_fails_wrong_tier_in_gold_file(export_repo: AdjudicationRepository, tmp_path: Path) -> None:
    _upsert_rule_state_and_tier(export_repo, "rule:http:1", tier=QualityTier.GOLD)
    out = tmp_path / "exp6"
    run_export(
        export_repo,
        out,
        tiers={QualityTier.GOLD},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=False,
    )
    path = out / ExportArtifact.GOLD_RULES.value
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    row["tier"] = "silver"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    raw = json.loads((out / ExportArtifact.MANIFEST.value).read_text(encoding="utf-8"))
    m = ExportManifest.model_validate(raw)
    m2 = m.model_copy(update={"exported_rows_by_file": {**m.exported_rows_by_file, ExportArtifact.GOLD_RULES.value: 1}})
    (out / ExportArtifact.MANIFEST.value).write_text(
        json.dumps(m2.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    res = validate_export_dir(out)
    assert not res.ok
    assert any("expected tier gold" in e for e in res.errors)


def test_reproducibility_normalized(export_repo: AdjudicationRepository, tmp_path: Path) -> None:
    _upsert_rule_state_and_tier(export_repo, "rule:http:1", tier=QualityTier.GOLD)
    out1 = tmp_path / "r1"
    out2 = tmp_path / "r2"
    run_export(
        export_repo,
        out1,
        tiers={QualityTier.GOLD},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=True,
    )
    run_export(
        export_repo,
        out2,
        tiers={QualityTier.GOLD},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=True,
    )
    n1 = normalize_export_for_repro_compare(out1, tiers={QualityTier.GOLD})
    n2 = normalize_export_for_repro_compare(out2, tiers={QualityTier.GOLD})
    assert n1 == n2


def test_eval_subsets_structure(export_repo: AdjudicationRepository, tmp_path: Path) -> None:
    _upsert_rule_state_and_tier(export_repo, "rule:b:1", tier=QualityTier.GOLD)
    _upsert_rule_state_and_tier(
        export_repo,
        "rule:http:1",
        tier=QualityTier.GOLD,
        is_duplicate=True,
        duplicate_of="rule:b:1",
        family_id="fam-x",
    )
    # family must exist for canonical assignment to be meaningful; membership links rule
    export_repo.create_canonical_family(
        NewCanonicalFamily(
            family_id="fam-x",
            canonical_title="T",
            status=CanonicalFamilyStatus.ACTIVE,
            created_by="u1",
        )
    )
    export_repo.add_rule_to_family(
        NewMembership(family_id="fam-x", rule_id="rule:http:1", membership_role=MembershipRole.MEMBER)
    )
    _upsert_evidence_gold(export_repo, "ev:1")
    out = tmp_path / "evs"
    run_export(
        export_repo,
        out,
        tiers={QualityTier.GOLD},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=True,
    )
    for art in (
        ExportArtifact.EVAL_RETRIEVAL_RULES,
        ExportArtifact.EVAL_DUPLICATE_PAIRS,
        ExportArtifact.EVAL_EVIDENCE_SUPPORT,
        ExportArtifact.EVAL_CANONICAL_ASSIGNMENTS,
    ):
        p = out / art.value
        assert p.is_file()
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) >= 1 or art == ExportArtifact.EVAL_DUPLICATE_PAIRS
    dup = json.loads((out / ExportArtifact.EVAL_DUPLICATE_PAIRS.value).read_text().splitlines()[0])
    assert dup["subset"] == "eval_duplicate_pairs"
    v = validate_export_dir(out)
    assert v.ok, v.errors


def test_validate_with_db_path(export_repo: AdjudicationRepository, tmp_path: Path) -> None:
    _upsert_rule_state_and_tier(export_repo, "rule:http:1", tier=QualityTier.GOLD)
    out = tmp_path / "dbval"
    run_export(
        export_repo,
        out,
        tiers={QualityTier.GOLD},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=True,
    )
    res = validate_export_dir(out, db_path=export_repo.db_path)
    assert res.ok, res.errors


def test_strict_provenance_fails_without_lesson(export_repo: AdjudicationRepository, tmp_path: Path) -> None:
    _upsert_rule_state_and_tier(export_repo, "rule:http:1", tier=QualityTier.GOLD)
    out = tmp_path / "prov"
    run_export(
        export_repo,
        out,
        tiers={QualityTier.GOLD},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=False,
    )
    res = validate_export_dir(out, strict_provenance=True)
    assert not res.ok
    assert any("lesson_id" in e for e in res.errors)


def test_validation_fails_duplicate_target_id_in_file(export_repo: AdjudicationRepository, tmp_path: Path) -> None:
    _upsert_rule_state_and_tier(export_repo, "rule:http:1", tier=QualityTier.GOLD)
    out = tmp_path / "duprow"
    run_export(
        export_repo,
        out,
        tiers={QualityTier.GOLD},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=False,
    )
    path = out / ExportArtifact.GOLD_RULES.value
    line = path.read_text(encoding="utf-8").strip()
    path.write_text(line + "\n" + line + "\n", encoding="utf-8")
    raw = json.loads((out / ExportArtifact.MANIFEST.value).read_text(encoding="utf-8"))
    m = ExportManifest.model_validate(raw)
    m2 = m.model_copy(
        update={"exported_rows_by_file": {**m.exported_rows_by_file, ExportArtifact.GOLD_RULES.value: 2}}
    )
    (out / ExportArtifact.MANIFEST.value).write_text(
        json.dumps(m2.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    res = validate_export_dir(out)
    assert not res.ok
    assert any("duplicate target" in e for e in res.errors)


def test_validation_fails_broken_canonical_family_reference(
    export_repo: AdjudicationRepository, tmp_path: Path
) -> None:
    _upsert_rule_state_and_tier(export_repo, "rule:http:1", tier=QualityTier.GOLD)
    out = tmp_path / "badfam"
    run_export(
        export_repo,
        out,
        tiers={QualityTier.GOLD},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=False,
    )
    path = out / ExportArtifact.GOLD_RULES.value
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    row["canonical_family_id"] = "no-such-family-in-export"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    res = validate_export_dir(out)
    assert not res.ok
    assert any("not found in gold_canonical_families" in e for e in res.errors)


def test_canonical_family_export_row(export_repo: AdjudicationRepository, tmp_path: Path) -> None:
    rid = "rule:http:1"
    _upsert_rule_state_and_tier(export_repo, rid, tier=QualityTier.GOLD, family_id="fam-g")
    export_repo.create_canonical_family(
        NewCanonicalFamily(
            family_id="fam-g",
            canonical_title="Fam",
            status=CanonicalFamilyStatus.ACTIVE,
            created_by="u1",
        )
    )
    export_repo.add_rule_to_family(
        NewMembership(family_id="fam-g", rule_id=rid, membership_role=MembershipRole.MEMBER)
    )
    out = tmp_path / "fam"
    run_export(
        export_repo,
        out,
        tiers={QualityTier.GOLD},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=False,
    )
    lines = [ln for ln in (out / ExportArtifact.GOLD_CANONICAL_FAMILIES.value).read_text().splitlines() if ln.strip()]
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["family_id"] == "fam-g"
    assert rid in row["member_rule_ids"]
