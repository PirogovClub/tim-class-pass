"""One-off: build minimal adjudication DB + export into audit bundle examples/."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    MembershipRole,
    QualityTier,
    ReviewerKind,
)
from pipeline.adjudication.export_validation import validate_export_dir
from pipeline.adjudication.models import NewCanonicalFamily, NewMembership, NewReviewer
from pipeline.adjudication.repository import AdjudicationRepository
from pipeline.adjudication.time_utils import utc_now_iso
from pipeline.adjudication.export_service import run_export

from tests.adjudication_api.corpus_index_fixtures import STANDARD_TEST_CORPUS_INDEX


def main() -> None:
    examples = ROOT / "audit" / "stage5_6_audit_bundle_2026-03-24" / "examples"
    if examples.exists():
        shutil.rmtree(examples)
    examples.mkdir(parents=True)

    db = ROOT / "audit" / "stage5_6_audit_bundle_2026-03-24" / "_sample.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    initialize_adjudication_storage(db)
    repo = AdjudicationRepository(db)
    repo.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="Audit"))

    now = utc_now_iso()
    rid = "rule:http:1"
    with repo.connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO rule_card_reviewed_state (
                target_id, current_status, latest_decision_type, canonical_family_id,
                is_duplicate, duplicate_of_rule_id, is_ambiguous, is_deferred, is_unsupported,
                last_reviewed_at, last_reviewer_id, last_decision_id, notes_summary
            ) VALUES (?, 'approved', 'approve', 'fam-audit', 1, 'rule:b:1', 0, 0, 0, ?, 'u1', 'd1', NULL)
            """,
            (rid, now),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO materialized_tier_state (
                target_type, target_id, tier, tier_reasons_json, blocker_codes_json,
                is_eligible, is_promotable_to_gold, resolved_at, policy_version
            ) VALUES ('rule_card', ?, 'gold', '[]', '[]', 1, 0, ?, 'export_sample')
            """,
            (rid, now),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO evidence_link_reviewed_state (
                target_id, support_status, last_reviewed_at, last_reviewer_id, last_decision_id
            ) VALUES ('ev:1', 'strong', ?, 'u1', 'd2')
            """,
            (now,),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO materialized_tier_state (
                target_type, target_id, tier, tier_reasons_json, blocker_codes_json,
                is_eligible, is_promotable_to_gold, resolved_at, policy_version
            ) VALUES ('evidence_link', 'ev:1', 'gold', '[]', '[]', 1, 0, ?, 'export_sample')
            """,
            (now,),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO rule_card_reviewed_state (
                target_id, current_status, latest_decision_type, canonical_family_id,
                is_duplicate, duplicate_of_rule_id, is_ambiguous, is_deferred, is_unsupported,
                last_reviewed_at, last_reviewer_id, last_decision_id, notes_summary
            ) VALUES ('rule:a:1', 'approved', 'approve', NULL, 0, NULL, 0, 0, 0, ?, 'u1', 'd3', NULL)
            """,
            (now,),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO materialized_tier_state (
                target_type, target_id, tier, tier_reasons_json, blocker_codes_json,
                is_eligible, is_promotable_to_gold, resolved_at, policy_version
            ) VALUES ('rule_card', 'rule:a:1', 'silver', '[]', '[]', 1, 0, ?, 'export_sample')
            """,
            (now,),
        )
        # Second gold rule so duplicate_of and eval_duplicate_pairs close over exported gold_rules.jsonl.
        conn.execute(
            """
            INSERT OR REPLACE INTO rule_card_reviewed_state (
                target_id, current_status, latest_decision_type, canonical_family_id,
                is_duplicate, duplicate_of_rule_id, is_ambiguous, is_deferred, is_unsupported,
                last_reviewed_at, last_reviewer_id, last_decision_id, notes_summary
            ) VALUES ('rule:b:1', 'approved', 'approve', NULL, 0, NULL, 0, 0, 0, ?, 'u1', 'd1b', NULL)
            """,
            (now,),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO materialized_tier_state (
                target_type, target_id, tier, tier_reasons_json, blocker_codes_json,
                is_eligible, is_promotable_to_gold, resolved_at, policy_version
            ) VALUES ('rule_card', 'rule:b:1', 'gold', '[]', '[]', 1, 0, ?, 'export_sample')
            """,
            (now,),
        )

    repo.create_canonical_family(
        NewCanonicalFamily(
            family_id="fam-audit",
            canonical_title="Audit family",
            status=CanonicalFamilyStatus.ACTIVE,
            created_by="u1",
        )
    )
    repo.add_rule_to_family(
        NewMembership(family_id="fam-audit", rule_id=rid, membership_role=MembershipRole.MEMBER)
    )

    out = examples.parent / "_export_out"
    if out.exists():
        shutil.rmtree(out)
    run_export(
        repo,
        out,
        tiers={QualityTier.GOLD, QualityTier.SILVER},
        corpus_index=STANDARD_TEST_CORPUS_INDEX,
        explorer=None,
        write_eval_subsets=True,
    )
    for p in out.iterdir():
        shutil.copy2(p, examples / p.name)
    shutil.rmtree(out)

    v_default = validate_export_dir(examples)
    v_db = validate_export_dir(examples, db_path=db)
    lines = [
        f"validate_export_dir (default): {'OK' if v_default.ok else 'FAIL'}",
        *([""] + v_default.errors if v_default.errors else []),
        f"validate_export_dir (--db equivalent): {'OK' if v_db.ok else 'FAIL'}",
        *v_db.errors,
    ]
    (examples.parent / "validation_sample_output.txt").write_text(
        "\n".join(lines).strip() + "\n",
        encoding="utf-8",
    )
    db.unlink(missing_ok=True)
    print("Wrote", examples)


if __name__ == "__main__":
    main()
