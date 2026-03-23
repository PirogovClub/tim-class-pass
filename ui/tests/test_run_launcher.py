from __future__ import annotations

import time
from pathlib import Path

from ui.tests.helpers import register_project, scaffold_project_files, wait_for_run_status


def test_batch_run_launch_persists_metadata_and_waiting_remote(ui_context, monkeypatch):
    monkeypatch.setenv("UI_FAKE_BATCH_POLLS_BEFORE_SUCCESS", "1")
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Batch Lesson", transcript=True, dense_analysis=True)
    project = register_project(store, settings, "Batch Lesson")

    response = client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "batch_knowledge_only"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    row = wait_for_run_status(store, str(run["run_id"]), {"WAITING_REMOTE"})
    assert row["command"]
    assert row["pipeline_db_path"]
    assert row["current_stage"] == "knowledge_remote"
    assert row["remote_job_name"]


def test_project_concurrency_lock_blocks_second_active_run(ui_context, monkeypatch):
    monkeypatch.setenv("UI_FAKE_BATCH_POLLS_BEFORE_SUCCESS", "1")
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Lock Lesson", transcript=True, dense_analysis=True)
    project = register_project(store, settings, "Lock Lesson")

    first = client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "batch_knowledge_only"},
        follow_redirects=False,
    )
    assert first.status_code == 303
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    wait_for_run_status(store, str(run["run_id"]), {"WAITING_REMOTE"})

    second = client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "deterministic_postprocess_only"},
        follow_redirects=True,
    )

    assert second.status_code == 200
    assert "already has active background work" in second.text


def test_cancel_waiting_remote_run_marks_row_cancelled(ui_context, monkeypatch):
    monkeypatch.setenv("UI_FAKE_BATCH_POLLS_BEFORE_SUCCESS", "1")
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Cancel Lesson", transcript=True, dense_analysis=True)
    project = register_project(store, settings, "Cancel Lesson")
    client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "batch_knowledge_only"},
        follow_redirects=False,
    )
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    wait_for_run_status(store, str(run["run_id"]), {"WAITING_REMOTE"})

    response = client.post(f"/runs/{run['run_id']}/cancel", follow_redirects=True)

    assert response.status_code == 200
    updated = store.get_run(str(run["run_id"]))
    assert updated is not None
    assert updated["status"] == "CANCELLED"


def test_sync_full_missing_prerequisites_writes_helpful_failure_log(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Missing Queue Lesson", transcript=True, video=True)
    project = register_project(store, settings, "Missing Queue Lesson")

    response = client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "sync_full"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    failed = wait_for_run_status(store, str(run["run_id"]), {"FAILED"})
    error_message = str(failed["error_message"])
    assert "sync vision stage" in error_message
    assert "dense_index.json" in error_message
    assert "llm_queue" in error_message
    assert "Step 1.6" in error_message

    log_path = Path(str(failed["log_path"]))
    deadline = time.time() + 5
    log_text = ""
    while time.time() < deadline:
        log_text = log_path.read_text(encoding="utf-8")
        if "run metadata" in log_text and "sync vision prerequisites" in log_text:
            break
        time.sleep(0.1)
    assert "run metadata" in log_text
    assert "owner project snapshot" in log_text
    assert "sync vision prerequisites" in log_text
    assert "dense_index_exists" in log_text
    assert "queue_manifest_exists" in log_text


def test_unicode_project_name_does_not_break_worker_logging(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    lesson_name = "Урок 5. Уровни (часть 4)_1_1"
    scaffold_project_files(settings, lesson_name, transcript=True, video=True)
    project = register_project(store, settings, lesson_name)

    response = client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "batch_vision_only"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    failed = wait_for_run_status(store, str(run["run_id"]), {"FAILED"})
    error_message = str(failed["error_message"])
    assert "batch vision submit stage" in error_message
    assert "llm_queue" in error_message

    log_path = Path(str(failed["log_path"]))
    deadline = time.time() + 5
    log_text = ""
    while time.time() < deadline:
        log_text = log_path.read_text(encoding="utf-8")
        if "owner project snapshot" in log_text and lesson_name in log_text:
            break
        time.sleep(0.1)
    assert "run metadata" in log_text
    assert "owner project snapshot" in log_text
    assert lesson_name in log_text

