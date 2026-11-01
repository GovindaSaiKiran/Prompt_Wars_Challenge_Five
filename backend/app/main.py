"""Main FastAPI application module for EventPrice Intelligence Backend."""

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    ai,
    assistant,
    budgets,
    events,
    external,
    health,
    prices,
    tasks,
    vendors,
)
from app.core.config import get_settings

# Retrieve application settings
settings = get_settings()

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("eventprice.backend")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle events handler."""
    logger.info("Starting up %s (version: %s)", settings.APP_NAME, settings.APP_VERSION)
    logger.info("Environment: %s | Debug: %s", settings.ENVIRONMENT, settings.DEBUG)
    logger.info("Configured CORS Origins: %s", settings.CORS_ORIGINS)
    # Ensure database tables exist (essential for cloud deployments with fresh SQLite or Postgres)
    try:
        from app.models import __all__  # Ensure all models are registered
        from app.core.database import Base, engine
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema verified and initialized.")
    except Exception as e:
        logger.error("Failed to initialize database tables: %s", e)
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


def create_application() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="FastAPI Backend for EventPrice Intelligence Platform",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Exception Handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        logger.warning(
            "HTTP %d error at %s: %s",
            exc.status_code,
            request.url.path,
            exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTPException",
                "status_code": exc.status_code,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning(
            "Validation error on %s %s: %s",
            request.method,
            request.url.path,
            exc.errors(),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "ValidationError",
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "detail": jsonable_encoder(exc.errors()),
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "detail": "An unexpected server error occurred." if not settings.DEBUG else str(exc),
            },
        )

    # Register Routes
    # Root health endpoint (/health) as specified in requirements
    app.include_router(health.router)

    # Also make health check accessible via API namespace
    app.include_router(health.router, prefix="/api/v1")

    # Event and Requirement endpoints
    app.include_router(events.router, prefix="/api/v1")

    # Vendor and Vendor Service endpoints
    app.include_router(vendors.router, prefix="/api/v1")

    # Vendor Price Record and Evidence endpoints
    app.include_router(prices.router, prefix="/api/v1")

    # Event Budget, Line Items, and Scenarios endpoints
    app.include_router(budgets.router, prefix="/api/v1")

    # Event Tasks, Timeline, Dependencies, and Progress endpoints
    app.include_router(tasks.router, prefix="/api/v1")

    # AI Planning Advice endpoints
    app.include_router(ai.router, prefix="/api/v1")

    # GenAI Structured Planning Assistant endpoints
    app.include_router(assistant.router, prefix="/api/v1")

    # External Data Integrations (Weather, Geocoding, Places)
    app.include_router(external.router, prefix="/api/v1")

    @app.get(
        "/",
        tags=["Root"],
        summary="API Root",
        description="Returns basic service index and health status link.",
    )
    async def root() -> dict:
        return {
            "message": f"Welcome to {settings.APP_NAME}",
            "version": settings.APP_VERSION,
            "docs_url": "/docs",
            "health_url": "/health",
        }

    return app


# Export application instance
app = create_application()

