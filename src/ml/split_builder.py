"""Deterministic train/validation/test splits (time-aware when timestamps sort)."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SPLIT_POLICY_TIME_ORDERED = "time_ordered"
SPLIT_POLICY_LESSON_GROUP = "lesson_group"

SPLIT_SEED_POLICY = "sort_by_anchor_timestamp_then_candidate_id_v1"
SPLIT_LESSON_GROUP_POLICY = "group_by_lesson_id_order_groups_by_min_anchor_v1"


def _mark_ineligible_none(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible = [r for r in rows if r.get("eligible_for_training")]
    ineligible_ids = {id(r) for r in rows if not r.get("eligible_for_training")}
    for r in rows:
        if id(r) in ineligible_ids:
            r["split"] = "none"
    return eligible


def _assign_blocks(n: int) -> tuple[int, int, int]:
    """Return (n_train, n_val, n_test) for n items, 60/20/20 with at least one test when n>=3."""
    if n <= 0:
        return 0, 0, 0
    if n == 1:
        return 1, 0, 0
    if n == 2:
        return 1, 1, 0
    n_train = max(1, (n * 6) // 10)
    n_val = max(1, (n * 2) // 10)
    n_test = n - n_train - n_val
    if n_test < 1:
        n_train = max(1, n_train - 1)
        n_test = n - n_train - n_val
    if n_test < 1:
        n_val = max(1, n_val - 1)
        n_test = n - n_train - n_val
    return n_train, n_val, n_test


def _assign_splits_time_ordered(eligible: list[dict[str, Any]]) -> None:
    eligible.sort(key=lambda x: (x.get("anchor_timestamp", ""), x.get("candidate_id", "")))
    n = len(eligible)
    if n == 1:
        eligible[0]["split"] = "train"
        return
    if n == 2:
        eligible[0]["split"] = "train"
        eligible[1]["split"] = "validation"
        return
    n_train, n_val, _n_test = _assign_blocks(n)
    for i, r in enumerate(eligible):
        if i < n_train:
            r["split"] = "train"
        elif i < n_train + n_val:
            r["split"] = "validation"
        else:
            r["split"] = "test"


def _lesson_group_key(r: dict[str, Any]) -> str:
    ref = r.get("source_refs") if isinstance(r.get("source_refs"), dict) else {}
    lid = ref.get("lesson_id")
    if lid is None or lid == "":
        return "__no_lesson__"
    return str(lid)


def _assign_splits_lesson_group(eligible: list[dict[str, Any]]) -> None:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in eligible:
        groups[_lesson_group_key(r)].append(r)

    def group_sort_key(k: str) -> tuple[str, str]:
        g = groups[k]
        return min((x.get("anchor_timestamp", ""), x.get("candidate_id", "")) for x in g)

    sorted_keys = sorted(groups.keys(), key=group_sort_key)
    n_g = len(sorted_keys)
    if n_g == 1:
        for r in groups[sorted_keys[0]]:
            r["split"] = "train"
        return
    if n_g == 2:
        for r in groups[sorted_keys[0]]:
            r["split"] = "train"
        for r in groups[sorted_keys[1]]:
            r["split"] = "validation"
        return
    n_train, n_val, _n_test = _assign_blocks(n_g)
    for i, k in enumerate(sorted_keys):
        sp = "train" if i < n_train else ("validation" if i < n_train + n_val else "test")
        for r in groups[k]:
            r["split"] = sp


def assign_splits(rows: list[dict[str, Any]], *, policy: str = SPLIT_POLICY_TIME_ORDERED) -> None:
    """
    In-place: set split on each row to train|validation|test|none.
    Only eligible_for_training rows receive non-none splits; others stay 'none'.

    policy:
      - time_ordered: sort rows by (anchor_timestamp, candidate_id); 60/20/20 contiguous blocks.
      - lesson_group: group by source_refs.lesson_id; order groups by min anchor in group;
        assign whole groups to 60/20/20 blocks (lesson-level leakage avoidance).
    """
    eligible = _mark_ineligible_none(rows)
    if not eligible:
        return
    if policy == SPLIT_POLICY_LESSON_GROUP:
        _assign_splits_lesson_group(eligible)
    else:
        _assign_splits_time_ordered(eligible)


def write_split_manifest(
    rows: list[dict[str, Any]],
    out: Path,
    *,
    split_policy: str = SPLIT_POLICY_TIME_ORDERED,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    counts: dict[str, int] = {}
    for r in rows:
        if not r.get("eligible_for_training"):
            continue
        s = r.get("split", "none")
        counts[s] = counts.get(s, 0) + 1
    if split_policy == SPLIT_POLICY_LESSON_GROUP:
        policy_id = SPLIT_LESSON_GROUP_POLICY
        desc = (
            "Groups rows by source_refs.lesson_id; order groups by min(anchor_timestamp, candidate_id); "
            "60/20/20 over groups so all rows from one lesson share a split."
        )
    else:
        policy_id = SPLIT_SEED_POLICY
        desc = "Ordered split on (anchor_timestamp, candidate_id); contiguous blocks 60/20/20%."
    man = {
        "split_manifest_id": "split_manifest_v1",
        "split_policy": split_policy,
        "policy": policy_id,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "eligible_counts_by_split": counts,
        "description": desc,
    }
    out.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return man


def main() -> int:
    ap = argparse.ArgumentParser(description="Assign splits to modeling_dataset.jsonl rows")
    ap.add_argument("--dataset", type=Path, default=Path("ml_output/step7/modeling_dataset.jsonl"))
    ap.add_argument("--out-manifest", type=Path, default=Path("ml_output/step7/split_manifest.json"))
    ap.add_argument(
        "--split-policy",
        choices=(SPLIT_POLICY_TIME_ORDERED, SPLIT_POLICY_LESSON_GROUP),
        default=SPLIT_POLICY_TIME_ORDERED,
    )
    args = ap.parse_args()
    path = args.dataset.resolve()
    if not path.is_file():
        print(f"ERROR: {path}", file=sys.stderr)
        return 1
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    assign_splits(rows, policy=args.split_policy)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    write_split_manifest(rows, args.out_manifest.resolve(), split_policy=args.split_policy)
    print(f"Updated splits in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
