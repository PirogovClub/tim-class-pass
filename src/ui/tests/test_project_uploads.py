from __future__ import annotations

from ui.tests.helpers import create_external_source


def test_project_upload_copies_video_and_transcript_into_data_root(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]

    response = client.post(
        "/projects",
        data={"title": "Uploaded Lesson", "project_root": "", "source_video_path": "", "transcript_path": ""},
        files={
            "source_video_upload": ("lesson.mp4", b"fake-video", "video/mp4"),
            "transcript_upload": ("lesson.vtt", b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello\n", "text/vtt"),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    project_root = settings.data_root / "Uploaded Lesson"
    assert (project_root / "Uploaded Lesson.mp4").exists()
    assert (project_root / "Uploaded Lesson.vtt").exists()
    assert "ready_to_run" in response.text


def test_project_import_copies_manual_paths_into_project_root(ui_context, tmp_path):
    client = ui_context["client"]
    settings = ui_context["settings"]

    external_video = create_external_source(tmp_path, "inbox/video.mp4", "fake-video")
    external_transcript = create_external_source(
        tmp_path,
        "inbox/transcript.vtt",
        "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello\n",
    )

    response = client.post(
        "/projects",
        data={
            "title": "Copied Lesson",
            "project_root": "",
            "source_video_path": str(external_video),
            "transcript_path": str(external_transcript),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    project_root = settings.data_root / "Copied Lesson"
    assert (project_root / "Copied Lesson.mp4").exists()
    assert (project_root / "Copied Lesson.vtt").exists()


def test_project_upload_rejects_invalid_transcript_extension(ui_context):
    client = ui_context["client"]

    response = client.post(
        "/projects",
        data={"title": "Bad Upload", "project_root": "", "source_video_path": "", "transcript_path": ""},
        files={
            "transcript_upload": ("lesson.txt", b"not-a-vtt", "text/plain"),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert 'data-testid="form-error"' in response.text
    assert "Unsupported file extension" in response.text

