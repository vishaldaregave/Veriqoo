"""Service engine for Phase U10 — Consumer -> Authority Action Bridge."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Sequence

from backend.app.api.session_store import InMemoryInspectionStore, InspectionSession
from backend.app.auth.models import AuthenticatedUser
from backend.app.localization.service import LocalizationService, get_localization_service
from backend.app.services.authority.prioritizer import InspectionPrioritizer
from backend.app.services.consumer_intelligence.service import ConsumerIntelligenceService
from backend.app.services.consumer_report.models import (
    AuthorityCaseInput,
    ConsumerReport,
    ConsumerReportEligibility,
    ConsumerReportStatus,
    ReportFindingPackage,
)
from backend.app.services.consumer_result.service import ConsumerResultService
from backend.app.services.inspection.errors import InspectionNotFoundError, InspectionStateError
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus

logger = logging.getLogger(__name__)


class ConsumerReportService:
    """Orchestrates evidence packaging, eligibility checking, and authority case snapshotting for consumer reports."""

    def __init__(
        self,
        store: InMemoryInspectionStore | None = None,
        repository: Any | None = None,
        localization: LocalizationService | None = None,
        consumer_intel_service: ConsumerIntelligenceService | None = None,
        consumer_result_service: ConsumerResultService | None = None,
    ) -> None:
        self._store = store
        self._repository = repository
        self._localization = localization or get_localization_service()
        self._consumer_intel = consumer_intel_service or ConsumerIntelligenceService(
            store=store, localization=self._localization
        )
        self._consumer_result = consumer_result_service or ConsumerResultService(
            session_store=store, localization_service=self._localization
        )

    def check_eligibility(
        self, session: InspectionSession | str
    ) -> tuple[bool, str, ConsumerReportEligibility]:
        """Determine whether an inspection session is eligible for authority reporting."""
        if isinstance(session, str):
            if not self._store:
                raise InspectionNotFoundError(
                    f"Inspection store not configured.",
                    details={"inspection_id": session},
                )
            sess = self._store.get_session(session)
        else:
            sess = session

        insp = sess.inspection
        if insp.is_failed or insp.status == InspectionStatus.FAILED:
            return (
                False,
                f"Cannot report failed inspection '{insp.inspection_id}'.",
                ConsumerReportEligibility.INELIGIBLE_FAILED,
            )

        if insp.status != InspectionStatus.COMPLETED or sess.report is None:
            return (
                False,
                f"Inspection must be COMPLETED with verified findings before reporting to authorities.",
                ConsumerReportEligibility.INELIGIBLE_INCOMPLETE,
            )

        report = sess.report
        canonical_status = (
            report.overall_status.value
            if hasattr(report.overall_status, "value")
            else str(report.overall_status)
        )

        # Ineligible if no applicable requirements evaluated or all not-applicable
        if report.applicable_requirement_count == 0 or (
            report.pass_count == 0
            and report.fail_count == 0
            and report.review_required_count == 0
            and report.not_applicable_count > 0
        ):
            return (
                False,
                "Inspection contains only exempt or not-applicable declarations with no reportable findings.",
                ConsumerReportEligibility.INELIGIBLE_NOT_APPLICABLE,
            )

        # Ineligible if purely PASS with no findings or issues
        if canonical_status == "PASS" and report.fail_count == 0 and report.review_required_count == 0:
            return (
                False,
                "Fully compliant inspections (PASS) cannot be submitted as authority violation reports.",
                ConsumerReportEligibility.INELIGIBLE_PASS,
            )

        return (
            True,
            "Inspection contains observed compliance issues and is eligible for authority reporting.",
            ConsumerReportEligibility.ELIGIBLE,
        )

    def create_consumer_report(
        self,
        inspection_id: str,
        user: AuthenticatedUser,
        consumer_description: str | None = None,
        lang: str | None = None,
    ) -> ConsumerReport:
        """Create and freeze an evidence-backed authority report from a completed inspection session.

        Guarantees:
        - Strict ownership verification (raises safe 404 for cross-user requests).
        - Idempotent: Returns existing report if already submitted for same user + inspection.
        - Preserves immutable snapshot of U2 annotations, U5 scan intelligence, U6 findings, and U9 priority.
        - User description is clearly categorized as user context and never mutates canonical facts.
        """
        if not self._store:
            raise InspectionNotFoundError(
                f"Inspection store not configured.",
                details={"inspection_id": inspection_id},
            )

        session = self._store.get_session(inspection_id)

        # Verify ownership: cross-user access MUST raise safe 404
        owner_id = getattr(session.inspection, "owner_id", None)
        if owner_id is not None and owner_id != user.user_id:
            raise InspectionNotFoundError(
                f"Inspection with ID '{inspection_id}' not found.",
                details={"inspection_id": inspection_id},
            )

        # Idempotency / duplicate check
        existing_report = None
        if self._repository:
            existing_report = self._repository.get_consumer_report_by_inspection(
                inspection_id=inspection_id,
                user_id=user.user_id,
            )
        if existing_report is None and self._store:
            existing_report = self._store.get_consumer_report_by_inspection(
                inspection_id=inspection_id,
                user_id=user.user_id,
            )
        if existing_report is not None:
            logger.info("Returning existing consumer report %s for inspection %s", existing_report.report_id, inspection_id)
            return existing_report

        # Eligibility check
        is_eligible, reason, eligibility_code = self.check_eligibility(session)
        if not is_eligible:
            raise InspectionStateError(
                reason,
                details={
                    "inspection_id": inspection_id,
                    "eligibility_code": eligibility_code.value,
                },
            )

        # Generate U5 scan intelligence
        intel = self._consumer_intel.generate_intelligence(
            inspection_id=inspection_id,
            candidates=session.evidence_candidates,
            lang=lang,
        )

        # Generate U6 consumer compliance result
        consumer_res = self._consumer_result.generate_consumer_result(
            inspection_id=inspection_id,
            lang=lang,
        )

        # Generate U9 priority & risk signals
        loc = None
        if session.inspection.metadata:
            loc_data = session.inspection.metadata.get("location")
            if isinstance(loc_data, dict):
                loc = {
                    "state_code": loc_data.get("state_code"),
                    "district_code": loc_data.get("district_code"),
                    "state_name": loc_data.get("state_name"),
                    "district_name": loc_data.get("district_name"),
                }

        priority_item = InspectionPrioritizer.prioritize_inspection(
            inspection_id=inspection_id,
            report=session.report,
            intelligence=intel,
            consumer_result=consumer_res,
            location=loc,
            created_at=session.created_at.isoformat() if session.created_at else "",
        )

        # Collect U2 evidence visual annotations from report
        stored_annotations: list[dict[str, Any]] = []
        if session.report and session.report.evidence_annotations:
            for ann in session.report.evidence_annotations:
                if hasattr(ann, "to_dict"):
                    stored_annotations.append(ann.to_dict())
                elif isinstance(ann, dict):
                    stored_annotations.append(dict(ann))

        # Build packaged findings for authority review (focus on issues)
        finding_packages: list[ReportFindingPackage] = []
        issue_findings = [f for f in consumer_res.key_findings if f.status in ("FAIL", "REVIEW_REQUIRED", "NOT_VISIBLE")]
        target_findings = issue_findings if issue_findings else consumer_res.key_findings

        for f in target_findings:
            # Match visual annotations
            matching_anns = [
                ann for ann in stored_annotations
                if ann.get("requirement_id") == f.requirement_id
                or ann.get("annotation_id") in f.annotation_ids
            ]

            # Statutory legal metadata fallback
            v_match = None
            if session.report and session.report.verification_results:
                for vr in session.report.verification_results:
                    if vr.requirement_id == f.requirement_id:
                        v_match = vr
                        break

            rule_num = (
                f.legal_reference.rule_number
                if (f.legal_reference and f.legal_reference.rule_number)
                else (v_match.metadata.get("rule_number") if v_match and v_match.metadata else None)
            )
            stat_label = (
                f.legal_reference.statutory_label
                if (f.legal_reference and f.legal_reference.statutory_label)
                else (v_match.metadata.get("statutory_label") if v_match and v_match.metadata else None)
            )
            sec_ref = (
                f.legal_reference.section_reference
                if (f.legal_reference and f.legal_reference.section_reference)
                else (v_match.metadata.get("section_reference") if v_match and v_match.metadata else None)
            )

            pkg = ReportFindingPackage(
                finding_id=f.finding_id,
                requirement_id=f.requirement_id,
                canonical_status=f.status,
                consumer_title=f.consumer_title,
                consumer_explanation=f.consumer_explanation,
                severity=f.severity,
                rule_number=rule_num,
                statutory_label=stat_label,
                section_reference=sec_ref,
                evidence_ids=list(f.evidence_ids),
                observation_ids=list(f.evidence_ids),
                annotation_ids=list(f.annotation_ids),
                image_ids=[img.image_id for img in session.inspection.images],
                annotations=matching_anns,
            )
            finding_packages.append(pkg)

        # Build clean product summary
        product_summary: dict[str, Any] = {}
        if intel.product_identity:
            pid = intel.product_identity
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
            if pid.declared_mrp and pid.declared_mrp.value:
                product_summary["declared_mrp"] = pid.declared_mrp.value
            if pid.net_quantity and pid.net_quantity.value:
                product_summary["net_quantity"] = pid.net_quantity.value

        if session.inspection.metadata:
            if "brand" in session.inspection.metadata and session.inspection.metadata["brand"]:
                product_summary["brand"] = session.inspection.metadata["brand"]
            elif "product_name" in session.inspection.metadata and session.inspection.metadata["product_name"]:
                product_summary["brand"] = session.inspection.metadata["product_name"]

        # Construct immutable ConsumerReport snapshot
        report = ConsumerReport(
            inspection_id=inspection_id,
            submitted_by=user.user_id,
            status=ConsumerReportStatus.SUBMITTED,
            canonical_overall_status=consumer_res.canonical_status,
            consumer_overall_result=consumer_res.overall_result,
            consumer_description=consumer_description.strip() if consumer_description else None,
            product_summary=product_summary,
            identity_confidence=intel.identity_confidence,
            scan_quality=intel.scan_quality.to_dict() if intel.scan_quality else {},
            findings=finding_packages,
            priority_score=priority_item.priority_score,
            priority_band=priority_item.priority.value if hasattr(priority_item.priority, "value") else str(priority_item.priority),
            priority_reasons=priority_item.reasons,
            risk_signals=[s.to_dict() for s in priority_item.risk_signals],
            location=loc,
            inspection_created_at=session.created_at.isoformat() if session.created_at else "",
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                "compliance_score": consumer_res.score.score,
                "rating": consumer_res.score.rating,
                "language": lang or "en",
                "audit_event": "CONSUMER_REPORT_CREATED",
            },
        )

        if self._repository:
            self._repository.save_consumer_report(report)
        if self._store:
            self._store.save_consumer_report(report)

        logger.info("Successfully created consumer report %s for inspection %s by user %s", report.report_id, inspection_id, user.user_id)
        return report

    def get_consumer_report(
        self, report_id: str, user: AuthenticatedUser | None = None
    ) -> ConsumerReport:
        """Retrieve a specific consumer report with optional authorization check."""
        report = None
        if self._repository:
            report = self._repository.get_consumer_report(report_id)
        if report is None and self._store:
            report = self._store.get_consumer_report(report_id)

        if report is None:
            raise InspectionNotFoundError(
                f"Consumer report with ID '{report_id}' not found.",
                details={"report_id": report_id},
            )

        # Authorization check when caller is provided
        if user is not None:
            is_authority = user.role in ("authority", "admin", "inspector", "officer") or user.claims.get("role") in ("authority", "admin", "inspector", "officer")
            if report.submitted_by != user.user_id and not is_authority:
                raise InspectionNotFoundError(
                    f"Consumer report with ID '{report_id}' not found.",
                    details={"report_id": report_id},
                )

        return report

    def list_user_consumer_reports(
        self, user: AuthenticatedUser
    ) -> list[ConsumerReport]:
        """List all consumer reports submitted by the caller."""
        if self._repository:
            return self._repository.list_consumer_reports_for_user(user.user_id)
        if self._store:
            return self._store.list_consumer_reports_for_user(user.user_id)
        return []

    def list_all_consumer_reports(self) -> list[ConsumerReport]:
        """List all consumer reports across all users (authority use only)."""
        if self._repository:
            return self._repository.list_all_consumer_reports()
        if self._store:
            return self._store.list_all_consumer_reports()
        return []

    def to_authority_case_input(
        self, report: ConsumerReport
    ) -> AuthorityCaseInput:
        """Convert a frozen ConsumerReport into a typed AuthorityCaseInput for T3 case management."""
        findings_data = [f.to_dict() for f in report.findings]
        ps = report.product_summary

        return AuthorityCaseInput(
            source_report_id=report.report_id,
            inspection_id=report.inspection_id,
            consumer_user_id=report.submitted_by,
            case_type="CONSUMER_GRIEVANCE",
            priority=report.priority_band,
            priority_score=report.priority_score,
            canonical_status=report.canonical_overall_status,
            product_identity=ps,
            manufacturer_name=ps.get("manufacturer"),
            commodity=ps.get("commodity") or ps.get("generic_name"),
            brand=ps.get("brand"),
            barcode=ps.get("barcode"),
            findings_count=len(report.findings),
            findings=findings_data,
            consumer_notes=report.consumer_description,
            location=report.location,
            risk_signals=report.risk_signals,
            submitted_at=report.created_at,
        )
