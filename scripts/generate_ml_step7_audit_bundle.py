#!/usr/bin/env python3
"""Assemble ``audit/ml_step7_audit_bundle_<UTC-timestamp>/`` and zip for ML Step 7 handoff."""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _zip_dir(src_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing zip: {zip_path}")
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src_dir.rglob("*")):
            if p.is_file():
                arc = p.relative_to(src_dir.parent).as_posix()
                zf.write(p, arc)


def _run(cmd: list[str], cwd: Path, log: Path) -> int:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    prev = log.read_text(encoding="utf-8") if log.exists() else ""
    log.write_text(
        prev + f"\n\n=== {' '.join(cmd)} (cwd={cwd}) exit={proc.returncode} ===\n"
        + proc.stdout
        + "\n"
        + proc.stderr,
        encoding="utf-8",
    )
    return proc.returncode


def main() -> int:
    repo = _repo_root()
    py = sys.executable
    bundle_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S_%f")
    bundle = repo / "audit" / f"ml_step7_audit_bundle_{bundle_ts}"
    source = bundle / "source"
    examples = bundle / "examples"
    bundle.mkdir(parents=True)
    source.mkdir(parents=True)
    examples.mkdir(parents=True)

    log = bundle / "test_output.txt"
    log.write_text("", encoding="utf-8")

    step7_out = repo / "ml_output" / "step7_audit_sample"
    step7_out.mkdir(parents=True, exist_ok=True)

    codes: list[int] = []
    codes.append(_run([py, "-m", "pytest", "tests/test_feature_spec.py", "tests/test_feature_builder.py", "tests/test_dataset_builder.py", "tests/test_baselines.py", "-q"], repo, log))
    codes.append(_run([py, "-m", "ml.feature_spec_loader"], repo, log))
    codes.append(_run([py, "-m", "ml.label_generation", "--out-dir", str(step7_out.parent / "step6_for_step7_audit")], repo, log))
    lbl_dir = step7_out.parent / "step6_for_step7_audit" / "generated_labels.jsonl"
    if not lbl_dir.is_file():
        lbl_dir = repo / "ml_output" / "step6_sample" / "generated_labels.jsonl"
    codes.append(
        _run(
            [
                py,
                "-m",
                "ml.feature_builder",
                "--out",
                str(step7_out / "feature_rows.jsonl"),
            ],
            repo,
            log,
        )
    )
    codes.append(
        _run(
            [
                py,
                "-m",
                "ml.dataset_builder",
                "--labels",
                str(lbl_dir),
                "--out-dir",
                str(step7_out),
                "--include-weak",
            ],
            repo,
            log,
        )
    )
    codes.append(
        _run(
            [
                py,
                "-m",
                "ml.feature_qa",
                "--dataset",
                str(step7_out / "modeling_dataset.jsonl"),
                "--out",
                str(step7_out / "feature_quality_report.json"),
            ],
            repo,
            log,
        )
    )
    codes.append(
        _run(
            [
                py,
                "-m",
                "ml.baselines.symbolic_baseline",
                "--dataset",
                str(step7_out / "modeling_dataset.jsonl"),
                "--out",
                str(step7_out / "baseline_symbolic_report.json"),
            ],
            repo,
            log,
        )
    )
    codes.append(
        _run(
            [
                py,
                "-m",
                "ml.baselines.train_tabular_baseline",
                "--dataset",
                str(step7_out / "modeling_dataset.jsonl"),
                "--out-dir",
                str(step7_out),
            ],
            repo,
            log,
        )
    )

    ml_src = source / "ml"
    ml_src.mkdir(parents=True)
    # Step 6 (label_generation closure) + spec inputs for recompilation
    for name in (
        "__init__.py",
        "label_generation.py",
        "label_manifest_builder.py",
        "label_output_validator.py",
        "label_rules.py",
        "label_spec_compiler.py",
        "market_window.py",
        "task_validator.py",
        "class_ontology.json",
        "rule_to_class_mapping.json",
        "task_examples.json",
    ):
        p = repo / "src" / "ml" / name
        if p.exists():
            shutil.copy2(p, ml_src / name)
    for name in (
        "feature_spec.yaml",
        "feature_spec_loader.py",
        "feature_builder.py",
        "dataset_builder.py",
        "dataset_schema.json",
        "feature_qa.py",
        "split_builder.py",
        "step7_pipeline.py",
        "label_specs.json",
        "task_definition.yaml",
        "window_contract.yaml",
        "generated_labels.schema.json",
    ):
        p = repo / "src" / "ml" / name
        if p.exists():
            shutil.copy2(p, ml_src / name)
    bas = ml_src / "baselines"
    bas.mkdir(parents=True)
    for name in (
        "__init__.py",
        "symbolic_baseline.py",
        "train_tabular_baseline.py",
        "evaluate_tabular_baseline.py",
        "calibration.py",
    ):
        p = repo / "src" / "ml" / "baselines" / name
        if p.exists():
            shutil.copy2(p, bas / name)

    fix = ml_src / "fixtures" / "market_windows"
    fix.mkdir(parents=True)
    for f in (repo / "src" / "ml" / "fixtures" / "market_windows").glob("*.json"):
        shutil.copy2(f, fix / f.name)

    tests_d = source / "tests"
    tests_d.mkdir(parents=True)
    fx_src = repo / "tests" / "fixtures" / "step6_for_step7"
    fx_dst = tests_d / "fixtures" / "step6_for_step7"
    fx_dst.mkdir(parents=True, exist_ok=True)
    if fx_src.is_dir():
        for f in sorted(fx_src.iterdir()):
            if f.is_file():
                shutil.copy2(f, fx_dst / f.name)
    for t in (
        "step7_audit_fixtures.py",
        "test_feature_spec.py",
        "test_feature_builder.py",
        "test_dataset_builder.py",
        "test_baselines.py",
    ):
        tp = repo / "tests" / t
        if tp.is_file():
            shutil.copy2(tp, tests_d / t)

    sp = repo / "scripts" / "generate_ml_step7_audit_bundle.py"
    if sp.exists():
        dd = source / "scripts"
        dd.mkdir(parents=True)
        shutil.copy2(sp, dd / sp.name)

    docd = source / "docs"
    docd.mkdir(parents=True)
    dp = repo / "docs" / "ml_step7_feature_store_and_baselines.md"
    if dp.exists():
        shutil.copy2(dp, docd / dp.name)

    for md in ("RUN_ML_STEP7_AUDIT.md", "ML_STEP7_HANDOFF.md"):
        p = repo / md
        if p.exists():
            shutil.copy2(p, bundle / md)

    req = repo / "requirements-ml-step7-audit.txt"
    if req.is_file():
        shutil.copy2(req, bundle / req.name)

    ex = examples
    shutil.copy2(repo / "src" / "ml" / "feature_spec.yaml", ex / "feature_spec.yaml")
    if fx_src.is_dir():
        for f in sorted(fx_src.iterdir()):
            if f.is_file():
                shutil.copy2(f, ex / f.name)
    for fname in (
        "feature_rows.jsonl",
        "modeling_dataset.jsonl",
        "dataset_manifest.json",
        "split_manifest.json",
        "feature_quality_report.json",
        "baseline_symbolic_report.json",
        "baseline_logreg_report.json",
        "baseline_xgb_or_lgbm_report.json",
        "calibration_report.json",
        "coefficient_report.json",
        "feature_importance_report.json",
    ):
        p = step7_out / fname
        if p.exists():
            shutil.copy2(p, ex / fname)

    zip_path = repo / "audit" / f"ml_step7_audit_bundle_{bundle_ts}.zip"
    _zip_dir(bundle, zip_path)
    ar = repo / "audit" / "archives"
    ar.mkdir(parents=True, exist_ok=True)
    shutil.copy2(zip_path, ar / zip_path.name)

    print(f"Bundle: {bundle}")
    print(f"Zip: {zip_path}")
    rc = 0 if all(c == 0 for c in codes) else 1
    print(f"step_exit_codes={codes} final_rc={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
