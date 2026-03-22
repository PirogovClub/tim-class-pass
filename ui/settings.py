from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UISettings:
    project_root: Path
    data_root: Path
    state_db_path: Path
    log_root: Path
    page_size: int = 25

    @classmethod
    def default(cls, project_root: str | Path | None = None) -> "UISettings":
        root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
        return cls(
            project_root=root,
            data_root=root / "data",
            state_db_path=root / "var" / "ui_state.db",
            log_root=root / "var" / "ui-runs",
        )

