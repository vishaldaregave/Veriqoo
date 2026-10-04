"""Comprehensive unit and integration tests for Phase 8A FastAPI API Contracts.

Tests verify all REST endpoints, in-memory session store, image upload validation,
lifecycle state enforcement, pipeline execution, report retrieval, structured error contracts,
and dependency injection overrides.
"""

from __future__ import annotations

import io
from typing import Any
import unittest

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.api.dependencies import (
    get_current_user,
    get_ingestion_service,
    get_pipeline_orchestrator,
    get_session_store,
)
from backend.app.api.errors import ErrorCode
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth import AuthenticatedUser
from backend.app.main import app
from backend.app.services.applicability.models import TriState
from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.evidence.models import ImageArtifact, IngestionConfig
from backend.app.services.inspection_pipeline.models import (
    InspectionPipelineRequest,
    OverallInspectionStatus,
)
from backend.app.services.inspection_pipeline.orchestrator import InspectionPipelineOrchestrator
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.ocr.models import OCRObservation, OCRProcessingStatus, OCRResult
from backend.app.services.verification.models import (
    RequirementReference,
    VerificationResult,
    VerificationStatus,
)


def _create_sample_jpeg_bytes(width: int = 200, height: int = 100, color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    """Helper to create valid in-memory JPEG bytes."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _create_sample_png_bytes(width: int = 200, height: int = 100, color: tuple[int, int, int] = (0, 255, 0)) -> bytes:
    """Helper to create valid in-memory PNG bytes."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class MockOCREngine:
    """Deterministic mock OCR engine for API pipeline tests."""
    def __init__(self, text: str = "MRP Rs. 250.00 Net Qty 500 g") -> None:
        self.text = text

    def extract_from_artifact(self, artifact: ImageArtifact) -> OCRResult:
        obs = OCRObservation(
            observation_id="mock_obs_1",
            text=self.text,
            confidence=0.98,
            bounding_box=[[10, 10], [100, 10], [100, 30], [10, 30]],
            image_id=artifact.image_id,
        )
        return OCRResult(
            image_id=artifact.image_id,
            status=OCRProcessingStatus.SUCCESS,
            observations=[obs],
        )


class Phase8AAPITestCase(unittest.TestCase):
    """Test suite verifying Phase 8A FastAPI endpoints and in-memory lifecycle."""

    def setUp(self) -> None:
        # Isolated in-memory store for every test
        self.store = InMemoryInspectionStore()
        self.client = TestClient(app)
        self.test_user = AuthenticatedUser(user_id="default-test-user-id", email="test@veriqoo.ai")

        # Override dependencies
        app.dependency_overrides[get_session_store] = lambda: self.store
        app.dependency_overrides[get_current_user] = lambda: self.test_user

        # Default mock orchestrator
        mock_ocr = MockOCREngine()
        self.mock_orchestrator = InspectionPipelineOrchestrator(ocr_engine=mock_ocr)
        app.dependency_overrides[get_pipeline_orchestrator] = lambda: self.mock_orchestrator

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.store.clear()

    # =================================================================
    # 1. Health Check Tests
    # =================================================================

    def test_root_health_check(self) -> None:
        """Root GET /health returns 200 and standard health payload."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("Legal", data["service"])
        self.assertTrue(len(data["api_version"]) > 0)

    def test_v1_health_check(self) -> None:
        """GET /api/v1/health returns 200 and standard health schema."""
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("Legal", data["service"])
        self.assertTrue(len(data["api_version"]) > 0)

    # =================================================================
    # 2. Inspection Creation & Retrieval Tests
    # =================================================================

    def test_create_inspection_default(self) -> None:
        """POST /api/v1/inspections creates new session in COLLECTING status."""
        response = self.client.post("/api/v1/inspections", json={})
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("inspection_id", data)
        self.assertEqual(data["status"], "COLLECTING")
        self.assertEqual(data["image_count"], 0)
        self.assertEqual(data["images"], [])
        self.assertFalse(data["has_report"])

    def test_create_inspection_with_metadata(self) -> None:
        """POST /api/v1/inspections preserves metadata and inspection_date."""
        payload = {
            "metadata": {"officer_id": "OFFICER_42", "location": "Warehouse A"},
            "inspection_date": "2026-10-04",
        }
        response = self.client.post("/api/v1/inspections", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["metadata"]["officer_id"], "OFFICER_42")
        self.assertEqual(data["metadata"]["inspection_date"], "2026-10-04")

    def test_get_inspection_by_id(self) -> None:
        """GET /api/v1/inspections/{id} retrieves existing session."""
        session = self.store.create_session(metadata={"source": "test"})
        insp_id = session.inspection.inspection_id

        response = self.client.get(f"/api/v1/inspections/{insp_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["inspection_id"], insp_id)
        self.assertEqual(data["status"], "COLLECTING")
        self.assertEqual(data["metadata"]["source"], "test")

    def test_get_nonexistent_inspection_returns_404(self) -> None:
        """GET /api/v1/inspections/{id} for unknown ID returns 404 with structured error."""
        response = self.client.get("/api/v1/inspections/nonexistent-uuid-12345")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], ErrorCode.INSPECTION_NOT_FOUND.value)
        self.assertIn("nonexistent-uuid-12345", data["error"]["message"])

    # =================================================================
    # 3. Image Upload Tests
    # =================================================================

    def test_upload_valid_jpeg_image(self) -> None:
        """POST /api/v1/inspections/{id}/images successfully ingests and normalizes JPEG."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id
        img_bytes = _create_sample_jpeg_bytes(300, 200)

        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("front.jpg", img_bytes, "image/jpeg")},
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("image_id", data)
        self.assertEqual(data["sequence"], 1)
        self.assertEqual(data["source_format"], "JPEG")
        self.assertEqual(data["normalized_format"], "PNG")
        self.assertEqual(data["original_width"], 300)
        self.assertEqual(data["original_height"], 200)
        self.assertIn("normalized_hash", data)

        # Verify inspection container updated
        insp_resp = self.client.get(f"/api/v1/inspections/{insp_id}")
        self.assertEqual(insp_resp.json()["image_count"], 1)
        self.assertEqual(len(insp_resp.json()["images"]), 1)
        self.assertEqual(insp_resp.json()["images"][0]["sequence"], 1)

    def test_upload_valid_png_image(self) -> None:
        """POST /api/v1/inspections/{id}/images accepts valid PNG image."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id
        img_bytes = _create_sample_png_bytes(250, 150)

        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("label.png", img_bytes, "image/png")},
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["source_format"], "PNG")
        self.assertEqual(data["normalized_format"], "PNG")
        self.assertEqual(data["original_width"], 250)
        self.assertEqual(data["original_height"], 150)

    def test_upload_multiple_images_preserves_deterministic_sequence(self) -> None:
        """Upload multiple images sequentially and verify sequence 1, 2, 3."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # Image 1
        res1 = self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("img1.jpg", _create_sample_jpeg_bytes(100, 100), "image/jpeg")},
        )
        self.assertEqual(res1.status_code, 201)
        self.assertEqual(res1.json()["sequence"], 1)

        # Image 2
        res2 = self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("img2.png", _create_sample_png_bytes(150, 150), "image/png")},
        )
        self.assertEqual(res2.status_code, 201)
        self.assertEqual(res2.json()["sequence"], 2)

        # Verify inspection state
        insp_resp = self.client.get(f"/api/v1/inspections/{insp_id}")
        self.assertEqual(insp_resp.json()["image_count"], 2)
        images = insp_resp.json()["images"]
        self.assertEqual(images[0]["sequence"], 1)
        self.assertEqual(images[1]["sequence"], 2)

    def test_upload_empty_file_returns_400(self) -> None:
        """POST empty image file (0 bytes) returns 400 IMAGE_EMPTY."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("empty.jpg", b"", "image/jpeg")},
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], ErrorCode.IMAGE_EMPTY.value)

    def test_upload_invalid_bytes_returns_400(self) -> None:
        """POST corrupt non-image bytes returns 400 INVALID_IMAGE."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("corrupt.jpg", b"NOT_A_VALID_IMAGE_BYTES_XYZ", "image/jpeg")},
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], ErrorCode.INVALID_IMAGE.value)

    def test_upload_to_nonexistent_inspection_returns_404(self) -> None:
        """Upload to nonexistent inspection returns 404 INSPECTION_NOT_FOUND."""
        img_bytes = _create_sample_jpeg_bytes(100, 100)
        response = self.client.post(
            "/api/v1/inspections/fake-id-99999/images",
            files={"file": ("img.jpg", img_bytes, "image/jpeg")},
        )
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["error"]["code"], ErrorCode.INSPECTION_NOT_FOUND.value)

    def test_upload_oversized_image_returns_413(self) -> None:
        """Upload exceeding max dimensions/pixels returns 413 IMAGE_TOO_LARGE."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # Use strict custom ingestion config with low max_width
        strict_config = IngestionConfig(max_width=50, max_height=50)
        strict_service = ImageIngestionService(config=strict_config)
        app.dependency_overrides[get_ingestion_service] = lambda: strict_service

        img_bytes = _create_sample_jpeg_bytes(100, 100)
        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("large.jpg", img_bytes, "image/jpeg")},
        )
        self.assertEqual(response.status_code, 413)
        data = response.json()
        self.assertEqual(data["error"]["code"], ErrorCode.IMAGE_TOO_LARGE.value)

    # =================================================================
    # 4. Pipeline Execution & Report Tests
    # =================================================================

    def test_run_inspection_pipeline_success(self) -> None:
        """POST /api/v1/inspections/{id}/run executes orchestrator and returns report."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # Upload 1 image
        img_bytes = _create_sample_jpeg_bytes(200, 100)
        self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("label.jpg", img_bytes, "image/jpeg")},
        )

        run_payload = {
            "target_requirements": ["R-6-1-c", "R-6-1-d"],
            "applicability_context": {"R-6-1-c": "true", "R-6-1-d": "true"},
            "metadata": {"test_run": True},
        }

        response = self.client.post(f"/api/v1/inspections/{insp_id}/run", json=run_payload)
        self.assertEqual(response.status_code, 200)
        run_data = response.json()
        self.assertEqual(run_data["inspection_id"], insp_id)
        self.assertIn(run_data["status"], ["RUNNING", "COMPLETED"])

        # Fetch report via GET /report
        report_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(report_resp.status_code, 200)
        data = report_resp.json()
        self.assertEqual(data["inspection_id"], insp_id)
        self.assertIn(data["overall_status"], ["PASS", "FAIL", "REVIEW_REQUIRED"])
        self.assertIn("counts", data)
        self.assertEqual(data["counts"]["image_count"], 1)
        self.assertIn("verification_results", data)
        self.assertEqual(len(data["verification_results"]), 2)

        # Verify inspection container updated with has_report=True and status=COMPLETED
        insp_resp = self.client.get(f"/api/v1/inspections/{insp_id}")
        self.assertTrue(insp_resp.json()["has_report"])
        self.assertEqual(insp_resp.json()["status"], "COMPLETED")

    def test_get_report_after_run(self) -> None:
        """GET /api/v1/inspections/{id}/report returns generated report."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # Run pipeline
        self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})

        response = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["inspection_id"], insp_id)
        self.assertIn("overall_status", data)
        self.assertIn("summary", data)

    def test_get_report_before_run_returns_404(self) -> None:
        """GET /api/v1/inspections/{id}/report before run returns 404 REPORT_NOT_AVAILABLE."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        response = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["error"]["code"], ErrorCode.REPORT_NOT_AVAILABLE.value)

    def test_get_report_for_nonexistent_inspection_returns_404(self) -> None:
        """GET /api/v1/inspections/{id}/report for unknown ID returns 404 INSPECTION_NOT_FOUND."""
        response = self.client.get("/api/v1/inspections/nonexistent-id-0000/report")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["error"]["code"], ErrorCode.INSPECTION_NOT_FOUND.value)

    # =================================================================
    # 5. Lifecycle Guard Tests
    # =================================================================

    def test_upload_image_after_run_returns_409_state_error(self) -> None:
        """Attempting to upload image when inspection is in READY state raises 409 INVALID_INSPECTION_STATE."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # Execute run (transitions inspection to READY)
        self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})

        # Attempt to upload another image
        img_bytes = _create_sample_jpeg_bytes(100, 100)
        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("late_img.jpg", img_bytes, "image/jpeg")},
        )
        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertEqual(data["error"]["code"], ErrorCode.INVALID_INSPECTION_STATE.value)

    # =================================================================
    # 6. Structured Error Response Conformance Tests
    # =================================================================

    def test_upload_valid_webp_image(self) -> None:
        """POST /api/v1/inspections/{id}/images accepts valid WEBP image."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # Generate simple WEBP image
        img = Image.new("RGB", (120, 80), color=(0, 0, 255))
        buf = io.BytesIO()
        img.save(buf, format="WEBP")
        webp_bytes = buf.getvalue()

        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("photo.webp", webp_bytes, "image/webp")},
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["source_format"], "WEBP")
        self.assertEqual(data["normalized_format"], "PNG")
        self.assertEqual(data["original_width"], 120)
        self.assertEqual(data["original_height"], 80)

    def test_run_inspection_with_inspection_facts(self) -> None:
        """POST /api/v1/inspections/{id}/run correctly passes inspection facts to orchestrator."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # Upload 1 image
        img_bytes = _create_sample_jpeg_bytes(100, 100)
        self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("pkg.jpg", img_bytes, "image/jpeg")},
        )

        run_payload = {
            "inspection_facts": [
                {"fact_key": "is_prepackaged", "value": True},
                {"fact_key": "net_quantity_g", "value": 500, "unit": "g"},
            ],
            "target_requirements": ["R-6-1-a"],
            "applicability_context": {"R-6-1-a": "true"},
        }
        response = self.client.post(f"/api/v1/inspections/{insp_id}/run", json=run_payload)
        self.assertEqual(response.status_code, 200)
        rep_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(rep_resp.status_code, 200)
        data = rep_resp.json()
        self.assertEqual(data["inspection_id"], insp_id)
        self.assertIn("counts", data)

    def test_multiple_sessions_are_isolated(self) -> None:
        """Multiple inspection sessions in memory do not cross-contaminate images or reports."""
        sess1 = self.store.create_session(metadata={"label": "Session 1"})
        sess2 = self.store.create_session(metadata={"label": "Session 2"})
        id1 = sess1.inspection.inspection_id
        id2 = sess2.inspection.inspection_id

        # Upload image to session 1 only
        self.client.post(
            f"/api/v1/inspections/{id1}/images",
            files={"file": ("img1.jpg", _create_sample_jpeg_bytes(100, 100), "image/jpeg")},
        )

        # Check session 1 has 1 image
        r1 = self.client.get(f"/api/v1/inspections/{id1}")
        self.assertEqual(r1.json()["image_count"], 1)

        # Check session 2 has 0 images
        r2 = self.client.get(f"/api/v1/inspections/{id2}")
        self.assertEqual(r2.json()["image_count"], 0)

    def test_cors_headers_present(self) -> None:
        """CORS headers allow-origin are present on responses."""
        response = self.client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:3000")

    def test_validation_error_structure(self) -> None:
        """Invalid JSON schema payload returns 422 with standard error structure."""
        response = self.client.post(
            "/api/v1/inspections",
            headers={"Content-Type": "application/json"},
            content=b"{invalid_json_payload}",
        )
        self.assertIn(response.status_code, [400, 422])
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("code", data["error"])
        self.assertIn("message", data["error"])
        self.assertIn("details", data["error"])

    def test_openapi_schema_endpoint(self) -> None:
        """GET /openapi.json returns valid OpenAPI 3 schema documenting endpoints."""
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertEqual(schema["openapi"], "3.1.0")
        self.assertIn("/health", schema["paths"])
        self.assertIn("/api/v1/health", schema["paths"])
        self.assertIn("/api/v1/inspections", schema["paths"])
        self.assertIn("/api/v1/inspections/{inspection_id}", schema["paths"])
        self.assertIn("/api/v1/inspections/{inspection_id}/images", schema["paths"])
        self.assertIn("/api/v1/inspections/{inspection_id}/run", schema["paths"])
        self.assertIn("/api/v1/inspections/{inspection_id}/report", schema["paths"])

    def test_run_with_empty_images_succeeds_with_review_required(self) -> None:
        """Running pipeline on session with 0 images returns valid report with REVIEW_REQUIRED."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/run",
            json={"target_requirements": ["R-6-1-a"]},
        )
        self.assertEqual(response.status_code, 200)
        rep_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(rep_resp.status_code, 200)
        data = rep_resp.json()
        self.assertEqual(data["overall_status"], "REVIEW_REQUIRED")
        self.assertEqual(data["counts"]["image_count"], 0)

    def test_run_pipeline_fail_outcome(self) -> None:
        """When orchestrator produces a FAIL result, report overall_status is FAIL."""
        class FailingOrchestrator:
            def run(self, req: Any) -> InspectionReport:
                res = VerificationResult(
                    requirement_id="R-6-1-a",
                    status=VerificationStatus.FAIL,
                    reason="Mandatory MRP declaration is missing.",
                )
                return InspectionReport(
                    inspection_id=req.inspection_id,
                    overall_status=OverallInspectionStatus.FAIL,
                    verification_results=[res],
                    summary="Statutory compliance failure.",
                    evidence_count=0,
                    image_count=0,
                    applicable_requirement_count=1,
                    pass_count=0,
                    fail_count=1,
                    not_visible_count=0,
                    not_applicable_count=0,
                    review_required_count=0,
                )

        app.dependency_overrides[get_pipeline_orchestrator] = lambda: FailingOrchestrator()
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        response = self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})
        self.assertEqual(response.status_code, 200)
        rep_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(rep_resp.status_code, 200)
        data = rep_resp.json()
        self.assertEqual(data["overall_status"], "FAIL")
        self.assertEqual(data["counts"]["fail_count"], 1)

    def test_generic_exception_handler_returns_500(self) -> None:
        """When an unhandled exception occurs in pipeline, 500 PIPELINE_ERROR is returned on GET /report."""
        class CrashingOrchestrator:
            def run(self, req: Any) -> InspectionReport:
                raise RuntimeError("Simulated unexpected crash")

        app.dependency_overrides[get_pipeline_orchestrator] = lambda: CrashingOrchestrator()
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        response = self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})
        self.assertEqual(response.status_code, 200)
        rep_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(rep_resp.status_code, 500)
        data = rep_resp.json()
        self.assertEqual(data["error"]["code"], ErrorCode.PIPELINE_ERROR.value)
        self.assertIn("Simulated unexpected crash", data["error"]["details"]["error"])

    def test_pipeline_execution_error_returns_500_pipeline_error(self) -> None:
        """When orchestrator raises PipelineExecutionError, 500 with PIPELINE_ERROR code is returned on GET /report."""
        from backend.app.services.inspection_pipeline.errors import PipelineExecutionError

        class FailingPipelineOrchestrator:
            def run(self, req: Any) -> InspectionReport:
                raise PipelineExecutionError("Critical pipeline execution failure")

        app.dependency_overrides[get_pipeline_orchestrator] = lambda: FailingPipelineOrchestrator()
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        response = self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})
        self.assertEqual(response.status_code, 200)
        rep_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(rep_resp.status_code, 500)
        data = rep_resp.json()
        self.assertEqual(data["error"]["code"], ErrorCode.PIPELINE_ERROR.value)
        self.assertIn("Critical pipeline execution failure", data["error"]["message"])

    def test_upload_unsupported_format_returns_415(self) -> None:
        """Uploading an unsupported format such as GIF or BMP returns 415 IMAGE_UNSUPPORTED."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # Generate GIF image bytes
        img = Image.new("RGB", (50, 50), color=(100, 100, 100))
        buf = io.BytesIO()
        img.save(buf, format="GIF")
        gif_bytes = buf.getvalue()

        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("photo.gif", gif_bytes, "image/gif")},
        )
        self.assertEqual(response.status_code, 415)
        data = response.json()
        self.assertEqual(data["error"]["code"], ErrorCode.IMAGE_UNSUPPORTED.value)

    def test_reopen_inspection_lifecycle_via_store(self) -> None:
        """Verify marking ready and reopening inspection allows mutations again."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # Mark ready
        session.inspection.status = session.inspection.status.__class__.READY
        self.assertTrue(session.inspection.is_ready)

        # Reopen to COLLECTING
        session.inspection.status = session.inspection.status.__class__.COLLECTING
        self.assertTrue(session.inspection.is_collecting)

        # Adding image succeeds
        service = ImageIngestionService()
        art = service.ingest_bytes(_create_sample_jpeg_bytes(50, 50))
        ref = self.store.add_artifact(insp_id, art)
        self.assertEqual(ref.sequence, 1)

    def test_session_store_get_nonexistent_raises(self) -> None:
        """Directly querying nonexistent session on store raises InspectionNotFoundError."""
        from backend.app.services.inspection.errors import InspectionNotFoundError
        store = InMemoryInspectionStore()
        with self.assertRaises(InspectionNotFoundError):
            store.get_session("does_not_exist")


if __name__ == "__main__":
    unittest.main()






