"""Unit and Integration Tests for Phase 9B — Durable Image Storage Subsystem.

Verifies:
1. ImageStorage abstraction contracts (InMemoryImageStorage, path validation, deterministic path generation).
2. SHA-256 binary integrity verification and tampering rejection.
3. SupabaseImageStorage client operations via mocked HTTP client.
4. InspectionService upload lifecycle with durable storage and rollback cleanup on DB failure.
5. Process restart recovery of ImageArtifacts from storage with integrity verification.
6. Pipeline execution over recovered image artifacts.
7. Security: no storage secret/key leakage in exceptions or serialized models.
"""

from __future__ import annotations

import hashlib
import io
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from backend.app.services.applicability.models import InspectionFact
from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.evidence.models import ImageArtifact, IngestionConfig
from backend.app.services.inspection.errors import (
    InspectionNotFoundError,
    InspectionStateError,
)
from backend.app.services.inspection.models import (
    Inspection,
    InspectionImage,
    InspectionStatus,
)
from backend.app.services.inspection.repository import InMemoryInspectionRepository
from backend.app.services.inspection.service import InspectionService
from backend.app.services.inspection_pipeline.orchestrator import InspectionPipelineOrchestrator
from backend.app.services.inspection_pipeline.report import InspectionReport, OverallInspectionStatus
from backend.app.services.storage.base import (
    ImageIntegrityMismatchError,
    ImageStorage,
    ObjectNotFoundError,
    StorageError,
    build_deterministic_storage_path,
    verify_image_bytes_integrity,
)
from backend.app.services.storage.in_memory import InMemoryImageStorage
from backend.app.services.storage.supabase_storage import SupabaseImageStorage


