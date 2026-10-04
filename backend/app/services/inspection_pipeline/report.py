"""Inspection Report generator and overall status policy for Phase 7."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any, Sequence

from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.verification.models import VerificationResult, VerificationStatus


def compute_overall_status(results: Sequence[VerificationResult]) -> tuple[OverallInspectionStatus, str]:
    """Compute deterministic overall inspection compliance status and summary.

    Policy:
    1. If ANY result is FAIL -> overall status is FAIL.
    2. Else if ANY result is REVIEW_REQUIRED -> overall status is REVIEW_REQUIRED.
    3. Else if ANY result is NOT_VISIBLE -> overall status is REVIEW_REQUIRED.
    4. Else if all results are PASS or NOT_APPLICABLE (with at least one evaluated) -> overall status is PASS.
    5. If no requirements evaluated -> overall status is REVIEW_REQUIRED.
    """
    if not results:
        return OverallInspectionStatus.REVIEW_REQUIRED, "No legal requirements were evaluated in this inspection."

    has_fail = any(r.status == VerificationStatus.FAIL for r in results)
    if has_fail:
        failed_ids = [r.requirement_id for r in results if r.status == VerificationStatus.FAIL]
        return OverallInspectionStatus.FAIL, f"Statutory compliance failure in requirement(s): {failed_ids}."

    has_review = any(r.status == VerificationStatus.REVIEW_REQUIRED for r in results)
    if has_review:
        review_ids = [r.requirement_id for r in results if r.status == VerificationStatus.REVIEW_REQUIRED]
        return OverallInspectionStatus.REVIEW_REQUIRED, f"Manual review required for requirement(s): {review_ids}."

    has_not_visible = any(r.status == VerificationStatus.NOT_VISIBLE for r in results)
    if has_not_visible:
        not_vis_ids = [r.requirement_id for r in results if r.status == VerificationStatus.NOT_VISIBLE]
        return OverallInspectionStatus.REVIEW_REQUIRED, f"Required declaration(s) not visible in evidence for requirement(s): {not_vis_ids}."

    pass_count = sum(1 for r in results if r.status == VerificationStatus.PASS)
    na_count = sum(1 for r in results if r.status == VerificationStatus.NOT_APPLICABLE)

    if pass_count > 0 or na_count > 0:
        return OverallInspectionStatus.PASS, f"All applicable requirements satisfied ({pass_count} passed, {na_count} not applicable)."

    return OverallInspectionStatus.REVIEW_REQUIRED, "Unable to establish conclusive compliance state."


@dataclasses.dataclass
class InspectionReport:
    """Authoritative, strongly typed final output of the end-to-end inspection pipeline."""
    inspection_id: str
    overall_status: OverallInspectionStatus
    verification_results: list[VerificationResult]
    summary: str
    evidence_count: int
    image_count: int
    applicable_requirement_count: int
    pass_count: int
    fail_count: int
    not_visible_count: int
    not_applicable_count: int
    review_required_count: int
    created_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))
    errors: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to clean serializable dictionary representation."""
        return {
            "inspection_id": self.inspection_id,
            "overall_status": self.overall_status.value,
            "summary": self.summary,
            "counts": {
                "image_count": self.image_count,
                "evidence_count": self.evidence_count,
                "applicable_requirement_count": self.applicable_requirement_count,
                "pass_count": self.pass_count,
                "fail_count": self.fail_count,
                "not_visible_count": self.not_visible_count,
                "not_applicable_count": self.not_applicable_count,
                "review_required_count": self.review_required_count,
            },
            "verification_results": [r.to_dict() for r in self.verification_results],
            "errors": self.errors,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

