from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .assistants import AgentsAssistantService
from .config import Settings, get_settings
from .database import Base, SessionLocal, configure_database, engine
from .email import AuthEmailSender
from .media import OpenAIAudioTranscriber
from .rate_limit import InMemoryRateLimiter
from .retention import (
    discard_stale_transcription_reservations,
    discard_stale_unbound_attachments,
    purge_all_expired_conversations,
)
from .routes import attachments, auth, invitations, public, studio
from .schemas import VersionOut
from .seed import seed_demo_data


logger = logging.getLogger(__name__)
RETENTION_INITIAL_DELAY_SECONDS = 5 * 60
RETENTION_INTERVAL_SECONDS = 6 * 60 * 60
MAX_CONCURRENT_UPLOAD_REQUESTS = 2
UPLOAD_SLOT_WAIT_SECONDS = 5


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    configure_database(runtime_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime_settings.validate_runtime()
        # Re-import rebound globals after configure_database.
        from . import database

        if runtime_settings.auto_create_schema:
            Base.metadata.create_all(database.engine)
        if runtime_settings.seed_demo:
            with database.SessionLocal() as db:
                seed_demo_data(db, runtime_settings)
        runtime_settings.upload_dir.mkdir(parents=True, exist_ok=True)

        retention_stop = asyncio.Event()

        def run_retention_cycle() -> tuple[int, int, int]:
            with database.SessionLocal() as db:
                stale_audio = discard_stale_transcription_reservations(db)
                stale_attachments = discard_stale_unbound_attachments(db, runtime_settings)
                expired_conversations = len(
                    purge_all_expired_conversations(db, runtime_settings)
                )
                return expired_conversations, stale_audio, stale_attachments

        async def retention_worker() -> None:
            try:
                await asyncio.wait_for(
                    retention_stop.wait(), timeout=RETENTION_INITIAL_DELAY_SECONDS
                )
                return
            except TimeoutError:
                pass
            while not retention_stop.is_set():
                try:
                    deleted, stale_audio, stale_attachments = await asyncio.to_thread(
                        run_retention_cycle
                    )
                    if deleted or stale_audio or stale_attachments:
                        logger.info(
                            "automatic retention deleted %s conversations, %s stale audio "
                            "reservations, and %s abandoned attachments",
                            deleted,
                            stale_audio,
                            stale_attachments,
                        )
                except Exception:
                    # A transient database/filesystem failure must be visible but must not take the
                    # public service down. The next cycle retries the still-expired records.
                    logger.exception("automatic conversation retention cycle failed")
                try:
                    await asyncio.wait_for(
                        retention_stop.wait(), timeout=RETENTION_INTERVAL_SECONDS
                    )
                except TimeoutError:
                    continue

        retention_task = asyncio.create_task(
            retention_worker(), name="laggente-conversation-retention"
        )
        try:
            yield
        finally:
            retention_stop.set()
            # If a cycle is active, let its dedicated thread finish before disposing the engine;
            # normal idle shutdown wakes immediately from the stop event.
            await retention_task
            database.engine.dispose()

    app = FastAPI(
        title="LAGGENTE API",
        version=runtime_settings.version,
        docs_url="/api/docs" if not runtime_settings.is_production else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if not runtime_settings.is_production else None,
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.email_sender = AuthEmailSender(runtime_settings)
    app.state.assistant_service = AgentsAssistantService(runtime_settings)
    app.state.audio_transcriber = OpenAIAudioTranscriber(runtime_settings)
    app.state.upload_slots = asyncio.Semaphore(MAX_CONCURRENT_UPLOAD_REQUESTS)

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=runtime_settings.trusted_host_list)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.api_cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Conversation-Token", "Idempotency-Key"],
    )

    @app.middleware("http")
    async def security_boundaries(request: Request, call_next):
        request_path = request.url.path
        if request_path.startswith("/api/v1/auth") or request_path.startswith("/api/v1/studio"):
            host = request.headers.get("host", "").split(":", 1)[0].lower().rstrip(".")
            expected_app_host = (urlparse(runtime_settings.app_origin).hostname or "").lower()
            local_host = host in {"localhost", "127.0.0.1", "testserver"}
            if host != expected_app_host and (runtime_settings.is_production or not local_host):
                # Auth and Studio cookies are host-only. Never mint or accept them on a tenant,
                # apex, or unknown hostname even if a proxy accidentally forwards that route.
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and (
            request_path.startswith("/api/v1/studio")
            or request_path == "/api/v1/auth/logout"
        ):
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") != runtime_settings.app_origin.rstrip("/"):
                return JSONResponse(status_code=403, content={"detail": "Origine non autorizzata"})
        is_public_upload = (
            request.method == "POST"
            and request_path.startswith("/api/v1/public/conversations/")
            and request_path.rstrip("/").endswith("/attachments")
        )
        upload_slot_acquired = False
        if is_public_upload:
            try:
                await asyncio.wait_for(
                    app.state.upload_slots.acquire(), timeout=UPLOAD_SLOT_WAIT_SECONDS
                )
                upload_slot_acquired = True
            except TimeoutError:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Troppi allegati in elaborazione. Riprova tra poco."},
                    headers={"Retry-After": str(UPLOAD_SLOT_WAIT_SECONDS)},
                )
        try:
            # The upload semaphore is acquired before FastAPI parses/spools multipart content, so
            # at most two public bodies can occupy API memory and /tmp simultaneously.
            response = await call_next(request)
        finally:
            if upload_slot_acquired:
                app.state.upload_slots.release()
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=()")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(public.router, prefix="/api/v1")
    app.include_router(studio.router, prefix="/api/v1")
    app.include_router(invitations.router, prefix="/api/v1")
    app.include_router(attachments.router, prefix="/api/v1")

    @app.get("/healthz", include_in_schema=False)
    @app.get("/api/v1/health/live", include_in_schema=False)
    def health_live():
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    @app.get("/api/v1/health/ready", include_in_schema=False)
    def health_ready():
        from . import database

        try:
            with database.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            raise HTTPException(status_code=503, detail="database_not_ready")
        return {"status": "ready"}

    @app.get("/version", response_model=VersionOut, include_in_schema=False)
    @app.get("/api/v1/version", response_model=VersionOut, include_in_schema=False)
    def version():
        return VersionOut(version=runtime_settings.version or __version__, git_sha=runtime_settings.git_sha)

    return app


app = create_app()
