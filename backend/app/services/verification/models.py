"""Domain models and contracts for Phase 5E Evidence-to-Requirement Verification."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from backend.app.services.evidence.models import EvidenceCandidate, EvidenceField
from backend.app.services.verification.errors import (
    MissingRequirementError,
    InvalidVerificationStateError,
)


class VerificationStatus(str, Enum):
    """Controlled verification status vocabulary for Legal Metrology compliance."""
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_VISIBLE = "NOT_VISIBLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclasses.dataclass(frozen=True)
class RequirementReference:
    """Authoritative legal requirement specification provided by the legal pipeline."""
    requirement_id: str
    rule_number: str | None = None
    section_reference: str | None = None
    requirement_text: str | None = None
    target_field: EvidenceField | str | None = None
    target_fields: list[EvidenceField | str] = dataclasses.field(default_factory=list)
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.requirement_id or not str(self.requirement_id).strip():
            raise MissingRequirementError("requirement_id is mandatory and cannot be empty.")


@dataclasses.dataclass
class VerificationResult:
    """Authoritative output of requirement verification against evidence candidates."""
    requirement_id: str
    status: VerificationStatus
    reason: str
    verification_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    applicability_decision_id: str | None = None
    evidence_ids: list[str] = dataclasses.field(default_factory=list)
    source_observation_ids: list[str] = dataclasses.field(default_factory=list)
    image_ids: list[str] = dataclasses.field(default_factory=list)
    confidence: float | None = None
    review_required: bool = False
    created_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.requirement_id or not str(self.requirement_id).strip():
            raise MissingRequirementError(
                "VerificationResult must reference a valid legal requirement_id. Orphan results are prohibited."
            )

        if not isinstance(self.status, VerificationStatus):
            try:
                self.status = VerificationStatus(str(self.status))
            except ValueError:
                raise InvalidVerificationStateError(
                    f"Invalid status '{self.status}'. Must be one of {[s.value for s in VerificationStatus]}."
                )

        if self.status == VerificationStatus.REVIEW_REQUIRED:
            self.review_required = True

        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)

        self.evidence_ids = list(dict.fromkeys(self.evidence_ids))
        self.source_observation_ids = list(dict.fromkeys(self.source_observation_ids))
        self.image_ids = list(dict.fromkeys(self.image_ids))

    def to_dict(self) -> dict[str, Any]:
        """Convert result to clean dictionary representation."""
        return {
            "verification_id": self.verification_id,
            "requirement_id": self.requirement_id,
            "applicability_decision_id": self.applicability_decision_id,
            "status": self.status.value,
            "reason": self.reason,
            "evidence_ids": self.evidence_ids,
            "source_observation_ids": self.source_observation_ids,
            "image_ids": self.image_ids,
            "confidence": self.confidence,
            "review_required": self.review_required,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

