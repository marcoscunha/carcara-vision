# include fast api
import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.endpoints import alarms
from .api.endpoints import cameras
from .api.endpoints import detections
from .api.endpoints import discovery
from .api.endpoints import hardware
from .api.endpoints import inference_runtime
from .api.endpoints import models
from .api.endpoints import roi as roi_endpoints
from .api.endpoints import streams
from .api.endpoints import ws_detections
from .core.config import settings
from .core.logging import setup_logging
from .db.session import SessionLocal
from .models.stream import Stream
from .services.camera_connectivity import sync_local_camera_connectivity
from .services.inference_worker_manager import inference_worker_manager

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


async def _gstreamer_self_heal_loop() -> None:
    while True:
        await asyncio.sleep(max(settings.GSTREAMER_SELF_HEAL_INTERVAL_SECONDS, 5))
        db = SessionLocal()
        try:
            changed = sync_local_camera_connectivity(db)
            recovered, failed = await streams._recover_reconnected_local_streams(db)
            if changed or recovered or failed:
                logger.info(
                    "GStreamer self-heal tick: connectivity_changed=%s recovered=%d failed=%d",
                    changed,
                    recovered,
                    failed,
                )
        except Exception as exc:
            logger.exception("GStreamer self-heal loop failed: %s", exc)
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    logger.info("Application starting up...")
    logger.info(f"Environment: {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"AUTH_ENABLED: {settings.AUTH_ENABLED}")

    # Re-register active stream pipelines, then restore inference workers.
    db = SessionLocal()
    self_heal_task: asyncio.Task | None = None
    try:
        # First heal local camera bindings after detach/reattach events.
        sync_local_camera_connectivity(db)

        restored, failed = await streams.restore_active_stream_pipelines(db)
        logger.info("Startup stream pipeline restore: %d restored, %d failed", restored, failed)

        active_streams = db.query(Stream).filter(Stream.status == "active").all()
        inference_worker_manager.restore_workers(active_streams)
        logger.info("Restored %d active-stream workers", len(active_streams))

        if settings.GSTREAMER_SELF_HEAL_ENABLED:
            self_heal_task = asyncio.create_task(_gstreamer_self_heal_loop())
            logger.info(
                "Started GStreamer self-heal loop (interval=%ss, auto_recreate=%s)",
                settings.GSTREAMER_SELF_HEAL_INTERVAL_SECONDS,
                settings.GSTREAMER_AUTO_RECREATE,
            )
    finally:
        db.close()

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("Application shutting down — stopping all inference workers...")
    if self_heal_task is not None:
        self_heal_task.cancel()
    inference_worker_manager.stop_all()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(
        f"Request: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.2f}s"
    )
    return response


# Error handling middleware


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error handler caught: {exc!s}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


# Include HTTP routers
app.include_router(cameras.router, prefix=f"{settings.API_V1_STR}/cameras", tags=["cameras"])
app.include_router(streams.router, prefix=f"{settings.API_V1_STR}/streams", tags=["streams"])
app.include_router(detections.router, prefix=f"{settings.API_V1_STR}/detections", tags=["detections"])
app.include_router(models.router, prefix=f"{settings.API_V1_STR}/models", tags=["models"])
app.include_router(alarms.router, prefix=f"{settings.API_V1_STR}/alarms", tags=["alarms"])
app.include_router(roi_endpoints.router, prefix=f"{settings.API_V1_STR}/roi", tags=["roi"])
app.include_router(hardware.router, prefix=f"{settings.API_V1_STR}/hardware", tags=["hardware"])
app.include_router(discovery.router, prefix=f"{settings.API_V1_STR}/discovery", tags=["discovery"])
app.include_router(
    inference_runtime.router, prefix=f"{settings.API_V1_STR}/inference-runtime", tags=["inference-runtime"]
)

# WebSocket routers (no auth middleware — token can be passed as query param if needed)
app.include_router(ws_detections.router, prefix=f"{settings.API_V1_STR}/ws", tags=["websocket"])


@app.get("/")
def read_root():
    logger.info("Root endpoint accessed")
    return {
        "message": "Welcome to Carcara Vision Backend",
        "version": settings.VERSION,
        "docs_url": "/docs",
    }


@app.get("/health")
def health_check():
    """Health check endpoint - public, no authentication required."""
    return {
        "status": "healthy",
        "version": settings.VERSION,
    }
