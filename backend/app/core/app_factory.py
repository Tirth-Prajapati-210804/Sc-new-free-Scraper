from __future__ import annotations

import multiprocessing
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.core.redaction import redact_text
from app.schemas.health import HealthResponse


def _should_start_scheduler_for_process(
    argv: list[str] | tuple[str, ...] | None = None,
    process_name: str | None = None,
) -> bool:
    effective_argv = list(argv if argv is not None else sys.argv)
    effective_process_name = process_name or multiprocessing.current_process().name
    reload_enabled = "--reload" in effective_argv

    # Under uvicorn --reload on Windows, the MainProcess is the file watcher /
    # reloader supervisor and the spawned child process serves traffic.
    if reload_enabled and effective_process_name == "MainProcess":
        return False
    return True


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    configure_logging(settings.debug)
    log = get_logger(__name__)

    if settings.sentry_dsn:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        from app.db.session import AsyncSessionLocal
        from app.providers.registry import ProviderRegistry
        from app.services.auth_service import ensure_default_admin
        from app.tasks.scheduler import FlightScheduler

        app.state.settings = settings

        registry = ProviderRegistry(settings)
        app.state.provider_registry = registry

        async with AsyncSessionLocal() as session:
            await ensure_default_admin(session, settings)
            # Mark any collection runs stuck in "running" (from a previous crash) as failed
            from sqlalchemy import update as sa_update
            from app.models.collection_run import CollectionRun
            await session.execute(
                sa_update(CollectionRun)
                .where(CollectionRun.status == "running")
                .values(status="failed", errors=["Server restarted mid-collection"])
            )
            await session.commit()

        scheduler = FlightScheduler(
            settings=settings,
            session_factory=AsyncSessionLocal,
            provider_registry=registry,
        )
        app.state.scheduler = scheduler
        if _should_start_scheduler_for_process():
            scheduler.start()
        else:
            log.info("scheduler_start_skipped_in_reloader_parent")

        log.info("startup complete", environment=settings.environment)
        yield

        await scheduler.stop()
        await registry.close_all()
        log.info("shutdown complete")

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug or settings.expose_api_docs else None,
        redoc_url="/redoc" if settings.debug or settings.expose_api_docs else None,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json"
        if settings.debug or settings.expose_api_docs
        else None,
    )

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.get_allowed_hosts())

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins(),
        allow_origin_regex=settings.get_cors_origin_regex(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # ── Request body size limit (DoS prevention) ──────────────────────────
    _MAX_BODY_BYTES = 1_048_576  # 1 MB

    @app.middleware("http")
    async def limit_request_body(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
            )
        return await call_next(request)

    # ── Security headers ─────────────────────────────────────────────────
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request_id)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'",
        )
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), geolocation=(), microphone=()",
        )
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        return response

    from app.api.v1.router import router as v1_router
    app.include_router(v1_router, prefix=settings.api_v1_prefix)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"message": "Flight Price Tracker API is running."}

    @app.get("/health", response_model=HealthResponse)
    async def health(request: Request) -> HealthResponse:
        from app.db.health import check_db
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            db_ok = await check_db(session)

        s: Settings = request.app.state.settings
        registry = request.app.state.provider_registry
        provider_status = registry.status()

        db_status = "ok" if db_ok else "down"
        scheduler_running = request.app.state.scheduler.is_running
        provider_ready = s.demo_mode or any(
            status in {"configured", "active"}
            for status in provider_status.values()
        )
        overall = "ok" if db_ok and scheduler_running and provider_ready else "degraded"

        return HealthResponse(
            status=overall,
            environment=s.environment,
            database_status=db_status,
            scheduler_running=scheduler_running,
            provider_status=provider_status,
            demo_mode=s.demo_mode,
        )

    @app.get("/health/live")
    async def liveness(request: Request) -> dict[str, str]:
        return {"status": "ok", "request_id": request.state.request_id}

    @app.get("/health/ready")
    async def readiness(request: Request) -> JSONResponse:
        from app.db.health import check_db
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            db_ok = await check_db(session)

        s: Settings = request.app.state.settings
        registry = request.app.state.provider_registry
        provider_status = registry.status()
        scheduler_running = request.app.state.scheduler.is_running
        scheduler_ready = (not s.scheduler_enabled) or scheduler_running
        ready = db_ok and scheduler_ready

        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ok" if ready else "degraded",
                "database_status": "ok" if db_ok else "down",
                "scheduler_running": scheduler_running,
                "provider_status": provider_status,
                "demo_mode": s.demo_mode,
                "request_id": request.state.request_id,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        log.error(
            "unhandled exception",
            exc_info=exc,
            path=redact_text(str(request.url)),
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": detail,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        first_error = exc.errors()[0] if exc.errors() else {}
        detail = str(first_error.get("msg", "Invalid request payload"))
        return JSONResponse(
            status_code=422,
            content={
                "detail": detail,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    return app
