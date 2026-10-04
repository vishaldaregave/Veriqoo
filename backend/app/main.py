"""FastAPI application entrypoint for LegalMetrologyAI backend."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.errors import (
    ErrorResponse,
    generic_exception_handler,
    http_exception_handler,
    image_too_large_handler,
    inspection_not_found_handler,
    inspection_state_handler,
    invalid_image_handler,
    invalid_pipeline_input_handler,
    pipeline_error_handler,
    unsupported_image_handler,
    validation_exception_handler,
)
from backend.app.api.v1.endpoints.authority import router as authority_router
from backend.app.api.v1.endpoints.consumer_reports import router as consumer_reports_router
from backend.app.api.v1.endpoints.health import router as health_router
from backend.app.api.v1.endpoints.heatmap import router as heatmap_router
from backend.app.api.v1.endpoints.inspections import router as inspections_router
from backend.app.api.v1.endpoints.public_reports import router as public_reports_router
from backend.app.api.v1.endpoints.telegram_link import router as telegram_link_router
from backend.app.api.v1.endpoints.voice import router as voice_router
from backend.app.config import get_settings

from backend.app.services.evidence.errors import (
    ImageDecodeError,
    ImageIngestionError,
    ImageSecurityError,
    ImageTooLargeError,
    ImageTooManyPixelsError,
    InvalidImageError,
    UnsupportedImageFormatError,
)
from backend.app.services.inspection.errors import (
    InspectionNotFoundError,
    InspectionStateError,
    InvalidInspectionError,
    InvalidLifecycleTransitionError,
)
from backend.app.services.inspection_pipeline.errors import (
    InvalidPipelineInputError,
    PipelineError,
    PipelineExecutionError,
)


def create_app() -> FastAPI:
    """Application factory for LegalMetrologyAI FastAPI service."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Legal Metrology AI automated compliance verification service.",
        responses={
            400: {"model": ErrorResponse, "description": "Bad Request / Validation Failure"},
            404: {"model": ErrorResponse, "description": "Resource Not Found"},
            409: {"model": ErrorResponse, "description": "State Conflict"},
            500: {"model": ErrorResponse, "description": "Internal / Pipeline Error"},
        },
    )

    # Configure CORS
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )

    # Register Exception Handlers
    app.add_exception_handler(InspectionNotFoundError, inspection_not_found_handler)
    app.add_exception_handler(InspectionStateError, inspection_state_handler)
    app.add_exception_handler(InvalidLifecycleTransitionError, inspection_state_handler)
    app.add_exception_handler(ImageTooLargeError, image_too_large_handler)
    app.add_exception_handler(ImageTooManyPixelsError, image_too_large_handler)
    app.add_exception_handler(UnsupportedImageFormatError, unsupported_image_handler)
    app.add_exception_handler(InvalidImageError, invalid_image_handler)
    app.add_exception_handler(ImageDecodeError, invalid_image_handler)
    app.add_exception_handler(ImageSecurityError, invalid_image_handler)
    app.add_exception_handler(InvalidPipelineInputError, invalid_pipeline_input_handler)
    app.add_exception_handler(InvalidInspectionError, invalid_pipeline_input_handler)
    app.add_exception_handler(PipelineExecutionError, pipeline_error_handler)
    app.add_exception_handler(PipelineError, pipeline_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Register Routers
    # Root health endpoint and public report shares
    app.include_router(health_router)
    app.include_router(public_reports_router)
    # v1 health, inspections, public reports, heatmap, voice, authority, consumer reports, and telegram endpoints
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(inspections_router, prefix="/api/v1")
    app.include_router(consumer_reports_router, prefix="/api/v1")
    app.include_router(public_reports_router, prefix="/api/v1")
    app.include_router(heatmap_router, prefix="/api/v1")
    app.include_router(voice_router, prefix="/api/v1")
    app.include_router(authority_router, prefix="/api/v1")
    app.include_router(telegram_link_router, prefix="/api/v1")

    return app




app = create_app()