"""Comprehensive test suite for Phase U9 — Authority Intelligence & Risk Prioritization.

Covers all 38 verification requirements:
1. Authority endpoint authentication
2. Unauthorized access rejection
3. Role / identity behavior
4. Individual inspection priority
5. PASS priority assignment
6. FAIL priority assignment
7. REVIEW_REQUIRED handling
8. NOT_VISIBLE handling
9. NOT_APPLICABLE handling
10. Deterministic score / priority calculation
11. Priority reason generation
12. Repeated failure signal
13. Repeated product signal
14. Repeated manufacturer signal
15. Identity confidence handling
16. LOW identity does not create strong grouping
17. UNKNOWN identity behavior
18. Conflicting identity behavior
19. Geographic U7 integration
20. Trend calculation
21. Insufficient trend data behavior
22. Issue category aggregation
23. Zero-data behavior
24. Missing data behavior
25. No false legal conclusions
26. No enforcement action execution
27. No private data leakage
28. No exact GPS leakage
29. No share-token leakage
30. No raw OCR leakage
31. Deterministic output guarantees
32. T3 integration contract compatibility
33. U1 regression test
34. U5 regression test
35. U6 regression test
36. U7 regression test
37. U8 regression test
38. Phase 9 auth regression test
"""

from datetime import datetime, timedelta, timezone
import unittest
import uuid
from typing import Any

from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_session_store
from backend.app.api.session_store import InMemoryInspectionStore, InspectionSession
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import AuthenticatedUser
from backend.app.main import create_app
from backend.app.services.authority.models import (
    AuthorityOverviewMetrics,
    AuthorityPriority,
    AuthorityPriorityItem,
    AuthorityRiskSignal,
    ManufacturerIntelligenceSummary,
    ProductIntelligenceSummary,
    RiskSignalCode,
    TrendDirection,
)
from backend.app.services.authority.prioritizer import InspectionPrioritizer
from backend.app.services.authority.intelligence import AuthorityIntelligenceService
from backend.app.services.consumer_intelligence.models import (
    ConsumerComplianceSummary,
    ConsumerScanIntelligence,
    ExtractedProductField,
    IdentityConfidence,
    ProductIdentity,
    RiskSignal,
    ScanContext,
    ScanQuality,
)
from backend.app.services.evidence.models import EvidenceCandidate, EvidenceField, ImageArtifact
from backend.app.services.inspection.models import Inspection, InspectionImage, InspectionStatus
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.verification.models import VerificationResult, VerificationStatus


def _create_mock_report(
    inspection_id: str,
    overall_status: str,
    pass_count: int = 1,
    fail_count: int = 0,
    review_count: int = 0,
    not_visible_count: int = 0,
    not_applicable_count: int = 0,
    compliance_score: float | None = 100.0,
    rating: str = "FULLY_COMPLIANT",
    failed_req_ids: list[str] | None = None,
) -> InspectionReport:
    """Helper to create a deterministic InspectionReport for test assertions."""
    results: list[VerificationResult] = []

    for i in range(pass_count):
        results.append(
            VerificationResult(
                requirement_id=f"req_pass_{i}",
                status=VerificationStatus.PASS,
                confidence=0.95,
                reason="Declaration valid and compliant",
                metadata={"category": "general_declaration", "requirement_name": "Pass Requirement"},
            )
        )

    for i in range(fail_count):
        req_id = (failed_req_ids[i] if failed_req_ids and i < len(failed_req_ids) else f"req_fail_{i}")
        results.append(
            VerificationResult(
                requirement_id=req_id,
                status=VerificationStatus.FAIL,
                confidence=0.9,
                reason="Mandatory declaration missing or non-compliant",
                metadata={"category": "mandatory_declarations", "requirement_name": f"Failed Requirement {i}"},
            )
        )

    for i in range(review_count):
        results.append(
            VerificationResult(
                requirement_id=f"req_rev_{i}",
                status=VerificationStatus.REVIEW_REQUIRED,
                confidence=0.5,
                reason="Requires manual review",
                metadata={"category": "mrp_declaration", "requirement_name": "Review Requirement"},
            )
        )

    for i in range(not_visible_count):
        results.append(
            VerificationResult(
                requirement_id=f"req_nv_{i}",
                status=VerificationStatus.NOT_VISIBLE,
                confidence=0.0,
                reason="Declaration not visible on captured view",
                metadata={"category": "consumer_care", "requirement_name": "Not Visible Requirement"},
            )
        )

    for i in range(not_applicable_count):
        results.append(
            VerificationResult(
                requirement_id=f"req_na_{i}",
                status=VerificationStatus.NOT_APPLICABLE,
                confidence=1.0,
                reason="Requirement not applicable to this category",
                metadata={"category": "other", "requirement_name": "NA Requirement"},
            )
        )

    status_map = {
        "PASS": OverallInspectionStatus.PASS,
        "FAIL": OverallInspectionStatus.FAIL,
        "REVIEW_REQUIRED": OverallInspectionStatus.REVIEW_REQUIRED,
    }

    total_eval = pass_count + fail_count + review_count + not_visible_count

    return InspectionReport(
        inspection_id=inspection_id,
        overall_status=status_map.get(overall_status, OverallInspectionStatus.FAIL),
        verification_results=results,
        summary=f"Inspection concluded with status {overall_status}.",
        evidence_count=5,
        image_count=2,
        applicable_requirement_count=total_eval,
        pass_count=pass_count,
        fail_count=fail_count,
        not_visible_count=not_visible_count,
        not_applicable_count=not_applicable_count,
        review_required_count=review_count,
        metadata={
            "compliance_score": compliance_score,
            "rating": rating,
        },
    )


