from __future__ import annotations

from ui.run_launcher import launch_run_worker
from ui.services.runs import create_corpus_run
from ui.settings import UISettings
from ui.storage import UIStateStore


def launch_corpus_build(store: UIStateStore, settings: UISettings, project_ids: list[str]):
    run = create_corpus_run(store, settings, project_ids=project_ids)
    launch_run_worker(store, settings, run_id=run.run_id, action="start")
    return run

