"""Coordinated OCR Extractor service for Phase 5C."""

from __future__ import annotations

import uuid
from typing import Callable, Sequence

from backend.app.services.evidence.models import ImageArtifact
from backend.app.services.inspection.models import Inspection
from backend.app.services.ocr.config import OCRConfig
from backend.app.services.ocr.engine import OCREngine, PaddleOCREngine
from backend.app.services.ocr.errors import (
    OCRExtractionError,
    OCRInvalidInputError,
    OCRModelUnavailableError,
    OCRProcessingError,
)
from backend.app.services.ocr.models import (
    BoundingBox,
    OCRObservation,
    OCRProcessingStatus,
    OCRResult,
)
from backend.app.services.ocr.quality import OCRQualityAssessor


class OCRExtractor:
    """Production service extracting structured observations from Phase 5A ImageArtifacts."""

    def __init__(
        self,
        engine: OCREngine | None = None,
        config: OCRConfig | None = None,
    ) -> None:
        self.config = config or OCRConfig()
        self.engine = engine or PaddleOCREngine(config=self.config)
        self.quality_assessor = OCRQualityAssessor()

    def extract_from_artifact(
        self,
        artifact: ImageArtifact,
        config: OCRConfig | None = None,
    ) -> OCRResult:
        """Extract structured OCR observations from a Phase 5A ImageArtifact."""
        if not isinstance(artifact, ImageArtifact) or not artifact.image_id:
            raise OCRInvalidInputError(
                "Input to OCR extraction must be a valid Phase 5A ImageArtifact with a valid image_id.",
                details={"type": type(artifact).__name__},
            )

        cfg = config or self.config
        quality_report = self.quality_assessor.assess(artifact)

        try:
            raw_predictions = self.engine.predict(artifact.normalized_bytes, cfg)
        except OCRExtractionError as exc:
            return OCRResult(
                image_id=artifact.image_id,
                status=OCRProcessingStatus.FAILED,
                observations=[],
                engine=self.engine.engine_name,
                engine_version=self.engine.engine_version,
                language=cfg.language,
                quality_report=quality_report.to_dict(),
                error_message=str(exc),
            )
        except Exception as exc:
            return OCRResult(
                image_id=artifact.image_id,
                status=OCRProcessingStatus.FAILED,
                observations=[],
                engine=self.engine.engine_name,
                engine_version=self.engine.engine_version,
                language=cfg.language,
                quality_report=quality_report.to_dict(),
                error_message=f"Unhandled engine error during OCR extraction: {exc}",
            )

        if not raw_predictions:
            return OCRResult(
                image_id=artifact.image_id,
                status=OCRProcessingStatus.NO_TEXT_DETECTED,
                observations=[],
                engine=self.engine.engine_name,
                engine_version=self.engine.engine_version,
                language=cfg.language,
                quality_report=quality_report.to_dict(),
                error_message=None,
            )

        observations: list[OCRObservation] = []
        for seq_idx, (pts, (raw_text, confidence)) in enumerate(raw_predictions, 1):
            if cfg.min_confidence_threshold > 0.0 and confidence is not None:
                if confidence < cfg.min_confidence_threshold:
                    continue

            box = BoundingBox(points=pts)
            obs = OCRObservation(
                observation_id=f"obs_{uuid.uuid4().hex[:12]}",
                image_id=artifact.image_id,
                text=raw_text,
                confidence=confidence,
                bounding_box=box,
                sequence=seq_idx,
                engine=self.engine.engine_name,
                engine_version=self.engine.engine_version,
            )
            observations.append(obs)

        return OCRResult(
            image_id=artifact.image_id,
            status=OCRProcessingStatus.SUCCESS if observations else OCRProcessingStatus.NO_TEXT_DETECTED,
            observations=observations,
            engine=self.engine.engine_name,
            engine_version=self.engine.engine_version,
            language=cfg.language,
            quality_report=quality_report.to_dict(),
            error_message=None,
        )

    def extract_from_inspection(
        self,
        inspection: Inspection,
        artifact_resolver: Callable[[str], ImageArtifact | None] | dict[str, ImageArtifact],
        config: OCRConfig | None = None,
    ) -> list[OCRResult]:
        """Extract OCR results for all images in an inspection container preserving sequential order."""
        results: list[OCRResult] = []

        for ref in inspection.images:
            if callable(artifact_resolver):
                artifact = artifact_resolver(ref.image_id)
            else:
                artifact = artifact_resolver.get(ref.image_id)

            if artifact is None:
                results.append(
                    OCRResult(
                        image_id=ref.image_id,
                        status=OCRProcessingStatus.FAILED,
                        observations=[],
                        engine=self.engine.engine_name,
                        engine_version=self.engine.engine_version,
                        error_message=f"ImageArtifact with ID '{ref.image_id}' could not be resolved from provided store.",
                    )
                )
                continue

            result = self.extract_from_artifact(artifact, config=config)
            results.append(result)

        return results

