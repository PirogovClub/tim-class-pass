from __future__ import annotations

import pytest

from ui.models import RUN_STATUS_SUCCEEDED
from ui.services.runs import RUN_MODE_DETAILS, SUPPORTED_RUN_MODES, create_project_run
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
    assert "Step 1. Dense Capture" in response.text


def test_create_download_project_uses_detected_video_id(ui_context, monkeypatch):
    client = ui_context["client"]
    settings = ui_context["settings"]

    monkeypatch.setattr("pipeline.downloader.extract_video_id", lambda url: "abc123xyz00")

    response = client.post(
        "/projects",
        data={
            "title": "Downloaded Lesson",
            "project_root": "",
            "source_mode": "download",
            "source_url": "https://www.youtube.com/watch?v=abc123xyz00",
            "source_video_path": "",
            "transcript_path": "",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert (settings.data_root / "abc123xyz00").exists()
    assert "Source mode: download" in response.text
    assert "Run download" in response.text
    assert "Run Step 0 download" in response.text


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
    assert "Grouped actions" in response.text
    assert "Run Analyze project locally" in response.text
    assert "Full UI path: Step 0 -> Step 1 -> Step 1.5 -> Step 1.6 -> Step 1.7 -> Step 2 -> Step 3." in response.text
    assert "Run Corpus build" in response.text


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
    assert "Remote batch knowledge only" in response.text
    assert "Run Remote batch knowledge only" in response.text
    assert "Step 3. Component 2 And Exports" in response.text
    assert "Knowledge events" in response.text


def test_run_mode_details_cover_all_supported_modes():
    assert set(RUN_MODE_DETAILS) == set(SUPPORTED_RUN_MODES)
    for mode, details in RUN_MODE_DETAILS.items():
        assert details["title"], mode
        assert details["summary"], mode
        assert details["when_to_use"], mode
        assert details["outputs"], mode
        assert details["steps"], mode


def test_fresh_project_shows_prep_steps_before_analysis(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Prep Lesson", transcript=True, video=True)
    project = register_project(store, settings, "Prep Lesson")

    response = client.get(f"/projects/{project['project_id']}")

    assert response.status_code == 200
    assert "Run Step 1 dense capture" in response.text
    assert "Run Prepare project" in response.text
    assert "Run all locally" in response.text
    assert "Run Step 1 dense capture first." in response.text


def test_run_detail_shows_human_readable_remote_stage(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Lesson Delta", transcript=True, video=True, dense_analysis=True)
    project = register_project(store, settings, "Lesson Delta")
    store.create_run(
        run_id=f"{project['project_id']}::remote",
        project_id=project["project_id"],
        run_mode="batch_full",
        status="WAITING_REMOTE",
        current_stage="knowledge_remote",
        progress_message="Remote batch still processing.",
        remote_job_name="batches/example",
    )

    response = client.get(f"/runs/{project['project_id']}::remote")

    assert response.status_code == 200
    assert "Step 3 knowledge batch wait" in response.text
    assert "Processing: Knowledge extraction" in response.text
    assert "(knowledge_remote)" in response.text


def test_batch_vision_rerun_requires_force_overwrite(ui_context):
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Force Vision Lesson", transcript=True, video=True, dense_analysis=True)
    project = register_project(store, settings, "Force Vision Lesson")

    with pytest.raises(ValueError, match="Enable force overwrite"):
        create_project_run(
            store,
            settings,
            project_id=str(project["project_id"]),
            run_mode="batch_vision_only",
        )

    run = create_project_run(
        store,
        settings,
        project_id=str(project["project_id"]),
        run_mode="batch_vision_only",
        force_overwrite=True,
    )

    assert run.force_overwrite is True
    assert run.current_stage == "vision_submit"
    stored = store.get_run(run.run_id)
    assert stored is not None
    assert stored["force_overwrite"] == 1


def test_batch_full_force_overwrite_restarts_from_vision(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Force Batch Full Lesson", transcript=True, video=True, dense_analysis=True)
    project = register_project(store, settings, "Force Batch Full Lesson")

    default_run = create_project_run(
        store,
        settings,
        project_id=str(project["project_id"]),
        run_mode="batch_full",
    )
    store.update_run(default_run.run_id, status="SUCCEEDED")
    forced_run = create_project_run(
        store,
        settings,
        project_id=str(project["project_id"]),
        run_mode="batch_full",
        force_overwrite=True,
    )

    assert default_run.current_stage == "knowledge_submit"
    assert forced_run.current_stage == "vision_submit"

    response = client.get(f"/runs/{forced_run.run_id}")

    assert response.status_code == 200
    assert "Force overwrite: yes" in response.text
    assert "Force overwrite existing outputs when supported" in client.get(f"/projects/{project['project_id']}").text

