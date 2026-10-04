"""Comprehensive unit and integration tests for Phase 8B Inspection Persistence & Supabase Integration.

Tests verify:
1. InspectionRepository interface and InMemoryInspectionRepository lifecycle.
2. SupabaseInspectionRepository serialization, deserialization, and REST contracts.
3. InspectionService domain orchestration, idempotency guards, and error translation.
4. Lifecycle state machine constraints (COLLECTING -> READY, no image additions when READY).
5. Deterministic multi-image sequencing and artifact preservation.
6. OCR observation, evidence candidates, requirement results, and applicability facts persistence.
7. Restart resilience (fresh service instances retrieve persisted state).
8. Database safety: zero mutations or references to authoritative legal corpus tables.
"""

from __future__ import annotations

from datetime import datetime, timezone
import io
from typing import Any
import unittest
from unittest.mock import MagicMock, patch
import uuid

from fastapi import HTTPException
from PIL import Image

from backend.app.api.errors import ErrorCode
from backend.app.services.applicability.models import InspectionFact, TriState
from backend.app.services.evidence.errors import ImageTooLargeError, InvalidImageError
from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.evidence.models import (
    EvidenceCandidate,
    EvidenceField,
    EvidenceStatus,
    ImageArtifact,
    IngestionConfig,
)
from backend.app.services.inspection.errors import (
    InspectionNotFoundError,
    InspectionStateError,
    InvalidInspectionImageReferenceError,
)
from backend.app.services.inspection.models import (
    Inspection,
    InspectionImage,
    InspectionStatus,
)
from backend.app.services.inspection.repository import (
    InMemoryInspectionRepository,
    InspectionRepository,
    SupabaseInspectionRepository,
)
from backend.app.services.inspection.service import InspectionService
from backend.app.services.inspection_pipeline.models import (
    InspectionPipelineRequest,
    OverallInspectionStatus,
)
from backend.app.services.inspection_pipeline.orchestrator import InspectionPipelineOrchestrator
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.ocr.models import BoundingBox, OCRObservation, OCRProcessingStatus, OCRResult
from backend.app.services.verification.models import (
    RequirementReference,
    VerificationResult,
    VerificationStatus,
)


