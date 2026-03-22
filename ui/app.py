from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ui.reconcile import ReconcileScheduler
from ui.routes_corpus import router as corpus_router
from ui.routes_dashboard import router as dashboard_router
from ui.routes_projects import router as projects_router
from ui.routes_runs import router as runs_router
from ui.run_launcher import repair_stale_runs
from ui.settings import UISettings
from ui.storage import UIStateStore


def create_app(settings: UISettings | None = None, store: UIStateStore | None = None) -> FastAPI:
    settings = settings or UISettings.default()
    settings.data_root.mkdir(parents=True, exist_ok=True)
    settings.log_root.mkdir(parents=True, exist_ok=True)
    settings.pipeline_db_root.mkdir(parents=True, exist_ok=True)
    settings.corpus_output_root.mkdir(parents=True, exist_ok=True)

    templates_dir = Path(__file__).resolve().parent / "templates"
    static_dir = Path(__file__).resolve().parent / "static"

    app = FastAPI(title="Tim Class Pass Operator UI")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.state.settings = settings
    app.state.store = store or UIStateStore(settings.state_db_path)
    app.state.templates = Jinja2Templates(directory=str(templates_dir))
    app.state.scheduler = None

    @app.on_event("startup")
    async def _startup() -> None:
        repair_stale_runs(app.state.store)
        if settings.enable_periodic_reconcile:
            scheduler = ReconcileScheduler(app.state.store, settings)
            scheduler.start()
            app.state.scheduler = scheduler

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler is not None:
            scheduler.stop()

    app.include_router(dashboard_router)
    app.include_router(projects_router)
    app.include_router(runs_router)
    app.include_router(corpus_router)

    return app


def main() -> None:
    settings = UISettings.default()
    uvicorn.run("ui.app:create_app", host=settings.host, port=settings.port, reload=False, factory=True)


if __name__ == "__main__":
    main()

