from __future__ import annotations

import re

from ui.models import RUN_STATUS_FAILED, RUN_STATUS_WAITING_REMOTE
from ui.tests.helpers import register_project, scaffold_project_files


def test_root_redirects_to_dashboard(ui_context):
    client = ui_context["client"]

    response = client.get("/", follow_redirects=True)

    assert response.status_code == 200
    assert 'data-testid="dashboard-summary"' in response.text


def test_dashboard_filters_search_and_sort(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    scaffold_project_files(settings, "Alpha Missing", transcript=False)
    alpha = register_project(store, settings, "Alpha Missing")

    scaffold_project_files(settings, "Beta Ready", transcript=True)
    register_project(store, settings, "Beta Ready")

    scaffold_project_files(settings, "Gamma Failed", transcript=True, dense_analysis=True)
    gamma = register_project(store, settings, "Gamma Failed")
    store.create_run(
        run_id=f"{gamma['project_id']}::001",
        project_id=gamma["project_id"],
        run_mode="batch_knowledge_only",
        status=RUN_STATUS_FAILED,
    )

    failed_response = client.get("/dashboard", params={"status_filter": "failed"})
    assert failed_response.status_code == 200
    assert "Gamma Failed" in failed_response.text
    assert "Beta Ready" not in failed_response.text
    assert failed_response.text.count('data-testid="project-row"') == 1

    search_response = client.get("/dashboard", params={"query": "beta"})
    assert search_response.status_code == 200
    assert "Beta Ready" in search_response.text
    assert "Gamma Failed" not in search_response.text

    sort_response = client.get("/dashboard", params={"sort": "title_asc"})
    assert sort_response.status_code == 200
    alpha_pos = sort_response.text.index("Alpha Missing")
    beta_pos = sort_response.text.index("Beta Ready")
    gamma_pos = sort_response.text.index("Gamma Failed")
    assert alpha_pos < beta_pos < gamma_pos


def test_dashboard_handles_100_projects_with_pagination_and_counters(ui_context):
    client = ui_context["client"]
    settings = ui_context["settings"]
    store = ui_context["store"]

    for index in range(100):
        name = f"Lesson {index:03d}"
        bucket = index % 5
        scaffold_project_files(
            settings,
            name,
            transcript=True,
            dense_analysis=bucket in {1, 2, 4},
            corpus_ready=bucket == 2,
            exports_ready=bucket == 2,
        )
        project = register_project(store, settings, name)
        if bucket == 3:
            store.create_run(
                run_id=f"{project['project_id']}::failed",
                project_id=project["project_id"],
                run_mode="batch_full",
                status=RUN_STATUS_FAILED,
            )
        if bucket == 4:
            store.create_run(
                run_id=f"{project['project_id']}::remote",
                project_id=project["project_id"],
                run_mode="batch_full",
                status=RUN_STATUS_WAITING_REMOTE,
            )

    page_one = client.get("/dashboard")
    assert page_one.status_code == 200
    assert 'data-testid="counter-all"' in page_one.text
    assert re.search(r'data-testid="counter-all".*?<div class="counter-value">100</div>', page_one.text, re.S)
    assert page_one.text.count('data-testid="project-row"') == 25
    assert "Page 1 / 4" in page_one.text

    failed_only = client.get("/dashboard", params={"status_filter": "failed"})
    assert failed_only.status_code == 200
    assert "Showing 20 of 20 matching projects." in failed_only.text
    assert failed_only.text.count('data-testid="project-row"') == 20

    search_one = client.get("/dashboard", params={"query": "lesson 042"})
    assert search_one.status_code == 200
    assert "Lesson 042" in search_one.text
    assert search_one.text.count('data-testid="project-row"') == 1

    page_four = client.get("/dashboard", params={"page": 4})
    assert page_four.status_code == 200
    assert page_four.text.count('data-testid="project-row"') == 25
    assert "Page 4 / 4" in page_four.text

