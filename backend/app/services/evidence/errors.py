"""Explicit exception hierarchy for Phase 5A (Ingestion) & Phase 5D (Evidence Normalization)."""

from __future__ import annotations


# =====================================================================
# Phase 5A Image Ingestion Errors
# =====================================================================

class ImageIngestionError(Exception):
    """Base exception for all image ingestion and normalization errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UnsupportedImageFormatError(ImageIngestionError):
    """Raised when an unsupported image format or extension is provided."""
    pass


class InvalidImageError(ImageIngestionError):
    """Raised when provided bytes or file do not constitute a valid readable image."""
    pass


class ImageDecodeError(ImageIngestionError):
    """Raised when image decoding fails or corrupt image data is encountered."""
    pass


class ImageTooLargeError(ImageIngestionError):
    """Raised when image file size exceeds configured byte limits."""
    pass


class ImageTooManyPixelsError(ImageIngestionError):
    """Raised when image dimensions or total pixel count exceeds configured safety limits."""
    pass


class ImageSecurityError(ImageIngestionError):
    """Raised when security violations (e.g., path traversal, decompression bomb) are detected."""
    pass


# =====================================================================
# Phase 5D Evidence Normalization Errors
# =====================================================================

class EvidenceNormalizationError(Exception):
    """Base exception for evidence normalization and parsing failures."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class EvidenceParserError(EvidenceNormalizationError):
    """Raised when an evidence parser encounters an unrecoverable syntax or structure error."""
    pass


class InvalidEvidenceInputError(EvidenceNormalizationError):
    """Raised when input to evidence normalization is malformed, missing, or of wrong type."""
    pass


class AmbiguousEvidenceError(EvidenceNormalizationError):
    """Raised or referenced when evidence contains irreconcilable conflicting declarations."""
    pass
