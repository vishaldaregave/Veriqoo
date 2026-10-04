"""Health check endpoint for LegalMetrologyAI service."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import get_app_settings
from backend.app.api.schemas import HealthResponse
from backend.app.config import Settings


router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Returns current operating status and API version.",
)
def health_check(settings: Settings = Depends(get_app_settings)) -> HealthResponse:
    """Lightweight health check probe."""
    return HealthResponse(
        status="ok",
        service=settings.app_name or "LegalMetrologyAI Backend",
        api_version=settings.app_version or "1.0.0",
    )

