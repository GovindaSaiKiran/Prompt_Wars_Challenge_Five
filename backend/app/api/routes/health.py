"""Health check route returning application health status, name, and API version."""

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.core.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Schema for health endpoint response."""

    status: str = Field(
        default="healthy",
        description="Current health status of the backend service",
        examples=["healthy"],
    )
    application_name: str = Field(
        description="Name of the application",
        examples=["EventPrice Intelligence API"],
    )
    api_version: str = Field(
        description="Current API version",
        examples=["1.0.0"],
    )
    environment: str = Field(
        description="Active deployment environment",
        examples=["development"],
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Application Health Check",
    description="Returns operational status, application name, and API version.",
    tags=["Health"],
)
async def check_health() -> HealthResponse:
    """Check health and return operational metadata."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        application_name=settings.APP_NAME,
        api_version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )

