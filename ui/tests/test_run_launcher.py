from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import ui.run_launcher as run_launcher
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


def test_prepare_project_creates_all_prep_artifacts(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Prepare Flow Lesson", transcript=True, video=True)
    project = register_project(store, settings, "Prepare Flow Lesson")

    response = client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "prepare_project"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    wait_for_run_status(store, str(run["run_id"]), {"SUCCEEDED"})

    project_root = settings.data_root / "Prepare Flow Lesson"
    assert (project_root / "dense_index.json").exists()
    assert (project_root / "structural_index.json").exists()
    assert (project_root / "llm_queue" / "manifest.json").exists()
    assert list((project_root / "llm_queue").glob("*_prompt.txt"))


def test_run_all_batch_from_fresh_project_waits_for_remote(ui_context, monkeypatch):
    monkeypatch.setenv("UI_FAKE_BATCH_POLLS_BEFORE_SUCCESS", "1")
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Fresh Batch Lesson", transcript=True, video=True)
    project = register_project(store, settings, "Fresh Batch Lesson")

    response = client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "run_all_batch"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    waiting = wait_for_run_status(store, str(run["run_id"]), {"WAITING_REMOTE"})
    assert waiting["current_stage"] == "vision_remote"
    project_root = settings.data_root / "Fresh Batch Lesson"
    assert (project_root / "dense_index.json").exists()
    assert (project_root / "llm_queue" / "manifest.json").exists()
    assert list((project_root / "llm_queue").glob("*_prompt.txt"))


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
    assert "before starting another run" in second.text or "already in progress" in second.text


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


def test_repair_stale_remote_run_preserves_reconcile_resume(ui_context, monkeypatch):
    monkeypatch.setenv("UI_FAKE_BATCH_POLLS_BEFORE_SUCCESS", "1")
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Stale Remote Lesson", transcript=True, dense_analysis=True)
    project = register_project(store, settings, "Stale Remote Lesson")
    client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "batch_knowledge_only"},
        follow_redirects=False,
    )
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    waiting = wait_for_run_status(store, str(run["run_id"]), {"WAITING_REMOTE"})

    monkeypatch.setattr(run_launcher, "is_process_alive", lambda pid: False)
    store.update_run(
        str(waiting["run_id"]),
        status="RUNNING",
        pid=999999,
        current_stage="knowledge_remote",
        remote_job_name=str(waiting["remote_job_name"]),
        progress_message="Reconciling remote batch state.",
    )

    run_launcher.repair_stale_runs(store)

    repaired = store.get_run(str(waiting["run_id"]))
    assert repaired is not None
    assert repaired["status"] == "WAITING_REMOTE"
    assert repaired["pid"] is None
    events = store.list_run_events(str(waiting["run_id"]))
    assert any(event["event_type"] == "remote_reconcile_recovered" for event in events)


def test_sync_full_missing_prerequisites_are_blocked_in_ui(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Missing Queue Lesson", transcript=True, video=True)
    project = register_project(store, settings, "Missing Queue Lesson")

    response = client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "sync_full"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Run Step 1 dense capture first." in response.text
    assert store.get_latest_run(project["project_id"]) is None


def test_unicode_project_name_does_not_break_worker_logging(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    lesson_name = "Урок 5. Уровни (часть 4)_1_1"
    scaffold_project_files(settings, lesson_name, transcript=True, video=True, batch_ready=True)
    project = register_project(store, settings, lesson_name)

    response = client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "batch_vision_only"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    waiting = wait_for_run_status(store, str(run["run_id"]), {"WAITING_REMOTE"})

    log_path = Path(str(waiting["log_path"]))
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


def test_unicode_project_name_does_not_break_prepare_dense_capture(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    lesson_name = "Урок 5. Уровни (часть 4)_1_1"
    scaffold_project_files(settings, lesson_name, transcript=True, video=True)
    project = register_project(store, settings, lesson_name)

    response = client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "prepare_dense_capture"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    succeeded = wait_for_run_status(store, str(run["run_id"]), {"SUCCEEDED"})

    log_path = Path(str(succeeded["log_path"]))
    deadline = time.time() + 5
    log_text = ""
    while time.time() < deadline:
        log_text = log_path.read_text(encoding="utf-8")
        if "Running Step 1 dense capture." in log_text and lesson_name in log_text:
            break
        time.sleep(0.1)
    assert "Running Step 1 dense capture." in log_text
    assert lesson_name in log_text


def test_is_process_alive_windows_uses_tasklist(monkeypatch):
    monkeypatch.setattr(run_launcher.os, "name", "nt", raising=False)
    monkeypatch.setattr(
        run_launcher.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="python.exe                   10196 Console", stderr="", returncode=0),
    )

    assert run_launcher.is_process_alive(10196) is True


def test_is_process_alive_windows_returns_false_when_task_missing(monkeypatch):
    monkeypatch.setattr(run_launcher.os, "name", "nt", raising=False)
    monkeypatch.setattr(
        run_launcher.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout="INFO: No tasks are running which match the specified criteria.",
            stderr="",
            returncode=0,
        ),
    )

    assert run_launcher.is_process_alive(10196) is False

