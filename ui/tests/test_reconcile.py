from __future__ import annotations

from pathlib import Path

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

