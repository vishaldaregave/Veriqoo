"""Domain models and context contracts for Phase 7 Unified Inspection Pipeline."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
import uuid

from backend.app.services.applicability.models import ApplicabilityDecision, InspectionFact
from backend.app.services.evidence.models import EvidenceCandidate, ImageArtifact
from backend.app.services.gemini.models import GeminiEvidenceAssessment
from backend.app.services.inspection_pipeline.errors import InvalidPipelineInputError
from backend.app.services.ocr.models import OCRResult
from backend.app.services.verification.models import RequirementReference, VerificationResult


class OverallInspectionStatus(str, Enum):
    """Controlled overall compliance status for an end-to-end inspection."""
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclasses.dataclass
class InspectionPipelineRequest:
    """Strongly typed input request initiating an end-to-end inspection workflow."""
    inspection_id: str
    inspection_date: date | str | None = None
    image_artifacts: list[ImageArtifact] = dataclasses.field(default_factory=list)
    inspection_facts: list[InspectionFact] = dataclasses.field(default_factory=list)
    applicability_context: dict[str, Any] = dataclasses.field(default_factory=dict)
    target_requirements: list[RequirementReference | str] = dataclasses.field(default_factory=list)
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.inspection_id or not str(self.inspection_id).strip():
            raise InvalidPipelineInputError("inspection_id is mandatory and cannot be empty.")


@dataclasses.dataclass
class InspectionPipelineContext:
    """Transient in-memory execution context holding pipeline intermediate state."""
    inspection_id: str
    images: list[ImageArtifact] = dataclasses.field(default_factory=list)
    ocr_results: list[OCRResult] = dataclasses.field(default_factory=list)
    ocr_errors: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    evidence_candidates: list[EvidenceCandidate] = dataclasses.field(default_factory=list)
    inspection_facts: list[InspectionFact] = dataclasses.field(default_factory=list)
    applicability_decisions: dict[str, Any] = dataclasses.field(default_factory=dict)
    applicable_requirements: list[RequirementReference] = dataclasses.field(default_factory=list)
    legal_contexts: dict[str, Any] = dataclasses.field(default_factory=dict)
    gemini_assessments: dict[str, GeminiEvidenceAssessment] = dataclasses.field(default_factory=dict)
    verification_results: list[VerificationResult] = dataclasses.field(default_factory=list)
    errors: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    started_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is None:
            self.started_at = self.started_at.replace(tzinfo=timezone.utc)

