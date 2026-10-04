"""Phase 5A Evidence Image Ingestion & Normalization package."""

from backend.app.services.evidence.batch import ImageBatchIngestionService
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
from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.evidence.models import (
    BatchItem,
    ColorMode,
    ImageArtifact,
    ImageBatch,
    ImageFormat,
    IngestionConfig,
)
from backend.app.services.evidence.normalization import (
    encode_normalized_image,
    normalize_color,
    normalize_dimensions,
    normalize_orientation,
)

__all__ = [
    "BatchItem",
    "ColorMode",
    "ImageArtifact",
    "ImageBatch",
    "ImageBatchIngestionService",
    "ImageDecodeError",
    "ImageFormat",
    "ImageIngestionError",
    "ImageIngestionService",
    "ImageSecurityError",
    "ImageTooLargeError",
    "ImageTooManyPixelsError",
    "IngestionConfig",
    "InvalidImageError",
    "UnsupportedImageFormatError",
    "compute_sha256",
    "derive_image_id",
    "encode_normalized_image",
    "normalize_color",
    "normalize_dimensions",
    "normalize_orientation",
]

