from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse

from ui.reconcile import launch_waiting_remote_runs
from ui.services import DashboardPage, get_dashboard_page
from ui.web import get_settings, get_store, render


router = APIRouter()

STATUS_OPTIONS = [
    "missing_inputs",
    "ready_to_run",
    "ready_for_knowledge_extract",
    "running_sync",
    "running_batch",
    "waiting_for_remote",
    "failed",
    "ready_for_corpus",
    "complete",
]

SORT_OPTIONS = [
    ("updated_desc", "Updated desc"),
    ("title_asc", "Title asc"),
    ("status_asc", "Status asc"),
]


@router.get("/", name="root")
async def root(request: Request):
    return RedirectResponse(url=request.url_for("dashboard"), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/dashboard", name="dashboard")
async def dashboard(
    request: Request,
    query: str = "",
    status_filter: str = "",
    sort: str = "updated_desc",
    page: int = 1,
):
    dashboard_page: DashboardPage = get_dashboard_page(
        get_store(request),
        get_settings(request),
        query=query,
        status=status_filter,
        sort=sort,
        page=page,
    )
    prev_url = None
    next_url = None
    if dashboard_page.page > 1:
        prev_url = str(
            request.url.include_query_params(
                query=query,
                status_filter=status_filter,
                sort=sort,
                page=dashboard_page.page - 1,
            )
        )
    if dashboard_page.page < dashboard_page.total_pages:
        next_url = str(
            request.url.include_query_params(
                query=query,
                status_filter=status_filter,
                sort=sort,
                page=dashboard_page.page + 1,
            )
        )
    return render(
        request,
        "dashboard.html",
        page_data=dashboard_page,
        query=query,
        status_filter=status_filter,
        sort=sort,
        status_options=STATUS_OPTIONS,
        sort_options=SORT_OPTIONS,
        prev_url=prev_url,
        next_url=next_url,
    )


@router.post("/dashboard/reconcile-ready", name="reconcile_ready")
async def reconcile_ready(request: Request):
    launch_waiting_remote_runs(get_store(request), get_settings(request))
    return RedirectResponse(url=request.url_for("dashboard"), status_code=status.HTTP_303_SEE_OTHER)

