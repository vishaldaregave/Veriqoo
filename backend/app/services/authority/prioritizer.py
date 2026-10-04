"""Deterministic inspection priority scoring and risk signal generator for Phase U9."""

from __future__ import annotations

from typing import Any, Sequence

from backend.app.services.authority.models import (
    AuthorityPriority,
    AuthorityPriorityItem,
    AuthorityRiskSignal,
    RiskSignalCode,
)
from backend.app.services.consumer_intelligence.models import (
    ConsumerScanIntelligence,
    IdentityConfidence,
    RiskSignal,
)
from backend.app.services.consumer_result.models import ConsumerComplianceResult
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.inspection_pipeline.report import InspectionReport


class InspectionPrioritizer:
    """Calculates deterministic authority priority score, priority enum, risk signals, and reasons."""

    @staticmethod
    def prioritize_inspection(
        inspection_id: str,
        report: InspectionReport | None,
        intelligence: ConsumerScanIntelligence | None = None,
        consumer_result: ConsumerComplianceResult | None = None,
        repeat_failure_count: int = 0,
        is_elevated_region: bool = False,
        location: dict[str, Any] | None = None,
        created_at: str = "",
    ) -> AuthorityPriorityItem:
        """Deterministically prioritize an inspection for authority enforcement review.

        Guarantees:
        - Deterministic, bounded integer score (0-100).
        - No non-deterministic AI calculations.
        - Explainable reasons for every priority assignment.
        - Does NOT alter canonical status or invent legal requirements.
        """
        if report is None:
            # Inspection without report / in progress
            return AuthorityPriorityItem(
                inspection_id=inspection_id,
                priority=AuthorityPriority.INFORMATIONAL,
                priority_score=0,
                reasons=["Inspection has not been completed or evaluated"],
                canonical_status="INCOMPLETE",
                risk_signal=RiskSignal.INSUFFICIENT_EVIDENCE.value,
                compliance_score=None,
                rating=None,
                failed_requirement_count=0,
                review_required_count=0,
                not_visible_count=0,
                risk_signals=[
                    AuthorityRiskSignal(
                        code=RiskSignalCode.INSUFFICIENT_EVIDENCE.value,
                        severity="INFO",
                        explanation="Inspection is incomplete with no canonical report",
                        source="PIPELINE",
                    )
                ],
                product_summary={},
                identity_confidence="UNKNOWN",
                location=location,
                created_at=created_at,
            )

        canonical_status = (
            report.overall_status.value
            if hasattr(report.overall_status, "value")
            else str(report.overall_status)
        )

        fail_count = report.fail_count
        review_count = report.review_required_count
        not_visible_count = report.not_visible_count
        comp_score = getattr(report, "compliance_score", None) or (report.metadata.get("compliance_score") if hasattr(report, "metadata") and isinstance(report.metadata, dict) else None)
        rating_raw = getattr(report, "rating", None) or (report.metadata.get("rating") if hasattr(report, "metadata") and isinstance(report.metadata, dict) else None)
        rating_str = rating_raw.value if hasattr(rating_raw, "value") else (str(rating_raw) if rating_raw else None)

        v_results = getattr(report, "verification_results", getattr(report, "results", []))

        # Risk signal from intelligence if available
        risk_sig_enum = intelligence.risk_signal if intelligence else (
            RiskSignal.HIGH_RISK_NON_COMPLIANCE if fail_count > 0
            else (RiskSignal.POTENTIAL_COMPLIANCE_ISSUE if review_count > 0 else RiskSignal.NO_MAJOR_ISSUES_DETECTED)
        )
        risk_sig_str = risk_sig_enum.value if hasattr(risk_sig_enum, "value") else str(risk_sig_enum)

        # Identity confidence
        identity_conf_enum = intelligence.identity_confidence if intelligence else IdentityConfidence.UNKNOWN
        identity_conf_str = identity_conf_enum.value if hasattr(identity_conf_enum, "value") else str(identity_conf_enum)

        # Build product summary dict
        product_summary: dict[str, Any] = {}
        if intelligence and intelligence.product_identity:
            pid = intelligence.product_identity
            if pid.brand and pid.brand.value:
                product_summary["brand"] = pid.brand.value
            if pid.generic_name and pid.generic_name.value:
                product_summary["generic_name"] = pid.generic_name.value
            if pid.commodity and pid.commodity.value:
                product_summary["commodity"] = pid.commodity.value
            mfg_f = getattr(pid, "manufacturer_name", None) or getattr(pid, "manufacturer", None)
            if mfg_f and mfg_f.value:
                product_summary["manufacturer"] = mfg_f.value
            if pid.barcode and pid.barcode.value:
                product_summary["barcode"] = pid.barcode.value

        # Calculate deterministic score
        score = 0
        reasons: list[str] = []
        risk_signals: list[AuthorityRiskSignal] = []

        # 1. Base status contribution
        if canonical_status == OverallInspectionStatus.FAIL.value or canonical_status == "FAIL":
            score += 50
            reasons.append("Canonical inspection status is FAIL")
        elif canonical_status == OverallInspectionStatus.REVIEW_REQUIRED.value or canonical_status == "REVIEW_REQUIRED":
            score += 25
            reasons.append("Canonical inspection status requires authority review")
        elif canonical_status == OverallInspectionStatus.PASS.value or canonical_status == "PASS":
            reasons.append("Canonical inspection status is PASS")

        # 2. Finding burden
        if fail_count > 0:
            burden_add = min(30, fail_count * 10)
            score += burden_add
            reasons.append(f"Inspection contains {fail_count} non-compliant (FAIL) requirement(s)")
            if fail_count >= 2:
                risk_signals.append(
                    AuthorityRiskSignal(
                        code=RiskSignalCode.HIGH_FAILURE_BURDEN.value,
                        severity="HIGH",
                        explanation=f"Elevated non-compliance burden: {fail_count} failed requirements",
                        source="U6_FINDINGS",
                        requirement_ids=[
                            r.requirement_id for r in v_results if getattr(r, "status", None) == "FAIL" or getattr(getattr(r, "status", None), "value", None) == "FAIL"
                        ],
                    )
                )

        if review_count > 0:
            review_add = min(15, review_count * 5)
            score += review_add
            reasons.append(f"Inspection contains {review_count} requirement(s) requiring manual review")

        # 3. U5 Consumer Risk Signal
        if risk_sig_str == RiskSignal.HIGH_RISK_NON_COMPLIANCE.value:
            score += 10
            risk_signals.append(
                AuthorityRiskSignal(
                    code=RiskSignalCode.HIGH_RISK_NON_COMPLIANCE.value,
                    severity="HIGH",
                    explanation="Canonical scan intelligence classified as high risk non-compliance",
                    source="U5_INTELLIGENCE",
                )
            )
        elif risk_sig_str == RiskSignal.POTENTIAL_COMPLIANCE_ISSUE.value:
            score += 5
            risk_signals.append(
                AuthorityRiskSignal(
                    code=RiskSignalCode.POTENTIAL_COMPLIANCE_ISSUE.value,
                    severity="MEDIUM",
                    explanation="Potential declaration non-compliance detected",
                    source="U5_INTELLIGENCE",
                )
            )

        # 4. Compliance score penalty
        if comp_score is not None:
            if comp_score < 50.0:
                score += 10
                reasons.append(f"Low compliance score: {comp_score:.1f}/100")
                risk_signals.append(
                    AuthorityRiskSignal(
                        code=RiskSignalCode.LOW_COMPLIANCE_SCORE.value,
                        severity="HIGH",
                        explanation=f"U1 Compliance Score is critically low ({comp_score:.1f}/100)",
                        source="U1_SCORE",
                    )
                )
            elif comp_score < 75.0:
                score += 5
                reasons.append(f"Moderate compliance score: {comp_score:.1f}/100")

        # 5. Repeat Failure Cluster Signal
        if repeat_failure_count > 0 and identity_conf_str in ("HIGH", "MEDIUM"):
            repeat_add = min(15, repeat_failure_count * 5)
            score += repeat_add
            reasons.append(
                f"Associated with {repeat_failure_count} prior non-compliant inspection(s) for this entity"
            )
            risk_signals.append(
                AuthorityRiskSignal(
                    code=RiskSignalCode.REPEATED_FAILURES.value,
                    severity="HIGH",
                    explanation=f"Repeated observed compliance issues ({repeat_failure_count} prior failure samples)",
                    source="REPEAT_ANALYSIS",
                )
            )

        # 6. Geographic Context
        if is_elevated_region:
            score += 5
            reasons.append("Located in a district/state with elevated observed non-compliance rate")
            risk_signals.append(
                AuthorityRiskSignal(
                    code=RiskSignalCode.GEOGRAPHIC_ISSUE_ELEVATED.value,
                    severity="LOW",
                    explanation="Regional observed failure rate is above national baseline",
                    source="U7_HEATMAP",
                )
            )

        # 7. Identity Confidence Signal
        if identity_conf_str == "HIGH":
            risk_signals.append(
                AuthorityRiskSignal(
                    code=RiskSignalCode.PRODUCT_IDENTITY_CONFIRMED.value,
                    severity="INFO",
                    explanation="Product and manufacturer identity verified with high confidence",
                    source="U5_INTELLIGENCE",
                )
            )
        elif identity_conf_str in ("LOW", "UNKNOWN"):
            risk_signals.append(
                AuthorityRiskSignal(
                    code=RiskSignalCode.PRODUCT_IDENTITY_UNCERTAIN.value,
                    severity="LOW",
                    explanation="Product or manufacturer identity is uncertain or unconfirmed",
                    source="U5_INTELLIGENCE",
                )
            )

        # 8. Not Visible / Insufficient Evidence
        if not_visible_count > 0 and fail_count == 0 and review_count == 0:
            risk_signals.append(
                AuthorityRiskSignal(
                    code=RiskSignalCode.INSUFFICIENT_EVIDENCE.value,
                    severity="INFO",
                    explanation=f"{not_visible_count} declaration(s) were not visible in captured images",
                    source="PIPELINE",
                )
            )

        # 9. No issues signal
        if fail_count == 0 and review_count == 0 and (canonical_status == "PASS" or canonical_status == OverallInspectionStatus.PASS.value):
            risk_signals.append(
                AuthorityRiskSignal(
                    code=RiskSignalCode.NO_MAJOR_ISSUES_DETECTED.value,
                    severity="INFO",
                    explanation="All applicable statutory declarations satisfied",
                    source="CANONICAL_REPORT",
                )
            )

        # Bound score between 0 and 100
        bounded_score = max(0, min(100, score))

        # Assign priority band
        if bounded_score >= 80:
            priority = AuthorityPriority.CRITICAL
        elif bounded_score >= 60:
            priority = AuthorityPriority.HIGH
        elif bounded_score >= 35:
            priority = AuthorityPriority.MEDIUM
        elif bounded_score >= 10:
            priority = AuthorityPriority.LOW
        else:
            priority = AuthorityPriority.INFORMATIONAL

        return AuthorityPriorityItem(
            inspection_id=inspection_id,
            priority=priority,
            priority_score=bounded_score,
            reasons=reasons,
            canonical_status=canonical_status,
            risk_signal=risk_sig_str,
            compliance_score=comp_score,
            rating=rating_str,
            failed_requirement_count=fail_count,
            review_required_count=review_count,
            not_visible_count=not_visible_count,
            risk_signals=risk_signals,
            product_summary=product_summary,
            identity_confidence=identity_conf_str,
            location=location,
            created_at=created_at,
        )
