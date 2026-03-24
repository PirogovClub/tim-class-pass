from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


RUN_STATUS_QUEUED = "QUEUED"
RUN_STATUS_RUNNING = "RUNNING"
RUN_STATUS_WAITING_REMOTE = "WAITING_REMOTE"
RUN_STATUS_FAILED = "FAILED"
RUN_STATUS_SUCCEEDED = "SUCCEEDED"
RUN_STATUS_CANCEL_REQUESTED = "CANCEL_REQUESTED"
RUN_STATUS_CANCELLED = "CANCELLED"
RUN_STATUS_INTERRUPTED = "INTERRUPTED"

RUN_KIND_PROJECT = "PROJECT"
RUN_KIND_CORPUS = "CORPUS"


@dataclass(frozen=True)
class ArtifactSnapshot:
    transcript_exists: bool
    video_exists: bool
    dense_index_exists: bool
    structural_index_exists: bool
    queue_manifest_exists: bool
    prompt_files_exist: bool
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
    source_mode: str
    source_url: str | None
    source_video_path: Path | None
    transcript_path: Path | None
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    project_id: str
    run_kind: str
    run_mode: str
    force_overwrite: bool
    status: str
    current_stage: str | None
    progress_message: str | None
    log_path: Path | None
    pipeline_db_path: Path | None
    remote_job_name: str | None
    pid: int | None
    command: str | None
    last_heartbeat_at: str | None
    last_remote_poll_at: str | None
    started_at: str | None
    finished_at: str | None
    exit_code: int | None
    error_message: str | None
    cancel_requested_at: str | None
    created_at: str
    updated_at: str

    @property
    def is_active(self) -> bool:
        return self.status in {
            RUN_STATUS_QUEUED,
            RUN_STATUS_RUNNING,
            RUN_STATUS_WAITING_REMOTE,
            RUN_STATUS_CANCEL_REQUESTED,
        }


@dataclass(frozen=True)
class RunEventRecord:
    event_id: int
    run_id: str
    event_type: str
    stage: str | None
    message: str
    created_at: str


@dataclass(frozen=True)
class CorpusQueueRow:
    project: ProjectRecord
    artifacts: ArtifactSnapshot
    corpus_status: str
    latest_corpus_run: RunRecord | None
    output_root: Path | None


@dataclass(frozen=True)
class ProjectFlowCheck:
    label: str
    done: bool
    path_hint: str | None = None


@dataclass(frozen=True)
class ProjectFlowStage:
    key: str
    title: str
    status: str
    status_label: str
    summary: str
    checks: list[ProjectFlowCheck]
    suggested_run_modes: list[str]


@dataclass(frozen=True)
class ProjectFlowGuide:
    headline: str
    summary: str
    current_stage_label: str | None
    recommended_run_modes: list[str]
    stages: list[ProjectFlowStage]


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

