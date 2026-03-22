from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


RUN_STATUS_QUEUED = "QUEUED"
RUN_STATUS_RUNNING = "RUNNING"
RUN_STATUS_WAITING_REMOTE = "WAITING_REMOTE"
RUN_STATUS_FAILED = "FAILED"
RUN_STATUS_SUCCEEDED = "SUCCEEDED"


@dataclass(frozen=True)
class ArtifactSnapshot:
    transcript_exists: bool
    video_exists: bool
    filtered_visuals_exists: bool
    dense_analysis_exists: bool
    knowledge_events_exists: bool
    rule_cards_exists: bool
    evidence_index_exists: bool
    concept_graph_exists: bool
    review_markdown_exists: bool
    rag_ready_exists: bool
    export_manifest_exists: bool

    @property
    def corpus_ready(self) -> bool:
        return (
            self.knowledge_events_exists
            and self.rule_cards_exists
            and self.evidence_index_exists
            and self.concept_graph_exists
        )

    @property
    def exports_ready(self) -> bool:
        return self.review_markdown_exists and self.rag_ready_exists


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    slug: str
    title: str
    lesson_name: str
    project_root: Path
    source_video_path: Path | None
    transcript_path: Path | None
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    project_id: str
    run_mode: str
    status: str
    log_path: Path | None
    remote_job_name: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class DashboardRow:
    project: ProjectRecord
    artifacts: ArtifactSnapshot
    latest_run: RunRecord | None
    effective_status: str
    next_action: str
    updated_at: str

    @property
    def latest_run_mode(self) -> str:
        return "-" if self.latest_run is None else self.latest_run.run_mode

    @property
    def latest_run_status(self) -> str:
        return "-" if self.latest_run is None else self.latest_run.status

