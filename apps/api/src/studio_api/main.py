from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from studio_api.core.config import get_settings
from studio_api.core.db import create_schema
from studio_api.core.errors import StudioError, studio_error_handler
from studio_api.core.events import service_health
from studio_api.core.rate_limit import RateLimitMiddleware
from studio_api.modules.assets.router import router as assets_router
from studio_api.modules.characters.router import router as characters_router
from studio_api.modules.evaluation.router import router as evaluation_router
from studio_api.modules.exports.router import router as exports_router
from studio_api.modules.identity.router import router as identity_router
from studio_api.modules.models.router import router as models_router
from studio_api.modules.narrative.router import router as narrative_router
from studio_api.modules.projects.router import router as projects_router
from studio_api.modules.scenes.router import router as scenes_router
from studio_api.modules.workflows.automation_router import router as automation_router
from studio_api.modules.workflows.automation_router import webhook_router
from studio_api.modules.workflows.router import router as workflows_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.environment != "production":
        await create_schema()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Local-first Vietnamese children's story production API",
        lifespan=lifespan,
    )
    app.add_exception_handler(StudioError, studio_error_handler)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in (
        identity_router,
        projects_router,
        narrative_router,
        characters_router,
        scenes_router,
        assets_router,
        models_router,
        workflows_router,
        automation_router,
        evaluation_router,
        exports_router,
    ):
        app.include_router(router, prefix=settings.api_prefix)
    app.include_router(webhook_router)

    @app.get("/health", tags=["operations"])
    async def health() -> dict[str, object]:
        return await service_health()

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
