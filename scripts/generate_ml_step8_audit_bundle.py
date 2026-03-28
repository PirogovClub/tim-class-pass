#!/usr/bin/env python3
"""Assemble ``audit/ml_step8_audit_bundle_<UTC-timestamp>/`` and zip for ML Step 8 handoff."""

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
    bundle = repo / "audit" / f"ml_step8_audit_bundle_{bundle_ts}"
    source = bundle / "source"
    examples = bundle / "examples"
    bundle.mkdir(parents=True)
    source.mkdir(parents=True)
    examples.mkdir(parents=True)

    log = bundle / "test_output.txt"
    log.write_text("", encoding="utf-8")

    step8_tests = [
        "tests/test_walkforward_config.py",
        "tests/test_fold_builder.py",
        "tests/test_walkforward_runner.py",
        "tests/test_policy_evaluator.py",
        "tests/test_backtest_reports.py",
        "tests/test_calibration_drift.py",
        "tests/test_dataset_integrity.py",
    ]
    codes: list[int] = []
    codes.append(_run([py, "-m", "pytest"] + step8_tests + ["-q"], repo, log))

    lbl = repo / "tests" / "fixtures" / "step6_for_step7" / "generated_labels.jsonl"
    step7_out = repo / "ml_output" / "step8_audit_prereq"
    step7_out.mkdir(parents=True, exist_ok=True)
    ds_path = step7_out / "modeling_dataset.jsonl"
    if lbl.is_file():
        codes.append(
            _run(
                [
                    py,
                    "-m",
                    "ml.dataset_builder",
                    "--labels",
                    str(lbl),
                    "--out-dir",
                    str(step7_out),
                    "--include-weak",
                ],
                repo,
                log,
            )
        )
    elif (repo / "ml_output" / "step7" / "modeling_dataset.jsonl").is_file():
        shutil.copy2(repo / "ml_output" / "step7" / "modeling_dataset.jsonl", ds_path)
    else:
        log.write_text(log.read_text(encoding="utf-8") + "\nWARN: no dataset built for step8 audit sample\n", encoding="utf-8")

    cfg_path = repo / "src" / "ml" / "walkforward_config.yaml"
    audit_cfg = repo / "ml_output" / "step8_audit_walkforward.yaml"
    if ds_path.is_file():
        import yaml

        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        cfg["dataset"] = {"path": str(ds_path.resolve())}
        cfg["outputs"] = {**cfg["outputs"], "root": str((repo / "ml_output" / "step8_audit_sample").resolve())}
        audit_cfg.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        codes.append(_run([py, "-m", "ml.backtest.walkforward_config_loader", "--config", str(audit_cfg)], repo, log))
        codes.append(_run([py, "-m", "ml.backtest.fold_builder", "--config", str(audit_cfg)], repo, log))
        codes.append(_run([py, "-m", "ml.backtest.walkforward_runner", "--config", str(audit_cfg)], repo, log))
    else:
        codes.append(1)

    step8_out = repo / "ml_output" / "step8_audit_sample"

    ml_src = source / "ml"
    ml_src.mkdir(parents=True)
    for name in (
        "walkforward_config.yaml",
        "feature_spec.yaml",
        "feature_spec_loader.py",
    ):
        p = repo / "src" / "ml" / name
        if p.exists():
            shutil.copy2(p, ml_src / name)
    # Step 7 modules required by tests (step7_audit_fixtures -> ml.dataset_builder) and §1 runbook.
    for name in (
        "__init__.py",
        "dataset_builder.py",
        "feature_builder.py",
        "split_builder.py",
    ):
        p = repo / "src" / "ml" / name
        if p.is_file():
            shutil.copy2(p, ml_src / name)
    bt = ml_src / "backtest"
    bt.mkdir(parents=True)
    for p in (repo / "src" / "ml" / "backtest").glob("*.py"):
        shutil.copy2(p, bt / p.name)
    bas = ml_src / "baselines"
    bas.mkdir(parents=True)
    for name in ("__init__.py", "symbolic_baseline.py", "evaluate_tabular_baseline.py", "calibration.py"):
        p = repo / "src" / "ml" / "baselines" / name
        if p.exists():
            shutil.copy2(p, bas / name)

    fix = ml_src / "fixtures" / "market_windows"
    fix.mkdir(parents=True)
    for f in (repo / "src" / "ml" / "fixtures" / "market_windows").glob("*.json"):
        shutil.copy2(f, fix / f.name)

    tests_d = source / "tests"
    tests_d.mkdir(parents=True)
    fx = repo / "tests" / "fixtures" / "step6_for_step7"
    fxd = tests_d / "fixtures" / "step6_for_step7"
    fxd.mkdir(parents=True, exist_ok=True)
    if fx.is_dir():
        for f in fx.iterdir():
            if f.is_file():
                shutil.copy2(f, fxd / f.name)
    for t in step8_tests + ["step7_audit_fixtures.py", "test_feature_spec.py"]:
        tp = repo / "tests" / Path(t).name
        if tp.is_file():
            shutil.copy2(tp, tests_d / Path(t).name)

    docd = source / "docs"
    docd.mkdir(parents=True)
    for d in ("ml_step8_walkforward_backtests.md",):
        p = repo / "docs" / d
        if p.exists():
            shutil.copy2(p, docd / d)

    for md in ("RUN_ML_STEP8_AUDIT.md", "ML_STEP8_HANDOFF.md", "requirements-ml-step7-audit.txt"):
        p = repo / md
        if p.exists():
            shutil.copy2(p, bundle / md)

    sp = repo / "scripts" / "generate_ml_step8_audit_bundle.py"
    if sp.exists():
        sd = source / "scripts"
        sd.mkdir(parents=True)
        shutil.copy2(sp, sd / sp.name)

    if audit_cfg.is_file():
        shutil.copy2(audit_cfg, examples / "walkforward_config_audit_sample.yaml")
    if ds_path.is_file():
        shutil.copy2(ds_path, examples / "modeling_dataset_sample.jsonl")
    req_audit = repo / "requirements-ml-step7-audit.txt"
    if req_audit.is_file():
        shutil.copy2(req_audit, source / req_audit.name)

    prev = log.read_text(encoding="utf-8") if log.exists() else ""
    log.write_text(
        prev + "\n\n=== STANDALONE: pytest from bundle source/ (auditor cwd) ===\n",
        encoding="utf-8",
    )
    codes.append(_run([py, "-m", "pytest"] + step8_tests + ["-q"], source, log))

    for fname in (
        "walkforward_folds.json",
        "backtest_predictions.jsonl",
        "fold_metrics.json",
        "walkforward_report.json",
        "model_comparison_report.json",
        "calibration_drift_report.json",
        "policy_report.json",
        "step8_manifest.json",
        "threshold_sweep_report.json",
        "per_class_fold_metrics.json",
        "confusion_matrices.json",
        "aggregate_dimensions_report.json",
    ):
        p = step8_out / fname
        if p.exists():
            shutil.copy2(p, examples / fname)

    zip_path = repo / "audit" / f"ml_step8_audit_bundle_{bundle_ts}.zip"
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
