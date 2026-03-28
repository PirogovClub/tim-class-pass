#!/usr/bin/env python3
"""Assemble ``audit/ml_step9_audit_bundle_<UTC-timestamp>/`` and zip for ML Step 9 handoff."""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml


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
    bundle = repo / "audit" / f"ml_step9_audit_bundle_{bundle_ts}"
    source = bundle / "source"
    examples = bundle / "examples"
    bundle.mkdir(parents=True)
    source.mkdir(parents=True)
    examples.mkdir(parents=True)

    log = bundle / "test_output.txt"
    log.write_text("", encoding="utf-8")

    step9_tests = [
        "tests/test_step9_decision_config.py",
        "tests/test_step9_evidence_loader.py",
        "tests/test_failure_mode_analysis.py",
        "tests/test_model_family_decider.py",
        "tests/test_step10_brief_builder.py",
        "tests/test_step9_report_builder.py",
    ]
    codes: list[int] = []
    codes.append(_run([py, "-m", "pytest"] + step9_tests + ["-q"], repo, log))

    codes.append(_run([py, "-m", "ml.step9.cli", "full-audit-run", "--config", str(repo / "src" / "ml" / "step9_decision_config.yaml")], repo, log))

    step9_out = repo / "ml_output" / "step9"
    fx_src = repo / "tests" / "fixtures" / "step9_audit_step8"
    if not fx_src.is_dir():
        fx_src = repo / "ml_output" / "step8_audit_sample"
    fx_dst = source / "fixtures" / "step9_audit_step8"
    if fx_src.is_dir():
        shutil.copytree(fx_src, fx_dst, dirs_exist_ok=True)

    ml_src = source / "ml"
    ml_src.mkdir(parents=True)
    shutil.copy2(repo / "src" / "ml" / "step9_decision_config.yaml", ml_src / "step9_decision_config.yaml")
    s9 = ml_src / "step9"
    s9.mkdir(parents=True)
    for p in (repo / "src" / "ml" / "step9").glob("*.py"):
        shutil.copy2(p, s9 / p.name)

    tests_d = source / "tests"
    tests_d.mkdir(parents=True, exist_ok=True)
    for t in step9_tests:
        tp = repo / "tests" / Path(t).name
        if tp.is_file():
            shutil.copy2(tp, tests_d / Path(t).name)
    tf = repo / "tests" / "fixtures" / "step9_audit_step8"
    if tf.is_dir():
        tfd = tests_d / "fixtures" / "step9_audit_step8"
        tfd.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(tf, tfd, dirs_exist_ok=True)

    docd = source / "docs"
    docd.mkdir(parents=True)
    d9 = repo / "docs" / "ml_step9_model_family_decision.md"
    if d9.is_file():
        shutil.copy2(d9, docd / d9.name)

    for md in ("RUN_ML_STEP9_AUDIT.md", "ML_STEP9_HANDOFF.md", "requirements-ml-step7-audit.txt"):
        p = repo / md
        if p.exists():
            shutil.copy2(p, bundle / md)

    sp = repo / "scripts" / "generate_ml_step9_audit_bundle.py"
    if sp.exists():
        sd = source / "scripts"
        sd.mkdir(parents=True)
        shutil.copy2(sp, sd / sp.name)

    cfg_path = repo / "src" / "ml" / "step9_decision_config.yaml"
    audit_cfg = examples / "step9_decision_config_audit.yaml"
    if cfg_path.is_file():
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        cfg["evidence"] = {**cfg["evidence"], "step8_root": "source/fixtures/step9_audit_step8"}
        cfg["outputs"] = {**cfg["outputs"], "root": "examples/step9_sample_output"}
        cfg["minimum_evidence"] = {**cfg["minimum_evidence"], "min_prediction_lines": 4}
        audit_cfg.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    if step9_out.is_dir():
        out_ex = examples / "step9_sample_output"
        out_ex.mkdir(parents=True, exist_ok=True)
        for f in step9_out.iterdir():
            if f.is_file():
                shutil.copy2(f, out_ex / f.name)

    shutil.copy2(cfg_path, examples / "step9_decision_config.yaml")
    if fx_src.is_dir():
        ex8 = examples / "step8_audit_sample"
        shutil.copytree(fx_src, ex8, dirs_exist_ok=True)

    req_audit = repo / "requirements-ml-step7-audit.txt"
    if req_audit.is_file():
        shutil.copy2(req_audit, source / req_audit.name)

    prev = log.read_text(encoding="utf-8") if log.exists() else ""
    log.write_text(prev + "\n\n=== STANDALONE: pytest from bundle source/ ===\n", encoding="utf-8")
    codes.append(
        _run(
            [py, "-m", "pytest"] + [f"tests/{Path(t).name}" for t in step9_tests] + ["-q"],
            source,
            log,
        )
    )

    zip_path = repo / "audit" / f"ml_step9_audit_bundle_{bundle_ts}.zip"
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
