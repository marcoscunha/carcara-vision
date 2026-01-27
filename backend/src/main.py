# include fast api
import logging
import time
from contextlib import asynccontextmanager
from typing import List
from typing import Optional

from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.services.cameras import camera_stream_managers

from .api.endpoints import alarms
from .api.endpoints import cameras
from .api.endpoints import detections
from .api.endpoints import hardware
from .api.endpoints import models
from .api.endpoints import roi as roi_endpoints
from .api.endpoints import streams
from .core.config import settings
from .core.logging import setup_logging
from .db.init_db import init_db
from .db.session import get_db
from .models import alarm
from .models import camera
from .models import detection
from .models import roi
from .models import stream
from .services.detection import ObjectDetectionService

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize database
init_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
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
        f"Request: {request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.2f}s"
    )
    return response

# Error handling middleware


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error handler caught: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )

# Include routers
app.include_router(
    cameras.router,
    prefix=f"{settings.API_V1_STR}/cameras",
    tags=["cameras"]
)
app.include_router(
    streams.router,
    prefix=f"{settings.API_V1_STR}/streams",
    tags=["streams"]
)
app.include_router(
    detections.router,
    prefix=f"{settings.API_V1_STR}/detections",
    tags=["detections"]
)
app.include_router(
    models.router,
    prefix=f"{settings.API_V1_STR}/models",
    tags=["models"]
)
app.include_router(alarms.router, prefix=f"{settings.API_V1_STR}/alarms", tags=["alarms"])
app.include_router(roi_endpoints.router, prefix=f"{settings.API_V1_STR}/roi", tags=["roi"])
app.include_router(
    hardware.router,
    prefix=f"{settings.API_V1_STR}/hardware",
    tags=["hardware"]
)


@app.get("/")
def read_root():
    logger.info("Root endpoint accessed")
    return {
        "message": "Welcome to Carcara NVC Backend",
        "version": settings.VERSION,
        "docs_url": "/docs"
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Logic
    logger.info("Application starting up...")
    logger.info(f"Environment: {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Database URI: {settings.SQLALCHEMY_DATABASE_URI}")
    logger.info(f"Using GPU: {settings.USE_GPU}")
    logger.info(f"Camera Manager: {settings.MODEL_PATH}", end="")

    yield
    # Shutdown Logic
    logger.info("Application shutting down...")
    logger.info("Application shutting down...")
