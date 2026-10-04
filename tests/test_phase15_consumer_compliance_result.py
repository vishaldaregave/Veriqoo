"""Phase U6 Test Suite — Consumer Compliance Result & Explanation Layer.

Covers:
- Step 23 complete requirements
- Ownership & Security (Phase 9D 401/404 existence-obscuring semantics)
- Canonical status preservation
- U1 score projection
- U2 annotation linking & geometry preservation
- U3 multilingual localization (en, hi, mr)
- U5 scan intelligence integration
- No execution of OCR, Gemini, RAG, or applicability engine on GET
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_current_user, get_session_store
from backend.app.api.session_store import InMemoryInspectionStore, InspectionSession
from backend.app.auth.models import AuthenticatedUser
from backend.app.localization.service import SupportedLanguage, get_localization_service
from backend.app.main import create_app
from backend.app.services.consumer_intelligence.models import (
    ConsumerScanIntelligence,
    IdentityConfidence,
    ProductIdentity,
    RiskSignal,
    ScanQuality,
    ScanQualityIssue,
)
from backend.app.services.consumer_result.models import (
    ConsumerComplianceResult,
    ConsumerFinding,
    ConsumerOverallResult,
    ConsumerScore,
    FindingSeverity,
)
from backend.app.services.consumer_result.service import ConsumerResultService
from backend.app.services.evidence.models import EvidenceCandidate, EvidenceField
from backend.app.services.inspection.models import Inspection, InspectionStatus
from backend.app.services.inspection_pipeline.annotations import EvidenceAnnotation
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.verification.models import VerificationResult, VerificationStatus

app = create_app()


class TestPhase15ConsumerComplianceResult(unittest.TestCase):
    """Test suite for Phase U6 Consumer Compliance Result & Explanation."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        self.store = InMemoryInspectionStore()
        app.dependency_overrides[get_session_store] = lambda: self.store
        self.loc = get_localization_service()
        self.service = ConsumerResultService(session_store=self.store, localization_service=self.loc)

        self.owner_user = AuthenticatedUser(
            user_id="consumer-user-1234",
            email="consumer@example.com",
            role="authenticated",
        )
        self.other_user = AuthenticatedUser(
            user_id="different-user-5678",
            email="attacker@example.com",
            role="authenticated",
        )

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def _setup_completed_session(
        self,
        overall_status: OverallInspectionStatus = OverallInspectionStatus.PASS,
        owner_id: str = "consumer-user-1234",
        fail_count: int = 0,
        review_count: int = 0,
        not_visible_count: int = 0,
        applicable_count: int = 4,
        annotations: list[Any] | None = None,
        candidates: list[EvidenceCandidate] | None = None,
    ) -> str:
        """Helper to construct a fully populated completed session."""
        session = self.store.create_session(
            owner_id=owner_id,
            metadata={"scan_context": "CONSUMER"},
        )
        insp_id = session.inspection.inspection_id

        v_results: list[VerificationResult] = []
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
                    evidence_ids=["ev_005"],
                )
            )
        if not_visible_count > 0:
            v_results.append(
                VerificationResult(
                    requirement_id="R-6-1-d",
                    status=VerificationStatus.NOT_VISIBLE,
                    reason="Date of packing declaration not visible.",
                    evidence_ids=[],
                )
            )
        if not v_results:
            v_results.append(
                VerificationResult(
                    requirement_id="R-6-1-a",
                    status=VerificationStatus.PASS,
                    reason="Manufacturer name verified.",
                    evidence_ids=["ev_001"],
                )
            )

        report = InspectionReport(
            inspection_id=insp_id,
            overall_status=overall_status,
            verification_results=v_results,
            summary=f"Inspection summary for {insp_id}",
            evidence_count=4,
            image_count=2,
            applicable_requirement_count=applicable_count,
            pass_count=applicable_count - (fail_count + review_count + not_visible_count) if applicable_count > 0 else 0,
            fail_count=fail_count,
            not_visible_count=not_visible_count,
            not_applicable_count=0,
            review_required_count=review_count,
            evidence_annotations=annotations or [],
        )

        self.store.store_report(insp_id, report)
        if candidates:
            self.store.store_evidence(insp_id, candidates)
        return insp_id

    # -------------------------------------------------------------------------
    # 1. Owner can retrieve consumer result
    # -------------------------------------------------------------------------
    def test_01_owner_can_retrieve_consumer_result(self) -> None:
        """1. Authenticated session owner can successfully retrieve consumer compliance result."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["schema_version"], "1.0.0")
        self.assertEqual(data["inspection_id"], insp_id)
        self.assertEqual(data["overall_result"], "NO_MAJOR_ISSUES_DETECTED")
        self.assertEqual(data["canonical_status"], "PASS")

    # -------------------------------------------------------------------------
    # 2. Unauthenticated request rejected (401)
    # -------------------------------------------------------------------------
    def test_02_unauthenticated_request_rejected(self) -> None:
        """2. Unauthenticated request returns 401 AUTHENTICATION_REQUIRED."""
        insp_id = self._setup_completed_session()
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 401)
        self.assertIn("AUTHENTICATION", str(response.json()))

    # -------------------------------------------------------------------------
    # 3. Cross-user request returns 404 (Phase 9D IDOR safe)
    # -------------------------------------------------------------------------
    def test_03_cross_user_request_returns_404(self) -> None:
        """3. Cross-user access returns 404 INSPECTION_NOT_FOUND (obscuring existence, no 403)."""
        insp_id = self._setup_completed_session(owner_id=self.owner_user.user_id)
        app.dependency_overrides[get_current_user] = lambda: self.other_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(response.status_code, 403)
        err = response.json()
        code = err.get("error", {}).get("code") if isinstance(err.get("error"), dict) else (err.get("detail", {}).get("code") if isinstance(err.get("detail"), dict) else err.get("code"))
        self.assertEqual(code, "INSPECTION_NOT_FOUND")

    # -------------------------------------------------------------------------
    # 4. Nonexistent inspection returns 404
    # -------------------------------------------------------------------------
    def test_04_nonexistent_inspection_returns_404(self) -> None:
        """4. Nonexistent inspection ID returns 404 INSPECTION_NOT_FOUND."""
        app.dependency_overrides[get_current_user] = lambda: self.owner_user
        response = self.client.get("/api/v1/inspections/nonexistent-id-9999/consumer-result")
        self.assertEqual(response.status_code, 404)
        err = response.json()
        code = err.get("error", {}).get("code") if isinstance(err.get("error"), dict) else (err.get("detail", {}).get("code") if isinstance(err.get("detail"), dict) else err.get("code"))
        self.assertEqual(code, "INSPECTION_NOT_FOUND")

    # -------------------------------------------------------------------------
    # 5. Incomplete inspection rejected
    # -------------------------------------------------------------------------
    def test_05_incomplete_inspection_rejected(self) -> None:
        """5. Inspection still in COLLECTING state returns 400 state error."""
        session = self.store.create_session(owner_id=self.owner_user.user_id)
        insp_id = session.inspection.inspection_id
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 400)

    # -------------------------------------------------------------------------
    # 6. Missing report rejected
    # -------------------------------------------------------------------------
    def test_06_missing_report_rejected(self) -> None:
        """6. Session without an InspectionReport cannot generate consumer result."""
        session = self.store.create_session(owner_id=self.owner_user.user_id)
        session.inspection.status = InspectionStatus.COMPLETED
        insp_id = session.inspection.inspection_id
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 400)

    # -------------------------------------------------------------------------
    # 7. PASS maps to NO_MAJOR_ISSUES_DETECTED
    # -------------------------------------------------------------------------
    def test_07_pass_maps_to_no_major_issues_detected(self) -> None:
        """7. Canonical PASS maps to NO_MAJOR_ISSUES_DETECTED."""
        insp_id = self._setup_completed_session(overall_status=OverallInspectionStatus.PASS)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["overall_result"], "NO_MAJOR_ISSUES_DETECTED")
        self.assertEqual(data["canonical_status"], "PASS")

    # -------------------------------------------------------------------------
    # 8. FAIL maps to COMPLIANCE_ISSUE_DETECTED
    # -------------------------------------------------------------------------
    def test_08_fail_maps_to_compliance_issue_detected(self) -> None:
        """8. Canonical FAIL maps to COMPLIANCE_ISSUE_DETECTED."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.FAIL,
            fail_count=1,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["overall_result"], "COMPLIANCE_ISSUE_DETECTED")
        self.assertEqual(data["canonical_status"], "FAIL")

    # -------------------------------------------------------------------------
    # 9. REVIEW_REQUIRED maps to REVIEW_RECOMMENDED
    # -------------------------------------------------------------------------
    def test_09_review_required_maps_to_review_recommended(self) -> None:
        """9. Canonical REVIEW_REQUIRED maps to REVIEW_RECOMMENDED."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.REVIEW_REQUIRED,
            review_count=1,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["overall_result"], "REVIEW_RECOMMENDED")
        self.assertEqual(data["canonical_status"], "REVIEW_REQUIRED")

    # -------------------------------------------------------------------------
    # 10. NOT_VISIBLE maps to INSUFFICIENT_EVIDENCE
    # -------------------------------------------------------------------------
    def test_10_not_visible_maps_to_insufficient_evidence(self) -> None:
        """10. Declarations NOT_VISIBLE maps to INSUFFICIENT_EVIDENCE."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.REVIEW_REQUIRED,
            not_visible_count=1,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["overall_result"], "INSUFFICIENT_EVIDENCE")

    # -------------------------------------------------------------------------
    # 11. NOT_APPLICABLE never becomes an overall violation
    # -------------------------------------------------------------------------
    def test_11_not_applicable_never_becomes_overall_violation(self) -> None:
        """11. NOT_APPLICABLE requirements do not trigger violation status."""
        session = self.store.create_session(owner_id=self.owner_user.user_id)
        insp_id = session.inspection.inspection_id
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        report = InspectionReport(
            inspection_id=insp_id,
            overall_status=OverallInspectionStatus.PASS,
            verification_results=[
                VerificationResult(
                    requirement_id="R-6-1-g",
                    status=VerificationStatus.NOT_APPLICABLE,
                    reason="Country of origin not applicable to domestic non-imported package.",
                )
            ],
            summary="All applicable satisfied",
            evidence_count=1,
            image_count=1,
            applicable_requirement_count=0,
            pass_count=0,
            fail_count=0,
            not_visible_count=0,
            not_applicable_count=1,
            review_required_count=0,
        )
        self.store.store_report(insp_id, report)

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()["overall_result"], "COMPLIANCE_ISSUE_DETECTED")

    # -------------------------------------------------------------------------
    # 12. Canonical status preserved
    # -------------------------------------------------------------------------
    def test_12_canonical_status_preserved(self) -> None:
        """12. Authoritative overall_status (e.g. FAIL) is explicitly preserved in machine field."""
        insp_id = self._setup_completed_session(overall_status=OverallInspectionStatus.FAIL, fail_count=1)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["canonical_status"], "FAIL")

    # -------------------------------------------------------------------------
    # 13. U1 score reused exactly
    # -------------------------------------------------------------------------
    def test_13_u1_score_reused_exactly(self) -> None:
        """13. Score calculation matches canonical proportion (e.g. 3/4 passed = 75.0%)."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.FAIL,
            fail_count=1,
            applicable_count=4,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        score_data = response.json()["score"]
        self.assertEqual(score_data["score"], 75.0)
        self.assertEqual(score_data["evaluated_requirements"], 4)

    # -------------------------------------------------------------------------
    # 14. Null score remains null when zero evaluated requirements
    # -------------------------------------------------------------------------
    def test_14_null_score_remains_null(self) -> None:
        """14. If applicable requirement count is zero, score is null and rating is NOT_APPLICABLE."""
        session = self.store.create_session(owner_id=self.owner_user.user_id)
        insp_id = session.inspection.inspection_id
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        report = InspectionReport(
            inspection_id=insp_id,
            overall_status=OverallInspectionStatus.PASS,
            verification_results=[],
            summary="Empty inspection",
            evidence_count=0,
            image_count=1,
            applicable_requirement_count=0,
            pass_count=0,
            fail_count=0,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
        )
        self.store.store_report(insp_id, report)

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        score_data = response.json()["score"]
        self.assertIsNone(score_data["score"])
        self.assertEqual(score_data["rating"], "NOT_APPLICABLE")

    # -------------------------------------------------------------------------
    # 15. No independent score calculation
    # -------------------------------------------------------------------------
    def test_15_no_independent_score_calculation(self) -> None:
        """15. Score derives strictly from report pass and applicable counts."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.PASS,
            applicable_count=2,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["score"]["score"], 100.0)

    # -------------------------------------------------------------------------
    # 16. FAIL explanation uses canonical evidence & reason
    # -------------------------------------------------------------------------
    def test_16_fail_explanation_uses_canonical_evidence(self) -> None:
        """16. FAIL finding includes canonical requirement failure reason and associated evidence."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.FAIL,
            fail_count=1,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        findings = response.json()["key_findings"]
        fail_finding = next(f for f in findings if f["requirement_id"] == "R-6-1-e")
        self.assertEqual(fail_finding["status"], "FAIL")
        self.assertIn("ev_004", fail_finding["evidence_ids"])
        self.assertIn("currency", fail_finding["consumer_explanation"].lower())

    # -------------------------------------------------------------------------
    # 17. FAIL explanation does not invent evidence
    # -------------------------------------------------------------------------
    def test_17_fail_explanation_does_not_invent_evidence(self) -> None:
        """17. Finding evidence IDs match strictly the IDs present in VerificationResult."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.FAIL,
            fail_count=1,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        findings = response.json()["key_findings"]
        fail_finding = next(f for f in findings if f["requirement_id"] == "R-6-1-e")
        self.assertEqual(fail_finding["evidence_ids"], ["ev_004"])

    # -------------------------------------------------------------------------
    # 18. REVIEW_REQUIRED is not called a violation
    # -------------------------------------------------------------------------
    def test_18_review_required_is_not_called_a_violation(self) -> None:
        """18. REVIEW_REQUIRED finding uses non-judgmental guidance language."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.REVIEW_REQUIRED,
            review_count=1,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        findings = response.json()["key_findings"]
        rev_finding = next(f for f in findings if f["requirement_id"] == "R-6-1-f")
        self.assertNotIn("violation", rev_finding["consumer_explanation"].lower())
        self.assertNotIn("illegal", rev_finding["consumer_explanation"].lower())

    # -------------------------------------------------------------------------
    # 19. NOT_VISIBLE is treated as evidence limitation
    # -------------------------------------------------------------------------
    def test_19_not_visible_treated_as_evidence_limitation(self) -> None:
        """19. NOT_VISIBLE findings indicate missing visual evidence without fabricating a violation."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.REVIEW_REQUIRED,
            not_visible_count=1,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        findings = response.json()["key_findings"]
        nv_finding = next(f for f in findings if f["requirement_id"] == "R-6-1-d")
        self.assertEqual(nv_finding["severity"], "LOW")
        self.assertIn("not visible", nv_finding["consumer_explanation"].lower())

    # -------------------------------------------------------------------------
    # 20. PASS remains concise
    # -------------------------------------------------------------------------
    def test_20_pass_remains_concise(self) -> None:
        """20. PASS finding provides a concise verification confirmation."""
        insp_id = self._setup_completed_session(overall_status=OverallInspectionStatus.PASS)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        findings = response.json()["key_findings"]
        pass_finding = next(f for f in findings if f["requirement_id"] == "R-6-1-a")
        self.assertEqual(pass_finding["severity"], "INFO")
        self.assertIn("verified", pass_finding["consumer_explanation"].lower())

    # -------------------------------------------------------------------------
    # 21. Legal reference preserved
    # -------------------------------------------------------------------------
    def test_21_legal_reference_preserved(self) -> None:
        """21. Canonical statutory rule number is preserved in finding legal_reference."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        findings = response.json()["key_findings"]
        finding = next(f for f in findings if f["requirement_id"] == "R-6-1-a")
        self.assertIsNotNone(finding["legal_reference"])
        self.assertEqual(finding["legal_reference"]["rule_number"], "Rule 6(1)(a)")

    # -------------------------------------------------------------------------
    # 22. Unknown legal reference remains null
    # -------------------------------------------------------------------------
    def test_22_unknown_legal_reference_remains_null(self) -> None:
        """22. Custom/unknown requirement IDs do not invent false statutory citations."""
        legal_ref = self.service.extract_legal_reference("CUSTOM-UNKNOWN-REQ")
        self.assertIsNone(legal_ref)

    # -------------------------------------------------------------------------
    # 23. Evidence IDs are valid
    # -------------------------------------------------------------------------
    def test_23_evidence_ids_are_valid(self) -> None:
        """23. Findings correctly link evidence IDs from VerificationResult."""
        insp_id = self._setup_completed_session(overall_status=OverallInspectionStatus.PASS)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        findings = response.json()["key_findings"]
        self.assertEqual(findings[0]["evidence_ids"], ["ev_001"])

    # -------------------------------------------------------------------------
    # 24. Annotation IDs are valid
    # -------------------------------------------------------------------------
    def test_24_annotation_ids_are_valid(self) -> None:
        """24. Matching U2 annotation IDs are linked in finding."""
        from backend.app.services.inspection_pipeline.annotations import NormalizedBox
        ann = EvidenceAnnotation(
            annotation_id="ann_001",
            image_id="img_001",
            requirement_id="R-6-1-e",
            evidence_id="ev_004",
            status="FAIL",
            annotation_type="ERROR_LABEL",
            polygon=[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
            bounding_box={"x": 10.0, "y": 10.0, "width": 50.0, "height": 50.0},
            normalized_box=NormalizedBox(x_min=0.1, y_min=0.1, x_max=0.5, y_max=0.5),
            label="Maximum Retail Price (MRP)",
            reason="MRP missing currency symbol",
        )
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.FAIL,
            fail_count=1,
            annotations=[ann],
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        findings = response.json()["key_findings"]
        mrp_finding = next(f for f in findings if f["requirement_id"] == "R-6-1-e")
        self.assertIn("ann_001", mrp_finding["annotation_ids"])

    # -------------------------------------------------------------------------
    # 25. U2 geometry unchanged
    # -------------------------------------------------------------------------
    def test_25_u2_geometry_unchanged(self) -> None:
        """25. U2 NormalizedBox clamping and coordinates remain unmodified."""
        from backend.app.services.inspection_pipeline.annotations import NormalizedBox
        box = NormalizedBox(x_min=-0.5, y_min=0.2, x_max=1.5, y_max=0.8)
        self.assertEqual(box.x_min, 0.0)
        self.assertEqual(box.x_max, 1.0)

    # -------------------------------------------------------------------------
    # 26. No private storage path exposed
    # -------------------------------------------------------------------------
    def test_26_no_private_storage_path_exposed(self) -> None:
        """26. Output JSON contains no private filesystem or storage paths."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("storage_path", response.text)
        self.assertNotIn("s3://", response.text)
        self.assertNotIn("supabase.co/storage", response.text)

    # -------------------------------------------------------------------------
    # 27. U5 risk signal integrated
    # -------------------------------------------------------------------------
    def test_27_u5_risk_signal_integrated(self) -> None:
        """27. U5 derived risk signal is exposed in consumer result."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.FAIL,
            fail_count=1,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["risk_signal"], "HIGH_RISK_NON_COMPLIANCE")

    # -------------------------------------------------------------------------
    # 28. U5 identity confidence integrated
    # -------------------------------------------------------------------------
    def test_28_u5_identity_confidence_integrated(self) -> None:
        """28. Uncertain identity confidence adds limitation signal."""
        session = self.store.create_session(owner_id=self.owner_user.user_id)
        insp_id = session.inspection.inspection_id
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        report = InspectionReport(
            inspection_id=insp_id,
            overall_status=OverallInspectionStatus.PASS,
            verification_results=[
                VerificationResult(
                    requirement_id="R-6-1-a",
                    status=VerificationStatus.PASS,
                    reason="Pass",
                )
            ],
            summary="Pass",
            evidence_count=0,
            image_count=1,
            applicable_requirement_count=1,
            pass_count=1,
            fail_count=0,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
        )
        self.store.store_report(insp_id, report)

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        self.assertIn("PRODUCT_IDENTITY_UNCERTAIN", response.json()["limitations"])

    # -------------------------------------------------------------------------
    # 29. U5 scan quality integrated
    # -------------------------------------------------------------------------
    def test_29_u5_scan_quality_integrated(self) -> None:
        """29. Low OCR confidence or missing angles appear in limitations."""
        low_ocr_cand = EvidenceCandidate(
            field=EvidenceField.COMMODITY_NAME,
            normalized_text="Tea",
            ocr_confidence=0.35,
            confidence=0.35,
        )
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.PASS,
            candidates=[low_ocr_cand],
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        self.assertIn("LOW_OCR_CONFIDENCE", response.json()["limitations"])

    # -------------------------------------------------------------------------
    # 30. Consumer actions deterministic
    # -------------------------------------------------------------------------
    def test_30_consumer_actions_deterministic(self) -> None:
        """30. Recommended actions are deterministic enum codes."""
        insp_id = self._setup_completed_session(
            overall_status=OverallInspectionStatus.FAIL,
            fail_count=1,
        )
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        actions = response.json()["recommended_actions"]
        self.assertIn("CHECK_MRP", actions)

    # -------------------------------------------------------------------------
    # 31. Limitations generated deterministically
    # -------------------------------------------------------------------------
    def test_31_limitations_generated_deterministically(self) -> None:
        """31. Standard photo capture limitation is always present."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        self.assertIn("VERIFICATION_LIMITED_TO_CAPTURED_IMAGES", response.json()["limitations"])

    # -------------------------------------------------------------------------
    # 32. English localization (?lang=en)
    # -------------------------------------------------------------------------
    def test_32_english_localization(self) -> None:
        """32. English query parameter resolves English presentation labels."""
        insp_id = self._setup_completed_session(overall_status=OverallInspectionStatus.PASS)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result?lang=en")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["result_label"], "No Major Compliance Issues Detected")

    # -------------------------------------------------------------------------
    # 33. Hindi localization (?lang=hi)
    # -------------------------------------------------------------------------
    def test_33_hindi_localization(self) -> None:
        """33. Hindi query parameter resolves Hindi presentation labels."""
        insp_id = self._setup_completed_session(overall_status=OverallInspectionStatus.PASS)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result?lang=hi")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["result_label"], "कोई मुख्य अनुपालन त्रुटि नहीं मिली")

    # -------------------------------------------------------------------------
    # 34. Marathi localization (?lang=mr)
    # -------------------------------------------------------------------------
    def test_34_marathi_localization(self) -> None:
        """34. Marathi query parameter resolves Marathi presentation labels."""
        insp_id = self._setup_completed_session(overall_status=OverallInspectionStatus.PASS)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result?lang=mr")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["result_label"], "कोणतीही मुख्य अनुपालन त्रुटी आढळली नाही")

    # -------------------------------------------------------------------------
    # 35. Machine enums invariant across languages
    # -------------------------------------------------------------------------
    def test_35_machine_enums_invariant_across_languages(self) -> None:
        """35. Machine codes remain identical regardless of target display language."""
        insp_id = self._setup_completed_session(overall_status=OverallInspectionStatus.FAIL, fail_count=1)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        r_en = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result?lang=en").json()
        r_hi = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result?lang=hi").json()
        r_mr = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result?lang=mr").json()

        self.assertEqual(r_en["overall_result"], r_hi["overall_result"])
        self.assertEqual(r_hi["overall_result"], r_mr["overall_result"])
        self.assertEqual(r_en["canonical_status"], r_hi["canonical_status"])
        self.assertEqual(r_hi["canonical_status"], r_mr["canonical_status"])

    # -------------------------------------------------------------------------
    # 36. Canonical rule IDs invariant across languages
    # -------------------------------------------------------------------------
    def test_36_canonical_rule_ids_invariant_across_languages(self) -> None:
        """36. Requirement IDs (e.g. R-6-1-e) are never translated."""
        insp_id = self._setup_completed_session(overall_status=OverallInspectionStatus.FAIL, fail_count=1)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        r_hi = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result?lang=hi").json()
        req_ids = [f["requirement_id"] for f in r_hi["key_findings"]]
        self.assertIn("R-6-1-e", req_ids)

    # -------------------------------------------------------------------------
    # 37. No Gemini call
    # -------------------------------------------------------------------------
    def test_37_no_gemini_call(self) -> None:
        """37. Endpoint does not invoke Gemini AI during consumer result generation."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        with patch("backend.app.services.gemini.service.GeminiEvidenceService.evaluate_requirement") as mock_gemini:
            response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
            self.assertEqual(response.status_code, 200)
            mock_gemini.assert_not_called()

    # -------------------------------------------------------------------------
    # 38. No OCR call
    # -------------------------------------------------------------------------
    def test_38_no_ocr_call(self) -> None:
        """38. Endpoint does not invoke OCR during consumer result generation."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        with patch("backend.app.services.ocr.engine.PaddleOCREngine.predict") as mock_ocr:
            response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
            self.assertEqual(response.status_code, 200)
            mock_ocr.assert_not_called()

    # -------------------------------------------------------------------------
    # 39. No RAG call
    # -------------------------------------------------------------------------
    def test_39_no_rag_call(self) -> None:
        """39. Endpoint does not invoke legal RAG search during consumer result generation."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        with patch("backend.app.services.legal_rag.service.LegalRetrievalService.retrieve") as mock_rag:
            response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
            self.assertEqual(response.status_code, 200)
            mock_rag.assert_not_called()

    # -------------------------------------------------------------------------
    # 40. No applicability execution
    # -------------------------------------------------------------------------
    def test_40_no_applicability_execution(self) -> None:
        """40. Endpoint does not invoke applicability engine during consumer result generation."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        with patch("backend.app.services.applicability.service.ApplicabilityService.evaluate_run") as mock_app:
            response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
            self.assertEqual(response.status_code, 200)
            mock_app.assert_not_called()

    # -------------------------------------------------------------------------
    # 41. No pipeline execution
    # -------------------------------------------------------------------------
    def test_41_no_pipeline_execution(self) -> None:
        """41. Endpoint does not execute the end-to-end pipeline."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        with patch("backend.app.services.inspection_pipeline.orchestrator.InspectionPipelineOrchestrator.run") as mock_pipe:
            response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
            self.assertEqual(response.status_code, 200)
            mock_pipe.assert_not_called()

    # -------------------------------------------------------------------------
    # 42. Safe report reference included
    # -------------------------------------------------------------------------
    def test_42_safe_report_reference_included(self) -> None:
        """42. Response includes a safe report reference with counts and ID."""
        insp_id = self._setup_completed_session()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.get(f"/api/v1/inspections/{insp_id}/consumer-result")
        self.assertEqual(response.status_code, 200)
        report_ref = response.json()["report_reference"]
        self.assertEqual(report_ref["inspection_id"], insp_id)
        self.assertTrue(report_ref["has_report"])


if __name__ == "__main__":
    unittest.main()
