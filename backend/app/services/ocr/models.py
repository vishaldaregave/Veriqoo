"""Core models and contracts for Phase 5C OCR Observations and Results."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class OCRProcessingStatus(str, Enum):
    """Execution status for an OCR extraction operation."""
    SUCCESS = "SUCCESS"
    NO_TEXT_DETECTED = "NO_TEXT_DETECTED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class BoundingBox:
    """Quadrilateral bounding box geometry representing detected text regions in pixel coordinates.

    Points are structured as 4 sequential vertices: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
    relative to the normalized Phase 5A image origin (top-left 0,0).
    """
    points: list[list[float]]

    def __post_init__(self) -> None:
        if not self.points or len(self.points) != 4:
            raise ValueError(f"BoundingBox requires exactly 4 coordinate pairs, got {len(self.points) if self.points else 0}.")
        for pt in self.points:
            if not isinstance(pt, (list, tuple)) or len(pt) != 2:
                raise ValueError(f"Each bounding box point must be a 2-element list/tuple [x, y], got {pt}.")

    @property
    def x_min(self) -> float:
        return min(p[0] for p in self.points)

    @property
    def y_min(self) -> float:
        return min(p[1] for p in self.points)

    @property
    def x_max(self) -> float:
        return max(p[0] for p in self.points)

    @property
    def y_max(self) -> float:
        return max(p[1] for p in self.points)

    @property
    def width(self) -> float:
        return max(0.0, self.x_max - self.x_min)

    @property
    def height(self) -> float:
        return max(0.0, self.y_max - self.y_min)

    def to_dict(self) -> dict[str, Any]:
        return {
            "points": [[float(coord) for coord in pt] for pt in self.points],
            "x_min": float(self.x_min),
            "y_min": float(self.y_min),
            "x_max": float(self.x_max),
            "y_max": float(self.y_max),
            "width": float(self.width),
            "height": float(self.height),
        }


@dataclass(frozen=True)
class OCRObservation:
    """Immutable single OCR text detection observation.

    Preserves exact raw uncorrected text, geometry, confidence, and sequence.
    """
    observation_id: str
    image_id: str
    text: str
    confidence: float | None
    bounding_box: BoundingBox
    sequence: int
    engine: str
    engine_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "image_id": self.image_id,
            "text": self.text,
            "confidence": float(self.confidence) if self.confidence is not None else None,
            "bounding_box": self.bounding_box.to_dict(),
            "sequence": self.sequence,
            "engine": self.engine,
            "engine_version": self.engine_version,
        }


@dataclass
class OCRResult:
    """Structured collection of OCR observations produced from a single Phase 5A ImageArtifact."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    image_id: str = ""
    status: OCRProcessingStatus = OCRProcessingStatus.SUCCESS
    observations: list[OCRObservation] = field(default_factory=list)
    engine: str = "PaddleOCR"
    engine_version: str = "unknown"
    language: str = "en"
    processed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    quality_report: dict[str, Any] | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.processed_at.tzinfo is None:
            self.processed_at = self.processed_at.replace(tzinfo=timezone.utc)

    @property
    def total_observations(self) -> int:
        return len(self.observations)

    @property
    def is_success(self) -> bool:
        return self.status == OCRProcessingStatus.SUCCESS

    @property
    def raw_texts(self) -> list[str]:
        """Return raw list of detected text strings in sequential order."""
        return [obs.text for obs in self.observations]

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "image_id": self.image_id,
            "status": self.status.value,
            "total_observations": self.total_observations,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "language": self.language,
            "processed_at": self.processed_at.isoformat(),
            "observations": [obs.to_dict() for obs in self.observations],
            "quality_report": self.quality_report,
            "error_message": self.error_message,
        }

