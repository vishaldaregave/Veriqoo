"""Context resolution engine for Phase U8 — Voice AI."""

from __future__ import annotations

from typing import Any

from backend.app.api.session_store import InMemoryInspectionStore, InspectionSession
from backend.app.localization.service import LocalizationService, SupportedLanguage, get_localization_service
from backend.app.services.consumer_intelligence.service import ConsumerIntelligenceService
from backend.app.services.consumer_result.service import ConsumerResultService
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.voice.errors import VoiceContextNotFoundError
from backend.app.services.voice.models import VoiceReasoningContext


class VoiceContextResolver:
    """Resolves authorized inspection context and packages canonical compliance outputs for voice reasoning."""

    def __init__(
        self,
        session_store: InMemoryInspectionStore | None = None,
        localization: LocalizationService | None = None,
        consumer_result_service: ConsumerResultService | None = None,
        consumer_intelligence_service: ConsumerIntelligenceService | None = None,
    ) -> None:
        self._store = session_store
        self._localization = localization or get_localization_service()
        self._intelligence_service = consumer_intelligence_service or ConsumerIntelligenceService(
            store=session_store, localization=self._localization
        )
        self._consumer_result_service = consumer_result_service or ConsumerResultService(
            session_store=session_store,
            localization_service=self._localization,
            intelligence_service=self._intelligence_service,
        )

    def resolve_context(
        self,
        inspection_id: str | None,
        user_id: str | None = None,
        user_role: str = "consumer",
        language: str = "en",
    ) -> VoiceReasoningContext:
        """Retrieve authorized inspection context or return unattached conversational context.

        Guarantees:
        - Cross-user inspection access raises VoiceContextNotFoundError (404-safe).
        - Consumes canonical U1/U5/U6 outputs without creating new compliance logic.
        """
        if not inspection_id or not inspection_id.strip():
            return VoiceReasoningContext(
                has_inspection=False,
                user_role=user_role,
            )

        clean_id = inspection_id.strip()

        if self._store is None:
            raise VoiceContextNotFoundError(
                f"Inspection session '{clean_id}' not found.",
                details={"inspection_id": clean_id},
            )

        try:
            session = self._store.get_session(clean_id)
        except Exception as err:
            raise VoiceContextNotFoundError(
                f"Inspection session '{clean_id}' not found.",
                details={"inspection_id": clean_id},
            ) from err

        insp = session.inspection
        report = session.report

        # Security check: Assert ownership
        if insp.owner_id and user_id and insp.owner_id != user_id:
            raise VoiceContextNotFoundError(
                f"Inspection session '{clean_id}' not found.",
                details={"inspection_id": clean_id},
            )

        # Incomplete / Failed inspections
        if insp.status != InspectionStatus.COMPLETED or report is None:
            return VoiceReasoningContext(
                has_inspection=True,
                inspection_id=clean_id,
                overall_status=insp.status.value,
                user_role=user_role,
                limitations=["INSPECTION_NOT_COMPLETED"],
            )

        lang_enum = SupportedLanguage.from_str(language)

        # Extract U6 consumer result
        consumer_res = self._consumer_result_service.generate_consumer_result(
            inspection_id=clean_id,
            lang=language,
        )

        # Extract U5 intelligence
        try:
            intel = self._intelligence_service.generate_intelligence(
                inspection_id=clean_id,
                lang=language,
            )
            prod_summary = {}
            if intel.product_identity.brand and intel.product_identity.brand.value:
                prod_summary["brand"] = str(intel.product_identity.brand.value)
            if intel.product_identity.generic_name and intel.product_identity.generic_name.value:
                prod_summary["generic_name"] = str(intel.product_identity.generic_name.value)
            if intel.product_identity.net_quantity and intel.product_identity.net_quantity.value:
                prod_summary["net_quantity"] = f"{intel.product_identity.net_quantity.value} {intel.product_identity.net_quantity.unit or ''}".strip()
            if intel.product_identity.declared_mrp and intel.product_identity.declared_mrp.value:
                prod_summary["declared_mrp"] = str(intel.product_identity.declared_mrp.value)
            if intel.product_identity.manufacturer_name and intel.product_identity.manufacturer_name.value:
                prod_summary["manufacturer"] = str(intel.product_identity.manufacturer_name.value)
        except Exception:
            prod_summary = {}

        findings: list[dict[str, Any]] = []
        legal_refs: list[str] = []

        for f in consumer_res.key_findings:
            findings.append({
                "requirement_id": f.requirement_id,
                "status": f.status,
                "title": f.consumer_title,
                "explanation": f.consumer_explanation,
                "severity": f.severity,
            })
            if f.legal_reference and f.legal_reference.rule_number:
                legal_refs.append(f"{f.legal_reference.rule_number} ({f.consumer_title})")

        return VoiceReasoningContext(
            has_inspection=True,
            inspection_id=clean_id,
            overall_status=consumer_res.canonical_status,
            compliance_score=consumer_res.score.score,
            rating=consumer_res.score.rating,
            risk_signal=consumer_res.risk_signal,
            product_summary=prod_summary,
            findings_summary=findings,
            consumer_actions=consumer_res.recommended_actions,
            limitations=consumer_res.limitations,
            user_role=user_role,
            legal_references=legal_refs,
        )
