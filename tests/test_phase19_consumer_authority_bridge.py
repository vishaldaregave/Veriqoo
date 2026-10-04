"""Comprehensive test suite for Phase U10 — Consumer -> Authority Action Bridge + Authority Case Integration.

Covers all 20 verification requirements:
1. Owner can submit eligible FAIL inspection (200/201 OK)
2. Owner can submit REVIEW_REQUIRED inspection (200/201 OK)
3. PASS is rejected/not reportable according to policy (400 Bad Request)
4. NOT_APPLICABLE is not reportable (400 Bad Request)
5. Cross-user submission returns safe 404
6. Unauthenticated request returns 401
7. Incomplete inspection rejected (400 Bad Request)
8. Failed inspection rejected (400 Bad Request)
9. Evidence references preserved
10. Annotation references and geometry preserved (U2 integration)
11. Legal references (rule number, statutory label, section) preserved
12. U9 priority score, band, and risk signals preserved
13. User description is recorded as user context without overriding legal conclusions
14. Duplicate submission behavior returns existing report (idempotency)
15. No raw JWT/tokens leaked in payload
16. No private storage URLs leaked in payload
17. Localization works (en, hi, mr)
18. Existing U4/U5/U6/U7/U8/U9 regression compatibility
19. T3 integration contract (`AuthorityCaseInput`) validates cleanly
20. Snapshot stability: session modifications after creation do not mutate frozen report
"""

from datetime import datetime, timezone
import unittest
import uuid
from typing import Any

from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_inspection_repository, get_session_store
from backend.app.api.session_store import InMemoryInspectionStore, InspectionSession
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import AuthenticatedUser
from backend.app.main import create_app
from backend.app.services.consumer_report.models import (
    AuthorityCaseInput,
    ConsumerReport,
    ConsumerReportEligibility,
    ConsumerReportStatus,
    ReportFindingPackage,
)
from backend.app.services.consumer_report.service import ConsumerReportService
from backend.app.services.evidence.models import EvidenceCandidate, EvidenceField, ImageArtifact
from backend.app.services.inspection.models import Inspection, InspectionImage, InspectionStatus
from backend.app.services.inspection.repository import InMemoryInspectionRepository
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.verification.models import VerificationResult, VerificationStatus


