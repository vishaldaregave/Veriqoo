"""Phase 5C High-Accuracy PaddleOCR Extraction package."""

from backend.app.services.ocr.config import OCRConfig
from backend.app.services.ocr.engine import (
    MockOCREngine,
    OCREngine,
    PaddleOCREngine,
)
from backend.app.services.ocr.errors import (
    OCRExtractionError,
    OCRInitializationError,
    OCRInvalidInputError,
    OCRModelUnavailableError,
    OCRProcessingError,
)
from backend.app.services.ocr.extractor import OCRExtractor
from backend.app.services.ocr.models import (
    BoundingBox,
    OCRObservation,
    OCRProcessingStatus,
    OCRResult,
)
from backend.app.services.ocr.quality import (
    OCRQualityAssessor,
    OCRQualityReport,
)

__all__ = [
    "BoundingBox",
    "MockOCREngine",
    "OCRConfig",
    "OCREngine",
    "OCRExtractionError",
    "OCRExtractor",
    "OCRInitializationError",
    "OCRInvalidInputError",
    "OCRModelUnavailableError",
    "OCRObservation",
    "OCRProcessingError",
    "OCRProcessingStatus",
    "OCRQualityAssessor",
    "OCRQualityReport",
    "OCRResult",
    "PaddleOCREngine",
]

