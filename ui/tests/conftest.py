from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ui.app import create_app
from ui.settings import UISettings


@pytest.fixture
def ui_context(tmp_path: Path):
    repo_root = tmp_path / "repo"
    settings = UISettings(
        project_root=repo_root,
        data_root=repo_root / "data",
        state_db_path=repo_root / "var" / "ui_state.db",
        log_root=repo_root / "var" / "ui-runs",
        page_size=25,
    )
    app = create_app(settings=settings)
    client = TestClient(app)
    return {
        "app": app,
        "client": client,
        "settings": settings,
        "store": app.state.store,
    }

