"""FastAPI application factory.

Run with:  uvicorn --factory crm.api.app:create_app --reload
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..config import settings
from ..db import get_engine
from ..logging_config import setup_logging
from ..services import errors
from .auth import bind_actor
from .routers import (
    companies, contacts, dashboard, geocoding, interactions, invoices, products, voice_notes,
)

logger = logging.getLogger(__name__)

ERROR_STATUS = {
    errors.NotFoundError: 404,
    errors.ConflictError: 409,
    errors.InvalidReferenceError: 422,
    errors.ConfigurationError: 503,
}


class SPAStaticFiles(StaticFiles):
    """Serve the built frontend; unknown paths return index.html so client-side routes work."""

    async def get_response(self, path: str, scope):
        """Return the file, or index.html when it does not exist."""
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


def create_app(engine: Engine | None = None) -> FastAPI:
    """Build the application: /api routers (all authenticated), /health and the optional frontend."""
    setup_logging()
    app = FastAPI(title=settings.api.title)
    app.state.engine = engine or get_engine()

    if settings.api.cors_origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=settings.api.cors_origins,
            allow_methods=["*"], allow_headers=["*"],
        )

    @app.exception_handler(errors.ServiceError)
    async def service_error_handler(request: Request, exc: errors.ServiceError) -> JSONResponse:
        """Turn business-logic errors into HTTP responses."""
        code = next((c for cls, c in ERROR_STATUS.items() if isinstance(exc, cls)), 400)
        logger.warning("%s %s -> %s: %s", request.method, request.url.path, code, exc)
        return JSONResponse({"detail": str(exc)}, status_code=code)

    api = APIRouter(prefix="/api", dependencies=[Depends(bind_actor)])
    for module in (companies, contacts, interactions, dashboard, invoices, products, voice_notes, geocoding):
        api.include_router(module.router)
    app.include_router(api)

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    static_dir = Path(settings.api.static_dir) if settings.api.static_dir else None
    if static_dir and static_dir.is_dir():
        app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="frontend")
        logger.info("Serving the frontend from %s", static_dir)
    logger.info("Application ready: %s", settings.api.title)
    return app
