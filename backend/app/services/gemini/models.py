"""Domain models and structured schema contracts for Phase 6 Gemini Evidence Reasoning."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from backend.app.services.evidence.models import EvidenceCandidate
from backend.app.services.gemini.errors import GeminiValidationError


class GeminiRecommendation(str, Enum):
    """Allowed recommendation outcomes produced by Gemini evidence reasoning.

    NOT_APPLICABLE and NOT_VISIBLE are system-level states and are strictly prohibited here.
    """
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class EvidenceSufficiency(str, Enum):
    """Assessment of evidence completeness and clarity for the requirement."""
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    AMBIGUOUS = "AMBIGUOUS"
    CONTRADICTORY = "CONTRADICTORY"


@dataclasses.dataclass(frozen=True)
class GeminiVerificationRequest:
    """Structured input contract submitted to Gemini for evidence reasoning."""
    requirement_id: str
    requirement_text: str
    request_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    requirement_source_reference: str | None = None
    applicability_status: str = "APPLICABLE"
    evidence_candidates: list[EvidenceCandidate] = dataclasses.field(default_factory=list)
    verification_context: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.requirement_id or not str(self.requirement_id).strip():
            raise GeminiValidationError("requirement_id is mandatory and cannot be empty.")
        if not self.requirement_text or not str(self.requirement_text).strip():
            raise GeminiValidationError("requirement_text is mandatory and cannot be empty.")


@dataclasses.dataclass
class GeminiEvidenceAssessment:
    """Validated structured assessment returned by Gemini evidence reasoning."""
    requirement_id: str
    recommendation: GeminiRecommendation
    evidence_sufficiency: EvidenceSufficiency
    reason: str
    assessment_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    evidence_ids: list[str] = dataclasses.field(default_factory=list)
    ambiguities: list[str] = dataclasses.field(default_factory=list)
    contradictions: list[str] = dataclasses.field(default_factory=list)
    unsupported_claims: list[str] = dataclasses.field(default_factory=list)
    model: str = ""
    model_version: str = ""
    prompt_version: str = "phase6-v1"
    created_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.requirement_id or not str(self.requirement_id).strip():
            raise GeminiValidationError("requirement_id is mandatory in GeminiEvidenceAssessment.")

        if not isinstance(self.recommendation, GeminiRecommendation):
            try:
                self.recommendation = GeminiRecommendation(str(self.recommendation).upper())
            except ValueError:
                raise GeminiValidationError(
                    f"Invalid recommendation '{self.recommendation}'. Must be one of {[r.value for r in GeminiRecommendation]}."
                )

        if not isinstance(self.evidence_sufficiency, EvidenceSufficiency):
            try:
                self.evidence_sufficiency = EvidenceSufficiency(str(self.evidence_sufficiency).upper())
            except ValueError:
                raise GeminiValidationError(
                    f"Invalid evidence_sufficiency '{self.evidence_sufficiency}'. Must be one of {[s.value for s in EvidenceSufficiency]}."
                )

        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)

        # Deduplicate evidence IDs preserving order
        self.evidence_ids = list(dict.fromkeys(self.evidence_ids))
        self.ambiguities = list(dict.fromkeys(self.ambiguities))
        self.contradictions = list(dict.fromkeys(self.contradictions))

    def to_dict(self) -> dict[str, Any]:
        """Convert assessment to clean dictionary representation."""
        return {
            "assessment_id": self.assessment_id,
            "requirement_id": self.requirement_id,
            "recommendation": self.recommendation.value,
            "evidence_sufficiency": self.evidence_sufficiency.value,
            "reason": self.reason,
            "evidence_ids": self.evidence_ids,
            "ambiguities": self.ambiguities,
            "contradictions": self.contradictions,
            "unsupported_claims": self.unsupported_claims,
            "model": self.model,
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }
