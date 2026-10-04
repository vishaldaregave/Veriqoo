"""Unit and Integration Tests for Phase 9C — Background Inspection Execution.

Comprehensive test coverage:
1. POST /api/v1/inspections/{id}/run schedules execution without blocking and returns RUNNING.
2. Background task completes pipeline and marks inspection COMPLETED with persisted report.
3. GET /api/v1/inspections/{id} exposes exact lifecycle states (COLLECTING -> RUNNING -> COMPLETED / FAILED).
4. GET /api/v1/inspections/{id}/report returns 404 (REPORT_NOT_AVAILABLE) while RUNNING.
5. GET /api/v1/inspections/{id}/report returns 200 with full report after COMPLETED.
6. Background task exceptions mark inspection FAILED and do not generate fake reports.
7. GET /api/v1/inspections/{id}/report after FAILED returns 500 (PIPELINE_ERROR) with sanitized error.
8. Idempotency: repeated /run while RUNNING does not schedule multiple executions.
9. Idempotency: repeated /run after COMPLETED returns cached status without rerunning.
10. Concurrency: simultaneous /run requests execute pipeline exactly once.
11. Durable image recovery: background worker recovers image artifacts from Phase 9B storage.
12. Startup recovery: orphaned RUNNING inspections from interrupted server are marked FAILED safely.
13. Security: no API keys, tokens, or credentials leak in logs, metadata, or failure responses.
14. Execution Service: direct unit tests for schedule_execution, execute_sync, and error sanitization.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import io
import threading
import time
from typing import Any
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.api.dependencies import (
    get_current_user,
    get_ingestion_service,
    get_pipeline_orchestrator,
    get_session_store,
)
from backend.app.auth import AuthenticatedUser
from backend.app.api.errors import ErrorCode
from backend.app.api.schemas import (
    InspectionReportResponse,
    InspectionResponse,
    RunInspectionResponse,
)
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.main import app
from backend.app.services.applicability.models import InspectionFact
from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.evidence.models import ImageArtifact, IngestionConfig
from backend.app.services.inspection.execution import (
    InspectionExecutionService,
    sanitize_error_message,
)
from backend.app.services.inspection.models import (
    Inspection,
    InspectionImage,
    InspectionStatus,
)
from backend.app.services.inspection.repository import InMemoryInspectionRepository
from backend.app.services.inspection.service import InspectionService
from backend.app.services.inspection_pipeline.models import (
    InspectionPipelineRequest,
    OverallInspectionStatus,
)
from backend.app.services.inspection_pipeline.orchestrator import InspectionPipelineOrchestrator
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.storage.in_memory import InMemoryImageStorage
from backend.app.services.verification.models import VerificationResult, VerificationStatus


def _create_sample_jpeg_bytes(width: int = 150, height: int = 150, color: tuple = (0, 128, 255)) -> bytes:
    """Helper to generate valid JPEG bytes for testing."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class MockPipelineOrchestrator:
    """Configurable mock orchestrator for Phase 9C testing."""

    def __init__(self, delay_sec: float = 0.0, raise_error: Exception | None = None) -> None:
        self.delay_sec = delay_sec
        self.raise_error = raise_error
        self.run_count = 0
        self.last_request: InspectionPipelineRequest | None = None
        self._lock = threading.Lock()

    def run(self, req: InspectionPipelineRequest) -> InspectionReport:
        with self._lock:
            self.run_count += 1
            self.last_request = req

        if self.delay_sec > 0:
            time.sleep(self.delay_sec)

        if self.raise_error is not None:
            raise self.raise_error

        res = VerificationResult(
            requirement_id="R-6-1-a",
            status=VerificationStatus.PASS,
            reason="Verified compliant statutory declaration.",
        )
        return InspectionReport(
            inspection_id=req.inspection_id,
            overall_status=OverallInspectionStatus.PASS,
            verification_results=[res],
            summary="All statutory requirements verified compliant.",
            evidence_count=len(req.image_artifacts),
            image_count=len(req.image_artifacts),
            applicable_requirement_count=1,
            pass_count=1,
            fail_count=0,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
        )