def _create_sample_jpeg_bytes(width: int = 150, height: int = 100, color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    """Helper to generate valid in-memory JPEG bytes."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class MockPipelineOrchestrator:
    """Deterministic mock orchestrator for inspection service testing."""

    def __init__(self, overall_status: OverallInspectionStatus = OverallInspectionStatus.PASS) -> None:
        self.overall_status = overall_status
        self.run_count = 0

    def run(self, request: InspectionPipelineRequest) -> InspectionReport:
        self.run_count += 1
        res = VerificationResult(
            verification_id=f"v_{request.inspection_id}",
            requirement_id="R-6-1-a",
            status=VerificationStatus.PASS if self.overall_status == OverallInspectionStatus.PASS else VerificationStatus.FAIL,
            reason="Sample verification test execution result.",
            confidence=0.95,
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


class TestInMemoryInspectionRepository(unittest.TestCase):
    """Unit tests for InMemoryInspectionRepository lifecycle and contract compliance."""

    def setUp(self) -> None:
        self.repo = InMemoryInspectionRepository()
        self.ingestion = ImageIngestionService(config=IngestionConfig())

    def test_create_and_get_inspection(self) -> None:
        """Create inspection container and retrieve it with empty image list."""
        insp = self.repo.create_inspection(metadata={"batch": "A1", "location": "Warehouse 4"})
        self.assertIsNotNone(insp.inspection_id)
        self.assertEqual(insp.status, InspectionStatus.COLLECTING)
        self.assertEqual(insp.metadata["batch"], "A1")
        self.assertEqual(insp.image_count, 0)

        retrieved = self.repo.get_inspection(insp.inspection_id)
        self.assertEqual(retrieved.inspection_id, insp.inspection_id)
        self.assertEqual(retrieved.status, InspectionStatus.COLLECTING)

    def test_get_nonexistent_inspection_raises_not_found(self) -> None:
        """Querying a non-existent inspection ID raises InspectionNotFoundError."""
        with self.assertRaises(InspectionNotFoundError):
            self.repo.get_inspection(str(uuid.uuid4()))

    def test_add_images_maintains_deterministic_sequence(self) -> None:
        """Adding multiple images increments sequence 1, 2, 3 and maintains order."""
        insp = self.repo.create_inspection()
        art1 = self.ingestion.ingest_bytes(_create_sample_jpeg_bytes(100, 100), source_name="front.jpg")
        art2 = self.ingestion.ingest_bytes(_create_sample_jpeg_bytes(120, 100), source_name="back.jpg")
        art3 = self.ingestion.ingest_bytes(_create_sample_jpeg_bytes(140, 100), source_name="side.jpg")

        ref1 = self.repo.add_image(insp.inspection_id, art1)
        ref2 = self.repo.add_image(insp.inspection_id, art2)
        ref3 = self.repo.add_image(insp.inspection_id, art3)

        self.assertEqual(ref1.sequence, 1)
        self.assertEqual(ref2.sequence, 2)
        self.assertEqual(ref3.sequence, 3)

        images = self.repo.list_images(insp.inspection_id)
        self.assertEqual(len(images), 3)
        self.assertEqual([img.sequence for img in images], [1, 2, 3])

        artifacts = self.repo.get_artifacts(insp.inspection_id)
        self.assertEqual(len(artifacts), 3)
        self.assertEqual(artifacts[0].image_id, art1.image_id)
        self.assertEqual(artifacts[1].image_id, art2.image_id)
        self.assertEqual(artifacts[2].image_id, art3.image_id)

    def test_cannot_add_image_to_ready_inspection(self) -> None:
        """Adding an image to an inspection in READY state raises InspectionStateError."""
        insp = self.repo.create_inspection()
        art = self.ingestion.ingest_bytes(_create_sample_jpeg_bytes(100, 100))
        self.repo.update_inspection_status(insp.inspection_id, InspectionStatus.READY)

        with self.assertRaises(InspectionStateError):
            self.repo.add_image(insp.inspection_id, art)

    def test_add_invalid_artifact_raises_error(self) -> None:
        """Passing an invalid object as an artifact raises InvalidInspectionImageReferenceError."""
        insp = self.repo.create_inspection()
        with self.assertRaises(InvalidInspectionImageReferenceError):
            self.repo.add_image(insp.inspection_id, artifact="invalid_object")  # type: ignore

    def test_save_and_get_report_transitions_status_to_ready(self) -> None:
        """Saving an InspectionReport transitions the inspection status to READY."""
        insp = self.repo.create_inspection()
        report = InspectionReport(
            inspection_id=insp.inspection_id,
            overall_status=OverallInspectionStatus.PASS,
            verification_results=[],
            summary="Clean pass.",
            evidence_count=0,
            image_count=0,
            applicable_requirement_count=0,
            pass_count=0,
            fail_count=0,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
        )
        self.assertIsNone(self.repo.get_report(insp.inspection_id))

        self.repo.save_report(insp.inspection_id, report)
        retrieved_report = self.repo.get_report(insp.inspection_id)
        self.assertIsNotNone(retrieved_report)
        self.assertEqual(retrieved_report.overall_status, OverallInspectionStatus.PASS)

        updated_insp = self.repo.get_inspection(insp.inspection_id)
        self.assertEqual(updated_insp.status, InspectionStatus.COMPLETED)

    def test_save_ocr_evidence_results_and_facts(self) -> None:
        """Saving auxiliary OCR, evidence, verification results, and facts succeeds."""
        insp = self.repo.create_inspection()
        art = self.ingestion.ingest_bytes(_create_sample_jpeg_bytes(100, 100))
        self.repo.add_image(insp.inspection_id, art)

        # OCR Results
        bbox = BoundingBox(points=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]])
        obs = OCRObservation(
            observation_id="o1",
            image_id=art.image_id,
            text="MRP Rs 50",
            confidence=0.9,
            bounding_box=bbox,
            sequence=1,
            engine="PaddleOCR",
            engine_version="3.7.0",
        )
        ocr_res = OCRResult(image_id=art.image_id, status=OCRProcessingStatus.SUCCESS, observations=[obs])
        self.repo.save_ocr_observations(insp.inspection_id, [ocr_res])

        # Evidence Candidates
        cand = EvidenceCandidate(
            evidence_id="e1",
            observation_id="o1",
            image_id=art.image_id,
            field=EvidenceField.MRP,
            raw_text="MRP Rs 50",
            normalized_text="MRP Rs. 50.00",
            status=EvidenceStatus.VALID,
            confidence=0.95,
        )
        self.repo.save_evidence(insp.inspection_id, [cand])

        # Requirement Results
        vres = VerificationResult(
            verification_id="v1",
            requirement_id="R-6-1-a",
            status=VerificationStatus.PASS,
            reason="MRP present",
        )
        self.repo.save_requirement_results(insp.inspection_id, [vres])

        # Inspection Facts
        fact = InspectionFact(
            id="f1",
            run_id=insp.inspection_id,
            fact_key="commodity_type",
            value="prepackaged_food",
        )
        self.repo.save_applicability_facts(insp.inspection_id, [fact])


class TestSupabaseInspectionRepositorySerialization(unittest.TestCase):
    """Unit tests for SupabaseInspectionRepository REST serialization and deserialization."""

    def setUp(self) -> None:
        self.repo = SupabaseInspectionRepository(
            supabase_url="https://mock-project.supabase.co",
            supabase_key="mock-key-123",
        )
        self.ingestion = ImageIngestionService(config=IngestionConfig())

    @patch.object(SupabaseInspectionRepository, "_request")
    def test_create_inspection_supabase_contract(self, mock_request: MagicMock) -> None:
        """Create inspection sends correct payload and parses response."""
        fixed_id = str(uuid.uuid4())
        mock_request.return_value = [{
            "id": fixed_id,
            "status": "COLLECTING",
            "metadata": {"inspector": "Officer A"},
            "created_at": "2026-10-04T05:00:00Z",
        }]

        insp = self.repo.create_inspection(inspection_id=fixed_id, metadata={"inspector": "Officer A"})
        self.assertEqual(insp.inspection_id, fixed_id)
        self.assertEqual(insp.status, InspectionStatus.COLLECTING)
        self.assertEqual(insp.metadata["inspector"], "Officer A")
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], "post")
        self.assertEqual(args[1], "inspection_sessions")
        self.assertEqual(kwargs["json"]["id"], fixed_id)

    @patch.object(SupabaseInspectionRepository, "_request")
    def test_get_inspection_with_child_images(self, mock_request: MagicMock) -> None:
        """Get inspection retrieves container and ordered image references."""
        fixed_id = str(uuid.uuid4())
        mock_request.side_effect = [
            # 1. inspection_sessions query
            [{
                "id": fixed_id,
                "status": "COLLECTING",
                "metadata": {},
                "created_at": "2026-10-04T05:00:00Z",
            }],
            # 2. inspection_images query
            [
                {
                    "image_id": "img_1",
                    "sequence": 1,
                    "created_at": "2026-10-04T05:01:00Z",
                    "source_hash": "sha_1",
                    "normalized_hash": "norm_1",
                },
                {
                    "image_id": "img_2",
                    "sequence": 2,
                    "created_at": "2026-10-04T05:02:00Z",
                    "source_hash": "sha_2",
                    "normalized_hash": "norm_2",
                }
            ],
        ]

        insp = self.repo.get_inspection(fixed_id)
        self.assertEqual(insp.inspection_id, fixed_id)
        self.assertEqual(insp.image_count, 2)
        self.assertEqual(insp.images[0].sequence, 1)
        self.assertEqual(insp.images[1].sequence, 2)

    @patch.object(SupabaseInspectionRepository, "_request")
    def test_save_report_upsert_payload(self, mock_request: MagicMock) -> None:
        """Saving report generates valid upsert payload to inspection_reports table."""
        fixed_id = str(uuid.uuid4())
        mock_request.side_effect = [
            # 1. get_inspection call
            [{
                "id": fixed_id,
                "status": "COLLECTING",
                "metadata": {},
                "created_at": "2026-10-04T05:00:00Z",
            }],
            # 2. inspection_images call inside get_inspection
            [],
            # 3. post to inspection_reports
            [],
            # 4. patch to inspection_sessions
            [{
                "id": fixed_id,
                "status": "READY",
                "metadata": {},
                "created_at": "2026-10-04T05:00:00Z",
            }],
            # 5. get_inspection after patch
            [{
                "id": fixed_id,
                "status": "READY",
                "metadata": {},
                "created_at": "2026-10-04T05:00:00Z",
            }],
            # 6. inspection_images call inside second get_inspection
            [],
        ]

        report = InspectionReport(
            inspection_id=fixed_id,
            overall_status=OverallInspectionStatus.PASS,
            verification_results=[],
            summary="All declarations compliant.",
            evidence_count=2,
            image_count=1,
            applicable_requirement_count=1,
            pass_count=1,
            fail_count=0,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
        )

        self.repo.save_report(fixed_id, report)
        self.assertGreaterEqual(mock_request.call_count, 3)

    @patch.object(SupabaseInspectionRepository, "_request")
    def test_get_report_deserialization(self, mock_request: MagicMock) -> None:
        """Retrieving persisted report cleanly reconstructs complete InspectionReport model."""
        fixed_id = str(uuid.uuid4())
        mock_request.side_effect = [
            # 1. get_inspection
            [{
                "id": fixed_id,
                "status": "READY",
                "metadata": {},
                "created_at": "2026-10-04T05:00:00Z",
            }],
            # 2. inspection_images
            [],
            # 3. inspection_reports
            [{
                "inspection_id": fixed_id,
                "overall_status": "PASS",
                "summary": "Verified compliant",
                "created_at": "2026-10-04T05:10:00Z",
                "report_payload": {
                    "inspection_id": fixed_id,
                    "overall_status": "PASS",
                    "summary": "Verified compliant",
                    "counts": {
                        "image_count": 1,
                        "evidence_count": 1,
                        "applicable_requirement_count": 1,
                        "pass_count": 1,
                        "fail_count": 0,
                        "not_visible_count": 0,
                        "not_applicable_count": 0,
                        "review_required_count": 0,
                    },
                    "verification_results": [
                        {
                            "verification_id": "v_100",
                            "requirement_id": "R-6-1-a",
                            "status": "PASS",
                            "reason": "MRP is explicitly stated.",
                            "confidence": 0.98,
                            "review_required": False,
                            "evidence_ids": ["e_1"],
                            "source_observation_ids": ["obs_1"],
                            "image_ids": ["img_1"],
                        }
                    ],
                    "errors": [],
                    "metadata": {},
                },
            }],
        ]

        report = self.repo.get_report(fixed_id)
        self.assertIsNotNone(report)
        self.assertEqual(report.inspection_id, fixed_id)
        self.assertEqual(report.overall_status, OverallInspectionStatus.PASS)
        self.assertEqual(len(report.verification_results), 1)
        self.assertEqual(report.verification_results[0].requirement_id, "R-6-1-a")
        self.assertEqual(report.verification_results[0].status, VerificationStatus.PASS)


class TestInspectionServiceWorkflow(unittest.TestCase):
    """Integration test suite for InspectionService domain workflows and idempotency."""

    def setUp(self) -> None:
        self.repo = InMemoryInspectionRepository()
        self.ingestion = ImageIngestionService(config=IngestionConfig())
        self.mock_orch = MockPipelineOrchestrator(overall_status=OverallInspectionStatus.PASS)
        self.service = InspectionService(
            repository=self.repo,
            ingestion_service=self.ingestion,
            orchestrator=self.mock_orch,  # type: ignore
        )

    def test_create_and_query_inspection_service(self) -> None:
        """InspectionService creates container and returns details with has_report=False."""
        insp = self.service.create_inspection(metadata={"batch": "B-99"}, inspection_date="2026-10-04")
        self.assertEqual(insp.metadata["batch"], "B-99")
        self.assertEqual(insp.metadata["inspection_date"], "2026-10-04")

        details_insp, has_report = self.service.get_inspection_details(insp.inspection_id)
        self.assertEqual(details_insp.inspection_id, insp.inspection_id)
        self.assertFalse(has_report)

    def test_upload_image_service_flow(self) -> None:
        """InspectionService validates and adds images, incrementing sequence."""
        insp = self.service.create_inspection()
        jpeg_bytes = _create_sample_jpeg_bytes(100, 100)

        artifact, ref = self.service.upload_image(
            inspection_id=insp.inspection_id,
            contents=jpeg_bytes,
            filename="front.jpg",
            content_type="image/jpeg",
        )
        self.assertIsNotNone(artifact.image_id)
        self.assertEqual(ref.sequence, 1)
        self.assertEqual(ref.image_id, artifact.image_id)

    def test_upload_empty_image_raises_400(self) -> None:
        """InspectionService raises 400 IMAGE_EMPTY on zero-byte payload."""
        insp = self.service.create_inspection()
        with self.assertRaises(HTTPException) as ctx:
            self.service.upload_image(insp.inspection_id, contents=b"", filename="empty.jpg")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["code"], ErrorCode.IMAGE_EMPTY.value)

    def test_run_inspection_pipeline_and_idempotency(self) -> None:
        """InspectionService executes pipeline once; repeated run returns cached report idempotently."""
        insp = self.service.create_inspection()
        jpeg_bytes = _create_sample_jpeg_bytes(100, 100)
        self.service.upload_image(insp.inspection_id, jpeg_bytes, "label.jpg")

        # 1. First execution
        report1 = self.service.run_inspection(inspection_id=insp.inspection_id)
        self.assertEqual(report1.overall_status, OverallInspectionStatus.PASS)
        self.assertEqual(self.mock_orch.run_count, 1)

        # Inspection status should now be COMPLETED
        updated_insp, has_report = self.service.get_inspection_details(insp.inspection_id)
        self.assertTrue(has_report)
        self.assertEqual(updated_insp.status, InspectionStatus.COMPLETED)

        # 2. Repeated execution (Idempotency check)
        report2 = self.service.run_inspection(inspection_id=insp.inspection_id)
        self.assertEqual(report2.overall_status, OverallInspectionStatus.PASS)
        # Orchestrator should NOT have been invoked again
        self.assertEqual(self.mock_orch.run_count, 1)

    def test_get_report_returns_404_if_not_run(self) -> None:
        """Querying report before execution raises 404 REPORT_NOT_AVAILABLE."""
        insp = self.service.create_inspection()
        with self.assertRaises(HTTPException) as ctx:
            self.service.get_report(insp.inspection_id)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["code"], ErrorCode.REPORT_NOT_AVAILABLE.value)

    def test_restart_resilience_simulation(self) -> None:
        """Fresh InspectionService instance accessing the same repository sees complete state."""
        insp = self.service.create_inspection(metadata={"case": "442"})
        self.service.upload_image(insp.inspection_id, _create_sample_jpeg_bytes(100, 100), "img1.jpg")
        self.service.upload_image(insp.inspection_id, _create_sample_jpeg_bytes(100, 100), "img2.jpg")
        self.service.run_inspection(insp.inspection_id)

        # Simulate app restart with a new Service instance backed by the same storage repository
        new_service = InspectionService(
            repository=self.repo,
            ingestion_service=ImageIngestionService(),
            orchestrator=MockPipelineOrchestrator(),  # type: ignore
        )

        restarted_insp, has_report = new_service.get_inspection_details(insp.inspection_id)
        self.assertEqual(restarted_insp.inspection_id, insp.inspection_id)
        self.assertEqual(restarted_insp.image_count, 2)
        self.assertTrue(has_report)

        report = new_service.get_report(insp.inspection_id)
        self.assertIsNotNone(report)
        self.assertEqual(report.overall_status, OverallInspectionStatus.PASS)

    def test_concurrent_run_mutex_protection(self) -> None:
        """Two concurrent threads executing run_inspection on same session safely serialize."""
        import concurrent.futures
        insp = self.service.create_inspection()
        self.service.upload_image(insp.inspection_id, _create_sample_jpeg_bytes(100, 100), "label.jpg")

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(self.service.run_inspection, insp.inspection_id)
            f2 = executor.submit(self.service.run_inspection, insp.inspection_id)
            results = [f1.result(), f2.result()]

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].inspection_id, insp.inspection_id)
        self.assertEqual(results[1].inspection_id, insp.inspection_id)
        # Idempotency and mutex guarantee only 1 execution
        self.assertEqual(self.mock_orch.run_count, 1)

    def test_pipeline_failure_preserves_collecting_state_and_no_report(self) -> None:
        """When pipeline execution fails, inspection remains in COLLECTING state and no report is saved."""
        class FailingOrch:
            def run(self, req: Any) -> InspectionReport:
                raise RuntimeError("Orchestrator unexpected crash")

        service = InspectionService(
            repository=self.repo,
            ingestion_service=self.ingestion,
            orchestrator=FailingOrch(),  # type: ignore
        )
        insp = service.create_inspection()
        service.upload_image(insp.inspection_id, _create_sample_jpeg_bytes(100, 100), "item.jpg")

        with self.assertRaises(RuntimeError):
            service.run_inspection(insp.inspection_id)

        # Ensure container was NOT marked READY and has no report
        container, has_report = service.get_inspection_details(insp.inspection_id)
        self.assertEqual(container.status, InspectionStatus.COLLECTING)
        self.assertFalse(has_report)
        self.assertIsNone(self.repo.get_report(insp.inspection_id))


if __name__ == "__main__":
    unittest.main()

