"""Domain Coordination Service for Inspection Lifecycle, Pipeline Orchestration, and Durable Image Storage.

Bridges the FastAPI presentation layer to persistent InspectionRepository,
durable ImageStorage, Phase 5A ImageIngestionService, and Phase 7 Orchestrator.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
from typing import Any, Sequence
import uuid

from fastapi import HTTPException, status

from backend.app.api.errors import ErrorCode
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
from backend.app.services.inspection.repository import (
    InMemoryInspectionRepository,
    InspectionRepository,
)
from backend.app.services.inspection_pipeline.models import InspectionPipelineRequest
from backend.app.services.inspection_pipeline.orchestrator import InspectionPipelineOrchestrator
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.storage import (
    ImageIntegrityMismatchError,
    ImageStorage,
    InMemoryImageStorage,
    ObjectNotFoundError,
    StorageError,
    build_deterministic_storage_path,
    verify_image_bytes_integrity,
)

logger = logging.getLogger(__name__)


class InspectionService:
    """Orchestrates persistent inspection session workflows, durable image storage, and verification pipeline."""

    def __init__(
        self,
        repository: InspectionRepository | None = None,
        ingestion_service: ImageIngestionService | None = None,
        orchestrator: InspectionPipelineOrchestrator | None = None,
        storage: ImageStorage | None = None,
    ) -> None:
        self.repository = repository or InMemoryInspectionRepository()
        self.ingestion_service = ingestion_service or ImageIngestionService(config=IngestionConfig())
        self.orchestrator = orchestrator or InspectionPipelineOrchestrator()
        self.storage = storage or InMemoryImageStorage()
        self._run_lock = threading.Lock()

    def create_inspection(
        self,
        metadata: dict[str, Any] | None = None,
        inspection_date: str | None = None,
        owner_id: str | None = None,
    ) -> Inspection:
        """Create a new persistent inspection in COLLECTING state."""
        meta = dict(metadata or {})
        if inspection_date:
            meta["inspection_date"] = inspection_date
        return self.repository.create_inspection(metadata=meta, owner_id=owner_id)

    def get_inspection_details(self, inspection_id: str) -> tuple[Inspection, bool]:
        """Retrieve inspection container and whether a report is currently generated."""
        insp = self.repository.get_inspection(inspection_id)
        report = self.repository.get_report(inspection_id)
        has_report = report is not None
        return insp, has_report

    def upload_image(
        self,
        inspection_id: str,
        contents: bytes,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> tuple[ImageArtifact, InspectionImage]:
        """Ingest, validate, normalize, durably store, and persist package photograph evidence."""
        # 1. Ensure inspection session exists first
        insp = self.repository.get_inspection(inspection_id)

        # 2. Validate non-empty file stream
        if not contents or len(contents) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": ErrorCode.IMAGE_EMPTY.value,
                    "message": "Uploaded image file is empty (0 bytes).",
                    "details": {"filename": filename},
                },
            )

        # 3. Normalization via Phase 5A Ingestion Service
        artifact = self.ingestion_service.ingest_bytes(
            data=contents,
            source_name=filename or "upload.jpg",
            metadata={"content_type": content_type} if content_type else {},
        )

        # 4. Derive next sequence and deterministic storage path
        next_sequence = len(insp.images) + 1
        storage_path = build_deterministic_storage_path(
            inspection_id=inspection_id,
            sequence=next_sequence,
            normalized_hash=artifact.normalized_hash,
            extension=artifact.normalized_format,
        )

        # 5. Upload canonical normalized bytes to private ImageStorage
        mime_type = "image/png" if artifact.normalized_format.upper() == "PNG" else "image/jpeg"
        uploaded_path = self.storage.upload(
            path=storage_path,
            data=artifact.normalized_bytes,
            content_type=mime_type,
            upsert=True,
        )

        # 6. Persist metadata in repository with rollback cleanup on error
        try:
            ref = self.repository.add_image(
                inspection_id=inspection_id,
                artifact=artifact,
                storage_path=uploaded_path,
            )
        except Exception as exc:
            # Cleanup orphaned object from storage
            try:
                self.storage.delete(uploaded_path)
            except Exception as cleanup_err:
                logger.warning("Failed to clean up storage object '%s' after DB failure: %s", uploaded_path, cleanup_err)
            raise exc

        return artifact, ref

    def get_or_recover_artifacts(self, inspection_id: str) -> list[ImageArtifact]:
        """Retrieve cached artifacts or recover them from durable storage with SHA-256 integrity verification."""
        insp = self.repository.get_inspection(inspection_id)
        cached_artifacts = self.repository.get_artifacts(inspection_id)
        if len(cached_artifacts) == len(insp.images) and len(insp.images) > 0:
            return cached_artifacts

        cached_map = {a.image_id: a for a in cached_artifacts}
        recovered_artifacts: list[ImageArtifact] = []

        for ref in sorted(insp.images, key=lambda r: r.sequence):
            if ref.image_id in cached_map:
                recovered_artifacts.append(cached_map[ref.image_id])
                continue

            # Download from storage
            if not ref.storage_path:
                raise StorageError(
                    f"Image '{ref.image_id}' in inspection '{inspection_id}' has no storage_path.",
                    details={"image_id": ref.image_id, "inspection_id": inspection_id},
                )

            downloaded_bytes = self.storage.download(ref.storage_path)

            # Cryptographic SHA-256 integrity verification
            verify_image_bytes_integrity(
                data=downloaded_bytes,
                expected_hash=ref.normalized_hash,
                path_context=ref.storage_path,
            )

            # Reconstruct ImageArtifact using Phase 5A Ingestion Service
            reconstructed = self.ingestion_service.ingest_bytes(
                data=downloaded_bytes,
                source_name=f"{ref.image_id}.png",
                metadata={"recovered_from_storage": True, "storage_path": ref.storage_path},
            )
            reconstructed.image_id = ref.image_id
            recovered_artifacts.append(reconstructed)

        return recovered_artifacts

    def run_inspection(
        self,
        inspection_id: str,
        facts: list[dict[str, Any]] | None = None,
        inspection_facts: list[dict[str, Any]] | None = None,
        applicability_context: dict[str, Any] | None = None,
        target_requirements: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InspectionReport:
        """Execute or retrieve cached verification report with concurrency & idempotency protection."""
        effective_facts = inspection_facts or facts or []
        with self._run_lock:
            # 1. Idempotency Check: Return already generated report if exists
            existing_report = self.repository.get_report(inspection_id)
            if existing_report is not None:
                return existing_report

            # 2. Retrieve inspection and recover available image artifacts from durable storage
            insp = self.repository.get_inspection(inspection_id)
            artifacts = self.get_or_recover_artifacts(inspection_id)

            # 3. Construct InspectionFact entities
            req_facts: list[InspectionFact] = []
            if effective_facts:
                for idx, fact_dict in enumerate(effective_facts):
                    fact_id = fact_dict.get("id", str(uuid.uuid4()))
                    run_id = fact_dict.get("run_id", inspection_id)
                    fact_key = fact_dict.get("fact_key", f"fact_{idx}")
                    value = fact_dict.get("value")
                    unit = fact_dict.get("unit")
                    req_facts.append(
                        InspectionFact(
                            id=fact_id,
                            run_id=run_id,
                            fact_key=fact_key,
                            value=value,
                            unit=unit,
                        )
                    )

            # 4. Construct typed pipeline request
            pipeline_req = InspectionPipelineRequest(
                inspection_id=inspection_id,
                image_artifacts=artifacts,
                inspection_facts=req_facts,
                applicability_context=applicability_context or {},
                target_requirements=target_requirements or [],
                metadata=metadata or {},
            )

            # 5. Execute orchestrator
            report = self.orchestrator.run(pipeline_req)

            # 6. Save report & transition state to READY
            try:
                self.repository.save_requirement_results(inspection_id, report.verification_results)
                if req_facts:
                    self.repository.save_applicability_facts(inspection_id, req_facts)
                self.repository.save_report(inspection_id, report)
            except Exception as exc:
                logger.warning("Failed persisting report results to database for inspection '%s': %s", inspection_id, exc)

            return report

    def get_report(self, inspection_id: str) -> InspectionReport:
        """Retrieve persisted verification report. Raises 404 if report is not available."""
        self.repository.get_inspection(inspection_id)
        report = self.repository.get_report(inspection_id)
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": ErrorCode.REPORT_NOT_AVAILABLE.value,
                    "message": f"Inspection report has not been generated for inspection '{inspection_id}'.",
                    "details": {"inspection_id": inspection_id},
                },
            )
        return report
