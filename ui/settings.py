from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UISettings:
    project_root: Path
    data_root: Path
    state_db_path: Path
    log_root: Path
    pipeline_db_root: Path
    corpus_output_root: Path
    upload_max_video_bytes: int = 512 * 1024 * 1024
    upload_max_transcript_bytes: int = 5 * 1024 * 1024
    page_size: int = 25
    scheduler_interval_seconds: int = 10
    enable_periodic_reconcile: bool = True
    test_mode: bool = False
    host: str = "127.0.0.1"
    port: int = 8000

    @classmethod
    def default(cls, project_root: str | Path | None = None) -> "UISettings":
        root_override = project_root or os.getenv("UI_PROJECT_ROOT")
        root = Path(root_override or Path(__file__).resolve().parents[1]).resolve()
        state_db_path = Path(os.getenv("UI_STATE_DB_PATH") or root / "var" / "ui_state.db").resolve()
        log_root = Path(os.getenv("UI_LOG_ROOT") or root / "var" / "ui-runs").resolve()
        pipeline_db_root = Path(os.getenv("UI_PIPELINE_DB_ROOT") or root / "var" / "pipeline-runs").resolve()
        corpus_output_root = Path(os.getenv("UI_CORPUS_OUTPUT_ROOT") or root / "var" / "ui-corpus").resolve()
        return cls(
            project_root=root,
            data_root=Path(os.getenv("UI_DATA_ROOT") or root / "data").resolve(),
            state_db_path=state_db_path,
            log_root=log_root,
            pipeline_db_root=pipeline_db_root,
            corpus_output_root=corpus_output_root,
            upload_max_video_bytes=int(os.getenv("UI_UPLOAD_MAX_VIDEO_BYTES") or 512 * 1024 * 1024),
            upload_max_transcript_bytes=int(os.getenv("UI_UPLOAD_MAX_TRANSCRIPT_BYTES") or 5 * 1024 * 1024),
            page_size=int(os.getenv("UI_PAGE_SIZE") or 25),
            scheduler_interval_seconds=int(os.getenv("UI_RECONCILE_INTERVAL_SECONDS") or 10),
            enable_periodic_reconcile=(os.getenv("UI_ENABLE_PERIODIC_RECONCILE", "1") != "0"),
            test_mode=(os.getenv("UI_TEST_MODE", "0") == "1"),
            host=os.getenv("UI_HOST") or "127.0.0.1",
            port=int(os.getenv("UI_PORT") or 8000),
        )

