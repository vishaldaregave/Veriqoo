"""Deterministic, safe image ingestion service for Phase 5A Evidence Pipeline."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, BinaryIO

from PIL import Image, UnidentifiedImageError

from backend.app.services.evidence.errors import (
    ImageDecodeError,
    ImageIngestionError,
    ImageSecurityError,
    ImageTooLargeError,
    ImageTooManyPixelsError,
    InvalidImageError,
    UnsupportedImageFormatError,
)
from backend.app.services.evidence.hashing import compute_sha256, derive_image_id
from backend.app.services.evidence.models import (
    ImageArtifact,
    ImageFormat,
    IngestionConfig,
)
from backend.app.services.evidence.normalization import (
    encode_normalized_image,
    normalize_color,
    normalize_dimensions,
    normalize_orientation,
)
from backend.app.services.evidence.validation import (
    validate_file_path,
    validate_image_dimensions,
    validate_image_format,
    validate_source_bytes,
)


class ImageIngestionService:
    """Production service for ingesting, validating, and normalizing package photographs."""

    def __init__(self, config: IngestionConfig | None = None) -> None:
        self.config = config or IngestionConfig()

    def ingest_bytes(
        self,
        data: bytes,
        source_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ImageArtifact:
        """Ingest raw image bytes, validate security constraints, and produce normalized artifact."""
        meta = dict(metadata or {})
        if source_name:
            meta["source_name"] = source_name

        # 1. Byte validation
        validate_source_bytes(data, self.config)
        source_hash = compute_sha256(data)

        # 2. Decompression safety limits
        Image.MAX_IMAGE_PIXELS = self.config.max_pixels

        # 3. Decode & format validation
        try:
            # First pass: verify stream integrity and detect format
            test_img = Image.open(io.BytesIO(data))
            detected_format = test_img.format
            validated_format = validate_image_format(detected_format, self.config)

            # Re-open fresh stream for full decoding and pixel manipulation
            img = Image.open(io.BytesIO(data))
            img.load()  # Force full decode to detect corrupt byte streams
        except (UnsupportedImageFormatError, ImageIngestionError):
            raise
        except UnidentifiedImageError as exc:
            raise InvalidImageError(f"File could not be identified as a valid image: {exc}") from exc
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ImageTooManyPixelsError(f"Maximum pixel threshold or decompression bomb limit exceeded: {exc}") from exc
        except Exception as exc:
            raise ImageDecodeError(f"Failed to decode image bytes: {exc}") from exc

        # 4. Dimension validation
        orig_width, orig_height = img.size
        validate_image_dimensions(orig_width, orig_height, self.config)

        # 5. Orientation normalization (physical EXIF transposition)
        oriented_img, was_oriented = normalize_orientation(img)

        # 6. Color normalization (standard RGB)
        color_img = normalize_color(oriented_img)

        # 7. Dimension normalization (aspect-ratio preserving downscale)
        norm_img, was_resized = normalize_dimensions(color_img, self.config)
        norm_width, norm_height = norm_img.size

        # 8. Byte encoding in normalized target format
        normalized_bytes = encode_normalized_image(norm_img, self.config.target_format, self.config)
        normalized_hash = compute_sha256(normalized_bytes)
        image_id = derive_image_id(normalized_hash)

        pixel_count = norm_width * norm_height
        aspect_ratio = round(norm_width / norm_height, 4) if norm_height > 0 else 1.0

        return ImageArtifact(
            image_id=image_id,
            source_hash=source_hash,
            normalized_hash=normalized_hash,
            source_format=validated_format.value,
            normalized_format=self.config.target_format.value,
            original_width=orig_width,
            original_height=orig_height,
            normalized_width=norm_width,
            normalized_height=norm_height,
            pixel_count=pixel_count,
            aspect_ratio=aspect_ratio,
            file_size_bytes=len(normalized_bytes),
            source_file_size_bytes=len(data),
            color_mode="RGB",
            normalized_bytes=normalized_bytes,
            was_resized=was_resized,
            was_orientation_corrected=was_oriented,
            metadata=meta,
        )

    def ingest_file(
        self,
        file_path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> ImageArtifact:
        """Ingest image from filesystem without modifying the original source file."""
        resolved = validate_file_path(file_path)
        meta = dict(metadata or {})
        meta["source_path"] = str(resolved)
        meta["source_filename"] = resolved.name

        try:
            with open(resolved, "rb") as f:
                data = f.read()
        except Exception as exc:
            raise InvalidImageError(f"Failed to read file from disk: {exc}") from exc

        return self.ingest_bytes(data, source_name=resolved.name, metadata=meta)

    def ingest_stream(
        self,
        stream: BinaryIO,
        source_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ImageArtifact:
        """Ingest image from an open binary stream."""
        try:
            data = stream.read()
        except Exception as exc:
            raise InvalidImageError(f"Failed to read from binary stream: {exc}") from exc

        return self.ingest_bytes(data, source_name=source_name, metadata=metadata)

