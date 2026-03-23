from __future__ import annotations

from ui.models import RUN_STATUS_SUCCEEDED
from ui.services.runs import RUN_MODE_DETAILS, SUPPORTED_RUN_MODES
from ui.tests.helpers import register_project, scaffold_project_files


def test_create_project_uses_data_root_when_root_is_blank(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]

    response = client.post(
        "/projects",
        data={"title": "Lesson Alpha", "project_root": "", "source_video_path": "", "transcript_path": ""},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert (settings.data_root / "Lesson Alpha").exists()
    assert 'data-testid="project-status"' in response.text
    assert "missing_inputs" in response.text
    assert "Pipeline map" in response.text
    assert "Add a transcript first" in response.text


def test_project_detail_detects_artifacts_and_run_history(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(
        settings,
        "Lesson Beta",
        transcript=True,
        video=True,
        filtered_visuals=True,
        dense_analysis=True,
        corpus_ready=True,
        exports_ready=True,
    )
    project = register_project(store, settings, "Lesson Beta")
    store.create_run(
        run_id=f"{project['project_id']}::001",
        project_id=project["project_id"],
        run_mode="sync_full",
        status=RUN_STATUS_SUCCEEDED,
    )

    response = client.get(f"/projects/{project['project_id']}")

    assert response.status_code == 200
    assert "complete" in response.text
    assert "Knowledge events: yes" in response.text
    assert "RAG-ready output: yes" in response.text
    assert f"{project['project_id']}::001" in response.text
    assert "What this run will do" in response.text
    assert "Runs the whole single-project pipeline in one background worker" in response.text
    assert "Typical order: Inputs -> Vision -> Knowledge -> Exports -> Corpus." in response.text
    assert "Project outputs are complete" in response.text


def test_project_detail_recommends_knowledge_stage_when_dense_analysis_exists(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(
        settings,
        "Lesson Gamma",
        transcript=True,
        video=True,
        dense_analysis=True,
    )
    project = register_project(store, settings, "Lesson Gamma")

    response = client.get(f"/projects/{project['project_id']}")

    assert response.status_code == 200
    assert "Dense analysis is ready. The next stage is knowledge extraction." in response.text
    assert "Remote batch knowledge only" in response.text
    assert 'option value="batch_knowledge_only" selected' in response.text
    assert "Knowledge events" in response.text


def test_run_mode_details_cover_all_supported_modes():
    assert set(RUN_MODE_DETAILS) == set(SUPPORTED_RUN_MODES)
    for mode, details in RUN_MODE_DETAILS.items():
        assert details["title"], mode
        assert details["summary"], mode
        assert details["when_to_use"], mode
        assert details["outputs"], mode
        assert details["steps"], mode

