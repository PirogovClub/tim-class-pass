"""Validate Stage 5.6 export directories (integrity, tiers, referential consistency, manifest counts)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.export_enums import ExportArtifact
from pipeline.adjudication.export_models import ExportManifest


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _expect_tier_for_gold_file(name: str) -> str | None:
    if name.startswith("gold_") and name.endswith(".jsonl"):
        return "gold"
    return None


def _expect_tier_for_silver_file(name: str) -> str | None:
    if name.startswith("silver_") and name.endswith(".jsonl"):
        return "silver"
    return None


def _load_jsonl_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Return parsed rows and parse/structure error messages."""
    errs: list[str] = []
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows, errs
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            errs.append(f"{path.name}:{i}: invalid JSON ({e})")
    return rows, errs


def validate_export_dir(
    output_dir: Path,
    *,
    db_path: Path | None = None,
    strict_provenance: bool = False,
) -> ValidationResult:
    """Validate export tree: manifest, counts, JSON, tiers, uniqueness, cross-file refs, optional DB."""
    out = ValidationResult(ok=True)
    root = Path(output_dir)
    mpath = root / ExportArtifact.MANIFEST.value
    if not mpath.is_file():
        out.ok = False
        out.errors.append(f"Missing manifest: {mpath}")
        return out

    try:
        raw = json.loads(mpath.read_text(encoding="utf-8"))
        manifest = ExportManifest.model_validate(raw)
    except Exception as e:
        out.ok = False
        out.errors.append(f"Invalid manifest: {e}")
        return out

    expected_counts = manifest.exported_rows_by_file
    gold_ids: set[tuple[str, str]] = set()
    silver_ids: set[tuple[str, str]] = set()

    # --- Pass 1: presence, line counts, per-row schema/tier/overlap ---
    for fname in sorted(manifest.files_written):
        fpath = root / fname
        if not fpath.is_file():
            out.ok = False
            out.errors.append(f"Missing file listed in manifest: {fname}")
            continue
        if fname == ExportArtifact.MANIFEST.value:
            continue
        text = fpath.read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        exp = expected_counts.get(fname)
        if exp is not None and len(lines) != exp:
            out.ok = False
            out.errors.append(
                f"Line count mismatch for {fname}: manifest says {exp}, file has {len(lines)}"
            )

        if fname.endswith(".jsonl"):
            for i, line in enumerate(lines, 1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as e:
                    out.ok = False
                    out.errors.append(f"{fname}:{i}: invalid JSON ({e})")
                    continue

                if fname.startswith("eval_"):
                    for key in ("schema_version", "subset"):
                        if key not in row:
                            out.ok = False
                            out.errors.append(f"{fname}:{i}: missing {key}")
                    continue

                if fname == ExportArtifact.GOLD_CANONICAL_FAMILIES.value:
                    for key in ("schema_version", "tier", "family_id", "member_rule_ids"):
                        if key not in row:
                            out.ok = False
                            out.errors.append(f"{fname}:{i}: missing {key}")
                    if row.get("tier") != "gold":
                        out.ok = False
                        out.errors.append(f"{fname}:{i}: canonical family row must be tier gold")
                    continue

                for key in ("schema_version", "tier", "target_type", "target_id"):
                    if key not in row:
                        out.ok = False
                        out.errors.append(f"{fname}:{i}: missing {key}")

                exp_g = _expect_tier_for_gold_file(fname)
                if exp_g and row.get("tier") != exp_g:
                    out.ok = False
                    out.errors.append(f"{fname}:{i}: expected tier {exp_g}, got {row.get('tier')}")

                exp_s = _expect_tier_for_silver_file(fname)
                if exp_s and row.get("tier") != exp_s:
                    out.ok = False
                    out.errors.append(f"{fname}:{i}: expected tier {exp_s}, got {row.get('tier')}")

                tt = row.get("target_type")
                tid = row.get("target_id")
                if isinstance(tt, str) and isinstance(tid, str):
                    key_pair = (tt, tid)
                    if exp_g:
                        if key_pair in silver_ids:
                            out.ok = False
                            out.errors.append(
                                f"{fname}:{i}: target {key_pair} also present in silver export"
                            )
                        gold_ids.add(key_pair)
                    if exp_s:
                        if key_pair in gold_ids:
                            out.ok = False
                            out.errors.append(
                                f"{fname}:{i}: target {key_pair} also present in gold export"
                            )
                        silver_ids.add(key_pair)

    # --- Pass 2: uniqueness within each tier JSONL file ---
    tier_files = [
        ExportArtifact.GOLD_RULES,
        ExportArtifact.GOLD_EVIDENCE_LINKS,
        ExportArtifact.GOLD_CONCEPT_LINKS,
        ExportArtifact.GOLD_RELATIONS,
        ExportArtifact.SILVER_RULES,
        ExportArtifact.SILVER_EVIDENCE_LINKS,
        ExportArtifact.SILVER_CONCEPT_LINKS,
        ExportArtifact.SILVER_RELATIONS,
    ]
    for art in tier_files:
        fname = art.value
        if fname not in manifest.files_written:
            continue
        fpath = root / fname
        rows, parse_errs = _load_jsonl_rows(fpath)
        for e in parse_errs:
            out.ok = False
            out.errors.append(e)
        seen: set[tuple[str, str]] = set()
        for i, row in enumerate(rows, 1):
            tt = row.get("target_type")
            tid = row.get("target_id")
            if not isinstance(tt, str) or not isinstance(tid, str):
                continue
            key = (tt, tid)
            if key in seen:
                out.ok = False
                out.errors.append(f"{fname}: duplicate target {key} at row {i}")
            seen.add(key)

    # --- Pass 3: unique family_id in gold canonical families ---
    gf_path = root / ExportArtifact.GOLD_CANONICAL_FAMILIES.value
    if ExportArtifact.GOLD_CANONICAL_FAMILIES.value in manifest.files_written:
        fam_rows, fe = _load_jsonl_rows(gf_path)
        for e in fe:
            out.ok = False
            out.errors.append(e)
        fam_seen: set[str] = set()
        for i, row in enumerate(fam_rows, 1):
            fid = row.get("family_id")
            if isinstance(fid, str):
                if fid in fam_seen:
                    out.ok = False
                    out.errors.append(f"{ExportArtifact.GOLD_CANONICAL_FAMILIES.value}: duplicate family_id {fid!r} at row {i}")
                fam_seen.add(fid)

    # --- Pass 4: cross-file reference consistency (in-export closure) ---
    gold_rule_rows, _ = _load_jsonl_rows(root / ExportArtifact.GOLD_RULES.value)
    gold_rule_ids = {str(r["target_id"]) for r in gold_rule_rows if isinstance(r.get("target_id"), str)}
    gold_ev_rows, _ = _load_jsonl_rows(root / ExportArtifact.GOLD_EVIDENCE_LINKS.value)
    gold_ev_ids = {str(r["target_id"]) for r in gold_ev_rows if isinstance(r.get("target_id"), str)}
    fam_rows, _ = _load_jsonl_rows(gf_path)
    family_ids_exported = {str(r["family_id"]) for r in fam_rows if isinstance(r.get("family_id"), str)}
    family_members: dict[str, set[str]] = {}
    for r in fam_rows:
        fid = r.get("family_id")
        mids = r.get("member_rule_ids")
        if isinstance(fid, str) and isinstance(mids, list):
            family_members[fid] = {str(x) for x in mids if isinstance(x, str)}

    silver_rule_rows, _ = _load_jsonl_rows(root / ExportArtifact.SILVER_RULES.value)

    for i, r in enumerate(gold_rule_rows, 1):
        if strict_provenance and r.get("target_type") == "rule_card":
            lid = r.get("lesson_id")
            if lid is None or (isinstance(lid, str) and not lid.strip()):
                out.ok = False
                out.errors.append(
                    f"{ExportArtifact.GOLD_RULES.value}:{i}: strict_provenance requires non-empty lesson_id for rule_card"
                )

        cid = r.get("canonical_family_id")
        if isinstance(cid, str) and cid.strip():
            if cid not in family_ids_exported:
                out.ok = False
                out.errors.append(
                    f"{ExportArtifact.GOLD_RULES.value}:{i}: canonical_family_id {cid!r} not found in gold_canonical_families.jsonl"
                )

        dup = r.get("duplicate_of_rule_id")
        is_dup = bool(r.get("is_duplicate"))
        if is_dup and isinstance(dup, str) and dup.strip():
            if db_path is not None:
                continue  # Pass 5 verifies against DB
            if dup not in gold_rule_ids:
                out.ok = False
                out.errors.append(
                    f"{ExportArtifact.GOLD_RULES.value}:{i}: duplicate_of_rule_id {dup!r} not present in gold_rules.jsonl "
                    "(export closed-world check; pass --db to validate against adjudication DB instead)"
                )

    for i, r in enumerate(silver_rule_rows, 1):
        if strict_provenance and r.get("target_type") == "rule_card":
            lid = r.get("lesson_id")
            if lid is None or (isinstance(lid, str) and not lid.strip()):
                out.ok = False
                out.errors.append(
                    f"{ExportArtifact.SILVER_RULES.value}:{i}: strict_provenance requires non-empty lesson_id for rule_card"
                )

    for fid, mids in family_members.items():
        for mid in mids:
            if mid not in gold_rule_ids:
                out.ok = False
                out.errors.append(
                    f"{ExportArtifact.GOLD_CANONICAL_FAMILIES.value}: member_rule_id {mid!r} not exported in gold_rules.jsonl"
                )

    # --- Pass 5: optional DB resolution ---
    if db_path is not None:
        if not Path(db_path).is_file():
            out.ok = False
            out.errors.append(f"Adjudication DB not found for reference check: {db_path}")
        else:
            initialize_adjudication_storage(Path(db_path))
            from pipeline.adjudication.repository import AdjudicationRepository

            repo = AdjudicationRepository(Path(db_path))
            for i, r in enumerate(gold_rule_rows, 1):
                tid = r.get("target_id")
                if not isinstance(tid, str):
                    continue
                if repo.get_rule_card_state(tid) is None:
                    out.ok = False
                    out.errors.append(
                        f"{ExportArtifact.GOLD_RULES.value}:{i}: target_id {tid!r} has no rule_card_reviewed_state in DB"
                    )
                dup = r.get("duplicate_of_rule_id")
                if bool(r.get("is_duplicate")) and isinstance(dup, str) and dup.strip():
                    if repo.get_rule_card_state(dup) is None:
                        out.ok = False
                        out.errors.append(
                            f"{ExportArtifact.GOLD_RULES.value}:{i}: duplicate_of_rule_id {dup!r} missing in DB"
                        )
                cid = r.get("canonical_family_id")
                if isinstance(cid, str) and cid.strip():
                    if repo.get_family(cid) is None:
                        out.ok = False
                        out.errors.append(
                            f"{ExportArtifact.GOLD_RULES.value}:{i}: canonical_family_id {cid!r} missing in DB"
                        )

            for i, r in enumerate(gold_ev_rows, 1):
                eid = r.get("target_id")
                if isinstance(eid, str) and repo.get_evidence_link_state(eid) is None:
                    out.ok = False
                    out.errors.append(
                        f"{ExportArtifact.GOLD_EVIDENCE_LINKS.value}:{i}: target_id {eid!r} missing evidence_link state in DB"
                    )

    # --- Pass 6: eval subset rows reference exported gold ids ---
    er_path = root / ExportArtifact.EVAL_RETRIEVAL_RULES.value
    if er_path.is_file() and ExportArtifact.EVAL_RETRIEVAL_RULES.value in manifest.files_written:
        for i, row in enumerate(_load_jsonl_rows(er_path)[0], 1):
            tid = row.get("target_id")
            if isinstance(tid, str) and tid not in gold_rule_ids:
                out.ok = False
                out.errors.append(f"{ExportArtifact.EVAL_RETRIEVAL_RULES.value}:{i}: target_id {tid!r} not in gold_rules export")

    ed_path = root / ExportArtifact.EVAL_DUPLICATE_PAIRS.value
    if ed_path.is_file() and ExportArtifact.EVAL_DUPLICATE_PAIRS.value in manifest.files_written:
        for i, row in enumerate(_load_jsonl_rows(ed_path)[0], 1):
            a, b = row.get("rule_id"), row.get("duplicate_of_rule_id")
            if isinstance(a, str) and a not in gold_rule_ids:
                out.ok = False
                out.errors.append(f"{ExportArtifact.EVAL_DUPLICATE_PAIRS.value}:{i}: rule_id {a!r} not in gold_rules export")
            if isinstance(b, str) and b not in gold_rule_ids:
                out.ok = False
                out.errors.append(
                    f"{ExportArtifact.EVAL_DUPLICATE_PAIRS.value}:{i}: duplicate_of_rule_id {b!r} not in gold_rules export"
                )

    ee_path = root / ExportArtifact.EVAL_EVIDENCE_SUPPORT.value
    if ee_path.is_file() and ExportArtifact.EVAL_EVIDENCE_SUPPORT.value in manifest.files_written:
        for i, row in enumerate(_load_jsonl_rows(ee_path)[0], 1):
            eid = row.get("evidence_link_target_id")
            if isinstance(eid, str) and eid not in gold_ev_ids:
                out.ok = False
                out.errors.append(
                    f"{ExportArtifact.EVAL_EVIDENCE_SUPPORT.value}:{i}: evidence_link_target_id {eid!r} not in gold_evidence_links export"
                )

    ec_path = root / ExportArtifact.EVAL_CANONICAL_ASSIGNMENTS.value
    if ec_path.is_file() and ExportArtifact.EVAL_CANONICAL_ASSIGNMENTS.value in manifest.files_written:
        for i, row in enumerate(_load_jsonl_rows(ec_path)[0], 1):
            rid = row.get("rule_id")
            fid = row.get("canonical_family_id")
            if isinstance(rid, str) and rid not in gold_rule_ids:
                out.ok = False
                out.errors.append(f"{ExportArtifact.EVAL_CANONICAL_ASSIGNMENTS.value}:{i}: rule_id {rid!r} not in gold_rules export")
            if isinstance(fid, str) and fid not in family_ids_exported:
                out.ok = False
                out.errors.append(
                    f"{ExportArtifact.EVAL_CANONICAL_ASSIGNMENTS.value}:{i}: canonical_family_id {fid!r} not in gold_canonical_families export"
                )

    return out
