from __future__ import annotations

import time
from pathlib import Path

from pipeline.orchestrator.state_store import StateStore as PipelineStateStore
from ui.tests.helpers import register_project, scaffold_project_files, wait_for_run_status


def test_reconcile_advances_waiting_remote_run_to_success(ui_context, monkeypatch):
    monkeypatch.setenv("UI_FAKE_BATCH_POLLS_BEFORE_SUCCESS", "0")
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Recon Lesson", transcript=True, dense_analysis=True)
    project = register_project(store, settings, "Recon Lesson")
    client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "batch_knowledge_only"},
        follow_redirects=False,
    )
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    wait_for_run_status(store, str(run["run_id"]), {"WAITING_REMOTE"})

    response = client.post(f"/runs/{run['run_id']}/reconcile", follow_redirects=True)

    assert response.status_code == 200
    final_row = wait_for_run_status(store, str(run["run_id"]), {"SUCCEEDED"})
    assert final_row["status"] == "SUCCEEDED"
    assert Path(str(final_row["pipeline_db_path"])).exists()
    assert (settings.data_root / "Recon Lesson" / "output_review" / "Recon Lesson.review_markdown.md").exists()


def test_reconcile_completes_fresh_project_batch_path(ui_context, monkeypatch):
    monkeypatch.setenv("UI_FAKE_BATCH_POLLS_BEFORE_SUCCESS", "0")
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Fresh Reconcile Lesson", transcript=True, video=True)
    project = register_project(store, settings, "Fresh Reconcile Lesson")
    client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "run_all_batch"},
        follow_redirects=False,
    )
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    current = wait_for_run_status(store, str(run["run_id"]), {"WAITING_REMOTE"})

    final_row = current if current["status"] == "SUCCEEDED" else None
    for _ in range(4):
        client.post(f"/runs/{run['run_id']}/reconcile", follow_redirects=True)
        deadline = time.time() + 15
        while time.time() < deadline:
            row = store.get_run(str(run["run_id"]))
            if row is not None and (
                row["status"] in {"SUCCEEDED", "FAILED"}
                or (row["status"] == "WAITING_REMOTE" and row.get("pid") is None)
            ):
                current = row
                break
            time.sleep(0.2)
        if current["status"] == "SUCCEEDED":
            final_row = current
            break

    assert final_row is not None
    assert final_row["status"] == "SUCCEEDED"
    project_root = settings.data_root / "Fresh Reconcile Lesson"
    assert (project_root / "dense_analysis.json").exists()
    assert (project_root / "output_review" / "Fresh Reconcile Lesson.review_markdown.md").exists()


def test_reconcile_marks_fake_batch_failure(ui_context, monkeypatch):
    monkeypatch.setenv("UI_FAKE_BATCH_SCENARIO", "fail")
    monkeypatch.setenv("UI_FAKE_BATCH_POLLS_BEFORE_SUCCESS", "0")
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Fail Lesson", transcript=True, dense_analysis=True)
    project = register_project(store, settings, "Fail Lesson")
    client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "batch_knowledge_only"},
        follow_redirects=False,
    )
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    wait_for_run_status(store, str(run["run_id"]), {"WAITING_REMOTE"})

    client.post(f"/runs/{run['run_id']}/reconcile", follow_redirects=True)

    failed = wait_for_run_status(store, str(run["run_id"]), {"FAILED"})
    assert "failure" in str(failed["error_message"]).lower()


def test_reconcile_advances_completed_vision_stage_without_active_jobs(ui_context, monkeypatch):
    monkeypatch.setenv("UI_FAKE_BATCH_POLLS_BEFORE_SUCCESS", "1")
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Completed Vision Lesson", transcript=True, video=True, batch_ready=True)
    project = register_project(store, settings, "Completed Vision Lesson")
    (settings.data_root / "Completed Vision Lesson" / "frames_dense").mkdir(parents=True, exist_ok=True)
    client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "batch_vision_only"},
        follow_redirects=False,
    )
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    wait_for_run_status(store, str(run["run_id"]), {"WAITING_REMOTE"})

    pipeline_store = PipelineStateStore(Path(str(run["pipeline_db_path"])))
    jobs = pipeline_store.list_batch_jobs(stage_name="vision")
    assert jobs
    for job in jobs:
        pipeline_store.update_batch_job_status(str(job["batch_job_name"]), status="SUCCEEDED")

    response = client.post(f"/runs/{run['run_id']}/reconcile", follow_redirects=True)

    assert response.status_code == 200
    final_row = wait_for_run_status(store, str(run["run_id"]), {"SUCCEEDED"})
    assert final_row["status"] == "SUCCEEDED"
    assert (settings.data_root / "Completed Vision Lesson" / "dense_analysis.json").exists()


def test_reconcile_recovers_stale_running_remote_worker(ui_context, monkeypatch):
    monkeypatch.setenv("UI_FAKE_BATCH_POLLS_BEFORE_SUCCESS", "0")
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Recovered Remote Lesson", transcript=True, dense_analysis=True)
    project = register_project(store, settings, "Recovered Remote Lesson")
    client.post(
        f"/projects/{project['project_id']}/runs",
        data={"run_mode": "batch_knowledge_only"},
        follow_redirects=False,
    )
    run = store.get_latest_run(project["project_id"])
    assert run is not None
    waiting = wait_for_run_status(store, str(run["run_id"]), {"WAITING_REMOTE"})

    store.update_run(
        str(waiting["run_id"]),
        status="RUNNING",
        pid=999999,
        current_stage="knowledge_remote",
        remote_job_name=str(waiting["remote_job_name"]),
        progress_message="Reconciling remote batch state.",
    )

    response = client.post(f"/runs/{waiting['run_id']}/reconcile", follow_redirects=True)

    assert response.status_code == 200
    final_row = wait_for_run_status(store, str(waiting["run_id"]), {"SUCCEEDED"})
    assert final_row["status"] == "SUCCEEDED"
    events = store.list_run_events(str(waiting["run_id"]))
    assert any(event["event_type"] == "remote_reconcile_recovered" for event in events)

