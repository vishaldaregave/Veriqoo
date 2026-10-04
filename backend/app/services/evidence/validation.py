"""Security and boundary validation for Phase 5A image ingestion."""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO

from PIL import Image

from backend.app.services.evidence.errors import (
    ImageSecurityError,
    ImageTooLargeError,
    ImageTooManyPixelsError,
    InvalidImageError,
    UnsupportedImageFormatError,
)
from backend.app.services.evidence.models import ImageFormat, IngestionConfig


def validate_file_path(file_path: str | Path) -> Path:
    """Validate that the target path exists, is a regular file, and has no path traversal exploits."""
    if not file_path:
        raise InvalidImageError("Image file path cannot be empty.")

    path_str = str(file_path)
    if "\x00" in path_str:
        raise ImageSecurityError("Null byte detected in file path.")

    try:
        resolved = Path(file_path).resolve()
    except Exception as exc:
        raise InvalidImageError(f"Invalid file path structure: {exc}") from exc

    if not resolved.exists():
        raise InvalidImageError(f"Image file does not exist: {resolved.name}")

    if not resolved.is_file():
        raise InvalidImageError(f"Specified path is not a regular file: {resolved.name}")

    return resolved


def validate_source_bytes(data: bytes, config: IngestionConfig) -> None:
    """Validate byte length, non-emptiness, and file size constraints."""
    if not data or len(data) == 0:
        raise InvalidImageError("Image byte stream is empty (0 bytes).")

    if len(data) > config.max_file_size_bytes:
        raise ImageTooLargeError(
            f"Image file size ({len(data)} bytes) exceeds maximum allowed limit ({config.max_file_size_bytes} bytes).",
            details={"size_bytes": len(data), "max_bytes": config.max_file_size_bytes},
        )


def validate_image_dimensions(width: int, height: int, config: IngestionConfig) -> None:
    """Validate that decoded image dimensions and pixel counts are within configured limits."""
    if width <= 0 or height <= 0:
        raise InvalidImageError(
            f"Invalid image dimensions: {width}x{height}. Both width and height must be > 0."
        )

    pixels = width * height
    if width > config.max_width or height > config.max_height:
        raise ImageTooManyPixelsError(
            f"Image dimensions ({width}x{height}) exceed maximum allowed dimensions ({config.max_width}x{config.max_height}).",
            details={"width": width, "height": height, "max_width": config.max_width, "max_height": config.max_height},
        )

    if pixels > config.max_pixels:
        raise ImageTooManyPixelsError(
            f"Total pixel count ({pixels:,}) exceeds maximum allowed pixel count ({config.max_pixels:,}).",
            details={"pixels": pixels, "max_pixels": config.max_pixels},
        )


def validate_image_format(format_name: str | None, config: IngestionConfig) -> ImageFormat:
    """Validate that the image encoding format is supported."""
    if not format_name:
        raise UnsupportedImageFormatError("Could not determine image encoding format.")

    img_format = ImageFormat.from_string(format_name)
    if img_format is None or img_format not in config.allowed_formats:
        allowed_names = [f.value for f in config.allowed_formats]
        raise UnsupportedImageFormatError(
            f"Unsupported image format: '{format_name}'. Allowed formats are: {allowed_names}",
            details={"format": format_name, "allowed": allowed_names},
        )

    return img_format

