from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from ui.run_launcher import launch_run_worker
from ui.services import get_project_detail, import_project
from ui.services.runs import (
    FLOW_STAGE_RUN_MODES,
    RUN_ACTION_GROUPS,
    RUN_MODE_DETAILS,
    SUPPORTED_RUN_MODES,
    create_project_run,
    get_project_run_mode_controls,
)
from ui.web import get_settings, get_store, render


router = APIRouter()


def _checkbox_value(raw: object) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


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
            source_mode_raw=str(form.get("source_mode", "")),
            source_url_raw=str(form.get("source_url", "")),
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
            source_mode=str(form.get("source_mode", "upload")),
            source_url=str(form.get("source_url", "")),
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
        project_row, runs, flow = get_project_detail(get_store(request), project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown project: {exc.args[0]}") from exc
    run_controls = get_project_run_mode_controls(project_row.project, latest_run=project_row.latest_run)
    force_run_controls = get_project_run_mode_controls(
        project_row.project,
        latest_run=project_row.latest_run,
        force_overwrite=True,
    )
    return render(
        request,
        "project_detail.html",
        row=project_row,
        runs=runs,
        flow=flow,
        run_modes=SUPPORTED_RUN_MODES,
        run_controls=run_controls,
        force_run_controls=force_run_controls,
        flow_stage_run_modes=FLOW_STAGE_RUN_MODES,
        run_action_groups=RUN_ACTION_GROUPS,
        run_mode_details=RUN_MODE_DETAILS,
        force_overwrite_enabled=False,
        error=error,
    )


@router.post("/projects/{project_id}/runs", name="create_run")
async def create_run(request: Request, project_id: str):
    form = await request.form()
    run_mode = str(form.get("run_mode") or "")
    force_overwrite = _checkbox_value(form.get("force_overwrite"))
    try:
        run = create_project_run(
            get_store(request),
            get_settings(request),
            project_id=project_id,
            run_mode=run_mode,
            force_overwrite=force_overwrite,
        )
        launch_run_worker(get_store(request), get_settings(request), run_id=run.run_id, action="start")
    except (KeyError, ValueError) as exc:
        try:
            row, runs, flow = get_project_detail(get_store(request), project_id)
        except KeyError as inner_exc:
            raise HTTPException(status_code=404, detail=f"Unknown project: {inner_exc.args[0]}") from inner_exc
        return render(
            request,
            "project_detail.html",
            row=row,
            runs=runs,
            flow=flow,
            run_modes=SUPPORTED_RUN_MODES,
            run_controls=get_project_run_mode_controls(row.project, latest_run=row.latest_run),
            force_run_controls=get_project_run_mode_controls(
                row.project,
                latest_run=row.latest_run,
                force_overwrite=True,
            ),
            flow_stage_run_modes=FLOW_STAGE_RUN_MODES,
            run_action_groups=RUN_ACTION_GROUPS,
            run_mode_details=RUN_MODE_DETAILS,
            force_overwrite_enabled=force_overwrite,
            error=str(exc),
        )
    return RedirectResponse(url=request.url_for("run_detail", run_id=run.run_id), status_code=status.HTTP_303_SEE_OTHER)