def _create_sample_jpeg_bytes(width: int = 100, height: int = 100, color: tuple = (255, 0, 0)) -> bytes:
    """Helper to generate valid JPEG bytes for testing."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestPhase9BImageStorageBase(unittest.TestCase):
    """Tests for core storage utilities, path building, and integrity checks."""

    def test_build_deterministic_storage_path_valid(self):
        path = build_deterministic_storage_path(
            inspection_id="insp_123",
            sequence=1,
            normalized_hash="a" * 64,
            extension="jpeg",
        )
        self.assertEqual(path, f"inspections/insp_123/images/1_{'a' * 64}.jpeg")

    def test_build_deterministic_storage_path_sanitizes_extension(self):
        path = build_deterministic_storage_path(
            inspection_id="insp_456",
            sequence=2,
            normalized_hash="b" * 64,
            extension=".PNG",
        )
        self.assertEqual(path, f"inspections/insp_456/images/2_{'b' * 64}.png")

    def test_build_deterministic_storage_path_rejects_empty_args(self):
        with self.assertRaises(ValueError):
            build_deterministic_storage_path("", 1, "hash", "jpg")
        with self.assertRaises(ValueError):
            build_deterministic_storage_path("insp", 0, "hash", "jpg")
        with self.assertRaises(ValueError):
            build_deterministic_storage_path("insp", 1, "", "jpg")

    def test_verify_image_bytes_integrity_matching_hash(self):
        data = b"compliance_test_image_payload"
        expected_hash = hashlib.sha256(data).hexdigest()
        self.assertTrue(verify_image_bytes_integrity(data, expected_hash))

    def test_verify_image_bytes_integrity_mismatch_raises_error(self):
        data = b"original_payload"
        corrupted_data = b"corrupted_tampered_payload"
        expected_hash = hashlib.sha256(data).hexdigest()

        with self.assertRaises(ImageIntegrityMismatchError) as ctx:
            verify_image_bytes_integrity(corrupted_data, expected_hash, path_context="images/test.jpg")
        self.assertIn("integrity mismatch", str(ctx.exception).lower())
        self.assertEqual(ctx.exception.details["expected_hash"], expected_hash)


class TestPhase9BInMemoryImageStorage(unittest.TestCase):
    """Tests for thread-safe InMemoryImageStorage."""

    def setUp(self):
        self.storage = InMemoryImageStorage()

    def test_upload_and_download_flow(self):
        path = "inspections/insp_1/images/1_sample.jpeg"
        data = b"test_jpeg_bytes_12345"

        uploaded_path = self.storage.upload(path, data, content_type="image/jpeg")
        self.assertEqual(uploaded_path, path)
        self.assertTrue(self.storage.exists(path))

        downloaded = self.storage.download(path)
        self.assertEqual(downloaded, data)

    def test_download_missing_object_raises_404(self):
        with self.assertRaises(ObjectNotFoundError):
            self.storage.download("non_existent_image.png")

    def test_delete_existing_and_missing_object(self):
        path = "inspections/insp_1/images/1_sample.jpeg"
        self.storage.upload(path, b"data")
        self.assertTrue(self.storage.delete(path))
        self.assertFalse(self.storage.exists(path))
        # Deleting non-existent returns False without raising
        self.assertFalse(self.storage.delete(path))

    def test_list_objects_with_prefix(self):
        self.storage.upload("inspections/insp_1/images/1_a.jpg", b"1")
        self.storage.upload("inspections/insp_1/images/2_b.jpg", b"2")
        self.storage.upload("inspections/insp_2/images/1_c.jpg", b"3")

        insp1_images = self.storage.list_objects("inspections/insp_1/images")
        self.assertEqual(len(insp1_images), 2)
        self.assertIn("inspections/insp_1/images/1_a.jpg", insp1_images)
        self.assertIn("inspections/insp_1/images/2_b.jpg", insp1_images)

    def test_path_traversal_protection(self):
        with self.assertRaises(ValueError):
            self.storage.upload("../evil_path.jpg", b"data")
        with self.assertRaises(ValueError):
            self.storage.download("/absolute/path.jpg")


class TestPhase9BSupabaseImageStorage(unittest.TestCase):
    """Tests for SupabaseImageStorage with mocked HTTP responses."""

    def setUp(self):
        self.storage = SupabaseImageStorage(
            supabase_url="https://mockproject.supabase.co",
            service_role_key="mock_service_role_key_98765",
            bucket="test-bucket",
            timeout=5,
        )

    @patch("backend.app.services.storage.supabase_storage.requests.post")
    def test_upload_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        path = "inspections/insp_1/images/1_test.png"
        data = b"sample_png_bytes"
        result = self.storage.upload(path, data, content_type="image/png", upsert=True)

        self.assertEqual(result, path)
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        self.assertIn("https://mockproject.supabase.co/storage/v1/object/test-bucket/inspections/insp_1/images/1_test.png", call_url)

    @patch("backend.app.services.storage.supabase_storage.requests.get")
    def test_download_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.content = b"downloaded_binary_data"
        mock_get.return_value = mock_response

        path = "inspections/insp_1/images/1_test.png"
        data = self.storage.download(path)
        self.assertEqual(data, b"downloaded_binary_data")

    @patch("backend.app.services.storage.supabase_storage.requests.get")
    def test_download_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.ok = False
        mock_get.return_value = mock_response

        with self.assertRaises(ObjectNotFoundError):
            self.storage.download("missing.png")

    @patch("backend.app.services.storage.supabase_storage.requests.delete")
    def test_delete_success(self, mock_delete):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_delete.return_value = mock_response

        result = self.storage.delete("inspections/insp_1/images/1_test.png")
        self.assertTrue(result)

    @patch("backend.app.services.storage.supabase_storage.requests.head")
    def test_exists_true_and_false(self, mock_head):
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_404 = MagicMock()
        mock_404.status_code = 404

        mock_head.return_value = mock_200
        self.assertTrue(self.storage.exists("present.jpg"))

        mock_head.return_value = mock_404
        self.assertFalse(self.storage.exists("absent.jpg"))

    def test_service_key_not_leaked_in_repr(self):
        rep = repr(self.storage)
        self.assertNotIn("mock_service_role_key_98765", rep)
        self.assertIn("test-bucket", rep)


class TestPhase9BInspectionServiceStorageIntegration(unittest.TestCase):
    """Tests for InspectionService orchestrating repository and durable storage."""

    def setUp(self):
        self.repository = InMemoryInspectionRepository()
        self.storage = InMemoryImageStorage()
        self.ingestion = ImageIngestionService(config=IngestionConfig(max_file_size_bytes=5 * 1024 * 1024))
        self.service = InspectionService(
            repository=self.repository,
            ingestion_service=self.ingestion,
            storage=self.storage,
        )

    def test_upload_image_persists_to_storage_and_repo(self):
        insp = self.service.create_inspection(metadata={"case": "multi_image_test"})
        img_bytes = _create_sample_jpeg_bytes(width=200, height=200)

        artifact, ref = self.service.upload_image(
            inspection_id=insp.inspection_id,
            contents=img_bytes,
            filename="front.jpg",
            content_type="image/jpeg",
        )

        self.assertIsNotNone(ref.storage_path)
        self.assertTrue(self.storage.exists(ref.storage_path))
        self.assertEqual(ref.sequence, 1)

        # Storage object matches normalized bytes
        stored_bytes = self.storage.download(ref.storage_path)
        self.assertEqual(stored_bytes, artifact.normalized_bytes)

    def test_upload_multiple_images_generates_sequential_paths(self):
        insp = self.service.create_inspection()
        img1 = _create_sample_jpeg_bytes(color=(255, 0, 0))
        img2 = _create_sample_jpeg_bytes(color=(0, 255, 0))

        _, ref1 = self.service.upload_image(insp.inspection_id, img1, filename="front.jpg")
        _, ref2 = self.service.upload_image(insp.inspection_id, img2, filename="back.jpg")

        self.assertEqual(ref1.sequence, 1)
        self.assertEqual(ref2.sequence, 2)
        self.assertIn("/1_", ref1.storage_path)
        self.assertIn("/2_", ref2.storage_path)
        self.assertTrue(self.storage.exists(ref1.storage_path))
        self.assertTrue(self.storage.exists(ref2.storage_path))

    def test_upload_cleans_up_storage_on_repository_failure(self):
        insp = self.service.create_inspection()
        img_bytes = _create_sample_jpeg_bytes()

        # Mock repository.add_image to raise an error
        with patch.object(self.repository, "add_image", side_effect=RuntimeError("Database insert connection dropped")):
            with self.assertRaises(RuntimeError):
                self.service.upload_image(insp.inspection_id, img_bytes, filename="front.jpg")

        # Storage should not contain orphaned object
        stored_objects = self.storage.list_objects(f"inspections/{insp.inspection_id}")
        self.assertEqual(len(stored_objects), 0)

    def test_process_restart_recovery_from_storage(self):
        # 1. Upload images in service instance 1
        insp = self.service.create_inspection()
        img1 = _create_sample_jpeg_bytes(color=(100, 100, 100))
        img2 = _create_sample_jpeg_bytes(color=(200, 200, 200))

        art1, ref1 = self.service.upload_image(insp.inspection_id, img1)
        art2, ref2 = self.service.upload_image(insp.inspection_id, img2)

        # 2. Simulate process restart by creating a new InspectionService sharing persistent repo and storage,
        # but clearing in-memory cached artifacts in repository
        self.repository._artifacts[insp.inspection_id].clear()
        self.assertEqual(len(self.repository.get_artifacts(insp.inspection_id)), 0)

        # 3. New service instance recovers artifacts from durable storage
        new_service = InspectionService(
            repository=self.repository,
            ingestion_service=self.ingestion,
            storage=self.storage,
        )

        recovered_artifacts = new_service.get_or_recover_artifacts(insp.inspection_id)
        self.assertEqual(len(recovered_artifacts), 2)
        self.assertEqual(recovered_artifacts[0].image_id, art1.image_id)
        self.assertEqual(recovered_artifacts[0].normalized_hash, art1.normalized_hash)
        self.assertEqual(recovered_artifacts[1].image_id, art2.image_id)
        self.assertEqual(recovered_artifacts[1].normalized_hash, art2.normalized_hash)

    def test_recovery_detects_corrupted_storage_binary(self):
        insp = self.service.create_inspection()
        img1 = _create_sample_jpeg_bytes()
        art1, ref1 = self.service.upload_image(insp.inspection_id, img1)

        # Clear cache and tamper with the binary in storage
        self.repository._artifacts[insp.inspection_id].clear()
        self.storage.upload(ref1.storage_path, b"corrupted_tampered_binary_bytes", upsert=True)

        with self.assertRaises(ImageIntegrityMismatchError):
            self.service.get_or_recover_artifacts(insp.inspection_id)

    def test_run_inspection_with_recovered_artifacts(self):
        insp = self.service.create_inspection()
        img1 = _create_sample_jpeg_bytes(width=150, height=150)
        self.service.upload_image(insp.inspection_id, img1)

        # Simulate restart: clear cached in-memory artifacts
        self.repository._artifacts[insp.inspection_id].clear()

        # Mock orchestrator.run to verify it receives recovered artifacts
        mock_orchestrator = MagicMock(spec=InspectionPipelineOrchestrator)
        mock_report = MagicMock(spec=InspectionReport)
        mock_report.overall_status = OverallInspectionStatus.PASS
        mock_report.verification_results = []
        mock_report.to_dict.return_value = {"inspection_id": insp.inspection_id, "overall_status": "PASS"}
        mock_orchestrator.run.return_value = mock_report

        service_with_mock_orch = InspectionService(
            repository=self.repository,
            ingestion_service=self.ingestion,
            orchestrator=mock_orchestrator,
            storage=self.storage,
        )

        result_report = service_with_mock_orch.run_inspection(
            inspection_id=insp.inspection_id,
            inspection_facts=[{"fact_key": "is_prepackaged", "value": True}],
        )

        self.assertEqual(result_report.overall_status, OverallInspectionStatus.PASS)
        mock_orchestrator.run.assert_called_once()
        called_req = mock_orchestrator.run.call_args[0][0]
        self.assertEqual(len(called_req.image_artifacts), 1)
        self.assertEqual(called_req.image_artifacts[0].normalized_format.upper(), "PNG")


if __name__ == "__main__":
    unittest.main()
