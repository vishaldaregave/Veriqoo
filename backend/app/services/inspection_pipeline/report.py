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
    evidence_annotations: list[Any] = dataclasses.field(default_factory=list)
    created_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))
    errors: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)

    def to_dict(self, lang: str | None = None) -> dict[str, Any]:
        """Convert report to clean serializable dictionary representation with optional presentation localization."""
        from backend.app.localization.service import SupportedLanguage, get_localization_service
        loc = get_localization_service()
        lang_enum = SupportedLanguage.from_str(lang) if lang else SupportedLanguage.EN

        failed_ids = [r.requirement_id for r in self.verification_results if r.status == VerificationStatus.FAIL]
        review_ids = [r.requirement_id for r in self.verification_results if r.status == VerificationStatus.REVIEW_REQUIRED]
        not_vis_ids = [r.requirement_id for r in self.verification_results if r.status == VerificationStatus.NOT_VISIBLE]

        # Localized summary statement
        localized_summary = loc.localize_report_summary(
            overall_status=self.overall_status.value,
            failed_ids=failed_ids,
            review_ids=review_ids,
            not_vis_ids=not_vis_ids,
            pass_count=self.pass_count,
            na_count=self.not_applicable_count,
            lang=lang_enum,
        ) if lang_enum != SupportedLanguage.EN else self.summary

        # Localize annotations presentation fields
        localized_annotations = []
        for a in self.evidence_annotations:
            ann_dict = a.to_dict() if hasattr(a, "to_dict") else dict(a)
            if lang_enum != SupportedLanguage.EN:
                ann_dict["label"] = loc.get_statutory_label(ann_dict.get("requirement_id", ""), lang=lang_enum)
                ann_dict["reason"] = loc.localize_verification_reason(
                    canonical_reason=ann_dict.get("reason", ""),
                    status=ann_dict.get("status", ""),
                    requirement_id=ann_dict.get("requirement_id", ""),
                    lang=lang_enum,
                )
            localized_annotations.append(ann_dict)

        # Localize verification results presentation fields
        localized_v_results = []
        for r in self.verification_results:
            r_dict = r.to_dict()
            if lang_enum != SupportedLanguage.EN:
                r_dict["reason"] = loc.localize_verification_reason(
                    canonical_reason=r.reason,
                    status=r.status.value if hasattr(r.status, "value") else str(r.status),
                    requirement_id=r.requirement_id,
                    lang=lang_enum,
                )
            localized_v_results.append(r_dict)

        return {
            "inspection_id": self.inspection_id,
            "overall_status": self.overall_status.value,
            "language": lang_enum.value,
            "summary": localized_summary,
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
            "evidence_annotations": localized_annotations,
            "verification_results": localized_v_results,
            "errors": self.errors,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

