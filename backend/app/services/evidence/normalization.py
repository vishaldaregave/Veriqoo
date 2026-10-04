"""Image and text normalization procedures for Phase 5A and Phase 5D.

Phase 5A:
1. Canonical EXIF orientation transposition (physical pixel rotation).
2. Deterministic color space normalization (standard RGB).
3. Aspect-ratio-preserving downscaling for excessively large images (no upscaling).
4. Lossless/high-fidelity byte encoding.

Phase 5D:
5. Safe, non-destructive text normalization (Unicode NFC, surrounding whitespace stripping, internal space collapsing).
"""

from __future__ import annotations

import io
import re
import unicodedata
from PIL import Image, ImageOps

from backend.app.services.evidence.models import ColorMode, ImageFormat, IngestionConfig


# =====================================================================
# Phase 5A Image Normalization Procedures
# =====================================================================

def normalize_orientation(image: Image.Image) -> tuple[Image.Image, bool]:
    """Transpose image pixels to physical canonical orientation based on EXIF metadata.

    Returns the transposed Image and a boolean flag indicating if transposition occurred.
    """
    try:
        transposed = ImageOps.exif_transpose(image)
        if transposed is not None:
            # Check if dimensions or pixel data changed due to orientation
            was_transposed = (
                transposed.size != image.size
                or transposed is not image
            )
            return transposed, was_transposed
    except Exception:
        # If EXIF reading fails safely fallback to original image
        pass

    return image, False


def normalize_color(image: Image.Image) -> Image.Image:
    """Normalize image color representation to standard RGB.

    Handles:
    - RGBA: alpha composite over white background to RGB.
    - Grayscale (L), Palette (P), CMYK, LA: converted to RGB.
    - Does NOT perform thresholding, binarizing, or OCR-specific enhancement.
    """
    if image.mode == "RGB":
        return image

    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        return background

    if image.mode == "LA":
        rgba = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[3])
        return background

    return image.convert("RGB")


def normalize_dimensions(
    image: Image.Image,
    config: IngestionConfig,
) -> tuple[Image.Image, bool]:
    """Downscale excessively large images while strictly preserving aspect ratio.

    Rules:
    - If image max dimension exceeds downscale_max_dimension and auto_downscale is True:
        Downscale using high-quality Lanczos resampling.
    - If image is smaller than downscale_max_dimension:
        DO NOT UPSCALE. Return image untouched.
    """
    width, height = image.size
    max_target = config.downscale_max_dimension

    if not config.auto_downscale or (width <= max_target and height <= max_target):
        return image, False

    # Calculate proportional downscale factor
    if width > height:
        new_width = max_target
        new_height = max(1, int(round((height / width) * max_target)))
    else:
        new_height = max_target
        new_width = max(1, int(round((width / height) * max_target)))

    resample_filter = getattr(Image.Resampling, "LANCZOS", getattr(Image, "LANCZOS", Image.BICUBIC))
    resized = image.resize((new_width, new_height), resample=resample_filter)
    return resized, True


def encode_normalized_image(
    image: Image.Image,
    target_format: ImageFormat,
    config: IngestionConfig,
) -> bytes:
    """Encode the normalized PIL Image into bytes in the specified target format."""
    buffer = io.BytesIO()

    if target_format == ImageFormat.PNG:
        image.save(buffer, format="PNG", optimize=True)
    elif target_format == ImageFormat.JPEG:
        image.save(buffer, format="JPEG", quality=config.jpeg_quality, optimize=True)
    elif target_format == ImageFormat.WEBP:
        image.save(buffer, format="WEBP", quality=config.jpeg_quality)
    else:
        image.save(buffer, format="PNG")

    return buffer.getvalue()


# =====================================================================
# Phase 5D Text Normalization Procedures
# =====================================================================

_WHITESPACE_COLLAPSE_RE = re.compile(r"[ \t\r\f\v]+")


def normalize_evidence_text(raw_text: str) -> str:
    """Perform safe, non-destructive textual normalization for OCR observations.

    Rules:
    1. Strips leading and trailing whitespace.
    2. Collapses internal repeated whitespace/tabs to a single space.
    3. Normalizes Unicode characters to standard Canonical Decomposition followed by Canonical Composition (NFC).
    4. NEVER modifies spelling, corrects characters, removes words, alters case, or replaces numbers.
    """
    if not raw_text:
        return ""

    # 1. Unicode NFC normalization
    normalized_unicode = unicodedata.normalize("NFC", str(raw_text))

    # 2. Strip and collapse whitespace
    collapsed = _WHITESPACE_COLLAPSE_RE.sub(" ", normalized_unicode).strip()

    return collapsed
