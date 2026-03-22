from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ui.services import DashboardPage, get_dashboard_page, get_project_detail, import_project
from ui.settings import UISettings
from ui.storage import UIStateStore


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


def create_app(settings: UISettings | None = None, store: UIStateStore | None = None) -> FastAPI:
    settings = settings or UISettings.default()
    settings.data_root.mkdir(parents=True, exist_ok=True)
    settings.log_root.mkdir(parents=True, exist_ok=True)

    templates_dir = Path(__file__).resolve().parent / "templates"
    static_dir = Path(__file__).resolve().parent / "static"

    app = FastAPI(title="Tim Class Pass Operator UI")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.state.settings = settings
    app.state.store = store or UIStateStore(settings.state_db_path)
    app.state.templates = Jinja2Templates(directory=str(templates_dir))

    def render(request: Request, name: str, **context):
        return request.app.state.templates.TemplateResponse(
            request=request,
            name=name,
            context=context,
        )

    @app.get("/", name="root")
    async def root(request: Request):
        return RedirectResponse(url=request.url_for("dashboard"), status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/dashboard", name="dashboard")
    async def dashboard(
        request: Request,
        query: str = "",
        status_filter: str = "",
        sort: str = "updated_desc",
        page: int = 1,
    ):
        dashboard_page: DashboardPage = get_dashboard_page(
            request.app.state.store,
            request.app.state.settings,
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

    @app.get("/projects/new", name="new_project")
    async def new_project(request: Request, error: str = ""):
        return render(request, "project_form.html", error=error)

    @app.post("/projects", name="create_project")
    async def create_project(request: Request):
        form = await request.form()
        try:
            project = import_project(
                request.app.state.store,
                request.app.state.settings,
                title=str(form.get("title", "")),
                project_root_raw=str(form.get("project_root", "")),
                source_video_raw=str(form.get("source_video_path", "")),
                transcript_raw=str(form.get("transcript_path", "")),
            )
        except ValueError as exc:
            return render(
                request,
                "project_form.html",
                error=str(exc),
                title=str(form.get("title", "")),
                project_root=str(form.get("project_root", "")),
                source_video_path=str(form.get("source_video_path", "")),
                transcript_path=str(form.get("transcript_path", "")),
            )
        return RedirectResponse(
            url=request.url_for("project_detail", project_id=project.project_id),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @app.get("/projects/{project_id}", name="project_detail")
    async def project_detail(request: Request, project_id: str):
        try:
            project_row, runs = get_project_detail(request.app.state.store, project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown project: {exc.args[0]}") from exc
        return render(
            request,
            "project_detail.html",
            row=project_row,
            runs=runs,
        )

    return app


def main() -> None:
    uvicorn.run("ui.app:create_app", host="127.0.0.1", port=8000, reload=False, factory=True)


if __name__ == "__main__":
    main()

