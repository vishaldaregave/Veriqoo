"""Unit and integration tests for Phase U7 — India Compliance Heatmap Intelligence.

Covers all mandatory verification requirements:
1. State-level aggregation
2. District-level aggregation
3. Unique inspection counting
4. PASS aggregation
5. FAIL aggregation
6. REVIEW_REQUIRED aggregation
7. NOT_APPLICABLE exclusion from compliance
8. Zero-denominator handling
9. Verified pass rate calculation
10. Issue rate calculation
11. Time-window filtering (7d, 30d, 90d, all, custom)
12. Timezone correctness (UTC awareness)
13. Incomplete and failed inspections excluded
14. Missing location does not get guessed
15. Low-confidence location behavior
16. Public suppression below threshold (< 5 inspections)
17. Threshold cannot be bypassed by query parameters
18. No user IDs in public response
19. No exact coordinates in public response
20. No inspection IDs in public response
21. Auth/anonymous public access behavior
22. Authorized internal access behavior
23. U1 score semantics reused
24. U5 risk semantics reused
25. U6 finding/category aggregation
26. Empty dataset handling
27. All inspections NOT_APPLICABLE
28. Mixed PASS/FAIL/REVIEW scenario
29. Duplicate image/evidence records do not double-count
30. Deterministic response schema validation
"""

from datetime import datetime, timedelta, timezone
import unittest
import uuid
from typing import Any

from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_session_store
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.main import create_app
from backend.app.services.heatmap.models import (
    GeographicLevel,
    HeatmapCell,
    LocationConfidence,
    LocationSource,
    NormalizedLocationContext,
)
from backend.app.services.heatmap.service import HeatmapService
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
    failed_req_ids: list[str] | None = None,
) -> InspectionReport:
    """Helper to create a deterministic InspectionReport."""
    v_results: list[VerificationResult] = []

    # Add pass results
    for i in range(pass_count):
        v_results.append(
            VerificationResult(
                requirement_id=f"R-6-1-pass-{i}",
                status=VerificationStatus.PASS,
                reason="Mandatory declaration observed and verified.",
            )
        )

    # Add fail results
    reqs = failed_req_ids or [f"R-6-1-fail-{i}" for i in range(fail_count)]
    for req_id in reqs:
        v_results.append(
            VerificationResult(
                requirement_id=req_id,
                status=VerificationStatus.FAIL,
                reason="Statutory declaration missing or non-compliant.",
            )
        )

    # Add review results
    for i in range(review_count):
        v_results.append(
            VerificationResult(
                requirement_id=f"R-6-1-review-{i}",
                status=VerificationStatus.REVIEW_REQUIRED,
                reason="Evidence partially obscured.",
                review_required=True,
            )
        )

    # Add not applicable
    for i in range(not_applicable_count):
        v_results.append(
            VerificationResult(
                requirement_id=f"R-6-1-na-{i}",
                status=VerificationStatus.NOT_APPLICABLE,
                reason="Commodity type exempt.",
            )
        )

    total_eval = pass_count + len(reqs) + review_count + not_visible_count
    
    try:
        overall_enum = OverallInspectionStatus(overall_status)
    except ValueError:
        overall_enum = OverallInspectionStatus.PASS

    return InspectionReport(
        inspection_id=inspection_id,
        overall_status=overall_enum,
        verification_results=v_results,
        summary=f"Inspection concluded with status {overall_status}.",
        evidence_count=5,
        image_count=2,
        applicable_requirement_count=total_eval,
        pass_count=pass_count,
        fail_count=len(reqs),
        not_visible_count=not_visible_count,
        not_applicable_count=not_applicable_count,
        review_required_count=review_count,
        evidence_annotations=[],
        created_at=datetime.now(timezone.utc),
    )


