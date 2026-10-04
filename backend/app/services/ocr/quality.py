"""Lightweight OCR-readiness quality assessment for Phase 5C."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.services.evidence.models import ImageArtifact


@dataclass(frozen=True)
class OCRQualityReport:
    """Readiness assessment report for an ImageArtifact."""
    is_suitable: bool
    warnings: list[str] = field(default_factory=list)
    original_width: int = 0
    original_height: int = 0
    normalized_width: int = 0
    normalized_height: int = 0
    pixel_count: int = 0
    aspect_ratio: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_suitable": self.is_suitable,
            "warnings": list(self.warnings),
            "original_width": self.original_width,
            "original_height": self.original_height,
            "normalized_width": self.normalized_width,
            "normalized_height": self.normalized_height,
            "pixel_count": self.pixel_count,
            "aspect_ratio": self.aspect_ratio,
        }


class OCRQualityAssessor:
    """Non-destructive image readiness evaluator detecting conditions that degrade OCR fidelity."""

    @staticmethod
    def assess(artifact: ImageArtifact) -> OCRQualityReport:
        warnings: list[str] = []

        w = artifact.normalized_width
        h = artifact.normalized_height
        pixels = artifact.pixel_count
        aspect = artifact.aspect_ratio

        if w < 100 or h < 100:
            warnings.append(f"Low resolution: image dimensions ({w}x{h}) are below recommended 100px threshold.")

        if aspect > 10.0 or aspect < 0.1:
            warnings.append(f"Extreme aspect ratio ({aspect:.2f}): text geometry may be elongated or distorted.")

        if pixels < 20_000:
            warnings.append(f"Low pixel density ({pixels:,} pixels): small font statutory declarations may not be resolvable.")

        is_suitable = len(warnings) == 0

        return OCRQualityReport(
            is_suitable=is_suitable,
            warnings=warnings,
            original_width=artifact.original_width,
            original_height=artifact.original_height,
            normalized_width=w,
            normalized_height=h,
            pixel_count=pixels,
            aspect_ratio=aspect,
        )

