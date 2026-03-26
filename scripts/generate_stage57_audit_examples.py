"""Generate example JSON responses for Stage 5.7 metrics (audit bundle ``examples/``)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pipeline.adjudication.api_errors import AdjudicationApiError, adjudication_api_error_handler
from pipeline.adjudication.api_routes import adjudication_router, init_adjudication
from pipeline.adjudication.enums import DecisionType, ReviewTargetType, ReviewerKind
from pipeline.adjudication.models import NewReviewDecision, NewReviewer
from pipeline.adjudication.repository import AdjudicationRepository

from tests.adjudication_api.corpus_index_fixtures import STANDARD_TEST_CORPUS_INDEX


class _FakeExplorerRepo:
    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs

    def get_all_docs(self) -> list[dict]:
        return self._docs


class _FakeExplorer:
    def __init__(self, docs: list[dict]) -> None:
        self._repo = _FakeExplorerRepo(docs)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    out_dir = repo_root / "audit" / "stage5_7_audit_bundle_2026-03-26" / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)

    docs = [
        {
            "doc_id": "rule:w:1",
            "unit_type": "rule_card",
            "lesson_id": "lesson_demo",
            "canonical_concept_ids": ["concept:demo"],
        },
        {
            "doc_id": "ev:1",
            "unit_type": "evidence_ref",
            "lesson_id": "lesson_demo",
            "canonical_concept_ids": ["concept:demo"],
        },
    ]

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "stage57_examples.sqlite"
        init_adjudication(db, explorer=_FakeExplorer(docs), corpus_index=STANDARD_TEST_CORPUS_INDEX)
        r = AdjudicationRepository(db)
        r.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
        r.append_decision_and_refresh_state(
            NewReviewDecision(
                target_type=ReviewTargetType.RULE_CARD,
                target_id="rule:w:1",
                decision_type=DecisionType.APPROVE,
                reviewer_id="u1",
            ),
        )

        app = FastAPI()
        app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
        app.include_router(adjudication_router)
        client = TestClient(app)

        routes: list[tuple[str, str]] = [
            ("metrics_summary.json", "/adjudication/metrics/summary"),
            ("metrics_queues.json", "/adjudication/metrics/queues"),
            ("metrics_proposals.json", "/adjudication/metrics/proposals"),
            ("metrics_throughput_7d.json", "/adjudication/metrics/throughput?window=7d"),
            ("metrics_throughput_30d.json", "/adjudication/metrics/throughput?window=30d"),
            ("metrics_coverage_lessons.json", "/adjudication/metrics/coverage/lessons"),
            ("metrics_coverage_concepts.json", "/adjudication/metrics/coverage/concepts"),
            ("metrics_flags.json", "/adjudication/metrics/flags"),
        ]
        for fname, path in routes:
            resp = client.get(path)
            if resp.status_code != 200:
                print(f"FAIL {path} -> {resp.status_code} {resp.text}", file=sys.stderr)
                return 1
            (out_dir / fname).write_text(
                json.dumps(resp.json(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    print(f"Wrote examples under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
