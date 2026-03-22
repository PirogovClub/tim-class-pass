from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from ui.run_launcher import launch_run_worker
from ui.services import get_project_detail, import_project
from ui.services.runs import SUPPORTED_RUN_MODES, create_project_run
from ui.web import get_settings, get_store, render


router = APIRouter()


@router.get("/projects/new", name="new_project")
async def new_project(request: Request, error: str = ""):
    return render(request, "project_form.html", error=error, run_modes=SUPPORTED_RUN_MODES)


@router.post("/projects", name="create_project")
async def create_project(request: Request):
    form = await request.form()
    try:
        project = import_project(
            get_store(request),
            get_settings(request),
            title=str(form.get("title", "")),
            project_root_raw=str(form.get("project_root", "")),
            source_video_raw=str(form.get("source_video_path", "")),
            transcript_raw=str(form.get("transcript_path", "")),
            source_video_upload=form.get("source_video_upload"),
            transcript_upload=form.get("transcript_upload"),
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
            run_modes=SUPPORTED_RUN_MODES,
        )
    return RedirectResponse(
        url=request.url_for("project_detail", project_id=project.project_id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/projects/{project_id}", name="project_detail")
async def project_detail(request: Request, project_id: str, error: str = ""):
    try:
        project_row, runs = get_project_detail(get_store(request), project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown project: {exc.args[0]}") from exc
    return render(
        request,
        "project_detail.html",
        row=project_row,
        runs=runs,
        run_modes=SUPPORTED_RUN_MODES,
        error=error,
    )


@router.post("/projects/{project_id}/runs", name="create_run")
async def create_run(request: Request, project_id: str):
    form = await request.form()
    run_mode = str(form.get("run_mode") or "")
    try:
        run = create_project_run(get_store(request), get_settings(request), project_id=project_id, run_mode=run_mode)
        launch_run_worker(get_store(request), get_settings(request), run_id=run.run_id, action="start")
    except (KeyError, ValueError) as exc:
        try:
            row, runs = get_project_detail(get_store(request), project_id)
        except KeyError as inner_exc:
            raise HTTPException(status_code=404, detail=f"Unknown project: {inner_exc.args[0]}") from inner_exc
        return render(
            request,
            "project_detail.html",
            row=row,
            runs=runs,
            run_modes=SUPPORTED_RUN_MODES,
            error=str(exc),
        )
    return RedirectResponse(url=request.url_for("run_detail", run_id=run.run_id), status_code=status.HTTP_303_SEE_OTHER)

