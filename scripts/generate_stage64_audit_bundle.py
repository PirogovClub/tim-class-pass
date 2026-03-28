#!/usr/bin/env python3
"""Assemble ``audit/stage6_4_audit_bundle_<UTC-timestamp>/`` and zip for Stage 6.4 handoff.

When ``output_rag/retrieval_docs_all.jsonl`` exists (full corpus checkout):

- ``examples/example_browser_*.json`` are captured via TestClient using **discovered** doc ids
  (search → rule → linked evidence/event/concept/lesson), not hardcoded ``lesson_alpha`` ids.
- **Live** Playwright screenshots require a running browser API (same corpus). Probe
  ``STAGE64_BROWSER_API_BASE`` (default ``http://127.0.0.1:8000``) ``GET /browser/health``.
- Set ``STAGE64_ALLOW_MOCK_ONLY_AUDIT_BUNDLE=1`` to skip the live screenshot requirement (not for final audit).
- For a **one-command final bundle** (recommended for auditors), use ``--auto-start-api``:
  spawns ``python -m pipeline.rag.cli serve`` on ``STAGE64_BROWSER_API_BASE`` if ``/browser/health`` is down,
  then runs live Playwright and shuts the server down.

Each run creates a new folder and zip; previous bundles are left in place.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

MIN_MOCK_SCREENSHOTS = 7
MIN_LIVE_SCREENSHOTS = 7


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


def _run(cmd: list[str], cwd: Path, log: Path, env: dict[str, str] | None = None) -> int:
    run_env = env if env is not None else os.environ.copy()
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=run_env)
    log.parent.mkdir(parents=True, exist_ok=True)
    prev = log.read_text(encoding="utf-8") if log.exists() else ""
    log.write_text(
        prev + f"\n\n=== {' '.join(cmd)} (cwd={cwd}) exit={proc.returncode} ===\n"
        + proc.stdout
        + "\n"
        + proc.stderr,
        encoding="utf-8",
    )
    return proc.returncode


def _load_capture_module(repo: Path) -> Any:
    path = repo / "scripts" / "stage64_browser_example_capture.py"
    spec = importlib.util.spec_from_file_location("stage64_browser_example_capture", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _browser_api_base() -> str:
    return os.environ.get("STAGE64_BROWSER_API_BASE", "http://127.0.0.1:8000").rstrip("/")


def _probe_browser_health(base: str, timeout_s: float = 3.0) -> bool:
    url = f"{base}/browser/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # noqa: S310 — audit script only
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False


def _api_host_port_from_base(base: str) -> tuple[str, int]:
    raw = base if "://" in base else f"http://{base}"
    u = urlparse(raw)
    host = u.hostname or "127.0.0.1"
    port = u.port or 8000
    return host, port


def _normalize_api_base(base: str) -> str:
    host, port = _api_host_port_from_base(base)
    return f"http://{host}:{port}"


def _wait_browser_health(base: str, timeout_s: float = 180.0, interval_s: float = 0.5) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _probe_browser_health(base, timeout_s=2.0):
            return True
        time.sleep(interval_s)
    return False


def _spawn_rag_api_server(repo: Path, host: str, port: int, stderr_path: Path) -> tuple[subprocess.Popen[Any], Any]:
    cmd = [
        sys.executable,
        "-m",
        "pipeline.rag.cli",
        "serve",
        "--host",
        host,
        "--port",
        str(port),
    ]
    err_f = stderr_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=repo,
        stdout=subprocess.DEVNULL,
        stderr=err_f,
        text=True,
    )
    return proc, err_f


def _terminate_spawned_api(
    proc: subprocess.Popen[Any] | None,
    err_f: Any,
    test_log: Path,
    label: str,
) -> None:
    if proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    if err_f is not None:
        try:
            err_f.close()
        except OSError:
            pass
    note = f"\n\n=== {label}: RAG API subprocess exit={proc.returncode} pid={proc.pid} ===\n"
    prev = test_log.read_text(encoding="utf-8") if test_log.exists() else ""
    test_log.write_text(prev + note, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    repo = _repo_root()
    bundle_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S_%f")
    bundle = repo / "audit" / f"stage6_4_audit_bundle_{bundle_ts}"
    source = bundle / "source"
    examples = bundle / "examples"
    screenshots = bundle / "screenshots"
    shot_mock = screenshots / "mock"
    shot_live = screenshots / "live"
    bundle.mkdir(parents=True)
    source.mkdir(parents=True)
    examples.mkdir(parents=True)
    shot_mock.mkdir(parents=True)
    shot_live.mkdir(parents=True)

    parser = argparse.ArgumentParser(description="Assemble Stage 6.4 audit bundle (timestamped zip).")
    parser.add_argument(
        "--auto-start-api",
        action="store_true",
        help="If /browser/health is down, spawn `python -m pipeline.rag.cli serve` then run live Playwright.",
    )
    args = parser.parse_args(argv)

    has_corpus = (repo / "output_rag" / "retrieval_docs_all.jsonl").is_file()
    allow_mock_only = os.environ.get("STAGE64_ALLOW_MOCK_ONLY_AUDIT_BUNDLE", "").strip() in (
        "1",
        "true",
        "yes",
    )

    test_log = bundle / "test_output.txt"
    test_log.write_text("", encoding="utf-8")
    rc_py = _run([sys.executable, "-m", "pytest", "tests/explorer", "-q"], repo, test_log)
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    rc_ui = _run(
        [npm, "test", "--", "--run"],
        repo / "ui" / "explorer",
        test_log,
    )
    rc_e2e_mock = _run(
        [npm, "run", "audit:screenshots:6.4"],
        repo / "ui" / "explorer",
        test_log,
    )

    # Code snapshots
    shutil.copytree(repo / "pipeline" / "explorer", source / "pipeline" / "explorer", dirs_exist_ok=True)
    shutil.copytree(repo / "tests" / "explorer", source / "tests" / "explorer", dirs_exist_ok=True)
    e2e_src = repo / "ui" / "explorer" / "tests" / "e2e"
    if e2e_src.is_dir():
        shutil.copytree(e2e_src, source / "ui" / "explorer" / "tests" / "e2e", dirs_exist_ok=True)
    for ui_root_file in ("playwright.config.ts", "package.json", "vite.config.ts", "tsconfig.json", "tsconfig.app.json"):
        p = repo / "ui" / "explorer" / ui_root_file
        if p.is_file():
            dest = source / "ui" / "explorer" / ui_root_file
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)

    ui_dest = source / "ui" / "explorer" / "src"
    ui_src = repo / "ui" / "explorer" / "src"
    for rel in (
        "app/router.tsx",
        "pages/SearchPage.tsx",
        "pages/CompareUnitsPage.tsx",
        "pages/EventPage.tsx",
        "pages/RagSearchPage.tsx",
        "pages/RagSearchPage.test.tsx",
        "components/layout/TopBar.tsx",
        "components/search/ResultCard.tsx",
        "components/common/ProvenanceSection.tsx",
        "components/event/EventDetailPage.tsx",
        "components/lesson/LessonTopEvents.tsx",
        "components/lesson/LessonDetailPage.tsx",
        "components/rule/RuleDetailPage.tsx",
        "components/evidence/EvidenceDetailPage.tsx",
        "hooks/useMultiUnitCompare.ts",
        "hooks/useMultiUnitCompare.test.ts",
        "hooks/useEventDetail.ts",
        "lib/api/browser.ts",
        "lib/api/rag.ts",
        "lib/api/schemas.ts",
        "lib/api/types.ts",
        "lib/utils/entity.ts",
    ):
        p = ui_src / rel
        if p.exists():
            out = ui_dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out)
    for script in ("generate_stage64_audit_bundle.py", "stage64_browser_example_capture.py"):
        sp = repo / "scripts" / script
        if sp.exists():
            dest = source / "scripts" / script
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sp, dest)

    for doc in (
        "docs/stage6_4_rule_browser.md",
        "RUN_STAGE6_4_AUDIT.md",
        "STAGE6_4_HANDOFF.md",
    ):
        p = repo / doc
        if p.exists():
            dest = bundle / Path(doc).name
            shutil.copy2(p, dest)

    for ctx in ("pyproject.toml",):
        p = repo / ctx
        if p.is_file():
            shutil.copy2(p, bundle / ctx)

    examples_note: dict[str, Any] = {
        "has_output_rag_corpus": has_corpus,
        "live_api_json_captured": False,
        "live_browser_screenshots": False,
        "mock_ui_screenshots": True,
        "note": "",
        "discovered_ids": {},
    }

    root_str = str(repo)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    if has_corpus:
        try:
            from fastapi.testclient import TestClient

            from pipeline.rag.api import app, init_app
            from pipeline.rag.config import RAGConfig

            cfg = RAGConfig()
            init_app(cfg)
            client = TestClient(app)
            cap_mod = _load_capture_module(repo)
            disc_meta = cap_mod.capture_browser_examples(client, examples)
            examples_note["live_api_json_captured"] = True
            examples_note["discovered_ids"] = disc_meta.get("discovered_ids", {})
            examples_note["note"] = (
                "example_browser_*.json captured via TestClient using ids discovered from /browser/search "
                f"and rule detail chain. Winning search query: {disc_meta.get('discovered_ids', {}).get('search_query_winning')!r}."
            )
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: Live example JSON capture failed: {exc}", file=sys.stderr)
            return 1
    else:
        examples_note["note"] = (
            "No output_rag/retrieval_docs_all.jsonl — example_browser_*.json were not generated "
            "(avoids misleading 404-style fixture ids). Run the bundle on a full corpus checkout for audit JSON."
        )

    # Mock screenshots → screenshots/mock/
    mock_out = repo / "ui" / "explorer" / "stage6-4-screenshots-out"
    audit_mock = repo / "audit" / "stage6_4_explorer_screenshots" / "mock"
    audit_mock.mkdir(parents=True, exist_ok=True)
    if mock_out.exists():
        for png in sorted(mock_out.glob("*.png")):
            shutil.copy2(png, audit_mock / png.name)
            shutil.copy2(png, shot_mock / png.name)

    mock_count = len(list(shot_mock.glob("*.png")))
    if mock_count < MIN_MOCK_SCREENSHOTS:
        print(
            f"ERROR: Expected at least {MIN_MOCK_SCREENSHOTS} mock PNGs in screenshots/mock, found {mock_count}.",
            file=sys.stderr,
        )
        return 1

    rc_e2e_live = 0
    api_proc: subprocess.Popen[Any] | None = None
    api_err_f: Any = None
    if has_corpus and not allow_mock_only:
        api_base = _normalize_api_base(_browser_api_base())
        spawned_local_api = False
        if not _probe_browser_health(api_base):
            if args.auto_start_api:
                host, port = _api_host_port_from_base(api_base)
                api_stderr = bundle / "rag_api_serve.stderr.log"
                prev = test_log.read_text(encoding="utf-8") if test_log.exists() else ""
                test_log.write_text(
                    prev
                    + f"\n\n=== Spawning RAG API: python -m pipeline.rag.cli serve --host {host} --port {port} ===\n"
                    + f"(stderr: {api_stderr.name})\n",
                    encoding="utf-8",
                )
                api_proc, api_err_f = _spawn_rag_api_server(repo, host, port, api_stderr)
                spawned_local_api = True
                if not _wait_browser_health(api_base, timeout_s=240.0):
                    print(
                        f"ERROR: RAG API did not become healthy at {api_base}/browser/health within timeout. "
                        f"See {api_stderr} for server stderr.",
                        file=sys.stderr,
                    )
                    _terminate_spawned_api(api_proc, api_err_f, test_log, "teardown after health timeout")
                    return 1
            else:
                print(
                    f"ERROR: Browser API not reachable at {api_base}/browser/health — "
                    "start the RAG API (same corpus as output_rag), run with "
                    "`python scripts/generate_stage64_audit_bundle.py --auto-start-api`, "
                    "or set STAGE64_ALLOW_MOCK_ONLY_AUDIT_BUNDLE=1 for a non-final bundle.",
                    file=sys.stderr,
                )
                return 1
        live_ok = False
        try:
            live_env = os.environ.copy()
            live_env["STAGE64_LIVE_E2E"] = "1"
            live_env["VITE_BROWSER_API_BASE"] = api_base
            rc_e2e_live = _run(
                [npm, "run", "audit:screenshots:6.4:live"],
                repo / "ui" / "explorer",
                test_log,
                env=live_env,
            )
            if rc_e2e_live != 0:
                print("ERROR: Live Playwright audit failed.", file=sys.stderr)
            else:
                live_out = repo / "ui" / "explorer" / "stage6-4-screenshots-live-out"
                audit_live = repo / "audit" / "stage6_4_explorer_screenshots" / "live"
                audit_live.mkdir(parents=True, exist_ok=True)
                if live_out.exists():
                    for png in sorted(live_out.glob("*.png")):
                        shutil.copy2(png, audit_live / png.name)
                        shutil.copy2(png, shot_live / png.name)

                live_count = len(list(shot_live.glob("*.png")))
                if live_count < MIN_LIVE_SCREENSHOTS:
                    print(
                        f"ERROR: Expected at least {MIN_LIVE_SCREENSHOTS} live PNGs in screenshots/live, "
                        f"found {live_count}.",
                        file=sys.stderr,
                    )
                else:
                    examples_note["live_browser_screenshots"] = True
                    if spawned_local_api:
                        examples_note["note"] += (
                            " RAG API was spawned by this bundle script (--auto-start-api) for live Playwright."
                        )
                    live_ok = True
        finally:
            if spawned_local_api:
                _terminate_spawned_api(api_proc, api_err_f, test_log, "teardown after live e2e")
        if not live_ok:
            return 1
    elif has_corpus and allow_mock_only:
        examples_note["live_browser_screenshots"] = False
        examples_note["note"] += " STAGE64_ALLOW_MOCK_ONLY_AUDIT_BUNDLE=1: live screenshots skipped."

    (examples / "examples_manifest.json").write_text(json.dumps(examples_note, indent=2), encoding="utf-8")

    _write(
        bundle / "REPRODUCIBILITY.md",
        f"""# Stage 6.4 audit bundle reproducibility