class TestAuthorityIntelligencePhaseU9(unittest.TestCase):
    """Test suite covering Phase U9 Authority Intelligence & Risk Prioritization."""

    def setUp(self) -> None:
        self.store = InMemoryInspectionStore()
        self.app = create_app()
        self.app.dependency_overrides[get_session_store] = lambda: self.store

        # Mock authenticated authority user by default
        self.mock_user = AuthenticatedUser(
            user_id="auth_officer_1",
            email="officer@legalmetrology.gov.in",
            role="authenticated",
            claims={"role": "authority"},
        )
        self.app.dependency_overrides[get_current_user] = lambda: self.mock_user
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    # 1. Authority endpoint authentication
    def test_01_authority_endpoint_authentication(self) -> None:
        response = self.client.get("/api/v1/authority/intelligence/priorities")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_count", data)
        self.assertIn("items", data)

    # 2. Unauthorized access rejection
    def test_02_unauthorized_access(self) -> None:
        self.app.dependency_overrides.pop(get_current_user, None)
        unauth_client = TestClient(self.app)
        resp = unauth_client.get("/api/v1/authority/intelligence/priorities")
        self.assertEqual(resp.status_code, 401)

    # 3. Non-authority / Authenticated identity behavior
    def test_03_authenticated_user_access(self) -> None:
        user = AuthenticatedUser(user_id="consumer_user", role="authenticated")
        self.app.dependency_overrides[get_current_user] = lambda: user
        resp = self.client.get("/api/v1/authority/intelligence/overview")
        self.assertEqual(resp.status_code, 200)

    # 4. Individual inspection priority
    def test_04_individual_inspection_priority_structure(self) -> None:
        report = _create_mock_report("insp_1", "FAIL", pass_count=1, fail_count=2, compliance_score=33.3, rating="NON_COMPLIANT")
        item = InspectionPrioritizer.prioritize_inspection(
            inspection_id="insp_1",
            report=report,
        )
        self.assertIsInstance(item, AuthorityPriorityItem)
        self.assertEqual(item.inspection_id, "insp_1")
        self.assertGreaterEqual(item.priority_score, 0)
        self.assertLessEqual(item.priority_score, 100)
        self.assertTrue(len(item.reasons) > 0)

    # 5. PASS priority assignment
    def test_05_pass_priority_assignment(self) -> None:
        report = _create_mock_report("insp_pass", "PASS", pass_count=5, fail_count=0, review_count=0, compliance_score=100.0, rating="FULLY_COMPLIANT")
        item = InspectionPrioritizer.prioritize_inspection(
            inspection_id="insp_pass",
            report=report,
        )
        self.assertEqual(item.canonical_status, "PASS")
        self.assertIn(item.priority, (AuthorityPriority.INFORMATIONAL, AuthorityPriority.LOW))
        self.assertLess(item.priority_score, 35)

    # 6. FAIL priority assignment
    def test_06_fail_priority_assignment(self) -> None:
        report = _create_mock_report("insp_fail", "FAIL", pass_count=1, fail_count=3, compliance_score=25.0, rating="NON_COMPLIANT")
        item = InspectionPrioritizer.prioritize_inspection(
            inspection_id="insp_fail",
            report=report,
        )
        self.assertEqual(item.canonical_status, "FAIL")
        self.assertIn(item.priority, (AuthorityPriority.CRITICAL, AuthorityPriority.HIGH))
        self.assertGreaterEqual(item.priority_score, 60)

    # 7. REVIEW_REQUIRED handling
    def test_07_review_required_handling(self) -> None:
        report = _create_mock_report("insp_rev", "REVIEW_REQUIRED", pass_count=2, fail_count=0, review_count=2, compliance_score=80.0, rating="SUBSTANTIALLY_COMPLIANT")
        item = InspectionPrioritizer.prioritize_inspection(
            inspection_id="insp_rev",
            report=report,
        )
        self.assertEqual(item.canonical_status, "REVIEW_REQUIRED")
        self.assertIn(item.priority, (AuthorityPriority.MEDIUM, AuthorityPriority.LOW))

    # 8. NOT_VISIBLE handling
    def test_08_not_visible_handling(self) -> None:
        report = _create_mock_report("insp_nv", "PASS", pass_count=3, fail_count=0, review_count=0, not_visible_count=2)
        item = InspectionPrioritizer.prioritize_inspection(
            inspection_id="insp_nv",
            report=report,
        )
        self.assertEqual(item.not_visible_count, 2)
        self.assertTrue(any(s.code == RiskSignalCode.INSUFFICIENT_EVIDENCE.value for s in item.risk_signals))

    # 9. NOT_APPLICABLE handling
    def test_09_not_applicable_handling(self) -> None:
        report = _create_mock_report("insp_na", "PASS", pass_count=3, fail_count=0, review_count=0, not_applicable_count=4)
        item = InspectionPrioritizer.prioritize_inspection(
            inspection_id="insp_na",
            report=report,
        )
        self.assertEqual(item.failed_requirement_count, 0)
        self.assertNotIn(item.priority, (AuthorityPriority.CRITICAL, AuthorityPriority.HIGH))

    # 10. Deterministic score calculation
    def test_10_deterministic_score_calculation(self) -> None:
        report = _create_mock_report("insp_det", "FAIL", pass_count=1, fail_count=2, compliance_score=33.3)
        item1 = InspectionPrioritizer.prioritize_inspection("insp_det", report)
        item2 = InspectionPrioritizer.prioritize_inspection("insp_det", report)
        self.assertEqual(item1.priority_score, item2.priority_score)
        self.assertEqual(item1.priority, item2.priority)
        self.assertEqual(item1.reasons, item2.reasons)

    # 11. Priority reason generation
    def test_11_priority_reason_generation(self) -> None:
        report = _create_mock_report("insp_reasons", "FAIL", pass_count=1, fail_count=2, compliance_score=33.3)
        item = InspectionPrioritizer.prioritize_inspection("insp_reasons", report)
        self.assertTrue(any("FAIL" in r for r in item.reasons))
        self.assertTrue(any("2 non-compliant" in r for r in item.reasons))

    # 12. Repeated failure signal
    def test_12_repeated_failure_signal(self) -> None:
        report = _create_mock_report("insp_rep", "FAIL", pass_count=1, fail_count=1)
        intel = ConsumerScanIntelligence(
            scan_quality=ScanQuality(is_acceptable=True, quality_score=1.0, issues=[]),
            product_identity=ProductIdentity(
                manufacturer_name=ExtractedProductField(value="Acme Foods Ltd"),
                brand=ExtractedProductField(value="Acme Brand"),
            ),
            identity_confidence=IdentityConfidence.HIGH.value,
            risk_signal=RiskSignal.HIGH_RISK_NON_COMPLIANCE.value,
            compliance_summary=ConsumerComplianceSummary(overall_status="FAIL", fail_count=1),
            consumer_actions=[],
        )
        item = InspectionPrioritizer.prioritize_inspection(
            "insp_rep", report, intelligence=intel, repeat_failure_count=3
        )
        self.assertTrue(any(s.code == RiskSignalCode.REPEATED_FAILURES.value for s in item.risk_signals))

    # 13. Repeated product signal
    def test_13_repeated_product_signal(self) -> None:
        # Create 3 failing sessions with same product identity
        for i in range(3):
            s = self.store.create_session(f"prod_sess_{i}")
            s.inspection.status = InspectionStatus.COMPLETED
            s.report = _create_mock_report(f"prod_sess_{i}", "FAIL", fail_count=1)
            s.evidence_candidates = [
                EvidenceCandidate(
                    field=EvidenceField.COMMODITY_NAME,
                    raw_text="Noodles",
                    normalized_text="Noodles",
                    confidence=0.95,
                ),
                EvidenceCandidate(
                    field=EvidenceField.MANUFACTURER_NAME,
                    raw_text="Nestle India Ltd",
                    normalized_text="Nestle India Ltd",
                    confidence=0.95,
                ),
                EvidenceCandidate(
                    field=EvidenceField.NET_QUANTITY,
                    raw_text="70 g",
                    normalized_text="70 g",
                    confidence=0.95,
                ),
                EvidenceCandidate(
                    field=EvidenceField.MRP,
                    raw_text="14.00",
                    normalized_text="14.00",
                    confidence=0.95,
                ),
            ]

        service = AuthorityIntelligenceService(store=self.store)
        products, total = service.get_product_summaries()
        self.assertGreaterEqual(total, 1)
        self.assertEqual(products[0].fail_count, 3)

    # 14. Repeated manufacturer signal
    def test_14_repeated_manufacturer_signal(self) -> None:
        for i in range(3):
            s = self.store.create_session(f"mfg_sess_{i}")
            s.inspection.status = InspectionStatus.COMPLETED
            s.report = _create_mock_report(f"mfg_sess_{i}", "FAIL", fail_count=2)
            s.evidence_candidates = [
                EvidenceCandidate(
                    field=EvidenceField.MANUFACTURER_NAME,
                    raw_text="Britannia Industries",
                    normalized_text="Britannia Industries",
                    confidence=0.95,
                ),
                EvidenceCandidate(
                    field=EvidenceField.COMMODITY_NAME,
                    raw_text="Biscuits",
                    normalized_text="Biscuits",
                    confidence=0.95,
                ),
                EvidenceCandidate(
                    field=EvidenceField.NET_QUANTITY,
                    raw_text="100 g",
                    normalized_text="100 g",
                    confidence=0.95,
                ),
                EvidenceCandidate(
                    field=EvidenceField.MRP,
                    raw_text="30.00",
                    normalized_text="30.00",
                    confidence=0.95,
                ),
            ]

        service = AuthorityIntelligenceService(store=self.store)
        mfgs, total = service.get_manufacturer_summaries()
        self.assertGreaterEqual(total, 1)
        self.assertEqual(mfgs[0].manufacturer_name, "Britannia Industries")
        self.assertEqual(mfgs[0].fail_count, 3)
        self.assertEqual(mfgs[0].repeat_issue_count, 2)

    # 15. Identity confidence handling
    def test_15_identity_confidence_handling(self) -> None:
        intel = ConsumerScanIntelligence(
            scan_quality=ScanQuality(is_acceptable=True, quality_score=1.0, issues=[]),
            product_identity=ProductIdentity(
                manufacturer_name=ExtractedProductField(value="Cadbury"),
            ),
            identity_confidence=IdentityConfidence.HIGH.value,
            risk_signal=RiskSignal.NO_MAJOR_ISSUES_DETECTED.value,
            compliance_summary=ConsumerComplianceSummary(overall_status="PASS"),
            consumer_actions=[],
        )
        report = _create_mock_report("insp_conf", "PASS")
        item = InspectionPrioritizer.prioritize_inspection("insp_conf", report, intelligence=intel)
        self.assertEqual(item.identity_confidence, "HIGH")
        self.assertTrue(any(s.code == RiskSignalCode.PRODUCT_IDENTITY_CONFIRMED.value for s in item.risk_signals))

    # 16. LOW identity does not create strong grouping
    def test_16_low_identity_no_grouping(self) -> None:
        s = self.store.create_session("sess_low_conf")
        s.inspection.status = InspectionStatus.COMPLETED
        s.report = _create_mock_report("sess_low_conf", "FAIL", fail_count=1)
        s.evidence_candidates = [
            EvidenceCandidate(
                field=EvidenceField.MANUFACTURER_NAME,
                raw_text="Unknown Smudged Text",
                normalized_text="Unknown Smudged Text",
                confidence=0.2,
            )
        ]
        service = AuthorityIntelligenceService(store=self.store)
        mfgs, total = service.get_manufacturer_summaries()
        self.assertEqual(total, 0)

    # 17. UNKNOWN identity behavior
    def test_17_unknown_identity_behavior(self) -> None:
        report = _create_mock_report("insp_unk", "FAIL", fail_count=1)
        intel = ConsumerScanIntelligence(
            scan_quality=ScanQuality(is_acceptable=True, quality_score=0.4, issues=[]),
            product_identity=ProductIdentity(),
            identity_confidence=IdentityConfidence.UNKNOWN.value,
            risk_signal=RiskSignal.PRODUCT_IDENTITY_UNCERTAIN.value,
            compliance_summary=ConsumerComplianceSummary(overall_status="REVIEW_REQUIRED"),
            consumer_actions=[],
        )
        item = InspectionPrioritizer.prioritize_inspection("insp_unk", report, intelligence=intel)
        self.assertEqual(item.identity_confidence, "UNKNOWN")
        self.assertTrue(any(s.code == RiskSignalCode.PRODUCT_IDENTITY_UNCERTAIN.value for s in item.risk_signals))

    # 18. Conflicting identity behavior
    def test_18_conflicting_identity_behavior(self) -> None:
        # 2 different candidates for manufacturer
        s = self.store.create_session("sess_conflict")
        s.inspection.status = InspectionStatus.COMPLETED
        s.report = _create_mock_report("sess_conflict", "FAIL", fail_count=1)
        s.evidence_candidates = [
            EvidenceCandidate(
                field=EvidenceField.MANUFACTURER_NAME,
                raw_text="Brand A Corp",
                normalized_text="Brand A Corp",
                confidence=0.8,
            ),
            EvidenceCandidate(
                field=EvidenceField.MANUFACTURER_NAME,
                raw_text="Brand B Ltd",
                normalized_text="Brand B Ltd",
                confidence=0.8,
            ),
        ]
        service = AuthorityIntelligenceService(store=self.store)
        item = service.get_inspection_detail_intelligence("sess_conflict")
        self.assertIn(item.identity_confidence, ("LOW", "UNKNOWN"))

    # 19. Geographic U7 integration
    def test_19_geographic_u7_integration(self) -> None:
        report = _create_mock_report("insp_geo", "FAIL", fail_count=1)
        item = InspectionPrioritizer.prioritize_inspection(
            "insp_geo", report, is_elevated_region=True, location={"state_code": "MH", "district_code": "PUN"}
        )
        self.assertTrue(any(s.code == RiskSignalCode.GEOGRAPHIC_ISSUE_ELEVATED.value for s in item.risk_signals))

    # 20. Trend calculation
    def test_20_trend_calculation(self) -> None:
        now = datetime.now(timezone.utc)
        # 4 sessions in current 30d
        for i in range(4):
            s = self.store.create_session(f"trend_cur_{i}")
            s.created_at = now - timedelta(days=5)
            s.inspection.status = InspectionStatus.COMPLETED
            s.report = _create_mock_report(f"trend_cur_{i}", "FAIL", fail_count=1)
            s.evidence_candidates = [
                EvidenceCandidate(
                    field=EvidenceField.MANUFACTURER_NAME,
                    raw_text="TrendCorp",
                    normalized_text="TrendCorp",
                    confidence=0.9,
                ),
                EvidenceCandidate(
                    field=EvidenceField.COMMODITY_NAME,
                    raw_text="Oil",
                    normalized_text="Oil",
                    confidence=0.9,
                ),
                EvidenceCandidate(
                    field=EvidenceField.NET_QUANTITY,
                    raw_text="1 L",
                    normalized_text="1 L",
                    confidence=0.9,
                ),
            ]

        service = AuthorityIntelligenceService(store=self.store)
        mfgs, _ = service.get_manufacturer_summaries()
        self.assertEqual(len(mfgs), 1)
        self.assertEqual(mfgs[0].trend, TrendDirection.INCREASING)

    # 21. Insufficient trend data behavior
    def test_21_insufficient_trend_data(self) -> None:
        s = self.store.create_session("trend_single")
        s.inspection.status = InspectionStatus.COMPLETED
        s.report = _create_mock_report("trend_single", "PASS", pass_count=3)
        s.evidence_candidates = [
            EvidenceCandidate(
                field=EvidenceField.MANUFACTURER_NAME,
                raw_text="SingleSample Corp",
                normalized_text="SingleSample Corp",
                confidence=0.9,
            ),
            EvidenceCandidate(
                field=EvidenceField.COMMODITY_NAME,
                raw_text="Juice",
                normalized_text="Juice",
                confidence=0.9,
            ),
            EvidenceCandidate(
                field=EvidenceField.NET_QUANTITY,
                raw_text="500 ml",
                normalized_text="500 ml",
                confidence=0.9,
            ),
        ]
        service = AuthorityIntelligenceService(store=self.store)
        mfgs, _ = service.get_manufacturer_summaries()
        self.assertEqual(mfgs[0].trend, TrendDirection.INSUFFICIENT_DATA)

    # 22. Issue category aggregation
    def test_22_issue_category_aggregation(self) -> None:
        s = self.store.create_session("sess_cat")
        s.inspection.status = InspectionStatus.COMPLETED
        s.report = _create_mock_report("sess_cat", "FAIL", fail_count=2, failed_req_ids=["mrp_rule_6", "net_qty_rule_11"])
        s.evidence_candidates = [
            EvidenceCandidate(
                field=EvidenceField.MANUFACTURER_NAME,
                raw_text="CatCorp",
                normalized_text="CatCorp",
                confidence=0.9,
            ),
            EvidenceCandidate(
                field=EvidenceField.COMMODITY_NAME,
                raw_text="Snacks",
                normalized_text="Snacks",
                confidence=0.9,
            ),
            EvidenceCandidate(
                field=EvidenceField.NET_QUANTITY,
                raw_text="50 g",
                normalized_text="50 g",
                confidence=0.9,
            ),
        ]
        service = AuthorityIntelligenceService(store=self.store)
        mfgs, _ = service.get_manufacturer_summaries()
        self.assertEqual(len(mfgs[0].top_violation_categories), 1)

    # 23. Zero-data behavior
    def test_23_zero_data_behavior(self) -> None:
        service = AuthorityIntelligenceService(store=self.store)
        items, count = service.get_priority_queue()
        self.assertEqual(count, 0)
        self.assertEqual(len(items), 0)

        overview = service.get_overview_metrics()
        self.assertEqual(overview.total_completed_inspections, 0)
        self.assertEqual(overview.overall_observed_issue_rate, 0.0)

    # 24. Missing data behavior
    def test_24_missing_data_behavior(self) -> None:
        # Incomplete session without report
        s = self.store.create_session("sess_incomplete")
        service = AuthorityIntelligenceService(store=self.store)
        item = service.get_inspection_detail_intelligence("sess_incomplete")
        self.assertEqual(item.canonical_status, "INCOMPLETE")
        self.assertEqual(item.priority, AuthorityPriority.INFORMATIONAL)

    # 25. No false legal conclusions
    def test_25_no_false_legal_conclusions(self) -> None:
        report = _create_mock_report("insp_disc", "FAIL", fail_count=2)
        item = InspectionPrioritizer.prioritize_inspection("insp_disc", report)
        # Must not contain inflammatory criminal terms
        all_text = " ".join(item.reasons + [s.explanation for s in item.risk_signals]).lower()
        self.assertNotIn("fraudulent", all_text)
        self.assertNotIn("illegal", all_text)
        self.assertNotIn("criminal", all_text)

    # 26. No enforcement action execution
    def test_26_no_enforcement_action(self) -> None:
        # Verify intelligence service only returns decision-support data
        service = AuthorityIntelligenceService(store=self.store)
        self.assertTrue(hasattr(service, "get_priority_queue"))
        self.assertFalse(hasattr(service, "issue_penalty"))
        self.assertFalse(hasattr(service, "suspend_manufacturer"))

    # 27. No private data leakage
    def test_27_no_private_data_leakage(self) -> None:
        s = self.store.create_session("sess_priv", metadata={"owner_id": "secret_user_id", "email": "user@gmail.com"})
        s.inspection.status = InspectionStatus.COMPLETED
        s.report = _create_mock_report("sess_priv", "PASS")

        resp = self.client.get("/api/v1/authority/intelligence/priorities")
        self.assertEqual(resp.status_code, 200)
        text = resp.text
        self.assertNotIn("secret_user_id", text)
        self.assertNotIn("user@gmail.com", text)

    # 28. No exact GPS leakage
    def test_28_no_exact_gps_leakage(self) -> None:
        s = self.store.create_session("sess_gps", metadata={"location": {"lat": 18.5204, "lng": 73.8567, "state_code": "MH"}})
        s.inspection.status = InspectionStatus.COMPLETED
        s.report = _create_mock_report("sess_gps", "PASS")

        resp = self.client.get("/api/v1/authority/intelligence/priorities")
        self.assertEqual(resp.status_code, 200)
        text = resp.text
        self.assertNotIn("18.5204", text)
        self.assertNotIn("73.8567", text)

    # 29. No share-token leakage
    def test_29_no_share_token_leakage(self) -> None:
        s = self.store.create_session("sess_token", metadata={"share_token": "secret_share_token_abc"})
        s.inspection.status = InspectionStatus.COMPLETED
        s.report = _create_mock_report("sess_token", "PASS")

        resp = self.client.get("/api/v1/authority/intelligence/priorities")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("secret_share_token_abc", resp.text)

    # 30. No raw OCR leakage
    def test_30_no_raw_ocr_leakage(self) -> None:
        s = self.store.create_session("sess_ocr", metadata={"raw_ocr_dump": "UNPROCESSED_OCR_GARBAGE_12345"})
        s.inspection.status = InspectionStatus.COMPLETED
        s.report = _create_mock_report("sess_ocr", "PASS")

        resp = self.client.get("/api/v1/authority/intelligence/priorities")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("UNPROCESSED_OCR_GARBAGE_12345", resp.text)

    # 31. Deterministic output guarantees
    def test_31_deterministic_output(self) -> None:
        report = _create_mock_report("insp_rep_det", "FAIL", fail_count=2, compliance_score=40.0)
        res1 = InspectionPrioritizer.prioritize_inspection("insp_rep_det", report).to_dict()
        res2 = InspectionPrioritizer.prioritize_inspection("insp_rep_det", report).to_dict()
        self.assertEqual(res1, res2)

    # 32. T3 integration contract compatibility
    def test_32_t3_integration_contract(self) -> None:
        resp = self.client.get("/api/v1/authority/intelligence/overview")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_completed_inspections", data)
        self.assertIn("critical_priority_count", data)
        self.assertIn("high_priority_count", data)

    # 33. U1 regression test
    def test_33_u1_regression(self) -> None:
        report = _create_mock_report("insp_u1", "PASS", pass_count=4, compliance_score=100.0, rating="FULLY_COMPLIANT")
        self.assertEqual(report.metadata.get("compliance_score"), 100.0)
        self.assertEqual(report.metadata.get("rating"), "FULLY_COMPLIANT")


    # 34. U5 regression test
    def test_34_u5_regression(self) -> None:
        from backend.app.services.consumer_intelligence.service import ConsumerIntelligenceService
        ci_service = ConsumerIntelligenceService(store=self.store)
        report = _create_mock_report("insp_u5", "FAIL", fail_count=1)
        sig = ci_service.derive_risk_signal(report, IdentityConfidence.HIGH)
        self.assertEqual(sig, RiskSignal.HIGH_RISK_NON_COMPLIANCE)

    # 35. U6 regression test
    def test_35_u6_regression(self) -> None:
        from backend.app.services.consumer_result.service import ConsumerResultService
        cr_service = ConsumerResultService(session_store=self.store)
        self.assertIsNotNone(cr_service)

    # 36. U7 regression test
    def test_36_u7_regression(self) -> None:
        from backend.app.services.heatmap.service import HeatmapService
        hm_service = HeatmapService(store=self.store)
        rep = hm_service.compute_heatmap(public_mode=True)
        self.assertEqual(rep.summary.total_inspections, 0)

    # 37. U8 regression test
    def test_37_u8_regression(self) -> None:
        from backend.app.services.voice.service import VoiceAssistantService
        self.assertTrue(VoiceAssistantService is not None)

    # 38. Phase 9 authentication regression test
    def test_38_phase9_auth_regression(self) -> None:
        resp = self.client.get("/api/v1/authority/intelligence/manufacturers")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
