"""Evidence Normalization Service orchestrating deterministic parsers for Phase 5D."""

from __future__ import annotations

from typing import Sequence

from backend.app.services.evidence.errors import InvalidEvidenceInputError
from backend.app.services.evidence.models import EvidenceCandidate
from backend.app.services.evidence.normalization import normalize_evidence_text
from backend.app.services.evidence.parsers import (
    BaseEvidenceParser,
    BatchParser,
    ContactParser,
    DateParser,
    GenericParser,
    IdentityParser,
    MRPParser,
    QuantityParser,
)
from backend.app.services.ocr.models import OCRObservation, OCRResult


class EvidenceNormalizationService:
    """Production service converting raw OCR observations into structured EvidenceCandidate objects.

    Principles:
    1. Preserves raw OCR text, geometry, confidence, sequence, and provenance without mutation.
    2. Executes deterministic parsers in prioritized order.
    3. Retains multi-image isolation and duplicate observations.
    4. Does NOT determine legal compliance, applicability rules, or PASS/FAIL status.
    """

    def __init__(self, parsers: list[BaseEvidenceParser] | None = None) -> None:
        self.parsers = parsers or [
            MRPParser(),
            QuantityParser(),
            DateParser(),
            ContactParser(),
            IdentityParser(),
            BatchParser(),
        ]
        self.fallback_parser = GenericParser()

    def normalize_observation(self, observation: OCRObservation) -> list[EvidenceCandidate]:
        """Normalize a single OCRObservation into one or more EvidenceCandidate objects."""
        if not isinstance(observation, OCRObservation):
            raise InvalidEvidenceInputError(
                f"Expected OCRObservation instance, got {type(observation).__name__}"
            )

        raw_text = observation.text or ""
        normalized_text = normalize_evidence_text(raw_text)

        candidates: list[EvidenceCandidate] = []
        for parser in self.parsers:
            if parser.can_parse(normalized_text):
                parsed = parser.parse(observation, normalized_text)
                if parsed:
                    candidates.extend(parsed)

        # Fallback to generic candidate if no specialized parser succeeded
        if not candidates:
            candidates.extend(self.fallback_parser.parse(observation, normalized_text))

        return candidates

    def normalize_ocr_result(self, ocr_result: OCRResult) -> list[EvidenceCandidate]:
        """Normalize all observations within an OCRResult for a single image artifact."""
        if not isinstance(ocr_result, OCRResult):
            raise InvalidEvidenceInputError(
                f"Expected OCRResult instance, got {type(ocr_result).__name__}"
            )

        candidates: list[EvidenceCandidate] = []
        for obs in ocr_result.observations:
            obs_candidates = self.normalize_observation(obs)
            candidates.extend(obs_candidates)

        return candidates

    def normalize_ocr_results(
        self,
        ocr_results: Sequence[OCRResult] | dict[str, OCRResult],
    ) -> list[EvidenceCandidate]:
        """Normalize multiple OCR results from sequential or keyed multi-image extractions."""
        results_list: Sequence[OCRResult]
        if isinstance(ocr_results, dict):
            results_list = list(ocr_results.values())
        elif isinstance(ocr_results, (list, tuple)):
            results_list = ocr_results
        else:
            raise InvalidEvidenceInputError(
                f"Expected Sequence[OCRResult] or dict[str, OCRResult], got {type(ocr_results).__name__}"
            )

        all_candidates: list[EvidenceCandidate] = []
        for result in results_list:
            all_candidates.extend(self.normalize_ocr_result(result))

        return all_candidates

    def normalize_inspection_observations(
        self,
        inspection_results: dict[str, OCRResult],
    ) -> dict[str, list[EvidenceCandidate]]:
        """Normalize OCR results grouped by ImageArtifact ID, strictly preserving image-level isolation."""
        if not isinstance(inspection_results, dict):
            raise InvalidEvidenceInputError(
                f"Expected dict[str, OCRResult], got {type(inspection_results).__name__}"
            )

        grouped_evidence: dict[str, list[EvidenceCandidate]] = {}
        for image_id, result in inspection_results.items():
            grouped_evidence[image_id] = self.normalize_ocr_result(result)

        return grouped_evidence

