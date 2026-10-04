"""Tests for U2 — Evidence Image Error Highlighting & Visual Annotations."""

from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.app.api.schemas import (
    EvidenceAnnotationResponse,
    InspectionReportResponse,
    NormalizedBoxResponse,
)
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.main import app
from backend.app.services.evidence.models import (
    EvidenceCandidate,
    EvidenceField,
    EvidenceStatus,
    ImageArtifact,
)
from backend.app.services.inspection.models import Inspection, InspectionStatus
from backend.app.services.inspection.repository import (
    InMemoryInspectionRepository,
    SupabaseInspectionRepository,
)
from backend.app.services.inspection_pipeline.annotations import (
    EvidenceAnnotation,
    NormalizedBox,
    build_deterministic_annotation_id,
    generate_evidence_annotations,
    resolve_annotation_label,
)
from backend.app.services.inspection_pipeline.models import (
    InspectionPipelineRequest,
    OverallInspectionStatus,
)
from backend.app.services.inspection_pipeline.orchestrator import InspectionPipelineOrchestrator
from backend.app.services.inspection_pipeline.report import (
    InspectionReport,
    compute_overall_status,
)
from backend.app.services.ocr.models import BoundingBox
from backend.app.services.verification.models import VerificationResult, VerificationStatus


def _create_sample_artifact(
    image_id: str = "img_001",
    norm_w: int = 1000,
    norm_h: int = 800,
) -> ImageArtifact:
    return ImageArtifact(
        image_id=image_id,
        source_hash="sha256_src",
        normalized_hash="sha256_norm",
        source_format="JPEG",
        normalized_format="JPEG",
        original_width=norm_w,
        original_height=norm_h,
        normalized_width=norm_w,
        normalized_height=norm_h,
        pixel_count=norm_w * norm_h,
        aspect_ratio=float(norm_w) / float(norm_h),
        file_size_bytes=1024,
        source_file_size_bytes=2048,
        color_mode="RGB",
        normalized_bytes=b"\xff\xd8\xff\xe0test_bytes",
        was_resized=False,
        was_orientation_corrected=False,
    )


def _create_sample_candidate(
    evidence_id: str = "ev_001",
    image_id: str = "img_001",
    field: EvidenceField = EvidenceField.MRP,
    points: list[tuple[float, float]] | None = None,
    conf: float = 0.95,
) -> EvidenceCandidate:
    pts = points or [(100.0, 200.0), (300.0, 200.0), (300.0, 250.0), (100.0, 250.0)]
    bbox = BoundingBox(
        points=[[float(p[0]), float(p[1])] for p in pts],
    )
    return EvidenceCandidate(
        evidence_id=evidence_id,
        observation_id="obs_001",
        image_id=image_id,
        field=field,
        raw_text="MRP Rs. 150.00",
        normalized_text="150.00",
        parsed_value=150.0,
        parsed_unit="INR",
        ocr_confidence=conf,
        parser_confidence=conf,
        confidence=conf,
        status=EvidenceStatus.VALID,
        bounding_box=bbox,
    )


