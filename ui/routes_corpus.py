from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse

from ui.run_launcher import launch_run_worker
from ui.services.dashboard import get_corpus_queue_page
from ui.services.runs import create_corpus_run
from ui.web import get_settings, get_store, render


router = APIRouter()


@router.get("/corpus", name="corpus_queue")
async def corpus_queue(request: Request):
    page = get_corpus_queue_page(get_store(request))
    return render(request, "corpus_queue.html", page=page)


@router.post("/corpus/build", name="corpus_build")
async def corpus_build(request: Request):
    form = await request.form()
    raw_selected = form.getlist("project_ids")
    project_ids = [str(value) for value in raw_selected if str(value).strip()]
    run = create_corpus_run(get_store(request), get_settings(request), project_ids=project_ids)
    launch_run_worker(get_store(request), get_settings(request), run_id=run.run_id, action="start")
    return RedirectResponse(url=request.url_for("run_detail", run_id=run.run_id), status_code=status.HTTP_303_SEE_OTHER)

