from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

from ui.settings import UISettings
from ui.storage import UIStateStore


ACTIVE_RUN_STATUSES = {"QUEUED", "RUNNING", "WAITING_REMOTE", "CANCEL_REQUESTED"}


def is_process_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def terminate_process(pid: int | None) -> None:
    if pid is None or pid <= 0:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def build_worker_command(settings: UISettings, run_id: str, *, action: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "ui.worker",
        "--project-root",
        str(settings.project_root),
        "--ui-db-path",
        str(settings.state_db_path),
        "--run-id",
        run_id,
        "--action",
        action,
    ]


def launch_run_worker(
    store: UIStateStore,
    settings: UISettings,
    *,
    run_id: str,
    action: str = "start",
) -> int:
    run = store.get_run(run_id)
    if run is None:
        raise KeyError(run_id)
    log_path = Path(str(run["log_path"])) if run.get("log_path") else settings.log_root / f"{run_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = build_worker_command(settings, run_id, action=action)
    env = os.environ.copy()
    source_root = Path(__file__).resolve().parents[1]
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(source_root) if not existing_pythonpath else f"{source_root}{os.pathsep}{existing_pythonpath}"
    if settings.test_mode:
        env["UI_TEST_MODE"] = "1"
    with open(log_path, "a", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=str(source_root),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
        )
    store.update_run(
        run_id,
        pid=process.pid,
        command=" ".join(command),
        status="RUNNING" if action == "start" else run.get("status", "RUNNING"),
        log_path=log_path,
        started_at=run.get("started_at") or run.get("created_at"),
        last_heartbeat_at=run.get("last_heartbeat_at") or run.get("updated_at"),
    )
    store.append_run_event(
        run_id=run_id,
        event_type="worker_launch",
        stage=run.get("current_stage"),
        message=f"Worker launched with action={action}, pid={process.pid}.",
    )
    return process.pid


def repair_stale_runs(store: UIStateStore) -> None:
    for run in store.list_runs(statuses=sorted(ACTIVE_RUN_STATUSES)):
        status = str(run.get("status") or "")
        pid_value = run.get("pid")
        pid = None if pid_value is None else int(pid_value)
        if status == "WAITING_REMOTE":
            if pid is not None and not is_process_alive(pid):
                store.update_run(run["run_id"], pid=None)
            continue
        if not is_process_alive(pid):
            store.update_run(
                run["run_id"],
                status="INTERRUPTED",
                pid=None,
                error_message=run.get("error_message") or "Background worker stopped unexpectedly.",
                finished_at=run.get("finished_at") or run.get("updated_at"),
            )
            store.append_run_event(
                run_id=str(run["run_id"]),
                event_type="interrupted",
                stage=run.get("current_stage"),
                message="Worker process was not running during startup repair.",
            )

