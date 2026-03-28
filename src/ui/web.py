from __future__ import annotations

from fastapi import Request

from ui.settings import UISettings
from ui.storage import UIStateStore


def get_settings(request: Request) -> UISettings:
    return request.app.state.settings


def get_store(request: Request) -> UIStateStore:
    return request.app.state.store


def render(request: Request, name: str, **context):
    return request.app.state.templates.TemplateResponse(
        request=request,
        name=name,
        context=context,
    )

