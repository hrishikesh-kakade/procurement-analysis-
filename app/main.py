import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession
from app.api.errors import register_exception_handlers
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.user_service import ensure_bootstrap_admin

settings = get_settings()
logger = logging.getLogger("app.request")

DESCRIPTION = """
REST API for procurement operations: suppliers, materials, purchase requisitions,
purchase orders, deliveries and spend analytics.

**Authentication:** `POST /api/v1/auth/login` returns a JWT; send it as `Authorization: Bearer <token>`
(use the *Authorize* button). Access is controlled by role: `admin`, `procurement_manager`,
`approver`, `requester`, `viewer`.
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    log = logging.getLogger(__name__)
    log.info("starting %s v%s", settings.app_name, settings.app_version)
    if settings.admin_email and settings.admin_password:
        try:
            with SessionLocal() as db:
                ensure_bootstrap_admin(db, settings.admin_email, settings.admin_password)
        except Exception:  # keep the API up even if bootstrap fails
            log.exception("could not create bootstrap admin")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=DESCRIPTION,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_logging(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request failed", extra={"request_id": request_id})
            raise
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return response

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID", "Content-Disposition"],
        )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health", tags=["Health"], summary="Liveness and database check")
    def health(db: DbSession):
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return {"status": "ok", "version": settings.app_version}

    return app


app = create_app()