class TestU2EvidenceHighlighting(unittest.TestCase):
    """Unit tests for U2 visual error highlighting domain models and generator."""

    def test_01_fail_result_generates_error_highlight(self) -> None:
        """1. FAIL result generates ERROR_HIGHLIGHT."""
        v_res = VerificationResult(
            requirement_id="R-6-1-e",
            status=VerificationStatus.FAIL,
            reason="MRP missing currency symbol",
            evidence_ids=["ev_001"],
        )
        cand = _create_sample_candidate(evidence_id="ev_001", image_id="img_001")
        img = _create_sample_artifact(image_id="img_001", norm_w=1000, norm_h=1000)

        annotations = generate_evidence_annotations(
            verification_results=[v_res],
            evidence_candidates=[cand],
            images=[img],
            inspection_id="insp_123",
        )

        self.assertEqual(len(annotations), 1)
        ann = annotations[0]
        self.assertEqual(ann.status, "FAIL")
        self.assertEqual(ann.annotation_type, "ERROR_HIGHLIGHT")
        self.assertEqual(ann.requirement_id, "R-6-1-e")
        self.assertEqual(ann.evidence_id, "ev_001")
        self.assertTrue(ann.is_locatable)

    def test_02_review_required_generates_review_highlight(self) -> None:
        """2. REVIEW_REQUIRED generates REVIEW_HIGHLIGHT."""
        v_res = VerificationResult(
            requirement_id="R-6-1-c",
            status=VerificationStatus.REVIEW_REQUIRED,
            reason="Ambiguous net quantity representation",
            evidence_ids=["ev_002"],
        )
        cand = _create_sample_candidate(
            evidence_id="ev_002",
            image_id="img_001",
            field=EvidenceField.NET_QUANTITY,
        )
        img = _create_sample_artifact(image_id="img_001")

        annotations = generate_evidence_annotations(
            verification_results=[v_res],
            evidence_candidates=[cand],
            images=[img],
            inspection_id="insp_123",
        )

        self.assertEqual(len(annotations), 1)
        ann = annotations[0]
        self.assertEqual(ann.status, "REVIEW_REQUIRED")
        self.assertEqual(ann.annotation_type, "REVIEW_HIGHLIGHT")

    def test_03_pass_generates_no_annotation_by_default(self) -> None:
        """3. PASS generates no annotation by default."""
        v_res = VerificationResult(
            requirement_id="R-6-1-a",
            status=VerificationStatus.PASS,
            reason="Manufacturer address compliant",
            evidence_ids=["ev_003"],
        )
        cand = _create_sample_candidate(evidence_id="ev_003")
        img = _create_sample_artifact()

        annotations = generate_evidence_annotations(
            verification_results=[v_res],
            evidence_candidates=[cand],
            images=[img],
        )

        self.assertEqual(len(annotations), 0)

    def test_04_not_visible_generates_no_fabricated_annotation(self) -> None:
        """4. NOT_VISIBLE generates no fabricated annotation."""
        v_res = VerificationResult(
            requirement_id="R-6-1-g",
            status=VerificationStatus.NOT_VISIBLE,
            reason="Country of origin not found anywhere on package",
            evidence_ids=[],
        )
        cand = _create_sample_candidate()
        img = _create_sample_artifact()

        annotations = generate_evidence_annotations(
            verification_results=[v_res],
            evidence_candidates=[cand],
            images=[img],
        )

        self.assertEqual(len(annotations), 0)

    def test_05_not_applicable_generates_no_annotation(self) -> None:
        """5. NOT_APPLICABLE generates no annotation."""
        v_res = VerificationResult(
            requirement_id="R-6-1-h",
            status=VerificationStatus.NOT_APPLICABLE,
            reason="Unit sale price not required for this package size",
            evidence_ids=[],
        )
        cand = _create_sample_candidate()
        img = _create_sample_artifact()

        annotations = generate_evidence_annotations(
            verification_results=[v_res],
            evidence_candidates=[cand],
            images=[img],
        )

        self.assertEqual(len(annotations), 0)

    def test_06_correct_evidence_id_linkage(self) -> None:
        """6. Correct evidence_id linkage."""
        v_res = VerificationResult(
            requirement_id="R-6-1-e",
            status=VerificationStatus.FAIL,
            reason="Error",
            evidence_ids=["ev_target_999"],
        )
        cand = _create_sample_candidate(evidence_id="ev_target_999")
        img = _create_sample_artifact()

        annotations = generate_evidence_annotations([v_res], [cand], [img])
        self.assertEqual(annotations[0].evidence_id, "ev_target_999")

    def test_07_correct_image_id_linkage(self) -> None:
        """7. Correct image_id linkage."""
        v_res = VerificationResult(
            requirement_id="R-6-1-e",
            status=VerificationStatus.FAIL,
            reason="Error",
            evidence_ids=["ev_001"],
        )
        cand = _create_sample_candidate(evidence_id="ev_001", image_id="img_side_panel")
        img = _create_sample_artifact(image_id="img_side_panel")

        annotations = generate_evidence_annotations([v_res], [cand], [img])
        self.assertEqual(annotations[0].image_id, "img_side_panel")

    def test_08_correct_requirement_id_linkage(self) -> None:
        """8. Correct requirement_id linkage."""
        v_res = VerificationResult(
            requirement_id="R-6-1-d",
            status=VerificationStatus.FAIL,
            reason="Date missing month",
            evidence_ids=["ev_001"],
        )
        cand = _create_sample_candidate(evidence_id="ev_001")
        img = _create_sample_artifact()

        annotations = generate_evidence_annotations([v_res], [cand], [img])
        self.assertEqual(annotations[0].requirement_id, "R-6-1-d")

    def test_09_ocr_quadrilateral_is_preserved(self) -> None:
        """9. OCR quadrilateral is preserved."""
        quad_points = [(50.0, 100.0), (250.0, 105.0), (248.0, 160.0), (48.0, 155.0)]
        cand = _create_sample_candidate(evidence_id="ev_001", points=quad_points)
        v_res = VerificationResult(
            requirement_id="R-6-1-e",
            status=VerificationStatus.FAIL,
            reason="Error",
            evidence_ids=["ev_001"],
        )
        img = _create_sample_artifact()

        annotations = generate_evidence_annotations([v_res], [cand], [img])
        self.assertEqual(len(annotations[0].polygon), 4)
        self.assertEqual(annotations[0].polygon[0], [50.0, 100.0])
        self.assertEqual(annotations[0].polygon[1], [250.0, 105.0])
        self.assertEqual(annotations[0].polygon[2], [248.0, 160.0])
        self.assertEqual(annotations[0].polygon[3], [48.0, 155.0])

    def test_10_bounding_rectangle_is_correct(self) -> None:
        """10. Bounding rectangle is correct."""
        quad_points = [(100.0, 200.0), (400.0, 200.0), (400.0, 300.0), (100.0, 300.0)]
        cand = _create_sample_candidate(evidence_id="ev_001", points=quad_points)
        v_res = VerificationResult(
            requirement_id="R-6-1-e",
            status=VerificationStatus.FAIL,
            reason="Error",
            evidence_ids=["ev_001"],
        )
        img = _create_sample_artifact()

        annotations = generate_evidence_annotations([v_res], [cand], [img])
        bbox = annotations[0].bounding_box
        self.assertEqual(bbox["x_min"], 100.0)
        self.assertEqual(bbox["y_min"], 200.0)
        self.assertEqual(bbox["x_max"], 400.0)
        self.assertEqual(bbox["y_max"], 300.0)
        self.assertEqual(bbox["width"], 300.0)
        self.assertEqual(bbox["height"], 100.0)

    def test_11_normalized_box_is_correct(self) -> None:
        """11. normalized_box is correct."""
        quad_points = [(200.0, 100.0), (800.0, 100.0), (800.0, 500.0), (200.0, 500.0)]
        cand = _create_sample_candidate(evidence_id="ev_001", points=quad_points)
        v_res = VerificationResult(
            requirement_id="R-6-1-e",
            status=VerificationStatus.FAIL,
            reason="Error",
            evidence_ids=["ev_001"],
        )
        img = _create_sample_artifact(norm_w=1000, norm_h=1000)

        annotations = generate_evidence_annotations([v_res], [cand], [img])
        norm_box = annotations[0].normalized_box
        self.assertAlmostEqual(norm_box.x_min, 0.2, places=4)
        self.assertAlmostEqual(norm_box.y_min, 0.1, places=4)
        self.assertAlmostEqual(norm_box.x_max, 0.8, places=4)
        self.assertAlmostEqual(norm_box.y_max, 0.5, places=4)

    def test_12_normalized_coordinates_clamped_within_0_to_1(self) -> None:
        """12. normalized coordinates remain strictly within 0..1."""
        box = NormalizedBox(x_min=-0.5, y_min=1.8, x_max=2.0, y_max=-0.1)
        self.assertEqual(box.x_min, 0.0)
        self.assertEqual(box.y_min, 1.0)
        self.assertEqual(box.x_max, 1.0)
        self.assertEqual(box.y_max, 0.0)

    def test_13_multiple_evidence_candidates_produce_multiple_annotations(self) -> None:
        """13. Multiple evidence candidates produce multiple annotations."""
        v_res = VerificationResult(
            requirement_id="R-6-1-a",
            status=VerificationStatus.FAIL,
            reason="Mismatch across two declarations",
            evidence_ids=["ev_001", "ev_002"],
        )
        cand1 = _create_sample_candidate(evidence_id="ev_001", points=[(10.0, 10.0), (50.0, 10.0), (50.0, 30.0), (10.0, 30.0)])
        cand2 = _create_sample_candidate(evidence_id="ev_002", points=[(100.0, 100.0), (200.0, 100.0), (200.0, 150.0), (100.0, 150.0)])
        img = _create_sample_artifact()

        annotations = generate_evidence_annotations([v_res], [cand1, cand2], [img])
        self.assertEqual(len(annotations), 2)
        ev_ids = {a.evidence_id for a in annotations}
        self.assertEqual(ev_ids, {"ev_001", "ev_002"})

    def test_14_multiple_images_remain_correctly_separated(self) -> None:
        """14. Multiple images remain correctly separated."""
        v_res = VerificationResult(
            requirement_id="R-6-1-a",
            status=VerificationStatus.FAIL,
            reason="Multi-panel failure",
            evidence_ids=["ev_front", "ev_back"],
        )
        cand1 = _create_sample_candidate(evidence_id="ev_front", image_id="img_front")
        cand2 = _create_sample_candidate(evidence_id="ev_back", image_id="img_back")
        img1 = _create_sample_artifact(image_id="img_front", norm_w=1000, norm_h=800)
        img2 = _create_sample_artifact(image_id="img_back", norm_w=500, norm_h=400)

        annotations = generate_evidence_annotations([v_res], [cand1, cand2], [img1, img2])
        self.assertEqual(len(annotations), 2)
        ann_img_map = {a.evidence_id: a.image_id for a in annotations}
        self.assertEqual(ann_img_map["ev_front"], "img_front")
        self.assertEqual(ann_img_map["ev_back"], "img_back")

    def test_15_exact_duplicate_evidence_does_not_create_duplicate_annotations(self) -> None:
        """15. Exact duplicate evidence does not create duplicate annotations."""
        v_res = VerificationResult(
            requirement_id="R-6-1-e",
            status=VerificationStatus.FAIL,
            reason="Error",
            evidence_ids=["ev_001", "ev_001"],  # duplicate ID
        )
        cand = _create_sample_candidate(evidence_id="ev_001")
        img = _create_sample_artifact()

        annotations = generate_evidence_annotations([v_res], [cand], [img])
        self.assertEqual(len(annotations), 1)

    def test_16_annotation_ids_are_deterministic(self) -> None:
        """16. Annotation IDs are deterministic."""
        id1 = build_deterministic_annotation_id("insp_1", "img_1", "R-6-1-e", "ev_1", "ERROR_HIGHLIGHT")
        id2 = build_deterministic_annotation_id("insp_1", "img_1", "R-6-1-e", "ev_1", "ERROR_HIGHLIGHT")
        self.assertEqual(id1, id2)
        self.assertTrue(id1.startswith("ann_"))

    def test_17_same_inputs_produce_identical_annotations(self) -> None:
        """17. Same inputs produce identical annotations."""
        v_res = VerificationResult(requirement_id="R-6-1-e", status=VerificationStatus.FAIL, reason="Error", evidence_ids=["ev_001"])
        cand = _create_sample_candidate(evidence_id="ev_001")
        img = _create_sample_artifact()

        run1 = generate_evidence_annotations([v_res], [cand], [img], "insp_fixed")
        run2 = generate_evidence_annotations([v_res], [cand], [img], "insp_fixed")

        self.assertEqual(len(run1), len(run2))
        self.assertEqual(run1[0].to_dict(), run2[0].to_dict())

    def test_18_missing_bounding_box_is_handled_safely(self) -> None:
        """18. Missing bounding box is handled safely."""
        cand = EvidenceCandidate(
            evidence_id="ev_nobox",
            observation_id="obs_001",
            image_id="img_001",
            field=EvidenceField.MRP,
            raw_text="No box",
            status=EvidenceStatus.VALID,
            bounding_box=None,
        )
        v_res = VerificationResult(
            requirement_id="R-6-1-e",
            status=VerificationStatus.FAIL,
            reason="Error",
            evidence_ids=["ev_nobox"],
        )
        img = _create_sample_artifact()

        annotations = generate_evidence_annotations([v_res], [cand], [img])
        self.assertEqual(len(annotations), 0)

    def test_19_malformed_out_of_range_geometry_handled_safely(self) -> None:
        """19. Malformed/out-of-range geometry is rejected or safely handled."""
        cand = EvidenceCandidate(
            evidence_id="ev_malformed",
            observation_id="obs_001",
            image_id="img_001",
            field=EvidenceField.MRP,
            raw_text="Malformed",
            status=EvidenceStatus.VALID,
            bounding_box={"points": [[10, 10]]},  # invalid, only 1 point
        )
        v_res = VerificationResult(
            requirement_id="R-6-1-e",
            status=VerificationStatus.FAIL,
            reason="Error",
            evidence_ids=["ev_malformed"],
        )
        img = _create_sample_artifact()

        annotations = generate_evidence_annotations([v_res], [cand], [img])
        self.assertEqual(len(annotations), 0)

    def test_20_inspection_report_serialization_includes_annotations(self) -> None:
        """20. InspectionReport serialization includes annotations."""
        norm_box = NormalizedBox(x_min=0.1, y_min=0.2, x_max=0.5, y_max=0.6)
        ann = EvidenceAnnotation(
            annotation_id="ann_test_123",
            image_id="img_001",
            requirement_id="R-6-1-e",
            evidence_id="ev_001",
            status="FAIL",
            annotation_type="ERROR_HIGHLIGHT",
            polygon=[[100.0, 200.0], [500.0, 200.0], [500.0, 600.0], [100.0, 600.0]],
            bounding_box={"x_min": 100.0, "y_min": 200.0, "x_max": 500.0, "y_max": 600.0, "width": 400.0, "height": 400.0},
            normalized_box=norm_box,
            label="Maximum Retail Price (MRP)",
            reason="Missing currency symbol",
            confidence=0.98,
            is_locatable=True,
        )
        report = InspectionReport(
            inspection_id="insp_serialization",
            overall_status=OverallInspectionStatus.FAIL,
            verification_results=[],
            summary="Test report",
            evidence_count=1,
            image_count=1,
            applicable_requirement_count=1,
            pass_count=0,
            fail_count=1,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
            evidence_annotations=[ann],
        )

        d = report.to_dict()
        self.assertIn("evidence_annotations", d)
        self.assertEqual(len(d["evidence_annotations"]), 1)
        self.assertEqual(d["evidence_annotations"][0]["annotation_id"], "ann_test_123")
        self.assertEqual(d["evidence_annotations"][0]["annotation_type"], "ERROR_HIGHLIGHT")

    def test_21_repository_save_load_preserves_annotations(self) -> None:
        """21. Repository save/load preserves annotations."""
        repo = InMemoryInspectionRepository()
        insp = repo.create_inspection("insp_repo_test")
        norm_box = NormalizedBox(x_min=0.1, y_min=0.2, x_max=0.5, y_max=0.6)
        ann = EvidenceAnnotation(
            annotation_id="ann_repo_test",
            image_id="img_001",
            requirement_id="R-6-1-e",
            evidence_id="ev_001",
            status="FAIL",
            annotation_type="ERROR_HIGHLIGHT",
            polygon=[[100.0, 200.0], [500.0, 200.0], [500.0, 600.0], [100.0, 600.0]],
            bounding_box={"x_min": 100.0, "y_min": 200.0, "x_max": 500.0, "y_max": 600.0, "width": 400.0, "height": 400.0},
            normalized_box=norm_box,
            label="MRP",
            reason="Missing currency symbol",
            confidence=0.98,
        )
        report = InspectionReport(
            inspection_id="insp_repo_test",
            overall_status=OverallInspectionStatus.FAIL,
            verification_results=[],
            summary="Report",
            evidence_count=1,
            image_count=1,
            applicable_requirement_count=1,
            pass_count=0,
            fail_count=1,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
            evidence_annotations=[ann],
        )
        repo.save_report("insp_repo_test", report)

        retrieved = repo.get_report("insp_repo_test")
        self.assertIsNotNone(retrieved)
        self.assertEqual(len(retrieved.evidence_annotations), 1)
        self.assertEqual(retrieved.evidence_annotations[0].annotation_id, "ann_repo_test")

    def test_22_legacy_report_without_annotations_loads_as_empty_list(self) -> None:
        """22. Legacy report without annotations loads as []."""
        mock_supabase = SupabaseInspectionRepository(supabase_url="http://mock.supabase.co", supabase_key="anon")
        legacy_payload = {
            "inspection_id": "insp_legacy",
            "overall_status": "FAIL",
            "summary": "Legacy report",
            "counts": {"pass_count": 0, "fail_count": 1},
            "verification_results": [],
            # notice: no "evidence_annotations" key
        }
        mock_supabase._request = MagicMock(return_value=[{
            "inspection_id": "insp_legacy",
            "overall_status": "FAIL",
            "summary": "Legacy report",
            "created_at": "2026-10-01T00:00:00Z",
            "report_payload": legacy_payload,
        }])
        mock_supabase.get_inspection = MagicMock()

        loaded_report = mock_supabase.get_report("insp_legacy")
        self.assertIsNotNone(loaded_report)
        self.assertEqual(loaded_report.evidence_annotations, [])

    def test_23_api_report_response_exposes_annotations(self) -> None:
        """23. API report response exposes annotations."""
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id="user_test_123", email="user@example.com", role="authenticated"
        )
        try:
            # Create inspection
            res_create = client.post("/api/v1/inspections", json={})
            self.assertEqual(res_create.status_code, 201)
            insp_id = res_create.json()["inspection_id"]

            # Populate session report in store
            from backend.app.api.dependencies import get_session_store
            store = app.dependency_overrides.get(get_session_store, get_session_store)()
            norm_box = NormalizedBox(x_min=0.1, y_min=0.2, x_max=0.5, y_max=0.6)
            ann = EvidenceAnnotation(
                annotation_id="ann_api_test",
                image_id="img_001",
                requirement_id="R-6-1-e",
                evidence_id="ev_001",
                status="FAIL",
                annotation_type="ERROR_HIGHLIGHT",
                polygon=[[100.0, 200.0], [500.0, 200.0], [500.0, 600.0], [100.0, 600.0]],
                bounding_box={"x_min": 100.0, "y_min": 200.0, "x_max": 500.0, "y_max": 600.0, "width": 400.0, "height": 400.0},
                normalized_box=norm_box,
                label="Maximum Retail Price (MRP)",
                reason="Missing currency symbol",
            )
            report = InspectionReport(
                inspection_id=insp_id,
                overall_status=OverallInspectionStatus.FAIL,
                verification_results=[],
                summary="API Test Report",
                evidence_count=1,
                image_count=1,
                applicable_requirement_count=1,
                pass_count=0,
                fail_count=1,
                not_visible_count=0,
                not_applicable_count=0,
                review_required_count=0,
                evidence_annotations=[ann],
            )
            store.store_report(insp_id, report)

            # Fetch report via API
            res_report = client.get(f"/api/v1/inspections/{insp_id}/report")
            self.assertEqual(res_report.status_code, 200)
            data = res_report.json()
            self.assertIn("evidence_annotations", data)
            self.assertEqual(len(data["evidence_annotations"]), 1)
            self.assertEqual(data["evidence_annotations"][0]["annotation_id"], "ann_api_test")
            self.assertEqual(data["evidence_annotations"][0]["annotation_type"], "ERROR_HIGHLIGHT")
        finally:
            app.dependency_overrides.clear()

    def test_24_unauthorized_report_access_remains_blocked(self) -> None:
        """24. Unauthorized report access remains blocked."""
        client = TestClient(app)
        # Without auth header / dependency override
        res = client.get("/api/v1/inspections/insp_123/report")
        self.assertEqual(res.status_code, 401)

    def test_25_adding_annotations_does_not_change_overall_status(self) -> None:
        """25. Adding annotations does not change overall_status."""
        v_res = VerificationResult(
            requirement_id="R-6-1-e",
            status=VerificationStatus.FAIL,
            reason="Failed",
            evidence_ids=["ev_001"],
        )
        status_before, _ = compute_overall_status([v_res])
        cand = _create_sample_candidate(evidence_id="ev_001")
        img = _create_sample_artifact()
        annotations = generate_evidence_annotations([v_res], [cand], [img])

        status_after, _ = compute_overall_status([v_res])
        self.assertEqual(status_before, status_after)
        self.assertEqual(status_after, OverallInspectionStatus.FAIL)

    def test_26_adding_annotations_does_not_change_compliance_score(self) -> None:
        """26. Adding annotations does not change compliance evaluation outcomes."""
        results = [
            VerificationResult(requirement_id="R-6-1-a", status=VerificationStatus.PASS, reason="Ok"),
            VerificationResult(requirement_id="R-6-1-e", status=VerificationStatus.FAIL, reason="Failed", evidence_ids=["ev_001"]),
        ]
        status_before, summary_before = compute_overall_status(results)

        cand = _create_sample_candidate(evidence_id="ev_001")
        img = _create_sample_artifact()
        annotations = generate_evidence_annotations(results, [cand], [img])

        status_after, summary_after = compute_overall_status(results)
        self.assertEqual(status_before, status_after)
        self.assertEqual(summary_before, summary_after)
        self.assertEqual(results[0].status, VerificationStatus.PASS)
        self.assertEqual(results[1].status, VerificationStatus.FAIL)

    def test_27_original_image_bytes_storage_metadata_remain_unchanged(self) -> None:
        """27. Original image bytes/storage metadata remain unchanged."""
        img = _create_sample_artifact(image_id="img_immutable")
        original_bytes = bytes(img.normalized_bytes)
        original_hash = str(img.normalized_hash)

        v_res = VerificationResult(requirement_id="R-6-1-e", status=VerificationStatus.FAIL, reason="Error", evidence_ids=["ev_001"])
        cand = _create_sample_candidate(evidence_id="ev_001", image_id="img_immutable")
        annotations = generate_evidence_annotations([v_res], [cand], [img])

        self.assertEqual(img.normalized_bytes, original_bytes)
        self.assertEqual(img.normalized_hash, original_hash)

    def test_28_background_execution_generates_and_persists_annotations(self) -> None:
        """28. Background execution generates and persists annotations."""
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id="user_bg_123", email="user@example.com", role="authenticated"
        )
        try:
            # Create inspection
            res_create = client.post("/api/v1/inspections", json={})
            insp_id = res_create.json()["inspection_id"]

            # Mock pipeline orchestrator run to return a report with annotations
            from backend.app.api.dependencies import get_pipeline_orchestrator
            mock_orchestrator = MagicMock()
            norm_box = NormalizedBox(x_min=0.2, y_min=0.3, x_max=0.8, y_max=0.7)
            ann = EvidenceAnnotation(
                annotation_id="ann_bg_123",
                image_id="img_001",
                requirement_id="R-6-1-e",
                evidence_id="ev_001",
                status="FAIL",
                annotation_type="ERROR_HIGHLIGHT",
                polygon=[[200.0, 300.0], [800.0, 300.0], [800.0, 700.0], [200.0, 700.0]],
                bounding_box={"x_min": 200.0, "y_min": 300.0, "x_max": 800.0, "y_max": 700.0, "width": 600.0, "height": 400.0},
                normalized_box=norm_box,
                label="Maximum Retail Price (MRP)",
                reason="Defective MRP format",
            )
            mock_report = InspectionReport(
                inspection_id=insp_id,
                overall_status=OverallInspectionStatus.FAIL,
                verification_results=[],
                summary="BG Report",
                evidence_count=1,
                image_count=1,
                applicable_requirement_count=1,
                pass_count=0,
                fail_count=1,
                not_visible_count=0,
                not_applicable_count=0,
                review_required_count=0,
                evidence_annotations=[ann],
            )
            mock_orchestrator.run.return_value = mock_report
            app.dependency_overrides[get_pipeline_orchestrator] = lambda: mock_orchestrator

            # Run inspection
            res_run = client.post(f"/api/v1/inspections/{insp_id}/run", json={})
            self.assertEqual(res_run.status_code, 200)

            # Get report
            res_rep = client.get(f"/api/v1/inspections/{insp_id}/report")
            self.assertEqual(res_rep.status_code, 200)
            data = res_rep.json()
            self.assertEqual(len(data["evidence_annotations"]), 1)
            self.assertEqual(data["evidence_annotations"][0]["annotation_id"], "ann_bg_123")
        finally:
            app.dependency_overrides.clear()

    def test_29_completed_rerun_produces_equivalent_annotations(self) -> None:
        """29. Completed rerun produces equivalent annotations."""
        v_res = VerificationResult(requirement_id="R-6-1-e", status=VerificationStatus.FAIL, reason="Error", evidence_ids=["ev_001"])
        cand = _create_sample_candidate(evidence_id="ev_001")
        img = _create_sample_artifact()

        ann_pass1 = generate_evidence_annotations([v_res], [cand], [img], "insp_rerun")
        ann_pass2 = generate_evidence_annotations([v_res], [cand], [img], "insp_rerun")

        self.assertEqual([a.to_dict() for a in ann_pass1], [a.to_dict() for a in ann_pass2])

    def test_30_full_pipeline_multi_status_orchestrator_generation(self) -> None:
        """30. Full pipeline multi-status report generation produces expected highlights and ignores non-highlights."""
        v_fail = VerificationResult(requirement_id="R-6-1-e", status=VerificationStatus.FAIL, reason="Defective MRP", evidence_ids=["ev_mrp"])
        v_rev = VerificationResult(requirement_id="R-6-1-c", status=VerificationStatus.REVIEW_REQUIRED, reason="Unclear unit", evidence_ids=["ev_net_qty"])
        v_pass = VerificationResult(requirement_id="R-6-1-a", status=VerificationStatus.PASS, reason="Compliant", evidence_ids=["ev_mfg"])
        v_notvis = VerificationResult(requirement_id="R-6-1-g", status=VerificationStatus.NOT_VISIBLE, reason="Not visible", evidence_ids=[])
        v_na = VerificationResult(requirement_id="R-6-1-h", status=VerificationStatus.NOT_APPLICABLE, reason="Exempt", evidence_ids=[])

        cand_mrp = _create_sample_candidate(evidence_id="ev_mrp", field=EvidenceField.MRP)
        cand_net_qty = _create_sample_candidate(evidence_id="ev_net_qty", field=EvidenceField.NET_QUANTITY)
        cand_mfg = _create_sample_candidate(evidence_id="ev_mfg", field=EvidenceField.MANUFACTURER_ADDRESS)
        img = _create_sample_artifact()

        annotations = generate_evidence_annotations(
            verification_results=[v_fail, v_rev, v_pass, v_notvis, v_na],
            evidence_candidates=[cand_mrp, cand_net_qty, cand_mfg],
            images=[img],
            inspection_id="insp_full_eval",
        )

        # Only FAIL and REVIEW_REQUIRED should have generated annotations
        self.assertEqual(len(annotations), 2)
        types = {a.annotation_type for a in annotations}
        self.assertEqual(types, {"ERROR_HIGHLIGHT", "REVIEW_HIGHLIGHT"})
        statuses = {a.status for a in annotations}
        self.assertEqual(statuses, {"FAIL", "REVIEW_REQUIRED"})


if __name__ == "__main__":
    unittest.main()
