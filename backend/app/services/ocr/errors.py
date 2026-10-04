"""Explicit exception hierarchy for Phase 5C PaddleOCR Extraction."""

from __future__ import annotations

from typing import Any


class OCRExtractionError(Exception):
    """Base exception for all OCR extraction, configuration, and engine errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class OCRInitializationError(OCRExtractionError):
    """Raised when OCR engine initialization fails or runtime environment is incompatible."""
    pass


class OCRProcessingError(OCRExtractionError):
    """Raised when an error occurs during OCR prediction or text recognition pass."""
    pass


class OCRModelUnavailableError(OCRExtractionError):
    """Raised when the requested OCR model weights or language package is unavailable."""
    pass


class OCRInvalidInputError(OCRExtractionError):
    """Raised when the input provided to OCR is not a valid Phase 5A ImageArtifact."""
    pass

