"""Service implementation for Phase U6 — Consumer Compliance Result & Explanation."""

from __future__ import annotations

from typing import Any, Sequence

from backend.app.localization.service import (
    LocalizationService,
    Persona,
    SupportedLanguage,
    get_localization_service,
)
from backend.app.services.consumer_intelligence.models import (
    ConsumerScanIntelligence,
    RiskSignal,
)
from backend.app.services.consumer_intelligence.service import (
    ConsumerIntelligenceService,
    get_consumer_intelligence_service,
)
from backend.app.services.consumer_result.models import (
    ConsumerComplianceResult,
    ConsumerFinding,
    ConsumerOverallResult,
    ConsumerReportReference,
    ConsumerScore,
    FindingSeverity,
    LegalReference,
)
from backend.app.services.inspection.errors import (
    InspectionNotFoundError,
    InspectionStateError,
)
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.verification.models import (
    VerificationResult,
    VerificationStatus,
)

# Canonical rule identifier mapping for Legal Metrology (Packaged Commodities) Rules, 2011
RULE_MAPPINGS: dict[str, dict[str, str]] = {
    "R-6-1-a": {
        "rule_number": "Rule 6(1)(a)",
        "statutory_label": "Manufacturer / Packer / Importer Identity & Address",
        "section_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
    },
    "R-6-1-b": {
        "rule_number": "Rule 6(1)(b)",
        "statutory_label": "Generic Name of Commodity",
        "section_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
    },
    "R-6-1-c": {
        "rule_number": "Rule 6(1)(c)",
        "statutory_label": "Net Quantity Declaration",
        "section_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
    },
    "R-6-1-d": {
        "rule_number": "Rule 6(1)(d)",
        "statutory_label": "Date of Manufacture / Packing / Import",
        "section_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
    },
    "R-6-1-e": {
        "rule_number": "Rule 6(1)(e)",
        "statutory_label": "Maximum Retail Price (MRP)",
        "section_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
    },
    "R-6-1-f": {
        "rule_number": "Rule 6(1)(f)",
        "statutory_label": "Consumer Care Contact Details",
        "section_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
    },
    "R-6-1-g": {
        "rule_number": "Rule 6(1)(g)",
        "statutory_label": "Country of Origin",
        "section_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
    },
    "R-6-1-h": {
        "rule_number": "Rule 6(1)(h)",
        "statutory_label": "Unit Sale Price (USP)",
        "section_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
    },
}


