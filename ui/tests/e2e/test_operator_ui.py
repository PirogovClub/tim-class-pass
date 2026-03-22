from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, *, timeout_seconds: float = 20.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.25)
    raise AssertionError(f"Timed out waiting for {url}")


@pytest.fixture
def live_ui_server(tmp_path: Path):
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    var_root = repo_root / "var"
    port = _free_port()
    source_root = Path(__file__).resolve().parents[3]
    env = {
        **dict(os.environ),
        "UI_PROJECT_ROOT": str(repo_root),
        "UI_DATA_ROOT": str(data_root),
        "UI_STATE_DB_PATH": str(var_root / "ui_state.db"),
        "UI_LOG_ROOT": str(var_root / "ui-runs"),
        "UI_PIPELINE_DB_ROOT": str(var_root / "pipeline-runs"),
        "UI_CORPUS_OUTPUT_ROOT": str(var_root / "ui-corpus"),
        "UI_ENABLE_PERIODIC_RECONCILE": "0",
        "UI_TEST_MODE": "1",
        "UI_FAKE_BATCH_POLLS_BEFORE_SUCCESS": "0",
        "UI_PORT": str(port),
        "PYTHONPATH": str(source_root),
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "ui"],
        cwd=str(source_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server(f"{base_url}/dashboard")
        yield {"base_url": base_url, "repo_root": repo_root}
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


class Operator:
    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url

    def open_dashboard(self) -> None:
        self.page.goto(f"{self.base_url}/dashboard")
        expect(self.page.get_by_test_id("dashboard-summary")).to_be_visible()

    def create_project(self, title: str, video_path: Path, transcript_path: Path) -> None:
        self.page.goto(f"{self.base_url}/projects/new")
        self.page.get_by_label("Project title").fill(title)
        self.page.locator('input[name="source_video_upload"]').set_input_files(str(video_path))
        self.page.locator('input[name="transcript_upload"]').set_input_files(str(transcript_path))
        self.page.get_by_role("button", name="Save project").click()

    def wait_for_run_status(self, status_text: str) -> None:
        expect(self.page.get_by_test_id("run-status")).to_have_text(status_text, timeout=20000)


def test_operator_can_create_project_reconcile_batch_and_build_corpus(page: Page, live_ui_server):
    operator = Operator(page, live_ui_server["base_url"])
    repo_root = live_ui_server["repo_root"]
    video_path = repo_root / "fixtures" / "lesson.mp4"
    transcript_path = repo_root / "fixtures" / "lesson.vtt"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_text("fake-video", encoding="utf-8")
    transcript_path.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello\n", encoding="utf-8")

    operator.open_dashboard()
    operator.create_project("Browser Lesson", video_path, transcript_path)
    expect(page.get_by_test_id("project-status")).to_have_text("ready_to_run")

    project_root = repo_root / "data" / "Browser Lesson"
    (project_root / "dense_analysis.json").write_text(json.dumps({"000001": {"material_change": True}}), encoding="utf-8")

    page.get_by_label("Run mode").select_option("batch_knowledge_only")
    page.get_by_role("button", name="Launch background run").click()
    operator.wait_for_run_status("WAITING_REMOTE")
    page.reload()
    page.get_by_role("button", name="Reconcile now").click()
    operator.wait_for_run_status("SUCCEEDED")

    page.goto(f"{live_ui_server['base_url']}/corpus")
    page.locator('input[name="project_ids"]').check()
    page.get_by_role("button", name="Build selected corpus").click()
    operator.wait_for_run_status("SUCCEEDED")


def test_operator_can_cancel_waiting_remote_run(page: Page, live_ui_server):
    operator = Operator(page, live_ui_server["base_url"])
    repo_root = live_ui_server["repo_root"]
    video_path = repo_root / "fixtures" / "cancel.mp4"
    transcript_path = repo_root / "fixtures" / "cancel.vtt"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_text("fake-video", encoding="utf-8")
    transcript_path.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello\n", encoding="utf-8")

    operator.create_project("Cancel Browser Lesson", video_path, transcript_path)
    project_root = repo_root / "data" / "Cancel Browser Lesson"
    (project_root / "dense_analysis.json").write_text(json.dumps({"000001": {"material_change": True}}), encoding="utf-8")

    page.get_by_label("Run mode").select_option("batch_knowledge_only")
    page.get_by_role("button", name="Launch background run").click()
    operator.wait_for_run_status("WAITING_REMOTE")
    page.reload()
    page.get_by_role("button", name="Cancel run").click()
    operator.wait_for_run_status("CANCELLED")

