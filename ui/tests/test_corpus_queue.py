from __future__ import annotations

from ui.services.runs import _safe_run_token
from ui.tests.helpers import register_project, scaffold_project_files, wait_for_run_status


def test_corpus_queue_filters_ready_and_blocked_projects(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Ready Lesson", transcript=True, dense_analysis=True, corpus_ready=True, exports_ready=True)
    register_project(store, settings, "Ready Lesson")
    scaffold_project_files(settings, "Blocked Lesson", transcript=True)
    register_project(store, settings, "Blocked Lesson")

    response = client.get("/corpus")

    assert response.status_code == 200
    assert "Ready Lesson" in response.text
    assert "Blocked Lesson" in response.text
    assert "ready" in response.text
    assert "blocked" in response.text


def test_corpus_build_runs_for_selected_projects(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Corpus A", transcript=True, dense_analysis=True, corpus_ready=True, exports_ready=True)
    project_a = register_project(store, settings, "Corpus A")
    scaffold_project_files(settings, "Corpus B", transcript=True, dense_analysis=True, corpus_ready=True, exports_ready=True)
    project_b = register_project(store, settings, "Corpus B")

    response = client.post(
        "/corpus/build",
        data={"project_ids": [project_a["project_id"], project_b["project_id"]]},
        follow_redirects=True,
    )

    assert response.status_code == 200
    run = next(row for row in store.list_runs(run_kind="CORPUS"))
    final_row = wait_for_run_status(store, str(run["run_id"]), {"SUCCEEDED"})
    assert final_row["status"] == "SUCCEEDED"
    output_root = settings.corpus_output_root / f"corpus_{_safe_run_token(str(run['run_id']))}"
    assert (output_root / "corpus_knowledge_events.jsonl").exists()
    assert (output_root / "validation_report.json").exists()

