"""Structured error models, codes, and exception handlers for LegalMetrologyAI API."""

from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

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
    ImageNotFoundInInspectionError,
    InspectionError,
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


class ErrorCode(str, Enum):
    """Standardized machine-readable error codes."""
    INVALID_REQUEST = "INVALID_REQUEST"
    INSPECTION_NOT_FOUND = "INSPECTION_NOT_FOUND"
    INVALID_INSPECTION_STATE = "INVALID_INSPECTION_STATE"
    INVALID_IMAGE = "INVALID_IMAGE"
    IMAGE_EMPTY = "IMAGE_EMPTY"
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"
    IMAGE_UNSUPPORTED = "IMAGE_UNSUPPORTED"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    AUTHENTICATION_INVALID = "AUTHENTICATION_INVALID"
    AUTHENTICATION_EXPIRED = "AUTHENTICATION_EXPIRED"
    INSPECTION_ACCESS_DENIED = "INSPECTION_ACCESS_DENIED"
    REPORT_NOT_AVAILABLE = "REPORT_NOT_AVAILABLE"
    PIPELINE_ERROR = "PIPELINE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SYNC_BATCH_TOO_LARGE = "SYNC_BATCH_TOO_LARGE"
    SYNC_OPERATION_INVALID = "SYNC_OPERATION_INVALID"
    SYNC_NOT_OWNER = "SYNC_NOT_OWNER"


class ErrorDetail(BaseModel):
    """Inner error payload following the standard API error contract."""
    code: str = Field(..., description="Machine-readable error identifier")
    message: str = Field(..., description="Human-readable explanation of the error")
    details: dict[str, Any] = Field(default_factory=dict, description="Structured contextual diagnostics")


class ErrorResponse(BaseModel):
    """Top-level standard error envelope."""
    error: ErrorDetail


def create_error_response(
    status_code: int,
    code: str | ErrorCode,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Helper to generate standardized JSONResponse for errors."""
    code_val = code.value if isinstance(code, ErrorCode) else str(code)
    payload = {
        "error": {
            "code": code_val,
            "message": message,
            "details": details or {},
        }
    }
    return JSONResponse(status_code=status_code, content=payload)


# =====================================================================
# Global Exception Handlers
# =====================================================================

async def inspection_not_found_handler(request: Request, exc: InspectionNotFoundError) -> JSONResponse:
    return create_error_response(
        status_code=404,
        code=ErrorCode.INSPECTION_NOT_FOUND,
        message=str(exc.message if hasattr(exc, "message") else exc),
        details=getattr(exc, "details", {}),
    )


async def inspection_state_handler(request: Request, exc: InspectionStateError) -> JSONResponse:
    return create_error_response(
        status_code=409,
        code=ErrorCode.INVALID_INSPECTION_STATE,
        message=str(exc.message if hasattr(exc, "message") else exc),
        details=getattr(exc, "details", {}),
    )


async def image_too_large_handler(request: Request, exc: ImageTooLargeError | ImageTooManyPixelsError) -> JSONResponse:
    return create_error_response(
        status_code=413,
        code=ErrorCode.IMAGE_TOO_LARGE,
        message=str(exc.message if hasattr(exc, "message") else exc),
        details=getattr(exc, "details", {}),
    )


async def unsupported_image_handler(request: Request, exc: UnsupportedImageFormatError) -> JSONResponse:
    return create_error_response(
        status_code=415,
        code=ErrorCode.IMAGE_UNSUPPORTED,
        message=str(exc.message if hasattr(exc, "message") else exc),
        details=getattr(exc, "details", {}),
    )


async def invalid_image_handler(request: Request, exc: InvalidImageError | ImageDecodeError | ImageSecurityError) -> JSONResponse:
    return create_error_response(
        status_code=400,
        code=ErrorCode.INVALID_IMAGE,
        message=str(exc.message if hasattr(exc, "message") else exc),
        details=getattr(exc, "details", {}),
    )


async def invalid_pipeline_input_handler(request: Request, exc: InvalidPipelineInputError | InvalidInspectionError) -> JSONResponse:
    return create_error_response(
        status_code=400,
        code=ErrorCode.INVALID_REQUEST,
        message=str(exc),
        details=getattr(exc, "details", {}),
    )


async def pipeline_error_handler(request: Request, exc: PipelineError) -> JSONResponse:
    return create_error_response(
        status_code=500,
        code=ErrorCode.PIPELINE_ERROR,
        message=str(exc),
        details={},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return create_error_response(
        status_code=422,
        code=ErrorCode.INVALID_REQUEST,
        message="Request validation failed.",
        details={"validation_errors": jsonable_encoder(exc.errors())},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # Check if detail is already a structured dict or message
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", ErrorCode.INVALID_REQUEST.value)
        message = exc.detail.get("message", "HTTP error")
        details = exc.detail.get("details", {})
    else:
        # Map common status codes
        if exc.status_code == 404:
            code = ErrorCode.INSPECTION_NOT_FOUND.value
        elif exc.status_code == 400:
            code = ErrorCode.INVALID_REQUEST.value
        elif exc.status_code == 403:
            code = ErrorCode.FORBIDDEN.value
        elif exc.status_code == 409:
            code = ErrorCode.INVALID_INSPECTION_STATE.value
        elif exc.status_code == 413:
            code = ErrorCode.IMAGE_TOO_LARGE.value
        elif exc.status_code == 415:
            code = ErrorCode.IMAGE_UNSUPPORTED.value
        elif exc.status_code == 422:
            code = ErrorCode.INVALID_REQUEST.value
        else:
            code = ErrorCode.INTERNAL_ERROR.value
        message = str(exc.detail)
        details = {}

    return create_error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        details=details,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return create_error_response(
        status_code=500,
        code=ErrorCode.INTERNAL_ERROR,
        message="An unexpected internal server error occurred.",
        details={"error_type": type(exc).__name__, "error": str(exc)},
    )