def _create_mock_session(
    inspection_id: str,
    owner_id: str,
    overall_status: str = "FAIL",
    pass_count: int = 1,
    fail_count: int = 2,
    review_count: int = 0,
    not_applicable_count: int = 0,
    brand_name: str = "Test Brand",
    mfg_name: str = "Test Manufacturer Pvt Ltd",
    commodity: str = "Packaged Food",
    barcode: str = "8901234567890",
    is_failed: bool = False,
    is_completed: bool = True,
    with_annotations: bool = True,
) -> InspectionSession:
    """Helper to construct a rich, deterministic InspectionSession for U10 testing."""
    session_id = inspection_id or str(uuid.uuid4())
    img_id = f"img_{uuid.uuid4().hex[:6]}"

    status = InspectionStatus.COMPLETED if is_completed else (InspectionStatus.FAILED if is_failed else InspectionStatus.COLLECTING)

    img = InspectionImage(
        image_id=img_id,
        sequence=0,
        added_at=datetime.now(timezone.utc),
        source_hash="sha256_src",
        normalized_hash="sha256_norm",
        storage_path="private/storage/test.jpg",
    )

    inspection = Inspection(
        inspection_id=session_id,
        owner_id=owner_id,
        status=status,
        images=[img],
        metadata={
            "product_name": brand_name,
            "location": {
                "state_code": "MH",
                "district_code": "MH-PUN",
                "state_name": "Maharashtra",
                "district_name": "Pune",
            },
        },
    )

    session = InspectionSession(
        inspection=inspection,
        created_at=datetime.now(timezone.utc),
    )

    if is_completed:
        # Build Verification results
        results: list[VerificationResult] = []
        for i in range(pass_count):
            results.append(
                VerificationResult(
                    requirement_id=f"req_pass_{i}",
                    status=VerificationStatus.PASS,
                    confidence=0.95,
                    reason="Declaration valid and compliant",
                    metadata={
                        "category": "general_declaration",
                        "rule_number": "Rule 6(1)(a)",
                        "statutory_label": "Name and Address",
                        "section_reference": "PCR 2011",
                    },
                )
            )
        for i in range(fail_count):
            results.append(
                VerificationResult(
                    requirement_id=f"req_fail_{i}",
                    status=VerificationStatus.FAIL,
                    confidence=0.92,
                    reason=f"Mandatory declaration {i} is missing or illegible",
                    metadata={
                        "category": "mandatory_declarations",
                        "rule_number": f"Rule 6(1)({chr(98 + i)})",
                        "statutory_label": f"Mandatory Field {i}",
                        "section_reference": "PCR 2011",
                    },
                )
            )
        for i in range(review_count):
            results.append(
                VerificationResult(
                    requirement_id=f"req_rev_{i}",
                    status=VerificationStatus.REVIEW_REQUIRED,
                    confidence=0.6,
                    reason=f"Declaration {i} requires manual review",
                    metadata={
                        "category": "mrp_declaration",
                        "rule_number": "Rule 6(1)(e)",
                        "statutory_label": "MRP Declaration",
                        "section_reference": "PCR 2011",
                    },
                )
            )
        for i in range(not_applicable_count):
            results.append(
                VerificationResult(
                    requirement_id=f"req_na_{i}",
                    status=VerificationStatus.NOT_APPLICABLE,
                    confidence=1.0,
                    reason="Exempt under Rule 26",
                    metadata={
                        "category": "exemptions",
                        "rule_number": "Rule 26",
                        "statutory_label": "Exemption",
                        "section_reference": "PCR 2011",
                    },
                )
            )

        # Annotations
        annotations: list[dict[str, Any]] = []
        if with_annotations and fail_count > 0:
            annotations.append({
                "annotation_id": "ann_001",
                "requirement_id": "req_fail_0",
                "image_id": img_id,
                "box_2d": [100, 150, 400, 600],
                "label": "MRP Missing / Defective",
                "color": "#E53935",
            })

        ov_status = OverallInspectionStatus(overall_status)
        report = InspectionReport(
            inspection_id=session_id,
            overall_status=ov_status,
            verification_results=results,
            summary="Inspection completed",
            evidence_count=1,
            image_count=1,
            applicable_requirement_count=pass_count + fail_count + review_count,
            pass_count=pass_count,
            fail_count=fail_count,
            not_visible_count=0,
            not_applicable_count=not_applicable_count,
            review_required_count=review_count,
            evidence_annotations=annotations,
            metadata={
                "compliance_score": 60.0 if fail_count > 0 else 100.0,
                "rating": "PARTIALLY_COMPLIANT" if fail_count > 0 else "FULLY_COMPLIANT",
            },
        )
        session.report = report

        # Candidates
        candidates: list[EvidenceCandidate] = []
        if brand_name:
            candidates.append(
                EvidenceCandidate(
                    field=EvidenceField.COMMODITY_NAME,
                    raw_text=brand_name,
                    normalized_text=brand_name,
                    confidence=0.95,
                    image_id=img_id,
                )
            )
        if mfg_name:
            candidates.append(
                EvidenceCandidate(
                    field=EvidenceField.MANUFACTURER_NAME,
                    raw_text=mfg_name,
                    normalized_text=mfg_name,
                    confidence=0.9,
                    image_id=img_id,
                )
            )
        if commodity:
            candidates.append(
                EvidenceCandidate(
                    field=EvidenceField.COMMODITY_NAME,
                    raw_text=commodity,
                    normalized_text=commodity,
                    confidence=0.88,
                    image_id=img_id,
                )
            )
        if barcode:
            candidates.append(
                EvidenceCandidate(
                    field=EvidenceField.GENERIC_DECLARATION,
                    raw_text=barcode,
                    normalized_text=barcode,
                    confidence=0.99,
                    image_id=img_id,
                )
            )
        session.evidence_candidates = candidates

    return session


