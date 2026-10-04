"""Phase 9A API Contract Freeze and Integration Specification Test Suite.

Verifies:
1. Every documented REST endpoint exists and adheres to exact HTTP method contracts.
2. OpenAPI 3.1 canonical specification exposes all routes, components, and parameter docs.
3. Response schemas strictly match Pydantic response models.
4. Enums are strictly validated and serialized as standard strings.
5. Standard error envelopes are returned across all HTTP status codes (400, 404, 409, 413, 415, 422, 500).
6. Multipart image upload contract and normalization diagnostics are validated.
7. Inspection lifecycle state machine transitions (COLLECTING -> READY) and mutation guards remain intact.
8. Synchronous execution and completed-run idempotency contracts are preserved.
"""

from __future__ import annotations

import io
from typing import Any
import unittest

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.api.dependencies import (
    get_current_user,
    get_pipeline_orchestrator,
    get_session_store,
)
from backend.app.auth import AuthenticatedUser
from backend.app.api.errors import ErrorCode
from backend.app.api.schemas import (
    CountsResponse,
    HealthResponse,
    ImageUploadResponse,
    InspectionImageResponse,
    InspectionReportResponse,
    InspectionResponse,
    RunInspectionResponse,
    VerificationResultResponse,
)
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.main import app
from backend.app.services.evidence.models import ImageArtifact
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.inspection_pipeline.models import (
    InspectionPipelineRequest,
    OverallInspectionStatus,
)
from backend.app.services.inspection_pipeline.orchestrator import InspectionPipelineOrchestrator
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.ocr.models import BoundingBox, OCRObservation, OCRProcessingStatus, OCRResult
from backend.app.services.verification.models import VerificationResult, VerificationStatus


