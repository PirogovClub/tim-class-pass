#!/usr/bin/env python3
"""Assemble ``audit/ml_step6_audit_bundle_<UTC-timestamp>/`` and zip for ML Step 6 handoff."""

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
    bundle_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S_%f")
    bundle = repo / "audit" / f"ml_step6_audit_bundle_{bundle_ts}"
    source = bundle / "source"
    examples = bundle / "examples"
    bundle.mkdir(parents=True)
    source.mkdir(parents=True)
    examples.mkdir(parents=True)

    test_log = bundle / "test_output.txt"
    test_log.write_text("", encoding="utf-8")

    rc_compile = _run([sys.executable, "-m", "ml.label_spec_compiler"], repo, test_log)
    rc_pt = _run(
        [sys.executable, "-m", "pytest", "tests/test_label_specs.py", "tests/test_label_generation.py", "-q"],
        repo,
        test_log,
    )
    rc_val = _run([sys.executable, "-m", "ml.task_validator"], repo, test_log)
    out_sample = repo / "ml_output" / "step6_audit_sample"
    rc_gen = _run(
        [
            sys.executable,
            "-m",
            "ml.label_generation",
            "--out-dir",
            str(out_sample),
        ],
        repo,
        test_log,
    )

    ml_src = source / "ml"
    ml_src.mkdir(parents=True)
    for name in (
        "__init__.py",
        "task_definition.yaml",
        "window_contract.yaml",
        "class_ontology.json",
        "rule_to_class_mapping.json",
        "task_examples.json",
        "task_validator.py",
        "label_spec_compiler.py",
        "label_specs.json",
        "market_window.py",
        "label_rules.py",
        "label_generation.py",
        "label_manifest_builder.py",
        "label_output_validator.py",
        "generated_labels.schema.json",
    ):
        p = repo / "src" / "ml" / name
        if p.exists():
            shutil.copy2(p, ml_src / name)

    fix_src = ml_src / "fixtures" / "market_windows"
    fix_src.mkdir(parents=True)
    for f in (repo / "src" / "ml" / "fixtures" / "market_windows").glob("*.json"):
        shutil.copy2(f, fix_src / f.name)

    tests_dest = source / "tests"
    tests_dest.mkdir(parents=True)
    for t in ("test_label_specs.py", "test_label_generation.py"):
        shutil.copy2(repo / "tests" / t, tests_dest / t)

    for script in ("generate_ml_step6_audit_bundle.py",):
        sp = repo / "scripts" / script
        if sp.exists():
            dest = source / "scripts" / script
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sp, dest)

    for doc in ("docs/ml_step6_label_generation.md",):
        p = repo / doc
        if p.exists():
            docs_d = source / "docs"
            docs_d.mkdir(parents=True)
            shutil.copy2(p, docs_d / Path(doc).name)

    for root_doc in ("RUN_ML_STEP6_AUDIT.md", "ML_STEP6_HANDOFF.md"):
        p = repo / root_doc
        if p.exists():
            shutil.copy2(p, bundle / root_doc)

    pytoml = repo / "pyproject.toml"
    if pytoml.is_file():
        shutil.copy2(pytoml, bundle / "pyproject.toml")

    ex_compiled = examples / "label_specs.json"
    shutil.copy2(repo / "src" / "ml" / "label_specs.json", ex_compiled)
    ex_win = examples / "sample_market_windows"
    ex_win.mkdir(parents=True)
    for f in (repo / "src" / "ml" / "fixtures" / "market_windows").glob("*.json"):
        shutil.copy2(f, ex_win / f.name)
    for name in ("generated_labels.jsonl", "label_generation_report.json", "label_dataset_manifest.json"):
        p = out_sample / name
        if p.exists():
            shutil.copy2(p, examples / name)

    zip_path = repo / "audit" / f"ml_step6_audit_bundle_{bundle_ts}.zip"
    _zip_dir(bundle, zip_path)
    archives = repo / "audit" / "archives"
    archives.mkdir(parents=True, exist_ok=True)
    shutil.copy2(zip_path, archives / zip_path.name)

    print(f"Bundle: {bundle}")
    print(f"Zip: {zip_path}")
    print(
        f"label_spec_compiler exit: {rc_compile}; pytest exit: {rc_pt}; "
        f"task_validator exit: {rc_val}; label_generation exit: {rc_gen}"
    )
    return 0 if rc_compile == 0 and rc_pt == 0 and rc_val == 0 and rc_gen == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
