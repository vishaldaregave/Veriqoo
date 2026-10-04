"""Consumer Scan Intelligence inference engine for Phase U5."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Sequence

from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.localization.service import (
    LocalizationService,
    SupportedLanguage,
    get_localization_service,
)
from backend.app.services.evidence.models import (
    EvidenceCandidate,
    EvidenceField,
    EvidenceStatus,
)
from backend.app.services.inspection.errors import (
    InspectionNotFoundError,
    InspectionStateError,
)
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.consumer_intelligence.models import (
    ConsumerAction,
    ConsumerComplianceSummary,
    ConsumerScanIntelligence,
    ExtractedProductField,
    FieldProvenance,
    IdentityConfidence,
    ProductIdentity,
    RiskSignal,
    ScanContext,
    ScanQuality,
    ScanQualityIssue,
)

logger = logging.getLogger(__name__)


class ConsumerIntelligenceService:
    """Infers structured product identity, scan quality, consumer risk, and actionable guidance from an inspection."""

    def __init__(
        self,
        store: InMemoryInspectionStore | None = None,
        localization: LocalizationService | None = None,
    ) -> None:
        self._store = store
        self._localization = localization or get_localization_service()

    def extract_product_identity(
        self,
        candidates: Sequence[EvidenceCandidate],
        user_selling_price: float | None = None,
    ) -> tuple[ProductIdentity, IdentityConfidence, list[str]]:
        """Extract structured product identity from evidence candidates without hallucination.

        Returns:
            tuple of (ProductIdentity, IdentityConfidence, missing_fields)
        """
        # Group valid candidates by standardized field
        field_candidates: dict[str, list[EvidenceCandidate]] = {}
        for c in candidates:
            field_name = c.field.value if isinstance(c.field, EvidenceField) else str(c.field)
            if field_name not in field_candidates:
                field_candidates[field_name] = []
            field_candidates[field_name].append(c)

        identity = ProductIdentity(user_entered_selling_price=user_selling_price)
        missing_fields: list[str] = []
        has_critical_conflicts = False

        def _process_field(field_key: str, is_commodity_or_generic: bool = False) -> ExtractedProductField | None:
            nonlocal has_critical_conflicts
            cand_list = field_candidates.get(field_key, [])
            if not cand_list:
                return None

            # Collect provenances
            provenances: list[FieldProvenance] = [
                FieldProvenance(
                    evidence_id=c.evidence_id,
                    observation_id=c.observation_id,
                    image_id=c.image_id,
                    confidence=c.confidence,
                )
                for c in cand_list
            ]

            # Detect distinct normalized values
            normalized_vals = list({c.normalized_text.strip() for c in cand_list if c.normalized_text.strip()})
            is_conflicting = len(normalized_vals) > 1
            if is_conflicting:
                has_critical_conflicts = True

            primary_cand = cand_list[0]
            val = primary_cand.parsed_value if primary_cand.parsed_value is not None else primary_cand.normalized_text
            unit = primary_cand.parsed_unit

            return ExtractedProductField(
                value=val,
                unit=unit,
                provenance=provenances,
                is_conflicting=is_conflicting,
                conflicting_values=normalized_vals if is_conflicting else [],
            )

        # 1. Commodity and Generic Name
        commodity_field = _process_field(EvidenceField.COMMODITY_NAME.value)
        if commodity_field:
            identity.commodity = commodity_field
            identity.generic_name = commodity_field
        else:
            missing_fields.append("commodity_name")

        # 2. Manufacturer / Packer / Importer
        mfg_name = _process_field(EvidenceField.MANUFACTURER_NAME.value)
        packer_name = _process_field(EvidenceField.PACKER_NAME.value)
        importer_name = _process_field(EvidenceField.IMPORTER_NAME.value)
        if mfg_name:
            identity.manufacturer_name = mfg_name
            identity.brand = mfg_name  # Derived brand candidate if distinct brand parser not present
        elif packer_name:
            identity.manufacturer_name = packer_name
            identity.brand = packer_name
        elif importer_name:
            identity.manufacturer_name = importer_name
            identity.brand = importer_name
        else:
            missing_fields.append("manufacturer_name")

        # 3. Manufacturer Address
        mfg_addr = _process_field(EvidenceField.MANUFACTURER_ADDRESS.value)
        packer_addr = _process_field(EvidenceField.PACKER_ADDRESS.value)
        importer_addr = _process_field(EvidenceField.IMPORTER_ADDRESS.value)
        if mfg_addr:
            identity.manufacturer_address = mfg_addr
        elif packer_addr:
            identity.manufacturer_address = packer_addr
        elif importer_addr:
            identity.manufacturer_address = importer_addr

        # 4. Net Quantity
        net_qty = _process_field(EvidenceField.NET_QUANTITY.value)
        if net_qty:
            identity.net_quantity = net_qty
        else:
            missing_fields.append("net_quantity")

        # 5. Maximum Retail Price (MRP)
        mrp_field = _process_field(EvidenceField.MRP.value)
        if mrp_field:
            identity.declared_mrp = mrp_field
        else:
            missing_fields.append("mrp")

        # 6. Batch / Lot Number
        batch_field = _process_field(EvidenceField.BATCH_NUMBER.value) or _process_field(EvidenceField.LOT_NUMBER.value)
        if batch_field:
            identity.batch_number = batch_field

        # 7. Dates
        mfg_date = _process_field(EvidenceField.MANUFACTURE_DATE.value) or _process_field(EvidenceField.PACKING_DATE.value)
        if mfg_date:
            identity.manufacturing_date = mfg_date

        # 8. Consumer Care
        cc_field = (
            _process_field(EvidenceField.CONSUMER_CARE.value)
            or _process_field(EvidenceField.CONSUMER_CARE_PHONE.value)
            or _process_field(EvidenceField.CONSUMER_CARE_EMAIL.value)
        )
        if cc_field:
            identity.consumer_care = cc_field

        # 9. Country of Origin
        coo_field = _process_field(EvidenceField.COUNTRY_OF_ORIGIN.value)
        if coo_field:
            identity.country_of_origin = coo_field

        # 10. Barcode (if present in custom candidates or metadata)
        barcode_cands = field_candidates.get("barcode", [])
        if barcode_cands:
            identity.barcode = _process_field("barcode")

        # -------------------------------------------------------------
        # Compute Deterministic Identity Confidence
        # -------------------------------------------------------------
        core_fields_present = sum(
            1 for f in (identity.commodity, identity.manufacturer_name, identity.net_quantity, identity.declared_mrp)
            if f is not None
        )

        all_confidences = [
            p.confidence for cand in candidates for p in [FieldProvenance(confidence=cand.confidence)]
            if cand.confidence is not None
        ]
        avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

        if has_critical_conflicts:
            confidence = IdentityConfidence.LOW if core_fields_present >= 2 else IdentityConfidence.UNKNOWN
        elif core_fields_present >= 3 and avg_conf >= 0.7:
            confidence = IdentityConfidence.HIGH
        elif core_fields_present >= 2 and avg_conf >= 0.5:
            confidence = IdentityConfidence.MEDIUM
        elif core_fields_present >= 1:
            confidence = IdentityConfidence.LOW
        else:
            confidence = IdentityConfidence.UNKNOWN

        return identity, confidence, missing_fields

    def evaluate_scan_quality(
        self,
        image_count: int,
        candidates: Sequence[EvidenceCandidate],
        identity_confidence: IdentityConfidence,
        has_conflicts: bool,
    ) -> ScanQuality:
        """Evaluate deterministic scan and image capture quality signals."""
        issues: list[str] = []

        if image_count < 1:
            issues.append(ScanQualityIssue.INSUFFICIENT_IMAGES.value)
        elif image_count == 1:
            issues.append(ScanQualityIssue.INCOMPLETE_PACKAGE_VIEW.value)

        # Average OCR confidence
        ocr_scores = [c.ocr_confidence for c in candidates if c.ocr_confidence is not None]
        avg_ocr = sum(ocr_scores) / len(ocr_scores) if ocr_scores else 1.0

        if ocr_scores and avg_ocr < 0.65:
            issues.append(ScanQualityIssue.LOW_OCR_CONFIDENCE.value)

        if has_conflicts:
            issues.append(ScanQualityIssue.CONFLICTING_OBSERVATIONS.value)

        if len(candidates) < 3:
            issues.append(ScanQualityIssue.INSUFFICIENT_REQUIRED_DECLARATIONS.value)

        if identity_confidence in (IdentityConfidence.LOW, IdentityConfidence.UNKNOWN):
            issues.append(ScanQualityIssue.PRODUCT_IDENTITY_UNCERTAIN.value)

        # Quality score composite
        base_score = 1.0
        if image_count < 2:
            base_score -= 0.2
        if avg_ocr < 0.7:
            base_score -= 0.3
        if has_conflicts:
            base_score -= 0.2
        if len(candidates) < 3:
            base_score -= 0.2
        quality_score = max(0.1, min(1.0, round(base_score, 2)))

        is_acceptable = quality_score >= 0.5 and ScanQualityIssue.INSUFFICIENT_IMAGES.value not in issues

        return ScanQuality(
            is_acceptable=is_acceptable,
            quality_score=quality_score,
            issues=issues,
            details={
                "image_count": image_count,
                "evidence_count": len(candidates),
                "average_ocr_confidence": round(avg_ocr, 4) if ocr_scores else None,
            },
        )

    def derive_risk_signal(
        self,
        report: InspectionReport,
        identity_confidence: IdentityConfidence,
    ) -> RiskSignal:
        """Deterministic policy deriving the consumer risk signal from canonical inspection results."""
        if report.fail_count > 0 or report.overall_status == OverallInspectionStatus.FAIL:
            return RiskSignal.HIGH_RISK_NON_COMPLIANCE
        elif report.review_required_count > 0:
            return RiskSignal.POTENTIAL_COMPLIANCE_ISSUE
        elif report.not_visible_count > 0:
            return RiskSignal.INSUFFICIENT_EVIDENCE
        elif report.overall_status == OverallInspectionStatus.REVIEW_REQUIRED:
            return RiskSignal.POTENTIAL_COMPLIANCE_ISSUE
        elif identity_confidence in (IdentityConfidence.LOW, IdentityConfidence.UNKNOWN):
            return RiskSignal.PRODUCT_IDENTITY_UNCERTAIN
        else:
            return RiskSignal.NO_MAJOR_ISSUES_DETECTED

    def derive_consumer_actions(
        self,
        report: InspectionReport,
        scan_quality: ScanQuality,
        product_identity: ProductIdentity,
    ) -> list[ConsumerAction]:
        """Deterministic mapping of verification findings and scan quality to consumer action suggestions."""
        actions: list[ConsumerAction] = []

        failed_req_ids = {r.requirement_id for r in report.verification_results if r.status.value in ("FAIL", "REVIEW_REQUIRED", "NOT_VISIBLE")}

        if report.fail_count > 0 or report.review_required_count > 0:
            actions.append(ConsumerAction.REVIEW_LABEL)

        if "R-6-1-e" in failed_req_ids or product_identity.declared_mrp is None:
            actions.append(ConsumerAction.CHECK_MRP)

        if "R-6-1-c" in failed_req_ids or product_identity.net_quantity is None:
            actions.append(ConsumerAction.CHECK_NET_QUANTITY)

        if "R-6-1-a" in failed_req_ids or product_identity.manufacturer_name is None:
            actions.append(ConsumerAction.CHECK_MANUFACTURER_DETAILS)

        if "R-6-1-f" in failed_req_ids or product_identity.consumer_care is None:
            actions.append(ConsumerAction.CHECK_CONSUMER_CARE_DETAILS)

        if ScanQualityIssue.INCOMPLETE_PACKAGE_VIEW.value in scan_quality.issues or report.not_visible_count > 0:
            actions.append(ConsumerAction.CAPTURE_BACK_PANEL)

        if product_identity.commodity is None:
            actions.append(ConsumerAction.CAPTURE_FRONT_PANEL)

        if ScanQualityIssue.LOW_OCR_CONFIDENCE.value in scan_quality.issues or ScanQualityIssue.CONFLICTING_OBSERVATIONS.value in scan_quality.issues:
            actions.append(ConsumerAction.RESCAN_PACKAGE)

        actions.append(ConsumerAction.REVIEW_REPORT)

        # Deduplicate preserving order
        deduped: list[ConsumerAction] = []
        for a in actions:
            if a not in deduped:
                deduped.append(a)
        return deduped

    def generate_intelligence(
        self,
        inspection_id: str,
        candidates: Sequence[EvidenceCandidate] | None = None,
        lang: str | None = None,
        user_selling_price: float | None = None,
    ) -> ConsumerScanIntelligence:
        """Generate structured consumer scan intelligence for a completed inspection."""
        if not self._store:
            raise InspectionNotFoundError(f"Inspection store not configured.")

        session = self._store.get_session(inspection_id)
        insp = session.inspection

        if insp.status == InspectionStatus.FAILED or insp.is_failed:
            raise InspectionStateError(
                f"Cannot generate consumer intelligence for failed inspection '{inspection_id}'.",
                details={"inspection_id": inspection_id, "status": insp.status.value},
            )

        if insp.status != InspectionStatus.COMPLETED or session.report is None:
            status_str = insp.status.value
            raise InspectionStateError(
                f"Cannot generate consumer intelligence for inspection in status '{status_str}'. Must be COMPLETED.",
                details={"inspection_id": inspection_id, "status": status_str},
            )

        report = session.report

        # Gather evidence candidates
        if candidates is not None:
            ev_candidates = list(candidates)
        else:
            ev_candidates = list(getattr(session, "evidence_candidates", []) or getattr(session, "evidence", []))

        # Extract product identity
        identity, id_conf, missing_info = self.extract_product_identity(
            candidates=ev_candidates,
            user_selling_price=user_selling_price,
        )

        has_conflicts = any(
            getattr(f, "is_conflicting", False)
            for f in (identity.commodity, identity.manufacturer_name, identity.net_quantity, identity.declared_mrp)
            if f is not None
        )

        # Evaluate scan quality
        scan_qual = self.evaluate_scan_quality(
            image_count=report.image_count,
            candidates=ev_candidates,
            identity_confidence=id_conf,
            has_conflicts=has_conflicts,
        )

        # Derive risk signal
        risk_sig = self.derive_risk_signal(report=report, identity_confidence=id_conf)

        # Derive consumer actions
        actions = self.derive_consumer_actions(
            report=report,
            scan_quality=scan_qual,
            product_identity=identity,
        )

        # Language resolution via U3
        target_lang = self._localization.resolve_language(
            explicit_lang=lang,
            inspection_meta=insp.metadata,
        )

        # Localized presentation labels
        risk_label = self._localization.get_string(
            section="consumer_risk_signals",
            key=risk_sig.value,
            lang=target_lang,
            default=risk_sig.value.replace("_", " ").title(),
        )

        action_labels = [
            self._localization.get_string(
                section="consumer_actions",
                key=a.value,
                lang=target_lang,
                default=a.value.replace("_", " ").title(),
            )
            for a in actions
        ]

        # Scan context
        scan_context_val = insp.metadata.get("scan_context") or insp.metadata.get("inspection_type") or ScanContext.CONSUMER.value
        scan_context_str = str(scan_context_val).upper()

        compliance_summary = ConsumerComplianceSummary(
            overall_status=report.overall_status.value,
            pass_count=report.pass_count,
            fail_count=report.fail_count,
            review_required_count=report.review_required_count,
            not_visible_count=report.not_visible_count,
            not_applicable_count=report.not_applicable_count,
            total_evaluated=report.applicable_requirement_count,
        )

        return ConsumerScanIntelligence(
            schema_version="1.0.0",
            inspection_id=inspection_id,
            scan_context=scan_context_str,
            product_identity=identity,
            identity_confidence=id_conf.value,
            scan_quality=scan_qual,
            compliance_summary=compliance_summary,
            risk_signal=risk_sig.value,
            risk_signal_label=risk_label,
            consumer_actions=[a.value for a in actions],
            consumer_action_labels=action_labels,
            missing_information=missing_info,
            generated_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                "language": target_lang.value,
                "has_report": True,
            },
        )


_GLOBAL_CONSUMER_INTELLIGENCE_SERVICE: ConsumerIntelligenceService | None = None


def get_consumer_intelligence_service(
    store: InMemoryInspectionStore | None = None,
    localization: LocalizationService | None = None,
) -> ConsumerIntelligenceService:
    """Provide singleton or configured ConsumerIntelligenceService."""
    global _GLOBAL_CONSUMER_INTELLIGENCE_SERVICE
    if _GLOBAL_CONSUMER_INTELLIGENCE_SERVICE is None:
        from backend.app.api.dependencies import get_session_store
        s = store or get_session_store()
        loc = localization or get_localization_service()
        _GLOBAL_CONSUMER_INTELLIGENCE_SERVICE = ConsumerIntelligenceService(store=s, localization=loc)
    return _GLOBAL_CONSUMER_INTELLIGENCE_SERVICE