class ConsumerResultService:
    """Generates structured consumer-facing compliance explanations and results."""

    def __init__(
        self,
        session_store: Any | None = None,
        localization_service: LocalizationService | None = None,
        intelligence_service: ConsumerIntelligenceService | None = None,
    ) -> None:
        self._store = session_store
        self._localization = localization_service or get_localization_service()
        self._intelligence = intelligence_service or get_consumer_intelligence_service(
            store=session_store, localization=self._localization
        )

    def map_overall_result(self, report: InspectionReport) -> ConsumerOverallResult:
        """Map canonical inspection status to a consumer-safe overall result category."""
        if report.overall_status == OverallInspectionStatus.FAIL or report.fail_count > 0:
            return ConsumerOverallResult.COMPLIANCE_ISSUE_DETECTED
        elif report.review_required_count > 0:
            return ConsumerOverallResult.REVIEW_RECOMMENDED
        elif report.not_visible_count > 0:
            return ConsumerOverallResult.INSUFFICIENT_EVIDENCE
        elif report.overall_status == OverallInspectionStatus.REVIEW_REQUIRED:
            return ConsumerOverallResult.REVIEW_RECOMMENDED
        elif report.overall_status == OverallInspectionStatus.PASS:
            return ConsumerOverallResult.NO_MAJOR_ISSUES_DETECTED
        else:
            return ConsumerOverallResult.REVIEW_RECOMMENDED

    def compute_consumer_score(
        self,
        report: InspectionReport,
        lang: SupportedLanguage,
    ) -> ConsumerScore:
        """Derive consumer compliance score and rating from canonical report counters."""
        total_eval = report.applicable_requirement_count
        if total_eval == 0 and (report.pass_count + report.fail_count + report.review_required_count + report.not_visible_count) == 0:
            rating_label = self._localization.get_rating_label("NOT_APPLICABLE", lang=lang)
            return ConsumerScore(
                score=None,
                percentage=None,
                rating="NOT_APPLICABLE",
                rating_label=rating_label,
                evaluated_requirements=0,
                pass_count=report.pass_count,
                fail_count=report.fail_count,
                review_count=report.review_required_count,
                not_visible_count=report.not_visible_count,
                not_applicable_count=report.not_applicable_count,
            )

        denom = total_eval if total_eval > 0 else (report.pass_count + report.fail_count + report.review_required_count + report.not_visible_count)
        calc_score = round((report.pass_count / denom) * 100.0, 1) if denom > 0 else 0.0

        if report.fail_count > 0:
            rating = "NON_COMPLIANT"
        elif calc_score == 100.0:
            rating = "FULLY_COMPLIANT"
        elif calc_score >= 80.0:
            rating = "SUBSTANTIALLY_COMPLIANT"
        elif calc_score >= 50.0:
            rating = "PARTIALLY_COMPLIANT"
        else:
            rating = "NON_COMPLIANT"

        rating_label = self._localization.get_rating_label(rating, lang=lang)

        return ConsumerScore(
            score=calc_score,
            percentage=f"{calc_score}%" if calc_score is not None else None,
            rating=rating,
            rating_label=rating_label,
            evaluated_requirements=denom,
            pass_count=report.pass_count,
            fail_count=report.fail_count,
            review_count=report.review_required_count,
            not_visible_count=report.not_visible_count,
            not_applicable_count=report.not_applicable_count,
        )

    def extract_legal_reference(self, requirement_id: str) -> LegalReference | None:
        """Extract canonical statutory reference details without guessing unknown rules."""
        if not requirement_id or not requirement_id.strip():
            return None

        clean_id = requirement_id.strip()
        if clean_id in RULE_MAPPINGS:
            data = RULE_MAPPINGS[clean_id]
            return LegalReference(
                requirement_id=clean_id,
                rule_number=data["rule_number"],
                statutory_label=data["statutory_label"],
                section_reference=data["section_reference"],
            )

        # If standard prefix matches Rule 6
        if clean_id.startswith("R-6-1-"):
            suffix = clean_id.split("-")[-1]
            return LegalReference(
                requirement_id=clean_id,
                rule_number=f"Rule 6(1)({suffix})",
                statutory_label=None,
                section_reference="Legal Metrology (Packaged Commodities) Rules, 2011",
            )

        return None

    def generate_findings(
        self,
        report: InspectionReport,
        lang: SupportedLanguage,
    ) -> list[ConsumerFinding]:
        """Convert canonical verification results into consumer findings with provenance."""
        findings: list[ConsumerFinding] = []

        # Index annotations by requirement_id
        ann_by_req: dict[str, list[str]] = {}
        for ann in report.evidence_annotations:
            req_id = getattr(ann, "requirement_id", None) or (ann.get("requirement_id") if isinstance(ann, dict) else None)
            ann_id = getattr(ann, "annotation_id", None) or (ann.get("annotation_id") if isinstance(ann, dict) else None)
            if req_id and ann_id:
                if req_id not in ann_by_req:
                    ann_by_req[req_id] = []
                ann_by_req[req_id].append(str(ann_id))

        for idx, v in enumerate(report.verification_results, start=1):
            req_id = v.requirement_id
            status_str = v.status.value if hasattr(v.status, "value") else str(v.status)

            # Statutory title
            title = self._localization.get_statutory_label(req_id, lang=lang)
            if not title or title == req_id:
                title = req_id

            legal_ref = self.extract_legal_reference(req_id)
            matching_ann_ids = ann_by_req.get(req_id, [])

            # Severity and consumer explanation
            if status_str == VerificationStatus.FAIL.value:
                severity = FindingSeverity.HIGH.value
                sev_label = self._localization.get_string("consumer_severities", "HIGH", lang=lang, default="Issue")
                canonical_reason = self._localization.localize_verification_reason(
                    canonical_reason=v.reason,
                    status=status_str,
                    requirement_id=req_id,
                    lang=lang,
                )
                explanation = canonical_reason or f"Non-compliance detected in {title}."
                corrective = self._localization.get_string("consumer_actions", "REVIEW_LABEL", lang=lang, default="Review package declaration.")
            elif status_str == VerificationStatus.REVIEW_REQUIRED.value:
                severity = FindingSeverity.MEDIUM.value
                sev_label = self._localization.get_string("consumer_severities", "MEDIUM", lang=lang, default="Review Needed")
                explanation = self._localization.get_string(
                    "consumer_finding_templates",
                    "review_required",
                    lang=lang,
                    params={"title": title},
                    default=f"Declaration for {title} could not be confidently verified from the images.",
                )
                corrective = self._localization.get_string("consumer_actions", "CAPTURE_BACK_PANEL", lang=lang, default="Capture a clearer image of this declaration.")
            elif status_str == VerificationStatus.NOT_VISIBLE.value:
                severity = FindingSeverity.LOW.value
                sev_label = self._localization.get_string("consumer_severities", "LOW", lang=lang, default="Not Visible")
                explanation = self._localization.get_string(
                    "consumer_finding_templates",
                    "not_visible",
                    lang=lang,
                    params={"title": title},
                    default=f"Declaration for {title} was not visible on the captured package panels.",
                )
                corrective = self._localization.get_string("consumer_actions", "CAPTURE_BACK_PANEL", lang=lang, default="Capture the package panel displaying this declaration.")
            elif status_str == VerificationStatus.PASS.value:
                severity = FindingSeverity.INFO.value
                sev_label = self._localization.get_string("consumer_severities", "INFO", lang=lang, default="Verified")
                explanation = self._localization.get_string(
                    "consumer_finding_templates",
                    "pass",
                    lang=lang,
                    params={"title": title},
                    default="Verified from the submitted package images.",
                )
                corrective = None
            else:
                severity = FindingSeverity.INFO.value
                sev_label = self._localization.get_string("consumer_severities", "INFO", lang=lang, default="Info")
                explanation = v.reason or "Requirement evaluated."
                corrective = None

            finding = ConsumerFinding(
                finding_id=f"find_{req_id}",
                requirement_id=req_id,
                status=status_str,
                consumer_title=title,
                consumer_explanation=explanation,
                evidence_ids=list(v.evidence_ids),
                annotation_ids=matching_ann_ids,
                legal_reference=legal_ref,
                corrective_action=corrective,
                severity=severity,
                severity_label=sev_label,
            )
            findings.append(finding)

        return findings

    def generate_limitations(
        self,
        report: InspectionReport,
        intelligence: ConsumerScanIntelligence,
        lang: SupportedLanguage,
    ) -> tuple[list[str], list[str]]:
        """Generate deterministic scan limitations and localized descriptions."""
        limitation_keys: list[str] = []

        # Standard legal verification disclaimer
        limitation_keys.append("VERIFICATION_LIMITED_TO_CAPTURED_IMAGES")

        if report.not_visible_count > 0:
            limitation_keys.append("SOME_DECLARATIONS_NOT_VISIBLE")

        if getattr(intelligence, "identity_confidence", "") in ("LOW", "UNKNOWN"):
            limitation_keys.append("PRODUCT_IDENTITY_UNCERTAIN")

        if report.not_applicable_count > 0:
            limitation_keys.append("NON_APPLICABLE_EXCLUDED")

        scan_issues = getattr(intelligence.scan_quality, "issues", [])
        if "INCOMPLETE_PACKAGE_VIEW" in scan_issues:
            limitation_keys.append("INCOMPLETE_PACKAGE_VIEW")
        if "LOW_OCR_CONFIDENCE" in scan_issues:
            limitation_keys.append("LOW_OCR_CONFIDENCE")

        # Deduplicate
        unique_keys: list[str] = []
        for k in limitation_keys:
            if k not in unique_keys:
                unique_keys.append(k)

        labels: list[str] = [
            self._localization.get_string(
                section="consumer_limitations",
                key=k,
                lang=lang,
                default=k.replace("_", " ").title(),
            )
            for k in unique_keys
        ]

        return unique_keys, labels

    def generate_consumer_result(
        self,
        inspection_id: str,
        lang: str | None = None,
        intelligence: ConsumerScanIntelligence | None = None,
    ) -> ConsumerComplianceResult:
        """Generate structured consumer compliance result and explanation."""
        if not self._store:
            raise InspectionNotFoundError(f"Inspection store not configured.")

        session = self._store.get_session(inspection_id)
        insp = session.inspection

        if insp.status == InspectionStatus.FAILED or insp.is_failed:
            raise InspectionStateError(
                f"Cannot generate consumer result for failed inspection '{inspection_id}'.",
                details={"inspection_id": inspection_id, "status": insp.status.value},
            )

        if insp.status != InspectionStatus.COMPLETED or session.report is None:
            status_str = insp.status.value
            raise InspectionStateError(
                f"Cannot generate consumer result for inspection in status '{status_str}'. Must be COMPLETED.",
                details={"inspection_id": inspection_id, "status": status_str},
            )

        report = session.report

        # Resolve target language via U3
        target_lang = self._localization.resolve_language(
            explicit_lang=lang,
            inspection_meta=insp.metadata,
        )

        # Obtain U5 scan intelligence
        if intelligence is None:
            intelligence = self._intelligence.generate_intelligence(
                inspection_id=inspection_id,
                lang=target_lang.value,
            )

        # 1. Overall Result Mapping
        overall_res = self.map_overall_result(report)
        result_label = self._localization.get_string(
            section="consumer_results",
            key=overall_res.value,
            lang=target_lang,
            default=overall_res.value.replace("_", " ").title(),
        )

        # 2. Summary
        summary = self._localization.get_string(
            section="consumer_summaries",
            key=overall_res.value,
            lang=target_lang,
            default="Compliance verification completed for this package.",
        )

        # 3. What This Means (Persona-tailored)
        what_this_means = self._localization.get_string(
            section="consumer_what_this_means",
            key=overall_res.value,
            lang=target_lang,
            default="This result is based on the package declarations verified from your submitted images.",
        )

        # 4. Compliance Score
        score = self.compute_consumer_score(report, lang=target_lang)

        # 5. Risk Signal from U5
        risk_sig_val = getattr(intelligence, "risk_signal", RiskSignal.NO_MAJOR_ISSUES_DETECTED.value)
        risk_sig_label = self._localization.get_string(
            section="consumer_risk_signals",
            key=risk_sig_val,
            lang=target_lang,
            default=risk_sig_val.replace("_", " ").title(),
        )

        # 6. Key Findings
        findings = self.generate_findings(report, lang=target_lang)

        # 7. Recommended Actions
        actions = list(getattr(intelligence, "consumer_actions", []))
        if not actions:
            actions = ["REVIEW_REPORT"]
        action_labels = [
            self._localization.get_string(
                section="consumer_actions",
                key=a,
                lang=target_lang,
                default=a.replace("_", " ").title(),
            )
            for a in actions
        ]

        # 8. Limitations
        lim_keys, lim_labels = self.generate_limitations(report, intelligence, lang=target_lang)

        # 9. Safe Report Reference
        report_ref = ConsumerReportReference(
            inspection_id=inspection_id,
            image_count=report.image_count,
            evidence_count=report.evidence_count,
            applicable_requirement_count=report.applicable_requirement_count,
            has_report=True,
            created_at=report.created_at.isoformat(),
        )

        return ConsumerComplianceResult(
            schema_version="1.0.0",
            inspection_id=inspection_id,
            overall_result=overall_res.value,
            canonical_status=report.overall_status.value,
            result_label=result_label,
            summary=summary,
            what_this_means=what_this_means,
            score=score,
            risk_signal=risk_sig_val,
            risk_signal_label=risk_sig_label,
            key_findings=findings,
            recommended_actions=actions,
            recommended_action_labels=action_labels,
            limitations=lim_keys,
            limitation_labels=lim_labels,
            report_reference=report_ref,
            metadata=dict(report.metadata),
        )


def get_consumer_result_service(
    store: Any | None = None,
    localization: LocalizationService | None = None,
    intelligence: ConsumerIntelligenceService | None = None,
) -> ConsumerResultService:
    """Factory helper for ConsumerResultService."""
    return ConsumerResultService(
        session_store=store,
        localization_service=localization,
        intelligence_service=intelligence,
    )
