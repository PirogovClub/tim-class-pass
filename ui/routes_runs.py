from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from helpers.clients.gemini_client import get_client as get_gemini_client
from ui.reconcile import launch_waiting_remote_runs
from ui.run_launcher import is_process_alive, terminate_process
from ui.services import get_run_detail
from ui.web import get_settings, get_store, render


router = APIRouter()


def _tail_log(log_path: Path | None, *, lines: int = 80) -> str:
    if log_path is None or not log_path.exists():
        return ""
    content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def _render_run_partial(request: Request, run_id: str):
    run, owner_project, events, targets = get_run_detail(get_store(request), run_id)
    log_tail = _tail_log(run.log_path)
    return render(
        request,
        "_run_status_partial.html",
        run=run,
        owner_project=owner_project,
        events=events,
        targets=targets,
        log_tail=log_tail,
    )


@router.get("/runs/{run_id}", name="run_detail")
async def run_detail(request: Request, run_id: str):
    try:
        run, owner_project, events, targets = get_run_detail(get_store(request), run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {exc.args[0]}") from exc
    return render(
        request,
        "run_detail.html",
        run=run,
        owner_project=owner_project,
        events=events,
        targets=targets,
        log_tail=_tail_log(run.log_path),
    )


@router.get("/runs/{run_id}/partial", name="run_partial")
async def run_partial(request: Request, run_id: str):
    try:
        return _render_run_partial(request, run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {exc.args[0]}") from exc


@router.post("/runs/{run_id}/cancel", name="cancel_run")
async def cancel_run(request: Request, run_id: str):
    store = get_store(request)
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")
    store.mark_cancel_requested(run_id)
    pid_value = run.get("pid")
    pid = None if pid_value is None else int(pid_value)
    if is_process_alive(pid):
        terminate_process(pid)
    elif run.get("remote_job_name"):
        try:
            client = get_gemini_client()
            batches_api = getattr(client, "batches", None)
            if batches_api is not None and hasattr(batches_api, "cancel"):
                batches_api.cancel(name=run["remote_job_name"])
        except Exception:
            pass
        store.update_run(
            run_id,
            status="CANCELLED",
            finished_at=run.get("finished_at") or run.get("updated_at"),
            progress_message="Cancelled by operator.",
            pid=None,
        )
    return RedirectResponse(url=request.url_for("run_detail", run_id=run_id), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/runs/{run_id}/reconcile", name="reconcile_run")
async def reconcile_run(request: Request, run_id: str):
    launched = launch_waiting_remote_runs(get_store(request), get_settings(request), run_ids=[run_id])
    if not launched:
        run = get_store(request).get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")
    return RedirectResponse(url=request.url_for("run_detail", run_id=run_id), status_code=status.HTTP_303_SEE_OTHER)

