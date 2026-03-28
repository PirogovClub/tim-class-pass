"""CLI for Step 9 decision gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ml.step9.evidence_loader import (
    Step9ConfigError,
    Step9EvidenceError,
    build_evidence_summary,
    load_step8_artifacts,
    load_step9_decision_config,
    resolve_step8_paths,
)
from ml.step9.failure_mode_analysis import analyze_failure_modes
from ml.step9.model_family_decider import decide_model_family
from ml.step9.report_builder import write_json, write_step9_bundle
from ml.step9.step10_brief_builder import build_step10_brief


def _repo_root(arg: str | None) -> Path:
    if arg:
        return Path(arg).resolve()
    # Repository root (this file lives at src/ml/step9/cli.py).
    return Path(__file__).resolve().parents[3]


def cmd_validate_config(args: argparse.Namespace) -> int:
    try:
        load_step9_decision_config(Path(args.config).resolve())
    except Step9ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    print("OK: decision config valid")
    return 0


def cmd_evidence_summary(args: argparse.Namespace) -> int:
    repo = _repo_root(args.repo_root)
    try:
        cfg = load_step9_decision_config(Path(args.config).resolve())
        summary = build_evidence_summary(cfg, repo, strict=not args.allow_missing)
    except (Step9ConfigError, Step9EvidenceError) as e:
        print(e, file=sys.stderr)
        return 1
    out = Path(args.out) if args.out else repo / str(cfg.get("outputs", {}).get("root", "ml_output/step9")) / str(
        cfg.get("outputs", {}).get("evidence_summary", "step9_evidence_summary.json")
    )
    write_json(out, summary)
    print(str(out))
    return 0


def _load_raw(cfg: dict[str, Any], repo: Path) -> dict[str, Any]:
    paths = resolve_step8_paths(cfg, repo)
    return load_step8_artifacts(paths, strict=True)


def cmd_failure_modes(args: argparse.Namespace) -> int:
    repo = _repo_root(args.repo_root)
    try:
        cfg = load_step9_decision_config(Path(args.config).resolve())
        raw = _load_raw(cfg, repo)
        failure = analyze_failure_modes(cfg, raw, repo)
    except (Step9ConfigError, Step9EvidenceError) as e:
        print(e, file=sys.stderr)
        return 1
    out = Path(args.out) if args.out else repo / str(cfg.get("outputs", {}).get("root", "ml_output/step9")) / str(
        cfg.get("outputs", {}).get("failure_mode_report", "failure_mode_report.json")
    )
    write_json(out, failure)
    print(str(out))
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    repo = _repo_root(args.repo_root)
    try:
        cfg = load_step9_decision_config(Path(args.config).resolve())
        raw = _load_raw(cfg, repo)
        evidence_summary = build_evidence_summary(cfg, repo, strict=True)
        failure = analyze_failure_modes(cfg, raw, repo)
        decision = decide_model_family(cfg, evidence_summary, failure, raw)
    except (Step9ConfigError, Step9EvidenceError) as e:
        print(e, file=sys.stderr)
        return 1
    out = Path(args.out) if args.out else repo / str(cfg.get("outputs", {}).get("root", "ml_output/step9")) / str(
        cfg.get("outputs", {}).get("model_family_decision", "model_family_decision.json")
    )
    write_json(out, decision)
    print(json.dumps({"outcome": decision.get("outcome"), "path": str(out)}, indent=2))
    return 0


def cmd_step10_brief(args: argparse.Namespace) -> int:
    repo = _repo_root(args.repo_root)
    try:
        cfg = load_step9_decision_config(Path(args.config).resolve())
        raw = _load_raw(cfg, repo)
        evidence_summary = build_evidence_summary(cfg, repo, strict=True)
        failure = analyze_failure_modes(cfg, raw, repo)
        decision = decide_model_family(cfg, evidence_summary, failure, raw)
        brief = build_step10_brief(cfg, decision, failure, evidence_summary)
    except (Step9ConfigError, Step9EvidenceError) as e:
        print(e, file=sys.stderr)
        return 1
    out = Path(args.out) if args.out else repo / str(cfg.get("outputs", {}).get("root", "ml_output/step9")) / str(
        cfg.get("outputs", {}).get("step10_architecture_brief", "step10_architecture_brief.json")
    )
    write_json(out, brief)
    print(str(out))
    return 0


def cmd_full_audit_run(args: argparse.Namespace) -> int:
    repo = _repo_root(args.repo_root)
    try:
        cfg = load_step9_decision_config(Path(args.config).resolve())
        raw = _load_raw(cfg, repo)
        evidence_summary = build_evidence_summary(cfg, repo, strict=True)
        failure = analyze_failure_modes(cfg, raw, repo)
        decision = decide_model_family(cfg, evidence_summary, failure, raw)
        brief = build_step10_brief(cfg, decision, failure, evidence_summary)
        write_step9_bundle(cfg, repo, evidence_summary, failure, decision, brief, raw)
    except (Step9ConfigError, Step9EvidenceError) as e:
        print(e, file=sys.stderr)
        return 1
    out = (repo / str(cfg.get("outputs", {}).get("root", "ml_output/step9"))).resolve()
    print(json.dumps({"ok": True, "output_dir": str(out), "outcome": decision.get("outcome")}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Step 9 model-family decision gate")
    sub = p.add_subparsers(dest="cmd", required=True)

    c1 = sub.add_parser("validate-config", help="Validate step9_decision_config.yaml")
    c1.add_argument("--config", default="src/ml/step9_decision_config.yaml")
    c1.set_defaults(func=cmd_validate_config)

    c2 = sub.add_parser("evidence-summary", help="Write step9_evidence_summary.json")
    c2.add_argument("--config", default="src/ml/step9_decision_config.yaml")
    c2.add_argument("--repo-root", default=None)
    c2.add_argument("--out", default=None)
    c2.add_argument("--allow-missing", action="store_true", help="Allow missing Step 8 files (summary only)")
    c2.set_defaults(func=cmd_evidence_summary)

    c3 = sub.add_parser("failure-modes", help="Write failure_mode_report.json")
    c3.add_argument("--config", default="src/ml/step9_decision_config.yaml")
    c3.add_argument("--repo-root", default=None)
    c3.add_argument("--out", default=None)
    c3.set_defaults(func=cmd_failure_modes)

    c4 = sub.add_parser("decide", help="Write model_family_decision.json")
    c4.add_argument("--config", default="src/ml/step9_decision_config.yaml")
    c4.add_argument("--repo-root", default=None)
    c4.add_argument("--out", default=None)
    c4.set_defaults(func=cmd_decide)

    c5 = sub.add_parser("step10-brief", help="Write step10_architecture_brief.json")
    c5.add_argument("--config", default="src/ml/step9_decision_config.yaml")
    c5.add_argument("--repo-root", default=None)
    c5.add_argument("--out", default=None)
    c5.set_defaults(func=cmd_step10_brief)

    c6 = sub.add_parser("full-audit-run", help="Run full pipeline and write all Step 9 artifacts")
    c6.add_argument("--config", default="src/ml/step9_decision_config.yaml")
    c6.add_argument("--repo-root", default=None)
    c6.set_defaults(func=cmd_full_audit_run)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