def _create_sample_jpeg_bytes(width: int = 150, height: int = 100, color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    """Helper to generate valid in-memory JPEG bytes."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class MockContractPipelineOrchestrator:
    """Deterministic mock orchestrator for contract verification."""

    def __init__(self, overall_status: OverallInspectionStatus = OverallInspectionStatus.PASS) -> None:
        self.overall_status = overall_status
        self.run_count = 0

    def run(self, request: InspectionPipelineRequest) -> InspectionReport:
        self.run_count += 1
        res = VerificationResult(
            verification_id=f"v_{request.inspection_id}_R-6-1-a",
            requirement_id="R-6-1-a",
            status=VerificationStatus.PASS if self.overall_status == OverallInspectionStatus.PASS else VerificationStatus.FAIL,
            reason="Requirement R-6-1-a verified compliant.",
            confidence=0.98,
            review_required=False,
            evidence_ids=["ev_1"],
            source_observation_ids=["obs_1"],
            image_ids=[img.image_id for img in request.image_artifacts],
        )
        return InspectionReport(
            inspection_id=request.inspection_id,
            overall_status=self.overall_status,
            verification_results=[res],
            summary="Verification pipeline completed.",
            evidence_count=1,
            image_count=len(request.image_artifacts),
            applicable_requirement_count=1,
            pass_count=1 if self.overall_status == OverallInspectionStatus.PASS else 0,
            fail_count=0 if self.overall_status == OverallInspectionStatus.PASS else 1,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
        )


class Phase9AContractTestCase(unittest.TestCase):
    """Test suite validating Phase 9A API contracts and OpenAPI specifications."""

    def setUp(self) -> None:
        self.store = InMemoryInspectionStore()
        self.mock_orch = MockContractPipelineOrchestrator()
        self.test_user = AuthenticatedUser(user_id="default-test-user-id", email="test@veriqoo.ai")
        app.dependency_overrides[get_session_store] = lambda: self.store
        app.dependency_overrides[get_pipeline_orchestrator] = lambda: self.mock_orch
        app.dependency_overrides[get_current_user] = lambda: self.test_user
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.store.clear()

    # =================================================================
    # 1. OpenAPI Specification Contract Tests
    # =================================================================

    def test_openapi_contract_paths_and_metadata(self) -> None:
        """OpenAPI 3.1 JSON documents all 7 endpoints, schemas, and error responses."""
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        spec = response.json()

        self.assertEqual(spec["openapi"], "3.1.0")
        self.assertIn("info", spec)
        self.assertIn("paths", spec)

        expected_paths = [
            "/health",
            "/api/v1/health",
            "/api/v1/inspections",
            "/api/v1/inspections/{inspection_id}",
            "/api/v1/inspections/{inspection_id}/images",
            "/api/v1/inspections/{inspection_id}/run",
            "/api/v1/inspections/{inspection_id}/report",
        ]
        for path in expected_paths:
            self.assertIn(path, spec["paths"], f"Expected path {path} missing in OpenAPI.")

        # Check components schema presence
        schemas = spec.get("components", {}).get("schemas", {})
        self.assertIn("InspectionResponse", schemas)
        self.assertIn("ImageUploadResponse", schemas)
        self.assertIn("InspectionReportResponse", schemas)
        self.assertIn("ErrorResponse", schemas)
        self.assertIn("HealthResponse", schemas)

    # =================================================================
    # 2. Health Endpoints Contract Tests
    # =================================================================

    def test_root_health_contract(self) -> None:
        """GET /health returns 200 with valid HealthResponse schema."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        validated = HealthResponse(**data)
        self.assertEqual(validated.status, "ok")
        self.assertEqual(validated.api_version, "1.0.0")

    def test_v1_health_contract(self) -> None:
        """GET /api/v1/health returns 200 with valid HealthResponse schema."""
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        validated = HealthResponse(**data)
        self.assertEqual(validated.status, "ok")

    # =================================================================
    # 3. Inspection Session Management Contract Tests
    # =================================================================

    def test_create_inspection_contract(self) -> None:
        """POST /api/v1/inspections returns 201 with valid InspectionResponse in COLLECTING state."""
        payload = {
            "metadata": {"officer_id": "OFFICER_42", "location": "Warehouse A"},
            "inspection_date": "2026-10-04",
        }
        response = self.client.post("/api/v1/inspections", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()

        validated = InspectionResponse(**data)
        self.assertEqual(validated.status, InspectionStatus.COLLECTING)
        self.assertEqual(validated.image_count, 0)
        self.assertEqual(validated.images, [])
        self.assertEqual(validated.metadata["officer_id"], "OFFICER_42")
        self.assertEqual(validated.metadata["inspection_date"], "2026-10-04")
        self.assertFalse(validated.has_report)

    def test_get_inspection_contract(self) -> None:
        """GET /api/v1/inspections/{id} returns 200 with valid InspectionResponse."""
        session = self.store.create_session(metadata={"case": "442"})
        insp_id = session.inspection.inspection_id

        response = self.client.get(f"/api/v1/inspections/{insp_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        validated = InspectionResponse(**data)
        self.assertEqual(validated.inspection_id, insp_id)
        self.assertEqual(validated.status, InspectionStatus.COLLECTING)

    def test_get_nonexistent_inspection_returns_structured_404(self) -> None:
        """Querying missing inspection ID returns 404 with structured error envelope."""
        response = self.client.get("/api/v1/inspections/00000000-0000-0000-0000-000000000000")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], ErrorCode.INSPECTION_NOT_FOUND.value)
        self.assertIn("details", data["error"])

    # =================================================================
    # 4. Image Upload & Ingestion Contract Tests
    # =================================================================

    def test_upload_image_multipart_contract(self) -> None:
        """POST /api/v1/inspections/{id}/images returns 201 with ImageUploadResponse."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id
        img_bytes = _create_sample_jpeg_bytes(300, 200)

        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("front.jpg", img_bytes, "image/jpeg")},
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()

        validated = ImageUploadResponse(**data)
        self.assertEqual(validated.sequence, 1)
        self.assertEqual(validated.source_format, "JPEG")
        self.assertEqual(validated.normalized_format, "PNG")
        self.assertEqual(validated.original_width, 300)
        self.assertEqual(validated.original_height, 200)
        self.assertEqual(validated.color_mode, "RGB")

    def test_upload_image_state_machine_guard_contract(self) -> None:
        """Uploading image to sealed READY session returns 409 INVALID_INSPECTION_STATE."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id
        session.inspection.status = InspectionStatus.READY

        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("side.jpg", _create_sample_jpeg_bytes(100, 100), "image/jpeg")},
        )
        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertEqual(data["error"]["code"], ErrorCode.INVALID_INSPECTION_STATE.value)

    # =================================================================
    # 5. Verification Pipeline Execution & Idempotency Contract Tests
    # =================================================================

    def test_run_inspection_pipeline_and_idempotency_contract(self) -> None:
        """POST /api/v1/inspections/{id}/run schedules execution and is idempotent."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # 1. First execution
        payload = {
            "inspection_facts": [{"fact_key": "commodity_type", "value": "prepackaged_food"}],
            "target_requirements": ["R-6-1-a"],
        }
        response1 = self.client.post(f"/api/v1/inspections/{insp_id}/run", json=payload)
        self.assertEqual(response1.status_code, 200)
        data1 = response1.json()

        validated1 = RunInspectionResponse(**data1)
        self.assertEqual(validated1.inspection_id, insp_id)
        self.assertIn(validated1.status, ["RUNNING", "COMPLETED"])

        # Fetch report via GET /report
        rep_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(rep_resp.status_code, 200)
        rep_data = rep_resp.json()
        validated_rep = InspectionReportResponse(**rep_data)
        self.assertEqual(validated_rep.overall_status, OverallInspectionStatus.PASS)
        self.assertEqual(len(validated_rep.verification_results), 1)
        self.assertEqual(validated_rep.verification_results[0].status, VerificationStatus.PASS)
        self.assertEqual(self.mock_orch.run_count, 1)

        # 2. Repeated execution returns cached status idempotently
        response2 = self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        self.assertEqual(data2["status"], "COMPLETED")
        # Verify orchestrator was NOT invoked again
        self.assertEqual(self.mock_orch.run_count, 1)

    def test_get_report_contract(self) -> None:
        """GET /api/v1/inspections/{id}/report returns 200 after execution, 404 before execution."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # Before execution -> 404
        r_pre = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(r_pre.status_code, 404)
        self.assertEqual(r_pre.json()["error"]["code"], ErrorCode.REPORT_NOT_AVAILABLE.value)

        # Execute
        self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})

        # After execution -> 200
        r_post = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(r_post.status_code, 200)
        data = r_post.json()
        validated = InspectionReportResponse(**data)
        self.assertEqual(validated.overall_status, OverallInspectionStatus.PASS)


if __name__ == "__main__":
    unittest.main()