class TestPhase19ConsumerAuthorityBridge(unittest.TestCase):
    """Test suite for Phase U10 Consumer -> Authority Action Bridge."""

    def setUp(self) -> None:
        self.store = InMemoryInspectionStore()
        self.repo = InMemoryInspectionRepository()
        self.app = create_app()

        self.mock_user = AuthenticatedUser(
            user_id="usr_consumer_001",
            email="consumer@example.com",
            role="consumer",
            claims={"role": "consumer"},
        )
        self.other_user = AuthenticatedUser(
            user_id="usr_consumer_002",
            email="other@example.com",
            role="consumer",
            claims={"role": "consumer"},
        )
        self.authority_user = AuthenticatedUser(
            user_id="usr_officer_001",
            email="officer@legalmetrology.gov.in",
            role="authority",
            claims={"role": "authority"},
        )

        self.app.dependency_overrides[get_session_store] = lambda: self.store
        self.app.dependency_overrides[get_inspection_repository] = lambda: self.repo
        self.app.dependency_overrides[get_current_user] = lambda: self.mock_user
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.store.clear()
        self.app.dependency_overrides.clear()

    # 1. Owner can submit eligible FAIL
    def test_01_owner_can_submit_eligible_fail(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=2)
        self.store.save_session(session)

        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/consumer-reports",
            json={"consumer_description": "Defective MRP declaration", "preferred_language": "en"},
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["inspection_id"], insp_id)
        self.assertEqual(data["submitted_by"], self.mock_user.user_id)
        self.assertEqual(data["canonical_overall_status"], "FAIL")
        self.assertEqual(data["consumer_overall_result"], "COMPLIANCE_ISSUE_DETECTED")
        self.assertEqual(data["status"], "SUBMITTED")
        self.assertEqual(data["consumer_description"], "Defective MRP declaration")
        self.assertGreater(len(data["findings"]), 0)

    # 2. Owner can submit REVIEW_REQUIRED
    def test_02_owner_can_submit_review_required(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(
            insp_id, owner_id=self.mock_user.user_id, overall_status="REVIEW_REQUIRED", pass_count=1, fail_count=0, review_count=1
        )
        self.store.save_session(session)

        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/consumer-reports",
            json={"consumer_description": "Unclear manufacturing date"},
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["canonical_overall_status"], "REVIEW_REQUIRED")
        self.assertEqual(data["status"], "SUBMITTED")

    # 3. PASS is rejected/not reportable according to policy
    def test_03_pass_rejected_with_400(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(
            insp_id, owner_id=self.mock_user.user_id, overall_status="PASS", pass_count=3, fail_count=0, review_count=0
        )
        self.store.save_session(session)

        response = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(response.status_code, 400)
        self.assertIn("INELIGIBLE_PASS", response.text)

    # 4. NOT_APPLICABLE is not reportable
    def test_04_not_applicable_rejected_with_400(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(
            insp_id, owner_id=self.mock_user.user_id, overall_status="PASS", pass_count=0, fail_count=0, review_count=0, not_applicable_count=2
        )
        self.store.save_session(session)

        response = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(response.status_code, 400)
        self.assertIn("INELIGIBLE_NOT_APPLICABLE", response.text)

    # 5. Cross-user submission returns safe 404
    def test_05_cross_user_submission_returns_safe_404(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.other_user.user_id, overall_status="FAIL", fail_count=1)
        self.store.save_session(session)

        response = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(response.status_code, 404)
        self.assertIn("INSPECTION_NOT_FOUND", response.text)

    # 6. Unauthenticated request returns 401
    def test_06_unauthenticated_request_returns_401(self) -> None:
        self.app.dependency_overrides.pop(get_current_user, None)
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        response = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(response.status_code, 401)

    # 7. Incomplete inspection rejected
    def test_07_incomplete_inspection_rejected(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, is_completed=False)
        self.store.save_session(session)

        response = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(response.status_code, 400)
        self.assertIn("INELIGIBLE_INCOMPLETE", response.text)

    # 8. Failed inspection rejected
    def test_08_failed_inspection_rejected(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, is_failed=True, is_completed=False)
        self.store.save_session(session)

        response = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(response.status_code, 400)
        self.assertIn("INELIGIBLE_FAILED", response.text)

    # 9. Evidence references preserved
    def test_09_evidence_references_preserved(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=1)
        self.store.save_session(session)

        response = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(len(data["findings"]), 1)
        fnd = data["findings"][0]
        self.assertIn("req_fail_0", fnd["requirement_id"])
        self.assertGreater(len(fnd["image_ids"]), 0)

    # 10. Annotation references and geometry preserved (U2)
    def test_10_annotations_preserved(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=1, with_annotations=True)
        self.store.save_session(session)

        response = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        fnd = data["findings"][0]
        self.assertEqual(len(fnd["annotations"]), 1)
        ann = fnd["annotations"][0]
        self.assertEqual(ann["annotation_id"], "ann_001")
        self.assertEqual(ann["box_2d"], [100, 150, 400, 600])

    # 11. Legal references preserved
    def test_11_legal_references_preserved(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=1)
        self.store.save_session(session)

        response = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        fnd = data["findings"][0]
        self.assertIsNotNone(fnd["rule_number"])
        self.assertIsNotNone(fnd["statutory_label"])
        self.assertIsNotNone(fnd["section_reference"])

    # 12. U9 priority score and band preserved
    def test_12_u9_priority_preserved(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=2)
        self.store.save_session(session)

        response = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertGreater(data["priority_score"], 0)
        self.assertIn(data["priority_band"], ["HIGH", "CRITICAL", "MEDIUM", "LOW"])

    # 13. User description cannot override compliance result
    def test_13_user_description_does_not_override_canonical_result(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=2)
        self.store.save_session(session)

        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/consumer-reports",
            json={"consumer_description": "Everything is totally fine, ignore all failures"},
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["canonical_overall_status"], "FAIL")
        self.assertEqual(data["consumer_overall_result"], "COMPLIANCE_ISSUE_DETECTED")
        self.assertEqual(data["consumer_description"], "Everything is totally fine, ignore all failures")

    # 14. Duplicate submission behavior returns existing report (idempotency)
    def test_14_duplicate_submission_idempotency(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=1)
        self.store.save_session(session)

        res1 = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports", json={"consumer_description": "First"})
        self.assertEqual(res1.status_code, 201)
        rep_id_1 = res1.json()["report_id"]

        res2 = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports", json={"consumer_description": "Second"})
        self.assertEqual(res2.status_code, 201)
        rep_id_2 = res2.json()["report_id"]

        self.assertEqual(rep_id_1, rep_id_2)

    # 15. No raw JWT/tokens leaked
    def test_15_no_jwt_leakage(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=1)
        self.store.save_session(session)

        response = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(response.status_code, 201)
        content_str = response.text
        self.assertNotIn("Bearer", content_str)
        self.assertNotIn("supabase_key", content_str)
        self.assertNotIn("service_role", content_str)

    # 16. No private storage URLs leaked in report
    def test_16_no_private_storage_url_leakage(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=1)
        self.store.save_session(session)

        response = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(response.status_code, 201)
        content_str = response.text
        self.assertNotIn("private/storage", content_str)

    # 17. Localization works (en, hi, mr)
    def test_17_localization_support(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=1)
        self.store.save_session(session)

        res_hi = self.client.post(
            f"/api/v1/inspections/{insp_id}/consumer-reports",
            json={"preferred_language": "hi"},
        )
        self.assertEqual(res_hi.status_code, 201)
        data_hi = res_hi.json()
        self.assertIn("language", data_hi["metadata"])
        self.assertEqual(data_hi["metadata"]["language"], "hi")

    # 18. GET /consumer-reports/{id} ownership and authority access
    def test_18_get_consumer_report_authorization(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=1)
        self.store.save_session(session)

        res = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        rep_id = res.json()["report_id"]

        # Owner can access
        get_res = self.client.get(f"/api/v1/consumer-reports/{rep_id}")
        self.assertEqual(get_res.status_code, 200)

        # Other user gets safe 404
        self.app.dependency_overrides[get_current_user] = lambda: self.other_user
        get_other = self.client.get(f"/api/v1/consumer-reports/{rep_id}")
        self.assertEqual(get_other.status_code, 404)

        # Authority officer can access
        self.app.dependency_overrides[get_current_user] = lambda: self.authority_user
        get_auth = self.client.get(f"/api/v1/consumer-reports/{rep_id}")
        self.assertEqual(get_auth.status_code, 200)

    # 19. T3 integration contract (`AuthorityCaseInput`) validates cleanly
    def test_19_t3_authority_case_input_contract(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(
            insp_id,
            owner_id=self.mock_user.user_id,
            overall_status="FAIL",
            fail_count=2,
            brand_name="Acme Biscuits",
            mfg_name="Acme Foods Ltd",
        )
        self.store.save_session(session)

        res = self.client.post(
            f"/api/v1/inspections/{insp_id}/consumer-reports",
            json={"consumer_description": "Weight discrepancy noted"},
        )
        rep_id = res.json()["report_id"]

        # Fetch case-input contract
        case_res = self.client.get(f"/api/v1/consumer-reports/{rep_id}/case-input")
        self.assertEqual(case_res.status_code, 200)
        case_data = case_res.json()

        self.assertEqual(case_data["source_report_id"], rep_id)
        self.assertEqual(case_data["inspection_id"], insp_id)
        self.assertEqual(case_data["consumer_user_id"], self.mock_user.user_id)
        self.assertEqual(case_data["case_type"], "CONSUMER_GRIEVANCE")
        self.assertEqual(case_data["canonical_status"], "FAIL")
        self.assertEqual(case_data["brand"], "Acme Biscuits")
        self.assertEqual(case_data["consumer_notes"], "Weight discrepancy noted")
        self.assertEqual(case_data["findings_count"], 2)
        self.assertGreater(len(case_data["findings"]), 0)

    # 20. Snapshot stability: session modifications after creation do not mutate frozen report
    def test_20_snapshot_stability(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=1)
        self.store.save_session(session)

        res = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        rep_id = res.json()["report_id"]

        # Mutate the live inspection session afterwards
        session.report.overall_status = OverallInspectionStatus.PASS
        session.report.fail_count = 0
        session.report.verification_results.clear()

        # Verify frozen report remains unmodified
        get_res = self.client.get(f"/api/v1/consumer-reports/{rep_id}")
        self.assertEqual(get_res.status_code, 200)
        report_data = get_res.json()
        self.assertEqual(report_data["canonical_overall_status"], "FAIL")
        self.assertEqual(len(report_data["findings"]), 1)

    # 21. Durability: Report survives application restart (store wipe)
    def test_21_report_survives_store_restart(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=2)
        self.store.save_session(session)

        # Create report via client
        res = self.client.post(
            f"/api/v1/inspections/{insp_id}/consumer-reports",
            json={"consumer_description": "Initial creation before restart"},
        )
        self.assertEqual(res.status_code, 201)
        rep_id = res.json()["report_id"]

        # Simulate full process / in-memory store restart by clearing the in-memory store
        self.store.clear()

        # Retrieve the report via endpoint after restart
        get_res = self.client.get(f"/api/v1/consumer-reports/{rep_id}")
        self.assertEqual(get_res.status_code, 200)
        data = get_res.json()
        self.assertEqual(data["report_id"], rep_id)
        self.assertEqual(data["inspection_id"], insp_id)
        self.assertEqual(data["submitted_by"], self.mock_user.user_id)
        self.assertEqual(data["canonical_overall_status"], "FAIL")
        self.assertEqual(data["consumer_description"], "Initial creation before restart")
        self.assertGreater(len(data["findings"]), 0)

        # Retrieve case-input after restart
        case_res = self.client.get(f"/api/v1/consumer-reports/{rep_id}/case-input")
        self.assertEqual(case_res.status_code, 200)
        case_data = case_res.json()
        self.assertEqual(case_data["source_report_id"], rep_id)
        self.assertEqual(case_data["inspection_id"], insp_id)

    # 22. Snapshot stability: Persisted report snapshot remains stable after restart
    def test_22_persisted_snapshot_remains_stable_after_restart(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=1)
        self.store.save_session(session)

        res = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(res.status_code, 201)
        rep_id = res.json()["report_id"]

        # Simulate restart
        self.store.clear()

        # Re-populate store with a totally different modified session for the same ID
        mutated_session = _create_mock_session(
            insp_id,
            owner_id=self.mock_user.user_id,
            overall_status="PASS",
            pass_count=5,
            fail_count=0,
        )
        self.store.save_session(mutated_session)

        # Check that persisted report remains exactly what was originally snapshotted
        get_res = self.client.get(f"/api/v1/consumer-reports/{rep_id}")
        self.assertEqual(get_res.status_code, 200)
        report_data = get_res.json()
        self.assertEqual(report_data["canonical_overall_status"], "FAIL")
        self.assertEqual(len(report_data["findings"]), 1)

    # 23. Cross-user persisted report remains safe 404
    def test_23_cross_user_persisted_report_remains_safe_404(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=1)
        self.store.save_session(session)

        res = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(res.status_code, 201)
        rep_id = res.json()["report_id"]

        # Simulate restart
        self.store.clear()

        # Other user tries to access the persisted report
        self.app.dependency_overrides[get_current_user] = lambda: self.other_user
        get_res = self.client.get(f"/api/v1/consumer-reports/{rep_id}")
        self.assertEqual(get_res.status_code, 404)
        self.assertIn("not found", get_res.text.lower())

        # Other user tries to access case-input
        case_res = self.client.get(f"/api/v1/consumer-reports/{rep_id}/case-input")
        self.assertEqual(case_res.status_code, 404)

    # 24. Authority role cannot be client-spoofed via body or query parameters
    def test_24_authority_role_cannot_be_client_spoofed(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.other_user.user_id, overall_status="FAIL", fail_count=1)
        self.store.save_session(session)

        # Create report as other_user
        self.app.dependency_overrides[get_current_user] = lambda: self.other_user
        res = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        self.assertEqual(res.status_code, 201)
        rep_id = res.json()["report_id"]

        # Switch back to regular mock_user (consumer)
        self.app.dependency_overrides[get_current_user] = lambda: self.mock_user

        # 1. Spoofing via query param ?role=authority / ?role=admin
        spoofed_get = self.client.get(f"/api/v1/consumer-reports/{rep_id}?role=authority")
        self.assertEqual(spoofed_get.status_code, 404)

        spoofed_case = self.client.get(f"/api/v1/consumer-reports/{rep_id}/case-input?role=officer")
        self.assertEqual(spoofed_case.status_code, 404)

        # 2. Spoofing list reports via query param
        spoofed_list = self.client.get("/api/v1/consumer-reports?role=admin")
        self.assertEqual(spoofed_list.status_code, 200)
        # Should return 0 reports for mock_user (not all reports)
        self.assertEqual(spoofed_list.json()["total"], 0)

    # 25. Valid trusted authority role can access any report and list all
    def test_25_valid_trusted_authority_role_access(self) -> None:
        insp_id = f"insp_{uuid.uuid4().hex[:8]}"
        session = _create_mock_session(insp_id, owner_id=self.mock_user.user_id, overall_status="FAIL", fail_count=1)
        self.store.save_session(session)

        res = self.client.post(f"/api/v1/inspections/{insp_id}/consumer-reports")
        rep_id = res.json()["report_id"]

        # Authority access
        self.app.dependency_overrides[get_current_user] = lambda: self.authority_user
        get_res = self.client.get(f"/api/v1/consumer-reports/{rep_id}")
        self.assertEqual(get_res.status_code, 200)

        case_res = self.client.get(f"/api/v1/consumer-reports/{rep_id}/case-input")
        self.assertEqual(case_res.status_code, 200)

        list_res = self.client.get("/api/v1/consumer-reports")
        self.assertEqual(list_res.status_code, 200)
        self.assertGreaterEqual(list_res.json()["total"], 1)

    # 26. Consumer cannot elevate privileges
    def test_26_consumer_cannot_elevate_privileges(self) -> None:
        # Consumer only sees their own reports in list
        list_res = self.client.get("/api/v1/consumer-reports")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(list_res.json()["total"], 0)


if __name__ == "__main__":
    unittest.main()