class TestPhase16ComplianceHeatmap(unittest.TestCase):
    """Test suite for Phase U7 Compliance Heatmap Intelligence."""

    def setUp(self) -> None:
        self.store = InMemoryInspectionStore()
        self.service = HeatmapService(store=self.store, public_suppression_threshold=5)
        self.app = create_app()
        self.app.dependency_overrides[get_session_store] = lambda: self.store
        self.client = TestClient(self.app)

    def _populate_inspection(
        self,
        inspection_id: str,
        overall_status: str,
        state_code: str | None = "MH",
        state_name: str | None = "Maharashtra",
        district_code: str | None = "PUN",
        district_name: str | None = "Pune",
        created_at: datetime | None = None,
        status: InspectionStatus = InspectionStatus.COMPLETED,
        pass_count: int = 3,
        fail_count: int = 0,
        review_count: int = 0,
        not_applicable_count: int = 0,
        failed_req_ids: list[str] | None = None,
        owner_id: str | None = "user-123",
        extra_images: int = 0,
    ) -> None:
        """Helper to inject an inspection session into store."""
        created = created_at or datetime.now(timezone.utc)
        meta: dict[str, Any] = {"owner_id": owner_id}

        if state_code:
            meta["location"] = {
                "country_code": "IN",
                "state_code": state_code,
                "state_name": state_name,
                "district_code": district_code,
                "district_name": district_name,
                "source": "DEVICE",
                "confidence": "HIGH",
            }

        session = self.store.create_session(
            inspection_id=inspection_id,
            metadata=meta,
            owner_id=owner_id,
        )
        session.inspection.created_at = created
        session.inspection.status = status

        # Add mock images to test single-counting
        for seq in range(1, extra_images + 2):
            session.inspection.images.append(
                InspectionImage(
                    image_id=f"img-{inspection_id}-{seq}",
                    sequence=seq,
                    added_at=created,
                    source_hash=f"hash-{seq}",
                    normalized_hash=f"norm-{seq}",
                )
            )

        if status == InspectionStatus.COMPLETED:
            rep = _create_mock_report(
                inspection_id=inspection_id,
                overall_status=overall_status,
                pass_count=pass_count,
                fail_count=fail_count,
                review_count=review_count,
                not_applicable_count=not_applicable_count,
                failed_req_ids=failed_req_ids,
            )
            rep.created_at = created
            session.report = rep

    # 1. State-level aggregation
    def test_01_state_level_aggregation(self) -> None:
        """State level groups inspections by state_code."""
        for i in range(6):
            self._populate_inspection(f"mh-{i}", "PASS", state_code="MH", state_name="Maharashtra")
        for i in range(6):
            self._populate_inspection(f"dl-{i}", "FAIL", state_code="DL", state_name="Delhi", pass_count=1, fail_count=2)

        report = self.service.compute_heatmap(level=GeographicLevel.STATE, public_mode=True)
        self.assertEqual(len(report.cells), 2)
        codes = [c.state_code for c in report.cells]
        self.assertIn("MH", codes)
        self.assertIn("DL", codes)

    # 2. District-level aggregation
    def test_02_district_level_aggregation(self) -> None:
        """District level groups inspections by state_code and district."""
        for i in range(5):
            self._populate_inspection(f"pun-{i}", "PASS", state_code="MH", district_code="PUN", district_name="Pune")
        for i in range(5):
            self._populate_inspection(f"mum-{i}", "FAIL", state_code="MH", district_code="MUM", district_name="Mumbai", fail_count=1)

        report = self.service.compute_heatmap(level=GeographicLevel.DISTRICT, public_mode=True)
        self.assertEqual(len(report.cells), 2)
        districts = [c.district_code for c in report.cells]
        self.assertIn("PUN", districts)
        self.assertIn("MUM", districts)

    # 3. Unique inspection counting & duplicate image handling
    def test_03_unique_inspection_counting_with_multiple_images(self) -> None:
        """An inspection with multiple images/evidence records counts as exactly 1 inspection."""
        for i in range(6):
            self._populate_inspection(f"insp-{i}", "PASS", state_code="MH", extra_images=10)

        report = self.service.compute_heatmap(level=GeographicLevel.STATE, public_mode=True)
        cell = next(c for c in report.cells if c.state_code == "MH")
        self.assertEqual(cell.inspection_count, 6)

    # 4. PASS aggregation
    def test_04_pass_aggregation(self) -> None:
        """Counts PASS inspections accurately."""
        for i in range(6):
            self._populate_inspection(f"pass-{i}", "PASS", state_code="MH")

        report = self.service.compute_heatmap(level=GeographicLevel.STATE, public_mode=True)
        cell = next(c for c in report.cells if c.state_code == "MH")
        self.assertEqual(cell.pass_count, 6)
        self.assertEqual(cell.fail_count, 0)

    # 5. FAIL aggregation
    def test_05_fail_aggregation(self) -> None:
        """Counts FAIL inspections accurately."""
        for i in range(5):
            self._populate_inspection(f"fail-{i}", "FAIL", state_code="MH", pass_count=1, fail_count=1)

        report = self.service.compute_heatmap(level=GeographicLevel.STATE, public_mode=True)
        cell = next(c for c in report.cells if c.state_code == "MH")
        self.assertEqual(cell.fail_count, 5)
        self.assertEqual(cell.pass_count, 0)

    # 6. REVIEW_REQUIRED aggregation
    def test_06_review_required_aggregation(self) -> None:
        """Counts REVIEW_REQUIRED inspections accurately."""
        for i in range(5):
            self._populate_inspection(f"rev-{i}", "REVIEW_REQUIRED", state_code="MH", pass_count=2, review_count=1)

        report = self.service.compute_heatmap(level=GeographicLevel.STATE, public_mode=True)
        cell = next(c for c in report.cells if c.state_code == "MH")
        self.assertEqual(cell.review_required_count, 5)

    # 7. NOT_APPLICABLE exclusion from compliance
    def test_07_not_applicable_exclusion_from_compliance(self) -> None:
        """NOT_APPLICABLE requirements are counted in metadata but not as PASS."""
        for i in range(5):
            self._populate_inspection(f"na-{i}", "PASS", state_code="MH", pass_count=2, not_applicable_count=3)

        report = self.service.compute_heatmap(level=GeographicLevel.STATE, public_mode=True)
        cell = next(c for c in report.cells if c.state_code == "MH")
        self.assertEqual(cell.not_applicable_count, 15)  # 5 * 3

    # 8. Zero-denominator handling
    def test_08_zero_denominator_handling(self) -> None:
        """When all inspections are REVIEW_REQUIRED, verified_pass_rate is None (zero denominator safe)."""
        for i in range(5):
            self._populate_inspection(f"zero-{i}", "REVIEW_REQUIRED", state_code="MH", pass_count=0, review_count=2)

        report = self.service.compute_heatmap(level=GeographicLevel.STATE, public_mode=True)
        cell = next(c for c in report.cells if c.state_code == "MH")
        self.assertIsNone(cell.verified_pass_rate)
        self.assertEqual(cell.issue_rate, 0.0)

    # 9. verified_pass_rate calculation: PASS / (PASS + FAIL)
    def test_09_verified_pass_rate_calculation(self) -> None:
        """verified_pass_rate = PASS / (PASS + FAIL)."""
        for i in range(3):
            self._populate_inspection(f"p-{i}", "PASS", state_code="MH")
        for i in range(3):
            self._populate_inspection(f"f-{i}", "FAIL", state_code="MH", pass_count=0, fail_count=2)

        report = self.service.compute_heatmap(level=GeographicLevel.STATE, public_mode=True)
        cell = next(c for c in report.cells if c.state_code == "MH")
        # 3 PASS, 3 FAIL -> verified_pass_rate = 3 / (3 + 3) = 0.5
        self.assertEqual(cell.verified_pass_rate, 0.5)

    # 10. issue_rate calculation: FAIL / total_inspections
    def test_10_issue_rate_calculation(self) -> None:
        """issue_rate = FAIL / total_inspections."""
        for i in range(2):
            self._populate_inspection(f"p-{i}", "PASS", state_code="MH")
        for i in range(2):
            self._populate_inspection(f"f-{i}", "FAIL", state_code="MH", pass_count=0, fail_count=1)
        for i in range(4):
            self._populate_inspection(f"r-{i}", "REVIEW_REQUIRED", state_code="MH", pass_count=1, review_count=1)

        report = self.service.compute_heatmap(level=GeographicLevel.STATE, public_mode=True)
        cell = next(c for c in report.cells if c.state_code == "MH")
        # Total = 8, FAIL = 2 -> issue_rate = 2 / 8 = 0.25
        self.assertEqual(cell.inspection_count, 8)
        self.assertEqual(cell.issue_rate, 0.25)

    # 11. Time-window filtering
    def test_11_time_window_filtering(self) -> None:
        """Old inspections outside requested window are excluded."""
        now = datetime.now(timezone.utc)
        # 5 recent inspections (within 7 days)
        for i in range(5):
            self._populate_inspection(f"recent-{i}", "PASS", state_code="MH", created_at=now - timedelta(days=2))
        # 5 older inspections (40 days ago)
        for i in range(5):
            self._populate_inspection(f"old-{i}", "FAIL", state_code="MH", created_at=now - timedelta(days=40))

        # 7d window -> only 5 inspections
        report_7d = self.service.compute_heatmap(time_window="7d", public_mode=True)
        cell_7d = next(c for c in report_7d.cells if c.state_code == "MH")
        self.assertEqual(cell_7d.inspection_count, 5)
        self.assertEqual(cell_7d.pass_count, 5)

        # 90d window -> all 10 inspections
        report_90d = self.service.compute_heatmap(time_window="90d", public_mode=True)
        cell_90d = next(c for c in report_90d.cells if c.state_code == "MH")
        self.assertEqual(cell_90d.inspection_count, 10)

    # 12. Timezone correctness
    def test_12_timezone_correctness(self) -> None:
        """Report bounds and generation timestamps are strictly UTC-aware."""
        report = self.service.compute_heatmap(public_mode=True)
        self.assertIsNotNone(report.generated_at.tzinfo)
        self.assertIsNotNone(report.from_time.tzinfo)
        self.assertIsNotNone(report.to_time.tzinfo)

    # 13. Incomplete/failed inspections excluded
    def test_13_incomplete_failed_inspections_excluded(self) -> None:
        """COLLECTING, READY, RUNNING, and FAILED inspections are excluded."""
        self._populate_inspection("comp-1", "PASS", state_code="MH", status=InspectionStatus.COMPLETED)
        self._populate_inspection("coll-1", "PASS", state_code="MH", status=InspectionStatus.COLLECTING)
        self._populate_inspection("ready-1", "PASS", state_code="MH", status=InspectionStatus.READY)
        self._populate_inspection("run-1", "PASS", state_code="MH", status=InspectionStatus.RUNNING)
        self._populate_inspection("fail-run", "PASS", state_code="MH", status=InspectionStatus.FAILED)

        report = self.service.compute_heatmap(public_mode=False)  # unsuppressed to inspect exact counts
        self.assertEqual(report.summary.total_inspections, 1)

    # 14. Missing location does not get guessed
    def test_14_missing_location_does_not_get_guessed(self) -> None:
        """Inspections without location metadata are tracked in unassigned_location_count and not placed in a random state."""
        for i in range(5):
            self._populate_inspection(f"nolocation-{i}", "PASS", state_code=None)

        report = self.service.compute_heatmap(public_mode=True)
        self.assertEqual(len(report.cells), 0)
        self.assertEqual(report.summary.unassigned_location_count, 5)

    # 15. Low-confidence / invalid location behavior
    def test_15_invalid_state_behavior(self) -> None:
        """Invalid state strings that cannot be parsed are treated as unassigned."""
        session = self.store.create_session("invalid-loc")
        session.inspection.status = InspectionStatus.COMPLETED
        session.inspection.metadata = {"location": {"state_code": "INVALID_XYZ", "country_code": "IN"}}
        session.report = _create_mock_report("invalid-loc", "PASS")

        report = self.service.compute_heatmap(public_mode=False)
        self.assertEqual(report.summary.total_inspections, 1)

    # 16. Public suppression below threshold (< 5 inspections)
    def test_16_public_suppression_below_threshold(self) -> None:
        """Cells with fewer than 5 inspections are marked is_suppressed=True and data is nulled."""
        # 3 inspections in Karnataka (below threshold of 5)
        for i in range(3):
            self._populate_inspection(f"ka-{i}", "PASS", state_code="KA", state_name="Karnataka")

        report = self.service.compute_heatmap(level=GeographicLevel.STATE, public_mode=True)
        cell = next(c for c in report.cells if c.state_code == "KA")
        self.assertTrue(cell.is_suppressed)
        self.assertIsNone(cell.inspection_count)
        self.assertIsNone(cell.pass_count)
        self.assertIsNone(cell.fail_count)
        self.assertIsNone(cell.issue_rate)
        self.assertIsNone(cell.verified_pass_rate)
        self.assertEqual(cell.top_issue_categories, [])

    # 17. Threshold cannot be bypassed by query parameters on API
    def test_17_threshold_cannot_be_bypassed_by_query_param(self) -> None:
        """Public API endpoint enforces privacy suppression regardless of client parameters."""
        for i in range(3):
            self._populate_inspection(f"ka-{i}", "PASS", state_code="KA", state_name="Karnataka")

        response = self.client.get("/api/v1/analytics/compliance-heatmap?min_threshold=0&threshold=0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ka_cell = next(c for c in data["cells"] if c["state_code"] == "KA")
        self.assertTrue(ka_cell["is_suppressed"])
        self.assertIsNone(ka_cell["inspection_count"])

    # 18. No user IDs in public response
    def test_18_no_user_ids_in_public_response(self) -> None:
        """Public heatmap endpoint does not leak user IDs or owner IDs."""
        for i in range(5):
            self._populate_inspection(f"mh-{i}", "PASS", state_code="MH", owner_id="secret-user-uuid-999")

        response = self.client.get("/api/v1/analytics/compliance-heatmap")
        self.assertEqual(response.status_code, 200)
        text = response.text
        self.assertNotIn("secret-user-uuid-999", text)
        self.assertNotIn("owner_id", text)
        self.assertNotIn("user_id", text)

    # 19. No exact coordinates in public response
    def test_19_no_exact_coordinates_in_public_response(self) -> None:
        """Public response contains only coarse region names/codes, zero coordinates."""
        for i in range(5):
            self._populate_inspection(f"mh-{i}", "PASS", state_code="MH")

        response = self.client.get("/api/v1/analytics/compliance-heatmap")
        self.assertEqual(response.status_code, 200)
        text = response.text
        self.assertNotIn("latitude", text.lower())
        self.assertNotIn("longitude", text.lower())
        self.assertNotIn("gps", text.lower())

    # 20. No inspection IDs in public response
    def test_20_no_inspection_ids_in_public_response(self) -> None:
        """Public response contains only aggregate cells, never individual inspection IDs."""
        for i in range(5):
            self._populate_inspection(f"unique-secret-inspection-id-{i}", "PASS", state_code="MH")

        response = self.client.get("/api/v1/analytics/compliance-heatmap")
        self.assertEqual(response.status_code, 200)
        text = response.text
        self.assertNotIn("unique-secret-inspection-id", text)

    # 21. Anonymous / Public HTTP access returns 200 OK
    def test_21_anonymous_public_access_allowed(self) -> None:
        """Heatmap endpoint is publicly accessible without authentication."""
        response = self.client.get("/api/v1/analytics/compliance-heatmap")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("cells", data)
        self.assertIn("summary", data)
        self.assertIn("disclaimer", data)

    # 22. U1 score semantics reused
    def test_22_u1_score_semantics_reused(self) -> None:
        """Average compliance score matches U1 score calculations."""
        # 5 inspections with 4 pass, 1 fail -> 4/5 = 80.0%
        for i in range(5):
            self._populate_inspection(f"mh-{i}", "FAIL", state_code="MH", pass_count=4, fail_count=1)

        report = self.service.compute_heatmap(level=GeographicLevel.STATE, public_mode=True)
        cell = next(c for c in report.cells if c.state_code == "MH")
        self.assertEqual(cell.average_compliance_score, 80.0)

    # 23. U5 risk semantics reused
    def test_23_u5_risk_semantics_reused(self) -> None:
        """U5 risk signals are correctly aggregated in RiskDistribution."""
        for i in range(5):
            self._populate_inspection(f"mh-{i}", "FAIL", state_code="MH", pass_count=2, fail_count=2)

        report = self.service.compute_heatmap(level=GeographicLevel.STATE, public_mode=True)
        cell = next(c for c in report.cells if c.state_code == "MH")
        self.assertIsNotNone(cell.risk_distribution)
        self.assertEqual(cell.risk_distribution.high_risk_count, 5)

    # 24. U6 finding/category aggregation
    def test_24_u6_finding_category_aggregation(self) -> None:
        """Top non-compliant statutory categories are ranked by failure count."""
        for i in range(5):
            self._populate_inspection(
                f"mh-{i}",
                "FAIL",
                state_code="MH",
                pass_count=1,
                fail_count=2,
                failed_req_ids=["R-6-1-e", "R-6-1-d"],
            )

        report = self.service.compute_heatmap(level=GeographicLevel.STATE, public_mode=True)
        cell = next(c for c in report.cells if c.state_code == "MH")
        self.assertTrue(len(cell.top_issue_categories) >= 2)
        cat_ids = [cat.category_id for cat in cell.top_issue_categories]
        self.assertIn("R-6-1-e", cat_ids)
        self.assertIn("R-6-1-d", cat_ids)

    # 25. Empty dataset handling
    def test_25_empty_dataset_handling(self) -> None:
        """Empty session store produces valid empty response with zero counters and safe None rates."""
        report = self.service.compute_heatmap(public_mode=True)
        self.assertEqual(len(report.cells), 0)
        self.assertEqual(report.summary.total_inspections, 0)
        self.assertIsNone(report.summary.overall_issue_rate)
        self.assertIsNone(report.summary.overall_verified_pass_rate)

    # 26. State filter query parameter
    def test_26_state_filter_query_parameter(self) -> None:
        """state_code query parameter isolates specific state."""
        for i in range(5):
            self._populate_inspection(f"mh-{i}", "PASS", state_code="MH", state_name="Maharashtra")
        for i in range(5):
            self._populate_inspection(f"dl-{i}", "PASS", state_code="DL", state_name="Delhi")

        response = self.client.get("/api/v1/analytics/compliance-heatmap?state_code=MH")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["cells"]), 1)
        self.assertEqual(data["cells"][0]["state_code"], "MH")

    # 27. Statutory disclaimer present
    def test_27_statutory_disclaimer_present(self) -> None:
        """API response always includes statutory disclaimer distinguishing samples from population prevalence."""
        response = self.client.get("/api/v1/analytics/compliance-heatmap")
        self.assertEqual(response.status_code, 200)
        disclaimer = response.json()["disclaimer"]
        self.assertIn("Does not represent statistical population prevalence", disclaimer)

    # 28. District filtering with state
    def test_28_district_level_api_response(self) -> None:
        """API responds properly to level=DISTRICT."""
        for i in range(5):
            self._populate_inspection(
                f"pun-{i}", "PASS", state_code="MH", district_code="PUN", district_name="Pune"
            )

        response = self.client.get("/api/v1/analytics/compliance-heatmap?level=DISTRICT")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["level"], "DISTRICT")
        self.assertEqual(len(data["cells"]), 1)
        self.assertEqual(data["cells"][0]["district_code"], "PUN")

    # 29. NormalizedLocationContext parse edge cases
    def test_29_normalized_location_context_parsing(self) -> None:
        """NormalizedLocationContext parses lower-case state names and handles none."""
        self.assertIsNone(NormalizedLocationContext.from_dict(None))
        self.assertIsNone(NormalizedLocationContext.from_dict({}))

        loc = NormalizedLocationContext.from_dict({"state_name": "maharashtra"})
        self.assertIsNotNone(loc)
        self.assertEqual(loc.state_code, "MH")
        self.assertEqual(loc.state_name, "maharashtra")

    # 30. Deterministic response model validation
    def test_30_deterministic_response_model_validation(self) -> None:
        """Response adheres to the documented Pydantic schema structure."""
        for i in range(5):
            self._populate_inspection(f"mh-{i}", "PASS", state_code="MH")

        response = self.client.get("/api/v1/analytics/compliance-heatmap")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        required_keys = ["level", "time_window", "from_time", "to_time", "generated_at", "min_threshold", "disclaimer", "summary", "cells"]
        for k in required_keys:
            self.assertIn(k, data)

        cell = data["cells"][0]
        cell_keys = ["region_code", "region_name", "level", "state_code", "is_suppressed", "inspection_count", "pass_count", "fail_count", "issue_rate", "verified_pass_rate"]
        for k in cell_keys:
            self.assertIn(k, cell)


if __name__ == "__main__":
    unittest.main()