- **source/** is a partial snapshot for review (not a standalone runnable tree).
- Re-run from a **full** `tim-class-pass` checkout per `RUN_STAGE6_4_AUDIT.md`.
- **examples/example_browser_*.json** (when `output_rag` is present): captured with FastAPI `TestClient` after **discovering** ids via `/browser/search` → rule → linked units (`scripts/stage64_browser_example_capture.py`).
- **screenshots/mock/**: Playwright with **mocked** `/browser/*` JSON (`tests/e2e/stage6-4-audit-screenshots.spec.ts`) — UI component proof.
- **screenshots/live/**: Playwright with **no mocks**, proxy to real API (`tests/e2e/stage6-4-live-audit-screenshots.spec.ts`) — integration proof; requires API at `VITE_BROWSER_API_BASE`.
- Bundle script requires **{MIN_MOCK_SCREENSHOTS}** mock PNGs; with corpus + strict mode, **{MIN_LIVE_SCREENSHOTS}** live PNGs and a healthy `/browser/health` probe (or use ``--auto-start-api``).
""",
    )

    zip_path = repo / "audit" / f"stage6_4_audit_bundle_{bundle_ts}.zip"
    _zip_dir(bundle, zip_path)
    archives = repo / "audit" / "archives"
    archives.mkdir(parents=True, exist_ok=True)
    archive_copy = archives / zip_path.name
    shutil.copy2(zip_path, archive_copy)

    live_n = len(list(shot_live.glob("*.png")))
    print(f"Bundle: {bundle}")
    print(f"Zip: {zip_path}")
    print(
        f"pytest explorer exit: {rc_py}; npm test exit: {rc_ui}; "
        f"playwright mock exit: {rc_e2e_mock}; playwright live exit: {rc_e2e_live}; "
        f"mock PNGs: {mock_count}; live PNGs: {live_n}"
    )
    if rc_py != 0 or rc_ui != 0 or rc_e2e_mock != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
