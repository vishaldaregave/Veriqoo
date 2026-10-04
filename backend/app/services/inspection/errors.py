"""Explicit exception hierarchy for Phase 5B Multi-Image Inspection Management."""

from __future__ import annotations

from typing import Any


class InspectionError(Exception):
    """Base exception for all inspection management errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidInspectionError(InspectionError):
    """Raised when an inspection model or configuration is invalid."""
    pass


class InspectionNotFoundError(InspectionError):
    """Raised when the requested inspection ID does not exist in the manager."""
    pass


class ImageNotFoundInInspectionError(InspectionError):
    """Raised when an image is not found within the specified inspection."""
    pass


class InvalidInspectionImageReferenceError(InspectionError):
    """Raised when an object is not a valid Phase 5A ImageArtifact or reference is invalid."""
    pass


class InspectionStateError(InspectionError):
    """Raised when an operation violates the current lifecycle state of an inspection."""
    pass


class InvalidLifecycleTransitionError(InspectionStateError):
    """Raised when an invalid status transition is attempted."""
    pass

