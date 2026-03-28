#!/usr/bin/env python3
"""Assemble ``audit/ml_step5_audit_bundle_<UTC-timestamp>/`` and zip for ML Step 5 handoff."""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    bundle = repo / "audit" / f"ml_step5_audit_bundle_{bundle_ts}"
    source = bundle / "source"
    examples = bundle / "examples"
    bundle.mkdir(parents=True)
    source.mkdir(parents=True)
    examples.mkdir(parents=True)

    test_log = bundle / "test_output.txt"
    test_log.write_text("", encoding="utf-8")

    rc_pytest = _run(
        [sys.executable, "-m", "pytest", "tests/test_ml_task_definition.py", "-q"],
        repo,
        test_log,
    )
    rc_val = _run([sys.executable, "-m", "ml.task_validator"], repo, test_log)

    # source snapshot
    ml_dest = source / "ml"
    ml_dest.mkdir(parents=True)
    for name in (
        "__init__.py",
        "task_definition.yaml",
        "window_contract.yaml",
        "class_ontology.json",
        "rule_to_class_mapping.json",
        "task_examples.json",
        "task_validator.py",
    ):
        p = repo / "src" / "ml" / name
        if p.exists():
            shutil.copy2(p, ml_dest / name)

    tests_dest = source / "tests"
    tests_dest.mkdir(parents=True)
    shutil.copy2(repo / "tests" / "test_ml_task_definition.py", tests_dest / "test_ml_task_definition.py")
    bad_src = repo / "tests" / "fixtures" / "ml_step5_bad"
    if bad_src.is_dir():
        shutil.copytree(bad_src, tests_dest / "fixtures" / "ml_step5_bad", dirs_exist_ok=True)

    for script in ("generate_ml_step5_audit_bundle.py",):
        sp = repo / "scripts" / script
        if sp.exists():
            dest = source / "scripts" / script
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sp, dest)

    task_doc = repo / "docs" / "ml_step5_task_definition.md"
    if task_doc.is_file():
        docs_dest = source / "docs"
        docs_dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(task_doc, docs_dest / "ml_step5_task_definition.md")

    for doc in (
        "docs/ml_step5_task_definition.md",
        "RUN_ML_STEP5_AUDIT.md",
        "ML_STEP5_HANDOFF.md",
    ):
        p = repo / doc
        if p.exists():
            shutil.copy2(p, bundle / Path(doc).name)

    pytoml = repo / "pyproject.toml"
    if pytoml.is_file():
        shutil.copy2(pytoml, bundle / "pyproject.toml")

    for name in (
        "task_definition.yaml",
        "window_contract.yaml",
        "class_ontology.json",
        "rule_to_class_mapping.json",
        "task_examples.json",
    ):
        shutil.copy2(repo / "src" / "ml" / name, examples / name)

    bad_ex = repo / "tests" / "fixtures" / "ml_step5_bad"
    if bad_ex.is_dir():
        ex_bad = examples / "bad_fixtures"
        ex_bad.mkdir(parents=True)
        for f in bad_ex.iterdir():
            if f.is_file():
                shutil.copy2(f, ex_bad / f.name)

    _write(
        bundle / "REPRODUCIBILITY.md",
        """# ML Step 5 audit bundle reproducibility

- **source/** is a partial snapshot; validate from a full `tim-class-pass` checkout.
- Re-run: `python -m ml.task_validator` and `python -m pytest tests/test_ml_task_definition.py -q`.
- Bad fixtures under **examples/bad_fixtures/** demonstrate validator failures.
""",
    )

    zip_path = repo / "audit" / f"ml_step5_audit_bundle_{bundle_ts}.zip"
    _zip_dir(bundle, zip_path)
    archives = repo / "audit" / "archives"
    archives.mkdir(parents=True, exist_ok=True)
    shutil.copy2(zip_path, archives / zip_path.name)

    print(f"Bundle: {bundle}")
    print(f"Zip: {zip_path}")
    print(f"pytest exit: {rc_pytest}; validator exit: {rc_val}")
    return 0 if rc_pytest == 0 and rc_val == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
