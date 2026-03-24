from __future__ import annotations

import threading
import time

from ui.run_launcher import is_process_alive, is_remote_reconcile_recoverable, launch_run_worker
from ui.settings import UISettings
from ui.storage import UIStateStore


def launch_waiting_remote_runs(
    store: UIStateStore,
    settings: UISettings,
    *,
    run_ids: list[str] | None = None,
) -> int:
    launched = 0
    candidates = [
        run
        for run in store.list_runs(statuses=["WAITING_REMOTE", "RUNNING"])
        if is_remote_reconcile_recoverable(run)
    ]
    if run_ids is not None:
        allowed = set(run_ids)
        candidates = [run for run in candidates if str(run["run_id"]) in allowed]
    for run in candidates:
        pid_value = run.get("pid")
        pid = None if pid_value is None else int(pid_value)
        if is_process_alive(pid):
            continue
        updates = {"pid": None}
        if str(run.get("status") or "") != "WAITING_REMOTE":
            updates.update(
                {
                    "status": "WAITING_REMOTE",
                    "finished_at": None,
                    "exit_code": None,
                    "error_message": None,
                }
            )
            store.append_run_event(
                run_id=str(run["run_id"]),
                event_type="remote_reconcile_recovered",
                stage=run.get("current_stage"),
                message="Recovered stale remote reconcile worker; relaunching reconcile.",
            )
        store.update_run(str(run["run_id"]), **updates)
        launch_run_worker(store, settings, run_id=str(run["run_id"]), action="continue")
        launched += 1
    return launched


class ReconcileScheduler:
    def __init__(self, store: UIStateStore, settings: UISettings) -> None:
        self.store = store
        self.settings = settings
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, name="ui-reconcile-scheduler", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run_loop(self) -> None:
        interval = max(2, int(self.settings.scheduler_interval_seconds))
        while not self._stop_event.wait(interval):
            try:
                launch_waiting_remote_runs(self.store, self.settings)
            except Exception:
                time.sleep(1)

