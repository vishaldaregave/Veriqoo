"""Comprehensive test suite for Veriqoo Backend Phase U5 — Consumer Scan Intelligence.

Tests verify:
1. Consumer inspection context.
2. Inspector context remains unchanged.
3. Completed inspection generates intelligence.
4. Running inspection rejected.
5. Failed inspection rejected.
6. Missing report rejected.
7. Product identity extracted from evidence.
8. No hallucinated product fields.
9. Evidence provenance preserved.
10. Barcode provenance preserved.
11. Conflicting observations detected.
12. Identity confidence HIGH.
13. Identity confidence MEDIUM.
14. Identity confidence LOW.
15. Identity confidence UNKNOWN.
16. Low OCR quality does not become FAIL.
17. Scan quality signals deterministic.
18. Any FAIL produces high-risk signal.
19. REVIEW_REQUIRED produces appropriate risk signal.
20. NOT_VISIBLE produces insufficient-evidence signal.
21. Uncertain identity produces identity-uncertain signal.
22. Clean PASS produces no-major-issues signal.
23. U1 score reused rather than recalculated.
24. PASS/FAIL/REVIEW_REQUIRED enums unchanged.
25. MRP remains distinct from selling price.
26. Missing selling price not inferred.
27. Duplicate image evidence does not duplicate product identity.
28. Conflicting values are not silently resolved.
29. Consumer actions are deterministic.
30. No unsupported legal claim invented.
31. U3 English localization.
32. U3 Hindi localization.
33. U3 Marathi localization.
34. Canonical machine codes invariant across languages.
35. No JWT exposure.
36. No Telegram identity exposure.
37. No storage path exposure.
38. Endpoint requires authentication.
39. Cross-user access rejected.
40. Endpoint does not invoke OCR.
41. Endpoint does not invoke Gemini.
42. Endpoint does not invoke legal RAG.
43. Endpoint does not execute inspection pipeline.
44. U2 annotations remain unchanged.
45. U4 share behavior remains unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    get_consumer_intelligence_service,
    get_current_user,
    get_session_store,
)
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth import AuthenticatedUser
from backend.app.config import get_settings
from backend.app.main import app
from backend.app.services.consumer_intelligence import (
    ConsumerAction,
    ConsumerIntelligenceService,
    IdentityConfidence,
    RiskSignal,
    ScanContext,
    ScanQualityIssue,
    get_consumer_intelligence_service,
)
from backend.app.services.evidence.models import (
    EvidenceCandidate,
    EvidenceField,
    EvidenceStatus,
    ImageArtifact,
)
from backend.app.services.inspection.models import Inspection, InspectionStatus
from backend.app.services.inspection_pipeline.annotations import (
    EvidenceAnnotation,
    NormalizedBox,
)
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.verification.models import VerificationResult, VerificationStatus


class TestPhase14ConsumerScanIntelligence(unittest.TestCase):
    """Unit and integration tests for Phase U5 Consumer Scan Intelligence."""

    def setUp(self) -> None:
        self.store = InMemoryInspectionStore()
        self.service = ConsumerIntelligenceService(store=self.store)

        app.dependency_overrides[get_session_store] = lambda: self.store
        app.dependency_overrides[get_consumer_intelligence_service] = lambda: self.service

        self.client = TestClient(app)
        self.owner_user = AuthenticatedUser(
            user_id="consumer-user-1234",
            email="consumer@veriqoo.ai",
            role="authenticated",
        )
        self.other_user = AuthenticatedUser(
            user_id="other-user-5678",
            email="other@veriqoo.ai",
            role="authenticated",
        )

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.store.clear()

    def _create_sample_candidates(self) -> list[EvidenceCandidate]:
        """Helper to create realistic evidence candidates for testing."""
        c1 = EvidenceCandidate(
            evidence_id="ev_001",
            observation_id="obs_001",
            image_id="img_001",
            field=EvidenceField.COMMODITY_NAME,
            raw_text="Pure Ceylon Green Tea",
            normalized_text="Green Tea",
            parsed_value="Green Tea",
            ocr_confidence=0.98,
            confidence=0.98,
        )
        c2 = EvidenceCandidate(
            evidence_id="ev_002",
            observation_id="obs_002",
            image_id="img_001",
            field=EvidenceField.MANUFACTURER_NAME,
            raw_text="Mfd by: Ceylon Tea Co Ltd, Colombo",
            normalized_text="Ceylon Tea Co Ltd",
            parsed_value="Ceylon Tea Co Ltd",
            ocr_confidence=0.95,
            confidence=0.95,
        )
        c3 = EvidenceCandidate(
            evidence_id="ev_003",
            observation_id="obs_003",
            image_id="img_002",
            field=EvidenceField.NET_QUANTITY,
            raw_text="Net Wt: 250 g",
            normalized_text="250 g",
            parsed_value=250.0,
            parsed_unit="g",
            ocr_confidence=0.92,
            confidence=0.92,
        )
        c4 = EvidenceCandidate(
            evidence_id="ev_004",
            observation_id="obs_004",
            image_id="img_002",
            field=EvidenceField.MRP,
            raw_text="MRP Rs. 350.00 (incl. of all taxes)",
            normalized_text="350.00",
            parsed_value=350.0,
            parsed_unit="INR",
            ocr_confidence=0.96,
            confidence=0.96,
        )
        return [c1, c2, c3, c4]

    def _setup_completed_session(
        self,
        overall_status: OverallInspectionStatus = OverallInspectionStatus.PASS,
        owner_id: str = "consumer-user-1234",
        scan_context: str = "CONSUMER",
        fail_count: int = 0,
        review_count: int = 0,
        not_visible_count: int = 0,
        candidates: list[EvidenceCandidate] | None = None,
    ) -> str:
        """Helper to initialize a completed inspection session in the store."""
        session = self.store.create_session(
            owner_id=owner_id,
            metadata={"scan_context": scan_context},
        )
        insp_id = session.inspection.inspection_id

        v_results = []
        if fail_count > 0:
            v_results.append(
                VerificationResult(
                    requirement_id="R-6-1-e",
                    status=VerificationStatus.FAIL,
                    reason="MRP declaration is missing currency symbol prefix.",
                    evidence_ids=["ev_004"],
                )
            )
        if review_count > 0:
            v_results.append(
                VerificationResult(
                    requirement_id="R-6-1-f",
                    status=VerificationStatus.REVIEW_REQUIRED,
                    reason="Consumer care contact format ambiguous.",
                )
            )
        if not_visible_count > 0:
            v_results.append(
                VerificationResult(
                    requirement_id="R-6-1-d",
                    status=VerificationStatus.NOT_VISIBLE,
                    reason="Date of packing declaration not visible.",
                )
            )
        if not v_results:
            v_results.append(
                VerificationResult(
                    requirement_id="R-6-1-a",
                    status=VerificationStatus.PASS,
                    reason="Manufacturer name verified.",
                    evidence_ids=["ev_002"],
                )
            )

        report = InspectionReport(
            inspection_id=insp_id,
            overall_status=overall_status,
            verification_results=v_results,
            summary=f"Inspection summary for {insp_id}",
            evidence_count=4,
            image_count=2,
            applicable_requirement_count=len(v_results),
            pass_count=1 if not fail_count and not review_count else 0,
            fail_count=fail_count,
            not_visible_count=not_visible_count,
            not_applicable_count=0,
            review_required_count=review_count,
        )

        self.store.store_report(insp_id, report)
        cands = candidates if candidates is not None else self._create_sample_candidates()
        self.store.store_evidence(insp_id, cands)
        return insp_id

    # -------------------------------------------------------------------------
    # 1. Consumer inspection context
    # -------------------------------------------------------------------------
    def test_01_consumer_inspection_context(self) -> None:
        """1. Scan context is correctly reported as 'CONSUMER' by default."""
        insp_id = self._setup_completed_session(scan_context="CONSUMER")
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["scan_context"], "CONSUMER")

    # -------------------------------------------------------------------------
    # 2. Inspector context remains unchanged
    # -------------------------------------------------------------------------
    def test_02_inspector_context_remains_unchanged(self) -> None:
        """2. When scan_context is 'INSPECTOR', intelligence reports 'INSPECTOR'."""
        insp_id = self._setup_completed_session(scan_context="INSPECTOR")
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["scan_context"], "INSPECTOR")

    # -------------------------------------------------------------------------
    # 3. Completed inspection generates intelligence
    # -------------------------------------------------------------------------
    def test_03_completed_inspection_generates_intelligence(self) -> None:
        """3. Completed inspection generates full structured intelligence object."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["inspection_id"], insp_id)
        self.assertIn("product_identity", data)
        self.assertIn("scan_quality", data)
        self.assertIn("compliance_summary", data)
        self.assertIn("risk_signal", data)

    # -------------------------------------------------------------------------
    # 4. Running inspection rejected
    # -------------------------------------------------------------------------
    def test_04_running_inspection_rejected(self) -> None:
        """4. Requesting intelligence on a RUNNING inspection returns 400."""
        session = self.store.create_session(owner_id=self.owner_user.user_id)
        insp_id = session.inspection.inspection_id
        session.inspection.status = InspectionStatus.RUNNING
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 400)

    # -------------------------------------------------------------------------
    # 5. Failed inspection rejected
    # -------------------------------------------------------------------------
    def test_05_failed_inspection_rejected(self) -> None:
        """5. Requesting intelligence on a FAILED inspection returns 400."""
        session = self.store.create_session(owner_id=self.owner_user.user_id)
        insp_id = session.inspection.inspection_id
        session.inspection.status = InspectionStatus.FAILED
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 400)

    # -------------------------------------------------------------------------
    # 6. Missing report rejected
    # -------------------------------------------------------------------------
    def test_06_missing_report_rejected(self) -> None:
        """6. Completed session with missing report returns 400."""
        session = self.store.create_session(owner_id=self.owner_user.user_id)
        insp_id = session.inspection.inspection_id
        session.inspection.status = InspectionStatus.COMPLETED
        session.report = None
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 400)

    # -------------------------------------------------------------------------
    # 7. Product identity extracted from evidence
    # -------------------------------------------------------------------------
    def test_07_product_identity_from_evidence(self) -> None:
        """7. Product identity correctly extracts commodity, manufacturer, quantity, and MRP."""
        cands = self._create_sample_candidates()
        identity, conf, missing = self.service.extract_product_identity(cands)

        self.assertIsNotNone(identity.commodity)
        self.assertEqual(identity.commodity.value, "Green Tea")
        self.assertIsNotNone(identity.manufacturer_name)
        self.assertEqual(identity.manufacturer_name.value, "Ceylon Tea Co Ltd")
        self.assertIsNotNone(identity.net_quantity)
        self.assertEqual(identity.net_quantity.value, 250.0)
        self.assertEqual(identity.net_quantity.unit, "g")
        self.assertIsNotNone(identity.declared_mrp)
        self.assertEqual(identity.declared_mrp.value, 350.0)

    # -------------------------------------------------------------------------
    # 8. No hallucinated product fields
    # -------------------------------------------------------------------------
    def test_08_no_hallucinated_product_fields(self) -> None:
        """8. Unobserved fields remain None and are documented in missing_information."""
        cands = self._create_sample_candidates()
        identity, conf, missing = self.service.extract_product_identity(cands)

        self.assertIsNone(identity.barcode)
        self.assertIsNone(identity.country_of_origin)
        self.assertIsNone(identity.batch_number)

    # -------------------------------------------------------------------------
    # 9. Evidence provenance preserved
    # -------------------------------------------------------------------------
    def test_09_evidence_provenance_preserved(self) -> None:
        """9. Extracted fields preserve source evidence ID, image ID, and confidence."""
        cands = self._create_sample_candidates()
        identity, _, _ = self.service.extract_product_identity(cands)

        prov = identity.commodity.provenance
        self.assertEqual(len(prov), 1)
        self.assertEqual(prov[0].evidence_id, "ev_001")
        self.assertEqual(prov[0].image_id, "img_001")
        self.assertEqual(prov[0].confidence, 0.98)

    # -------------------------------------------------------------------------
    # 10. Barcode provenance preserved
    # -------------------------------------------------------------------------
    def test_10_barcode_provenance_preserved(self) -> None:
        """10. Barcode candidate provenance is preserved when present."""
        barcode_cand = EvidenceCandidate(
            evidence_id="ev_bar_001",
            image_id="img_003",
            field="barcode",
            raw_text="8901234567890",
            normalized_text="8901234567890",
            parsed_value="8901234567890",
            confidence=1.0,
        )
        cands = self._create_sample_candidates() + [barcode_cand]
        identity, _, _ = self.service.extract_product_identity(cands)

        self.assertIsNotNone(identity.barcode)
        self.assertEqual(identity.barcode.value, "8901234567890")
        self.assertEqual(identity.barcode.provenance[0].image_id, "img_003")

    # -------------------------------------------------------------------------
    # 11. Conflicting observations detected
    # -------------------------------------------------------------------------
    def test_11_conflicting_observations_detected(self) -> None:
        """11. Contradictory declarations flag is_conflicting=True without silent resolution."""
        c1 = EvidenceCandidate(
            evidence_id="ev_003a",
            field=EvidenceField.NET_QUANTITY,
            raw_text="Net: 250 g",
            normalized_text="250 g",
            parsed_value=250.0,
        )
        c2 = EvidenceCandidate(
            evidence_id="ev_003b",
            field=EvidenceField.NET_QUANTITY,
            raw_text="Net: 500 g",
            normalized_text="500 g",
            parsed_value=500.0,
        )
        identity, conf, _ = self.service.extract_product_identity([c1, c2])

        self.assertIsNotNone(identity.net_quantity)
        self.assertTrue(identity.net_quantity.is_conflicting)
        self.assertIn("250 g", identity.net_quantity.conflicting_values)
        self.assertIn("500 g", identity.net_quantity.conflicting_values)

    # -------------------------------------------------------------------------
    # 12. Identity confidence HIGH
    # -------------------------------------------------------------------------
    def test_12_identity_confidence_high(self) -> None:
        """12. All core declarations present with high confidence -> HIGH."""
        cands = self._create_sample_candidates()
        _, conf, _ = self.service.extract_product_identity(cands)
        self.assertEqual(conf, IdentityConfidence.HIGH)

    # -------------------------------------------------------------------------
    # 13. Identity confidence MEDIUM
    # -------------------------------------------------------------------------
    def test_13_identity_confidence_medium(self) -> None:
        """13. Partial core declarations present -> MEDIUM."""
        cands = self._create_sample_candidates()[:2]
        _, conf, _ = self.service.extract_product_identity(cands)
        self.assertEqual(conf, IdentityConfidence.MEDIUM)

    # -------------------------------------------------------------------------
    # 14. Identity confidence LOW
    # -------------------------------------------------------------------------
    def test_14_identity_confidence_low(self) -> None:
        """14. Only a single declaration present -> LOW."""
        cands = self._create_sample_candidates()[:1]
        _, conf, _ = self.service.extract_product_identity(cands)
        self.assertEqual(conf, IdentityConfidence.LOW)

    # -------------------------------------------------------------------------
    # 15. Identity confidence UNKNOWN
    # -------------------------------------------------------------------------
    def test_15_identity_confidence_unknown(self) -> None:
        """15. No declarations present -> UNKNOWN."""
        _, conf, _ = self.service.extract_product_identity([])
        self.assertEqual(conf, IdentityConfidence.UNKNOWN)

    # -------------------------------------------------------------------------
    # 16. Low OCR quality does not become FAIL
    # -------------------------------------------------------------------------
    def test_16_low_ocr_quality_does_not_become_fail(self) -> None:
        """16. Low OCR quality triggers diagnostic quality issue, does not alter overall PASS status."""
        low_ocr_cands = [
            EvidenceCandidate(
                field=EvidenceField.COMMODITY_NAME,
                normalized_text="Green Tea",
                ocr_confidence=0.35,
                confidence=0.35,
            )
        ]
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.PASS,
            candidates=low_ocr_cands,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["compliance_summary"]["overall_status"], "PASS")
        self.assertIn("LOW_OCR_CONFIDENCE", data["scan_quality"]["issues"])

    # -------------------------------------------------------------------------
    # 17. Scan quality signals deterministic
    # -------------------------------------------------------------------------
    def test_17_scan_quality_signals_deterministic(self) -> None:
        """17. Scan quality produces deterministic issue codes."""
        qual = self.service.evaluate_scan_quality(
            image_count=1,
            candidates=[],
            identity_confidence=IdentityConfidence.UNKNOWN,
            has_conflicts=False,
        )
        self.assertIn("INCOMPLETE_PACKAGE_VIEW", qual.issues)
        self.assertIn("PRODUCT_IDENTITY_UNCERTAIN", qual.issues)

    # -------------------------------------------------------------------------
    # 18. Any FAIL produces high-risk signal
    # -------------------------------------------------------------------------
    def test_18_any_fail_produces_high_risk_signal(self) -> None:
        """18. When any requirement fails, risk signal is HIGH_RISK_NON_COMPLIANCE."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.FAIL,
            fail_count=1,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_signal"], "HIGH_RISK_NON_COMPLIANCE")

    # -------------------------------------------------------------------------
    # 19. REVIEW_REQUIRED produces appropriate risk signal
    # -------------------------------------------------------------------------
    def test_19_review_required_produces_appropriate_risk_signal(self) -> None:
        """19. When review is required, risk signal is POTENTIAL_COMPLIANCE_ISSUE."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.REVIEW_REQUIRED,
            review_count=1,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_signal"], "POTENTIAL_COMPLIANCE_ISSUE")

    # -------------------------------------------------------------------------
    # 20. NOT_VISIBLE produces insufficient-evidence signal
    # -------------------------------------------------------------------------
    def test_20_not_visible_produces_insufficient_evidence_signal(self) -> None:
        """20. When declarations are not visible, risk signal is INSUFFICIENT_EVIDENCE."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.REVIEW_REQUIRED,
            not_visible_count=1,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_signal"], "INSUFFICIENT_EVIDENCE")

    # -------------------------------------------------------------------------
    # 21. Uncertain identity produces identity-uncertain signal
    # -------------------------------------------------------------------------
    def test_21_uncertain_identity_produces_identity_uncertain_signal(self) -> None:
        """21. When identity is unknown, risk signal is PRODUCT_IDENTITY_UNCERTAIN."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.PASS,
            candidates=[],
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_signal"], "PRODUCT_IDENTITY_UNCERTAIN")

    # -------------------------------------------------------------------------
    # 22. Clean PASS produces no-major-issues signal
    # -------------------------------------------------------------------------
    def test_22_clean_pass_produces_no_major_issues_signal(self) -> None:
        """22. Fully compliant pass produces NO_MAJOR_ISSUES_DETECTED."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.PASS,
            fail_count=0,
            review_count=0,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_signal"], "NO_MAJOR_ISSUES_DETECTED")

    # -------------------------------------------------------------------------
    # 23. U1 score reused rather than recalculated
    # -------------------------------------------------------------------------
    def test_23_u1_score_reused_rather_than_recalculated(self) -> None:
        """23. Compliance summary reflects authoritative report counts directly."""
        insp_id = self._setup_completed_session(fail_count=1)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        summary = response.json()["compliance_summary"]
        self.assertEqual(summary["fail_count"], 1)

    # -------------------------------------------------------------------------
    # 24. PASS/FAIL/REVIEW_REQUIRED enums unchanged
    # -------------------------------------------------------------------------
    def test_24_pass_fail_review_required_enums_unchanged(self) -> None:
        """24. Canonical overall status enums are preserved as machine readable values."""
        insp_id = self._setup_completed_session(overall_status=OverallInspectionStatus.FAIL, fail_count=1)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["compliance_summary"]["overall_status"], "FAIL")

    # -------------------------------------------------------------------------
    # 25. MRP remains distinct from selling price
    # -------------------------------------------------------------------------
    def test_25_mrp_remains_distinct_from_selling_price(self) -> None:
        """25. Declared MRP is kept separate from user_entered_selling_price."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence?selling_price=320.00")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["product_identity"]["declared_mrp"]["value"], 350.0)
        self.assertEqual(data["product_identity"]["user_entered_selling_price"], 320.00)

    # -------------------------------------------------------------------------
    # 26. Missing selling price not inferred
    # -------------------------------------------------------------------------
    def test_26_missing_selling_price_not_inferred(self) -> None:
        """26. Selling price is None if not provided by caller."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["product_identity"]["user_entered_selling_price"])

    # -------------------------------------------------------------------------
    # 27. Duplicate image evidence does not duplicate product identity
    # -------------------------------------------------------------------------
    def test_27_duplicate_image_evidence_does_not_duplicate_product_identity(self) -> None:
        """27. Multiple observations of the same field across images merge provenance cleanly."""
        c1 = EvidenceCandidate(
            evidence_id="ev_001a",
            image_id="img_001",
            field=EvidenceField.COMMODITY_NAME,
            normalized_text="Green Tea",
        )
        c2 = EvidenceCandidate(
            evidence_id="ev_001b",
            image_id="img_002",
            field=EvidenceField.COMMODITY_NAME,
            normalized_text="Green Tea",
        )
        identity, _, _ = self.service.extract_product_identity([c1, c2])
        self.assertEqual(len(identity.commodity.provenance), 2)
        self.assertFalse(identity.commodity.is_conflicting)

    # -------------------------------------------------------------------------
    # 28. Conflicting values are not silently resolved
    # -------------------------------------------------------------------------
    def test_28_conflicting_values_are_not_silently_resolved(self) -> None:
        """28. Contradictory values retain conflict tracking in intelligence output."""
        c1 = EvidenceCandidate(
            field=EvidenceField.COMMODITY_NAME,
            normalized_text="Green Tea",
        )
        c2 = EvidenceCandidate(
            field=EvidenceField.COMMODITY_NAME,
            normalized_text="Black Tea",
        )
        identity, _, _ = self.service.extract_product_identity([c1, c2])
        self.assertTrue(identity.commodity.is_conflicting)

    # -------------------------------------------------------------------------
    # 29. Consumer actions are deterministic
    # -------------------------------------------------------------------------
    def test_29_consumer_actions_are_deterministic(self) -> None:
        """29. Missing/failed MRP generates CHECK_MRP action deterministically."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.FAIL,
            fail_count=1,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        actions = response.json()["consumer_actions"]
        self.assertIn("CHECK_MRP", actions)
        self.assertIn("REVIEW_LABEL", actions)

    # -------------------------------------------------------------------------
    # 30. No unsupported legal claim invented
    # -------------------------------------------------------------------------
    def test_30_no_legal_claim_invented(self) -> None:
        """30. Consumer actions offer practical guidance rather than legal conclusions."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        action_labels = response.json()["consumer_action_labels"]
        for label in action_labels:
            self.assertNotIn("violates Rule", label)
            self.assertNotIn("court", label.lower())

    # -------------------------------------------------------------------------
    # 31. U3 English localization
    # -------------------------------------------------------------------------
    def test_31_u3_english_localization(self) -> None:
        """31. ?lang=en returns English risk signal and action labels."""
        insp_id = self._setup_completed_session(fail_count=1)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence?lang=en")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["risk_signal_label"], "Potential serious compliance issue detected.")
        self.assertIn("Review package labels carefully before purchase.", data["consumer_action_labels"])

    # -------------------------------------------------------------------------
    # 32. U3 Hindi localization
    # -------------------------------------------------------------------------
    def test_32_u3_hindi_localization(self) -> None:
        """32. ?lang=hi returns Hindi risk signal and action labels."""
        insp_id = self._setup_completed_session(fail_count=1)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence?lang=hi")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("संभावित गंभीर विधिक अनुपालन त्रुटि", data["risk_signal_label"])
        self.assertIn("खरीदने से पहले पैकेज लेबल की ध्यानपूर्वक समीक्षा करें।", data["consumer_action_labels"])

    # -------------------------------------------------------------------------
    # 33. U3 Marathi localization
    # -------------------------------------------------------------------------
    def test_33_u3_marathi_localization(self) -> None:
        """33. ?lang=mr returns Marathi risk signal and action labels."""
        insp_id = self._setup_completed_session(fail_count=1)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence?lang=mr")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("संभाव्य गंभीर वैधानिक अनुपालन त्रुटी", data["risk_signal_label"])
        self.assertIn("खरेदी करण्यापूर्वी पॅकेटवरील लेबल्स काळजीपूर्वक तपासा.", data["consumer_action_labels"])

    # -------------------------------------------------------------------------
    # 34. Canonical machine codes invariant across languages
    # -------------------------------------------------------------------------
    def test_34_canonical_machine_codes_invariant_across_languages(self) -> None:
        """34. Machine codes (HIGH_RISK_NON_COMPLIANCE, CHECK_MRP) stay identical across languages."""
        insp_id = self._setup_completed_session(fail_count=1)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        res_en = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence?lang=en").json()
        res_hi = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence?lang=hi").json()
        res_mr = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence?lang=mr").json()

        self.assertEqual(res_en["risk_signal"], res_hi["risk_signal"])
        self.assertEqual(res_hi["risk_signal"], res_mr["risk_signal"])
        self.assertEqual(res_en["consumer_actions"], res_hi["consumer_actions"])
        self.assertEqual(res_hi["consumer_actions"], res_mr["consumer_actions"])

    # -------------------------------------------------------------------------
    # 35. No JWT exposure
    # -------------------------------------------------------------------------
    def test_35_no_jwt_exposure(self) -> None:
        """35. Consumer intelligence response contains no JWT tokens."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("eyJ", response.text)

    # -------------------------------------------------------------------------
    # 36. No Telegram identity exposure
    # -------------------------------------------------------------------------
    def test_36_no_telegram_identity_exposure(self) -> None:
        """36. Consumer intelligence response contains no Telegram account IDs."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("telegram_user_id", response.text)

    # -------------------------------------------------------------------------
    # 37. No storage path exposure
    # -------------------------------------------------------------------------
    def test_37_no_storage_path_exposure(self) -> None:
        """37. Consumer intelligence response contains no private storage paths."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("storage_path", response.text)

    # -------------------------------------------------------------------------
    # 38. Endpoint requires authentication
    # -------------------------------------------------------------------------
    def test_38_endpoint_requires_authentication(self) -> None:
        """38. Unauthenticated request returns 401 AUTHENTICATION_REQUIRED."""
        insp_id = self._setup_completed_session()
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(response.status_code, 401)
        err = response.json()
        self.assertIn("AUTHENTICATION", str(err))

    # -------------------------------------------------------------------------
    # 39. Cross-user access rejected (returns 404 INSPECTION_NOT_FOUND, not 403)
    # -------------------------------------------------------------------------
    def test_39_cross_user_access_rejected(self) -> None:
        """39. Requesting another user's inspection returns 404 INSPECTION_NOT_FOUND (IDOR safe, no 403)."""
        insp_id = self._setup_completed_session(owner_id=self.owner_user.user_id)
        app.dependency_overrides[get_current_user] = lambda: self.other_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        # Must return 404 NOT FOUND, NOT 403 FORBIDDEN (obscuring existence)
        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(response.status_code, 403)
        err = response.json()
        error_code = (
            err.get("error", {}).get("code")
            if isinstance(err.get("error"), dict)
            else (err.get("detail", {}).get("code") if isinstance(err.get("detail"), dict) else err.get("code"))
        )
        self.assertEqual(error_code, "INSPECTION_NOT_FOUND")

    def test_39b_nonexistent_inspection_returns_404(self) -> None:
        """39b. Nonexistent inspection ID returns 404 INSPECTION_NOT_FOUND."""
        app.dependency_overrides[get_current_user] = lambda: self.owner_user
        response = self.client.get("/api/v1/inspections/nonexistent-id-9999/consumer-intelligence")
        self.assertEqual(response.status_code, 404)
        err = response.json()
        error_code = (
            err.get("error", {}).get("code")
            if isinstance(err.get("error"), dict)
            else (err.get("detail", {}).get("code") if isinstance(err.get("detail"), dict) else err.get("code"))
        )
        self.assertEqual(error_code, "INSPECTION_NOT_FOUND")

    # -------------------------------------------------------------------------
    # 40. Endpoint does not invoke OCR
    # -------------------------------------------------------------------------
    def test_40_endpoint_does_not_invoke_ocr(self) -> None:
        """40. Intelligence generation does not invoke OCR predict engine."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        with patch("backend.app.services.ocr.engine.PaddleOCREngine.predict") as mock_ocr:
            response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
            self.assertEqual(response.status_code, 200)
            mock_ocr.assert_not_called()

    # -------------------------------------------------------------------------
    # 41. Endpoint does not invoke Gemini
    # -------------------------------------------------------------------------
    def test_41_endpoint_does_not_invoke_gemini(self) -> None:
        """41. Intelligence generation does not call Gemini AI models."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        with patch("backend.app.services.gemini.service.GeminiEvidenceService.evaluate_requirement") as mock_gemini:
            response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
            self.assertEqual(response.status_code, 200)
            mock_gemini.assert_not_called()

    # -------------------------------------------------------------------------
    # 42. Endpoint does not invoke legal RAG
    # -------------------------------------------------------------------------
    def test_42_endpoint_does_not_invoke_legal_rag(self) -> None:
        """42. Intelligence generation does not invoke Legal RAG retrieval."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        with patch("backend.app.services.legal_rag.service.LegalRetrievalService.retrieve_for_applicable_requirements") as mock_rag:
            response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
            self.assertEqual(response.status_code, 200)
            mock_rag.assert_not_called()

    # -------------------------------------------------------------------------
    # 43. Endpoint does not execute inspection pipeline
    # -------------------------------------------------------------------------
    def test_43_endpoint_does_not_execute_inspection_pipeline(self) -> None:
        """43. Intelligence generation does not re-execute the pipeline orchestrator."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        with patch("backend.app.services.inspection_pipeline.orchestrator.InspectionPipelineOrchestrator.run") as mock_orch:
            response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
            self.assertEqual(response.status_code, 200)
            mock_orch.assert_not_called()

    # -------------------------------------------------------------------------
    # 44. U2 annotations remain unchanged
    # -------------------------------------------------------------------------
    def test_44_u2_annotations_remain_unchanged(self) -> None:
        """44. Consumer intelligence does not alter or mutate evidence annotations."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        report_before = self.store.get_report(insp_id)
        self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        report_after = self.store.get_report(insp_id)

        self.assertEqual(report_before.evidence_annotations, report_after.evidence_annotations)

    # -------------------------------------------------------------------------
    # 45. U4 share behavior remains unchanged
    # -------------------------------------------------------------------------
    def test_45_u4_share_behavior_remains_unchanged(self) -> None:
        """45. U4 report sharing operates independently alongside consumer intelligence."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        res_share = self.client.post(f"/api/v1/inspections/{insp_id}/share", json={})
        self.assertEqual(res_share.status_code, 201)

        res_intel = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-intelligence")
        self.assertEqual(res_intel.status_code, 200)


if __name__ == "__main__":
    unittest.main()
