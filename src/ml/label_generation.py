"""Deterministic label generation for level_interaction_rule_satisfaction_v1."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from ml.label_manifest_builder import write_artifacts
from ml.label_output_validator import validate_generated_label_row
from ml.label_rules import PatternAnalysis, analyze_patterns, assign_by_decision_order
from ml.label_spec_compiler import GENERATOR_VERSION, write_label_specs
from ml.market_window import validate_market_window

_TIER_RANK = {"gold": 0, "silver": 1, "weak": 2}


def _metadata_for_row(window: dict[str, Any]) -> dict[str, Any]:
    src: dict[str, Any] = {}
    sm = window.get("source_metadata")
    if isinstance(sm, dict):
        src.update(sm)
    fam = window.get("rule_family_hint")
    if isinstance(fam, str) and fam.strip():
        src.setdefault("rule_family_hint", fam.strip())
    idx = window.get("anchor_bar_index")
    if isinstance(idx, int):
        src.setdefault("anchor_bar_index", idx)
    bba = window.get("bars_before_anchor")
    if isinstance(bba, int):
        src["bars_before_anchor"] = bba
    out: dict[str, Any] = {"notes": window.get("metadata_notes")}
    out["source"] = src if src else None
    return out


def _worsen_tier(current: str, floor: str) -> str:
    return current if _TIER_RANK[current] >= _TIER_RANK[floor] else floor


def _label_id(task_id: str, candidate_id: str, anchor_ts: str, label: str, status: str) -> str:
    payload = json.dumps(
        {"task_id": task_id, "candidate_id": candidate_id, "anchor_ts": anchor_ts, "label": label, "st": status},
        sort_keys=True,
    )
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"gl_{h}"


def _provenance(window: dict[str, Any], mapping_entries: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    concepts = list(window.get("linked_concept_ids") or [])
    refs: list[str] = []
    for m in mapping_entries:
        cids = m.get("canonical_concept_ids") or []
        if concepts and any(c in concepts for c in cids):
            hints = m.get("related_rule_family_hints") or []
            refs.append(f"mapping:{','.join(hints[:3])}")
    if not refs and concepts:
        refs.append("mapping:unresolved_concept_link")
    return refs, concepts


def _confidence(
    window: dict[str, Any],
    label: str,
    status: str,
    pa: PatternAnalysis,
    numeric: dict[str, Any],
) -> str:
    if status in ("excluded", "skipped_invalid_input"):
        return "weak"
    if window.get("confidence_override") in ("gold", "silver", "weak"):
        return str(window["confidence_override"])
    if label == "ambiguous":
        tier = "weak" if window.get("weak_ambiguity") else "silver"
        return tier
    tier = "gold"
    if window.get("approach_direction") == "unknown":
        tier = _worsen_tier(tier, "silver")
    if window.get("tick_size") in (None, 0, 0.0):
        tier = _worsen_tier(tier, "silver")
    anchor = int(window["anchor_bar_index"])
    forward = len(window["bars"]) - 1 - anchor
    if forward < 10:
        tier = _worsen_tier(tier, "weak")
    if window.get("borderline_geometry"):
        tier = _worsen_tier(tier, "weak")
    return tier


def generate_label_for_window(window: dict[str, Any], compiled: dict[str, Any]) -> dict[str, Any]:
    task_id = compiled["task_id"]
    numeric = compiled["numeric_thresholds"]
    max_fwd = int(numeric["max_forward_bars"])
    min_ctx = int(numeric["min_context_bars_inclusive_anchor"])

    fam = window.get("rule_family_hint")
    if isinstance(fam, str) and fam.strip():
        for ex in compiled.get("excluded_rule_families", []):
            if isinstance(ex, dict) and ex.get("family_hint") == fam.strip():
                cid = str(window.get("candidate_id", ""))
                ats = str(window.get("anchor_timestamp", ""))
                excluded_row = {
                    "generated_label_id": _label_id(task_id, cid, ats, "", "excluded"),
                    "task_id": task_id,
                    "candidate_id": cid,
                    "label": None,
                    "confidence_tier": "weak",
                    "status": "excluded",
                    "decision_order_path": ["excluded_rule_family"],
                    "matched_rule_refs": [],
                    "matched_concept_ids": list(window.get("linked_concept_ids") or []),
                    "matched_conditions": [],
                    "invalidation_hits": [],
                    "ambiguity_reason": None,
                    "exclusion_reason": f"excluded_rule_family:{fam} — {ex.get('reason', '')}",
                    "market_window_ref": cid,
                    "anchor_timestamp": ats,
                    "timeframe": str(window.get("timeframe", "")),
                    "label_horizon": 0,
                    "point_in_time_safe": True,
                    "metadata": _metadata_for_row(window),
                }
                ex_errs = validate_generated_label_row(excluded_row)
                if ex_errs:
                    raise RuntimeError("excluded row invalid: " + "; ".join(ex_errs))
                return excluded_row

    vr = validate_market_window(
        window,
        max_forward_bars=max_fwd,
        min_context_bars_inclusive_anchor=min_ctx,
    )
    candidate_id = str(window.get("candidate_id", ""))
    anchor_ts = str(window.get("anchor_timestamp", ""))
    tf = str(window.get("timeframe", ""))
    refs, concepts = _provenance(window, compiled.get("mapping_entries", []))

    base_meta = _metadata_for_row(window)

    if not vr.ok:
        reason = "; ".join(vr.errors)
        return {
            "generated_label_id": _label_id(task_id, candidate_id, anchor_ts, "", "skipped_invalid_input"),
            "task_id": task_id,
            "candidate_id": candidate_id,
            "label": None,
            "confidence_tier": "weak",
            "status": "skipped_invalid_input",
            "decision_order_path": ["validate_window:fail"],
            "matched_rule_refs": refs,
            "matched_concept_ids": concepts,
            "matched_conditions": [],
            "invalidation_hits": [],
            "ambiguity_reason": None,
            "exclusion_reason": reason,
            "market_window_ref": candidate_id,
            "anchor_timestamp": anchor_ts,
            "timeframe": tf,
            "label_horizon": min(max_fwd, max(0, len(window.get("bars", [])) - 1 - int(window.get("anchor_bar_index", 0)))),
            "point_in_time_safe": vr.point_in_time_safe,
            "metadata": base_meta,
        }

    pa = analyze_patterns(window, numeric=numeric)
    forced = window.get("force_ambiguity_reason")
    if isinstance(forced, str) and forced.strip():
        pa.ambiguity_codes.insert(0, forced.strip())

    order = compiled["class_decision_order"]
    label, path = assign_by_decision_order(order, pa)

    if label == "ambiguous":
        status = "ambiguous"
        amb_reason = pa.ambiguity_codes[0] if pa.ambiguity_codes else "MULTIPLE_PLAUSIBLE"
        exclusion_reason = None
        assigned_label = "ambiguous"
    else:
        status = "assigned"
        amb_reason = None
        exclusion_reason = None
        assigned_label = label

    pit_safe = bool(vr.point_in_time_safe)
    if window.get("simulate_pit_violation"):
        pit_safe = False

    horizon = min(max_fwd, len(window["bars"]) - 1 - int(window["anchor_bar_index"]))

    row = {
        "generated_label_id": _label_id(task_id, candidate_id, anchor_ts, assigned_label, status),
        "task_id": task_id,
        "candidate_id": candidate_id,
        "label": assigned_label,
        "confidence_tier": _confidence(window, assigned_label, status, pa, numeric),
        "status": status,
        "decision_order_path": path,
        "matched_rule_refs": refs,
        "matched_concept_ids": concepts,
        "matched_conditions": list(pa.matched_conditions),
        "invalidation_hits": [] if pit_safe else ["pit_001"],
        "ambiguity_reason": amb_reason,
        "exclusion_reason": exclusion_reason,
        "market_window_ref": candidate_id,
        "anchor_timestamp": anchor_ts,
        "timeframe": tf,
        "label_horizon": horizon,
        "point_in_time_safe": pit_safe,
        "metadata": base_meta,
    }

    errs = validate_generated_label_row(row)
    if errs:
        raise RuntimeError("internal label row failed validation: " + "; ".join(errs))
    return row


def run_batch(windows: list[dict[str, Any]], compiled: dict[str, Any]) -> list[dict[str, Any]]:
    return [generate_label_for_window(w, compiled) for w in windows]


def _load_windows_dir(d: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in sorted(d.glob("*.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="ML Step 6 deterministic label generation")
    parser.add_argument("--ml-root", type=Path, default=Path("ml"))
    parser.add_argument(
        "--windows-dir",
        type=Path,
        default=None,
        help="Directory of *.json market windows (default: <ml-root>/fixtures/market_windows)",
    )
    parser.add_argument("--out-dir", type=Path, default=Path("ml_output/step6_sample"))
    parser.add_argument(
        "--compile-specs-only",
        action="store_true",
        help="Only write label_specs.json from Step 5 sources",
    )
    args = parser.parse_args()

    ml_root = args.ml_root.resolve()
    if args.compile_specs_only:
        write_label_specs(ml_root, ml_root / "label_specs.json")
        return 0

    compiled_path = ml_root / "label_specs.json"
    if not compiled_path.is_file():
        write_label_specs(ml_root, compiled_path)
    compiled = json.loads(compiled_path.read_text(encoding="utf-8"))

    wdir = (args.windows_dir or (ml_root / "fixtures" / "market_windows")).resolve()
    if not wdir.is_dir():
        print(f"ERROR: windows dir missing: {wdir}", file=sys.stderr)
        return 1
    windows = _load_windows_dir(wdir)
    labels = run_batch(windows, compiled)

    spec_versions = {
        "task_definition": compiled["task_definition_version"],
        "window_contract": compiled["window_contract_version"],
        "ontology": compiled["ontology_version"],
        "mapping": compiled["mapping_version"],
        "task_examples": compiled.get("task_examples_version", ""),
        "label_specs_compiled_at": compiled.get("compiled_at_utc", ""),
    }

    jsonl, rep, man = write_artifacts(
        labels,
        args.out_dir.resolve(),
        task_id=compiled["task_id"],
        spec_versions=spec_versions,
        generator_version=GENERATOR_VERSION,
        input_sources=[str(wdir)],
        pit_declaration=(
            "Labels use only bars through anchor + max_forward_bars per window_contract.yaml; "
            "validator rejects excess forward bars and non-monotonic time."
        ),
        known_limitations=[
            "v1 numeric thresholds are simplified vs full production microstructure",
            "Higher timeframe context optional and unused in v1 predicates",
        ],
    )
    print(f"Wrote {jsonl}, {rep}, {man} ({len(labels)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