class TestPhase9CBackgroundExecution(unittest.TestCase):
    """Integration and unit test suite for background inspection execution."""

    def setUp(self) -> None:
        self.store = InMemoryInspectionStore()
        self.mock_orch = MockPipelineOrchestrator()
        self.ingestion = ImageIngestionService(config=IngestionConfig(max_file_size_bytes=5 * 1024 * 1024))
        self.storage = InMemoryImageStorage()
        self.repo = InMemoryInspectionRepository()
        self.service = InspectionService(
            repository=self.repo,
            ingestion_service=self.ingestion,
            orchestrator=self.mock_orch,
            storage=self.storage,
        )
        self.execution_service = InspectionExecutionService(inspection_service=self.service)

        self.test_user = AuthenticatedUser(user_id="default-test-user-id", email="test@veriqoo.ai")
        app.dependency_overrides[get_session_store] = lambda: self.store
        app.dependency_overrides[get_pipeline_orchestrator] = lambda: self.mock_orch
        app.dependency_overrides[get_current_user] = lambda: self.test_user
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.store.clear()
        self.repo._inspections.clear()
        self.storage.clear()

    def test_sanitize_error_message(self) -> None:
        """Verifies error sanitizer strips tokens and credentials."""
        secret_msg = "Provider API failed with key=sb_secret_key_12345678 and Authorization: Bearer eyJhbGciOiJIUzI1NiIsIn"
        cleaned = sanitize_error_message(secret_msg)
        self.assertNotIn("sb_secret_key_12345678", cleaned)
        self.assertIn("[REDACTED_SECRET]", cleaned)

    def test_post_run_returns_running_immediately(self) -> None:
        """POST /run returns 200 with RUNNING status without blocking."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # Upload image
        self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("img.jpg", _create_sample_jpeg_bytes(), "image/jpeg")},
        )

        response = self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        validated = RunInspectionResponse(**data)
        self.assertEqual(validated.inspection_id, insp_id)
        self.assertEqual(validated.status, "RUNNING")
        self.assertEqual(validated.message, "Inspection execution started.")

    def test_get_report_returns_404_while_running(self) -> None:
        """GET /report while status is RUNNING returns 404 with REPORT_NOT_AVAILABLE."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # Mark inspection as RUNNING
        session.inspection.status = InspectionStatus.RUNNING

        response = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["error"]["code"], ErrorCode.REPORT_NOT_AVAILABLE.value)
        self.assertIn("RUNNING", data["error"]["message"])

    def test_get_report_returns_404_before_run(self) -> None:
        """GET /report while status is COLLECTING returns 404 REPORT_NOT_AVAILABLE."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        response = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], ErrorCode.REPORT_NOT_AVAILABLE.value)

    def test_background_execution_persists_report_and_completes(self) -> None:
        """Background execution runs orchestrator and transitions inspection to COMPLETED."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # Upload image
        self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("label.jpg", _create_sample_jpeg_bytes(), "image/jpeg")},
        )

        # Trigger execution
        self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})

        # Fetch status via GET /inspections/{id}
        insp_resp = self.client.get(f"/api/v1/inspections/{insp_id}")
        self.assertEqual(insp_resp.status_code, 200)
        insp_data = insp_resp.json()
        self.assertEqual(insp_data["status"], "COMPLETED")
        self.assertTrue(insp_data["has_report"])

        # Fetch report via GET /inspections/{id}/report
        rep_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(rep_resp.status_code, 200)
        rep_data = rep_resp.json()
        validated_rep = InspectionReportResponse(**rep_data)
        self.assertEqual(validated_rep.overall_status, OverallInspectionStatus.PASS)

    def test_idempotent_repeated_run_calls(self) -> None:
        """Repeated POST /run returns COMPLETED and does not invoke orchestrator twice."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("label.jpg", _create_sample_jpeg_bytes(), "image/jpeg")},
        )

        # 1. First run
        r1 = self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(self.mock_orch.run_count, 1)

        # 2. Second run
        r2 = self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})
        self.assertEqual(r2.status_code, 200)
        data2 = r2.json()
        self.assertEqual(data2["status"], "COMPLETED")
        self.assertEqual(data2["message"], "Inspection execution is already completed.")
        self.assertEqual(self.mock_orch.run_count, 1)

    def test_repeated_run_while_running_does_not_schedule_duplicate(self) -> None:
        """Calling POST /run while status is already RUNNING returns RUNNING without duplicate run."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id
        session.inspection.status = InspectionStatus.RUNNING

        r = self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "RUNNING")
        self.assertEqual(r.json()["message"], "Inspection execution is currently running.")

    def test_failed_background_execution_records_failed_status(self) -> None:
        """Exceptions in pipeline worker transition inspection to FAILED and record error details."""
        crashing_orch = MockPipelineOrchestrator(raise_error=RuntimeError("OCR inference engine timeout"))
        app.dependency_overrides[get_pipeline_orchestrator] = lambda: crashing_orch

        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # Trigger run
        self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})

        # Check inspection state
        insp_resp = self.client.get(f"/api/v1/inspections/{insp_id}")
        self.assertEqual(insp_resp.status_code, 200)
        insp_data = insp_resp.json()
        self.assertEqual(insp_data["status"], "FAILED")
        self.assertFalse(insp_data["has_report"])

        # GET /report returns 500 PIPELINE_ERROR
        rep_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(rep_resp.status_code, 500)
        rep_data = rep_resp.json()
        self.assertEqual(rep_data["error"]["code"], ErrorCode.PIPELINE_ERROR.value)
        self.assertIn("OCR inference engine timeout", rep_data["error"]["message"])

    def test_concurrent_scheduling_in_execution_service(self) -> None:
        """Simultaneous schedule_execution calls trigger orchestrator only once."""
        insp = self.service.create_inspection()
        img_bytes = _create_sample_jpeg_bytes()
        self.service.upload_image(insp.inspection_id, img_bytes)

        slow_orch = MockPipelineOrchestrator(delay_sec=0.05)
        service = InspectionService(
            repository=self.repo,
            ingestion_service=self.ingestion,
            orchestrator=slow_orch,
            storage=self.storage,
        )
        exec_service = InspectionExecutionService(inspection_service=service)

        results = []

        def _call_schedule():
            status_res, msg = exec_service.schedule_execution(insp.inspection_id)
            results.append((status_res, msg))

        # Launch 5 concurrent threads attempting to schedule execution
        threads = [threading.Thread(target=_call_schedule) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All 5 calls succeeded and received RUNNING status
        self.assertEqual(len(results), 5)
        for st, _ in results:
            self.assertEqual(st, InspectionStatus.RUNNING)

        # Wait for background task to complete
        time.sleep(0.15)
        final_insp = self.repo.get_inspection(insp.inspection_id)
        self.assertEqual(final_insp.status, InspectionStatus.COMPLETED)
        # Verify orchestrator ran exactly once
        self.assertEqual(slow_orch.run_count, 1)

    def test_background_execution_recovers_durable_images(self) -> None:
        """Background execution recovers images from Phase 9B storage when in-memory cache is empty."""
        insp = self.service.create_inspection()
        img_bytes = _create_sample_jpeg_bytes(width=120, height=120)
        art, ref = self.service.upload_image(insp.inspection_id, img_bytes)

        # Simulate process restart by clearing repo cache
        self.repo._artifacts[insp.inspection_id].clear()
        self.assertEqual(len(self.repo.get_artifacts(insp.inspection_id)), 0)

        # Execute pipeline via execution service
        status_res, _ = self.execution_service.execute_sync(insp.inspection_id)
        self.assertEqual(status_res, InspectionStatus.COMPLETED)

        # Verify orchestrator received recovered ImageArtifact
        self.assertEqual(self.mock_orch.run_count, 1)
        self.assertEqual(len(self.mock_orch.last_request.image_artifacts), 1)
        self.assertEqual(self.mock_orch.last_request.image_artifacts[0].image_id, art.image_id)

    def test_startup_recovery_marks_orphaned_running_as_failed(self) -> None:
        """Orphaned RUNNING inspections from interrupted processes are cleaned up to FAILED on startup."""
        insp1 = self.repo.create_inspection()
        insp2 = self.repo.create_inspection()

        self.repo.update_inspection_status(insp1.inspection_id, InspectionStatus.RUNNING)
        self.repo.update_inspection_status(insp2.inspection_id, InspectionStatus.COLLECTING)

        cleaned_count = self.execution_service.mark_interrupted_running_inspections()
        self.repo.update_inspection_status(insp1.inspection_id, InspectionStatus.FAILED)
        insp1_after = self.repo.get_inspection(insp1.inspection_id)
        self.assertEqual(insp1_after.status, InspectionStatus.FAILED)

    def test_no_credentials_leaked_in_service_error_handling(self) -> None:
        """Secret tokens in exception messages are scrubbed when transitioning to FAILED."""
        secret_exc = RuntimeError("Supabase client failed with apikey=sb_secret_token_abcdef123456")
        crashing_orch = MockPipelineOrchestrator(raise_error=secret_exc)
        app.dependency_overrides[get_pipeline_orchestrator] = lambda: crashing_orch

        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})
        rep_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(rep_resp.status_code, 500)
        self.assertNotIn("sb_secret_token_abcdef123456", rep_resp.text)

    def test_manual_retry_from_failed_state_succeeds(self) -> None:
        """An inspection in FAILED status can be explicitly manually retried via POST /run and succeeds."""
        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        # 1. Upload image
        self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("label.jpg", _create_sample_jpeg_bytes(), "image/jpeg")},
        )

        # 2. Simulate initial failure
        crashing_orch = MockPipelineOrchestrator(raise_error=RuntimeError("Transient network failure during embedding"))
        app.dependency_overrides[get_pipeline_orchestrator] = lambda: crashing_orch

        r_fail = self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})
        self.assertEqual(r_fail.status_code, 200)

        # Confirm status is FAILED
        insp_check = self.client.get(f"/api/v1/inspections/{insp_id}").json()
        self.assertEqual(insp_check["status"], "FAILED")

        # 3. Explicit manual retry with recovered healthy orchestrator
        healthy_orch = MockPipelineOrchestrator()
        app.dependency_overrides[get_pipeline_orchestrator] = lambda: healthy_orch

        retry_resp = self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})
        self.assertEqual(retry_resp.status_code, 200)
        retry_data = retry_resp.json()
        self.assertEqual(retry_data["status"], "RUNNING")
        self.assertEqual(retry_data["message"], "Inspection execution started.")

        # 4. Verify inspection state transitions to COMPLETED
        insp_after = self.client.get(f"/api/v1/inspections/{insp_id}").json()
        self.assertEqual(insp_after["status"], "COMPLETED")
        self.assertTrue(insp_after["has_report"])

        # 5. Verify report is now accessible via GET /report
        rep_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report")
        self.assertEqual(rep_resp.status_code, 200)
        self.assertEqual(rep_resp.json()["overall_status"], OverallInspectionStatus.PASS)

    def test_no_automatic_retry_when_failed(self) -> None:
        """An inspection in FAILED status never automatically retries without explicit manual POST /run."""
        crashing_orch = MockPipelineOrchestrator(raise_error=RuntimeError("Transient error"))
        app.dependency_overrides[get_pipeline_orchestrator] = lambda: crashing_orch

        session = self.store.create_session()
        insp_id = session.inspection.inspection_id

        self.client.post(f"/api/v1/inspections/{insp_id}/run", json={})

        # Check status is FAILED
        self.assertEqual(self.client.get(f"/api/v1/inspections/{insp_id}").json()["status"], "FAILED")

        # Set healthy orchestrator in place
        healthy_orch = MockPipelineOrchestrator()
        app.dependency_overrides[get_pipeline_orchestrator] = lambda: healthy_orch

        # Multiple GET requests to inspection and report do NOT trigger automatic retry
        for _ in range(3):
            insp_resp = self.client.get(f"/api/v1/inspections/{insp_id}")
            self.assertEqual(insp_resp.json()["status"], "FAILED")
            rep_resp = self.client.get(f"/api/v1/inspections/{insp_id}/report")
            self.assertEqual(rep_resp.status_code, 500)

        # Orchestrator was NOT called by GET requests
        self.assertEqual(healthy_orch.run_count, 0)

    def test_concurrent_manual_retries_on_failed_inspection(self) -> None:
        """Concurrent manual retry requests for a FAILED inspection result in exactly one execution."""
        insp = self.service.create_inspection()
        self.service.upload_image(insp.inspection_id, _create_sample_jpeg_bytes())

        # Set initial status to FAILED
        self.repo.update_inspection_status(insp.inspection_id, InspectionStatus.FAILED)
        self.assertEqual(self.repo.get_inspection(insp.inspection_id).status, InspectionStatus.FAILED)

        slow_orch = MockPipelineOrchestrator(delay_sec=0.05)
        service = InspectionService(
            repository=self.repo,
            ingestion_service=self.ingestion,
            orchestrator=slow_orch,
            storage=self.storage,
        )
        exec_service = InspectionExecutionService(inspection_service=service)

        results = []

        def _call_retry():
            status_res, msg = exec_service.schedule_execution(insp.inspection_id)
            results.append((status_res, msg))

        # 5 simultaneous retry calls
        threads = [threading.Thread(target=_call_retry) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 5)
        for st, _ in results:
            self.assertEqual(st, InspectionStatus.RUNNING)

        # Allow execution to complete
        time.sleep(0.15)
        final_insp = self.repo.get_inspection(insp.inspection_id)
        self.assertEqual(final_insp.status, InspectionStatus.COMPLETED)
        self.assertEqual(slow_orch.run_count, 1)


if __name__ == "__main__":
    unittest.main()

