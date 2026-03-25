"""Shared FastAPI TestClient for Stage 5.2 adjudication API tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pipeline.adjudication.api_errors import AdjudicationApiError, adjudication_api_error_handler
from pipeline.adjudication.api_routes import adjudication_router, init_adjudication

from tests.adjudication_api.corpus_index_fixtures import STANDARD_TEST_CORPUS_INDEX


@pytest.fixture
def adj_client(tmp_path) -> TestClient:
    db = tmp_path / "adjudication.sqlite"
    init_adjudication(db, explorer=None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    return TestClient(app)
