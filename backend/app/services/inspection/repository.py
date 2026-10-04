"""Repository abstraction and implementations for persistent Inspection data in Phase 8B.

Supports both Supabase/PostgreSQL durable persistence and in-memory persistence
for isolated unit testing.
"""

from __future__ import annotations

import abc
from datetime import datetime, timezone
import json
import threading
from typing import Any, Sequence
import uuid

import requests

from backend.app.config import Settings, get_settings
from backend.app.services.applicability.models import InspectionFact
from backend.app.services.consumer_report.models import (
    ConsumerReport,
    ConsumerReportStatus,
    ReportFindingPackage,
)
from backend.app.services.evidence.models import EvidenceCandidate, ImageArtifact
from backend.app.services.inspection.errors import (
    ImageNotFoundInInspectionError,
    InspectionNotFoundError,
    InspectionStateError,
    InvalidInspectionImageReferenceError,
)
from backend.app.services.inspection.lifecycle import InspectionLifecycleValidator
from backend.app.services.inspection.models import (
    Inspection,
    InspectionImage,
    InspectionStatus,
)
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.ocr.models import OCRResult
from backend.app.services.report_sharing.models import ReportShare
from backend.app.services.verification.models import VerificationResult, VerificationStatus


class InspectionRepository(abc.ABC):
    """Abstract repository contract for inspection persistence."""

    @abc.abstractmethod
    def create_inspection(
        self,
        inspection_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        owner_id: str | None = None,
    ) -> Inspection:
        """Create a new inspection session."""
        pass

    @abc.abstractmethod
    def get_inspection(self, inspection_id: str) -> Inspection:
        """Retrieve an inspection container and its image references by ID."""
        pass

    @abc.abstractmethod
    def list_inspections_by_owner(
        self,
        owner_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Inspection], int]:
        """List active inspections owned by specific user with reverse-chronological ordering and pagination."""
        pass

    @abc.abstractmethod
    def update_inspection_status(
        self,
        inspection_id: str,
        status: InspectionStatus,
        completed_at: datetime | None = None,
    ) -> Inspection:
        """Update lifecycle state of an inspection."""
        pass

    @abc.abstractmethod
    def add_image(
        self,
        inspection_id: str,
        artifact: ImageArtifact,
        added_at: datetime | None = None,
        storage_path: str | None = None,
    ) -> InspectionImage:
        """Persist an ImageArtifact reference and metadata linked to an inspection."""
        pass

    @abc.abstractmethod
    def list_images(self, inspection_id: str) -> list[InspectionImage]:
        """List ordered image references for an inspection."""
        pass

    @abc.abstractmethod
    def get_artifacts(self, inspection_id: str) -> list[ImageArtifact]:
        """Retrieve underlying ImageArtifacts available for the inspection."""
        pass

    @abc.abstractmethod
    def save_report(
        self,
        inspection_id: str,
        report: InspectionReport,
    ) -> None:
        """Persist the final InspectionReport for an inspection."""
        pass

    @abc.abstractmethod
    def get_report(self, inspection_id: str) -> InspectionReport | None:
        """Retrieve persisted InspectionReport, or None if not run."""
        pass

    @abc.abstractmethod
    def save_ocr_observations(
        self,
        inspection_id: str,
        ocr_results: Sequence[OCRResult],
    ) -> None:
        """Persist technical raw OCR observations."""
        pass

    @abc.abstractmethod
    def save_evidence(
        self,
        inspection_id: str,
        evidence_candidates: Sequence[EvidenceCandidate],
    ) -> None:
        """Persist extracted and normalized evidence candidates."""
        pass

    @abc.abstractmethod
    def save_requirement_results(
        self,
        inspection_id: str,
        results: Sequence[VerificationResult],
    ) -> None:
        """Persist statutory requirement verification outcomes."""
        pass

    @abc.abstractmethod
    def save_applicability_facts(
        self,
        inspection_id: str,
        facts: Sequence[InspectionFact],
    ) -> None:
        """Persist observed inspection facts in Phase 3A runtime tables."""
        pass

    def get_ocr_observations(self, inspection_id: str) -> list[dict[str, Any]]:
        """Retrieve persisted raw OCR observations."""
        return []

    def get_evidence(self, inspection_id: str) -> list[dict[str, Any]]:
        """Retrieve persisted extracted evidence candidates."""
        return []

    def get_requirement_results(self, inspection_id: str) -> list[dict[str, Any]]:
        """Retrieve persisted requirement results."""
        return []

    def get_applicability_facts(self, inspection_id: str) -> list[InspectionFact]:
        """Retrieve persisted inspection facts."""
        return []

    @abc.abstractmethod
    def save_share(self, share: ReportShare) -> None:
        """Persist or update a report share record."""
        pass

    @abc.abstractmethod
    def get_share(self, share_id: str) -> ReportShare | None:
        """Retrieve a report share record by ID."""
        pass

    @abc.abstractmethod
    def get_share_by_token_hash(self, token_hash: str) -> ReportShare | None:
        """Retrieve a report share record by token hash."""
        pass

    @abc.abstractmethod
    def list_shares(self, inspection_id: str) -> list[ReportShare]:
        """List all report share records for an inspection."""
        pass

    @abc.abstractmethod
    def revoke_share(self, share_id: str) -> ReportShare | None:
        """Revoke a report share record by ID."""
        pass

    @abc.abstractmethod
    def save_consumer_report(self, report: ConsumerReport) -> None:
        """Persist or update an authoritative consumer report record."""
        pass

    @abc.abstractmethod
    def get_consumer_report(self, report_id: str) -> ConsumerReport | None:
        """Retrieve a consumer report by report_id."""
        pass

    @abc.abstractmethod
    def get_consumer_report_by_inspection(self, inspection_id: str, user_id: str) -> ConsumerReport | None:
        """Retrieve an existing consumer report by inspection ID and user ID."""
        pass

    @abc.abstractmethod
    def list_consumer_reports_for_user(self, user_id: str) -> list[ConsumerReport]:
        """List all consumer reports submitted by a specific user."""
        pass

    @abc.abstractmethod
    def list_all_consumer_reports(self) -> list[ConsumerReport]:
        """List all consumer reports across all users for regulatory review."""
        pass


class InMemoryInspectionRepository(InspectionRepository):
    """Thread-safe in-memory repository for unit testing without network/DB dependencies."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._inspections: dict[str, Inspection] = {}
        self._artifacts: dict[str, dict[str, ImageArtifact]] = {}  # inspection_id -> {image_id: artifact}
        self._reports: dict[str, InspectionReport] = {}
        self._ocr_obs: dict[str, list[dict[str, Any]]] = {}
        self._evidence: dict[str, list[dict[str, Any]]] = {}
        self._req_results: dict[str, list[dict[str, Any]]] = {}
        self._facts: dict[str, list[InspectionFact]] = {}
        self._shares: dict[str, ReportShare] = {}
        self._shares_by_hash: dict[str, str] = {}
        self._consumer_reports: dict[str, ConsumerReport] = {}
        self._consumer_reports_by_key: dict[tuple[str, str], str] = {}

    def create_inspection(
        self,
        inspection_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        owner_id: str | None = None,
    ) -> Inspection:
        with self._lock:
            iid = inspection_id or str(uuid.uuid4())
            meta = dict(metadata or {})
            if owner_id is not None:
                meta["owner_id"] = owner_id
            insp = Inspection(
                inspection_id=iid,
                status=InspectionStatus.COLLECTING,
                metadata=meta,
                owner_id=owner_id,
            )
            self._inspections[iid] = insp
            self._artifacts[iid] = {}
            return insp

    def get_inspection(self, inspection_id: str) -> Inspection:
        with self._lock:
            if not inspection_id or inspection_id not in self._inspections:
                raise InspectionNotFoundError(
                    f"Inspection with ID '{inspection_id}' not found.",
                    details={"inspection_id": inspection_id},
                )
            return self._inspections[inspection_id]

    def list_inspections_by_owner(
        self,
        owner_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Inspection], int]:
        with self._lock:
            matched = [
                insp for insp in self._inspections.values()
                if insp.owner_id == owner_id or insp.metadata.get("owner_id") == owner_id
            ]
            matched.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matched)
            paginated = matched[offset : offset + limit]
            return paginated, total

    def update_inspection_status(
        self,
        inspection_id: str,
        status: InspectionStatus,
        completed_at: datetime | None = None,
    ) -> Inspection:
        with self._lock:
            insp = self.get_inspection(inspection_id)
            insp.status = status
            return insp

    def add_image(
        self,
        inspection_id: str,
        artifact: ImageArtifact,
        added_at: datetime | None = None,
        storage_path: str | None = None,
    ) -> InspectionImage:
        with self._lock:
            insp = self.get_inspection(inspection_id)
            InspectionLifecycleValidator.assert_can_mutate(insp, operation="add image to")

            if not isinstance(artifact, ImageArtifact) or not artifact.image_id:
                raise InvalidInspectionImageReferenceError(
                    "Provided object is not a valid ImageArtifact.",
                    details={"type": type(artifact).__name__},
                )

            seq = len(insp.images) + 1
            ref = InspectionImage.from_artifact(
                artifact=artifact,
                sequence=seq,
                added_at=added_at,
                storage_path=storage_path,
            )
            insp.images.append(ref)
            self._artifacts[inspection_id][artifact.image_id] = artifact
            return ref

    def list_images(self, inspection_id: str) -> list[InspectionImage]:
        with self._lock:
            insp = self.get_inspection(inspection_id)
            return list(sorted(insp.images, key=lambda r: r.sequence))

    def get_artifacts(self, inspection_id: str) -> list[ImageArtifact]:
        with self._lock:
            insp = self.get_inspection(inspection_id)
            art_map = self._artifacts.get(inspection_id, {})
            ordered_refs = sorted(insp.images, key=lambda r: r.sequence)
            return [art_map[r.image_id] for r in ordered_refs if r.image_id in art_map]

    def save_report(
        self,
        inspection_id: str,
        report: InspectionReport,
    ) -> None:
        with self._lock:
            self.get_inspection(inspection_id)
            self._reports[inspection_id] = report
            self.update_inspection_status(
                inspection_id,
                InspectionStatus.COMPLETED,
                completed_at=datetime.now(timezone.utc),
            )

    def get_report(self, inspection_id: str) -> InspectionReport | None:
        with self._lock:
            self.get_inspection(inspection_id)
            return self._reports.get(inspection_id)

    def save_ocr_observations(
        self,
        inspection_id: str,
        ocr_results: Sequence[OCRResult],
    ) -> None:
        with self._lock:
            self.get_inspection(inspection_id)
            obs_list = []
            for res in ocr_results:
                for obs in res.observations:
                    obs_list.append(obs.to_dict() if hasattr(obs, "to_dict") else {"text": obs.text})
            self._ocr_obs[inspection_id] = obs_list

    def save_evidence(
        self,
        inspection_id: str,
        evidence_candidates: Sequence[EvidenceCandidate],
    ) -> None:
        with self._lock:
            self.get_inspection(inspection_id)
            self._evidence[inspection_id] = [e.to_dict() for e in evidence_candidates]

    def save_requirement_results(
        self,
        inspection_id: str,
        results: Sequence[VerificationResult],
    ) -> None:
        with self._lock:
            self.get_inspection(inspection_id)
            self._req_results[inspection_id] = [r.to_dict() for r in results]

    def save_applicability_facts(
        self,
        inspection_id: str,
        facts: Sequence[InspectionFact],
    ) -> None:
        with self._lock:
            self.get_inspection(inspection_id)
            self._facts[inspection_id] = list(facts)

    def get_ocr_observations(self, inspection_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self.get_inspection(inspection_id)
            return list(self._ocr_obs.get(inspection_id, []))

    def get_evidence(self, inspection_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self.get_inspection(inspection_id)
            return list(self._evidence.get(inspection_id, []))

    def get_requirement_results(self, inspection_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self.get_inspection(inspection_id)
            return list(self._req_results.get(inspection_id, []))

    def get_applicability_facts(self, inspection_id: str) -> list[InspectionFact]:
        with self._lock:
            self.get_inspection(inspection_id)
            return list(self._facts.get(inspection_id, []))

    def save_share(self, share: ReportShare) -> None:
        with self._lock:
            self.get_inspection(share.inspection_id)
            self._shares[share.id] = share
            if share.token_hash:
                self._shares_by_hash[share.token_hash] = share.id

    def get_share(self, share_id: str) -> ReportShare | None:
        with self._lock:
            return self._shares.get(share_id)

    def get_share_by_token_hash(self, token_hash: str) -> ReportShare | None:
        with self._lock:
            share_id = self._shares_by_hash.get(token_hash)
            if share_id:
                return self._shares.get(share_id)
            return None

    def list_shares(self, inspection_id: str) -> list[ReportShare]:
        with self._lock:
            self.get_inspection(inspection_id)
            return [s for s in self._shares.values() if s.inspection_id == inspection_id]

    def revoke_share(self, share_id: str) -> ReportShare | None:
        with self._lock:
            share = self._shares.get(share_id)
            if share is not None and share.revoked_at is None:
                share.revoked_at = datetime.now(timezone.utc)
            return share

    def save_consumer_report(self, report: ConsumerReport) -> None:
        with self._lock:
            self._consumer_reports[report.report_id] = report
            if report.inspection_id and report.submitted_by:
                self._consumer_reports_by_key[(report.inspection_id, report.submitted_by)] = report.report_id

    def get_consumer_report(self, report_id: str) -> ConsumerReport | None:
        with self._lock:
            return self._consumer_reports.get(report_id)

    def get_consumer_report_by_inspection(self, inspection_id: str, user_id: str) -> ConsumerReport | None:
        with self._lock:
            rep_id = self._consumer_reports_by_key.get((inspection_id, user_id))
            if rep_id:
                return self._consumer_reports.get(rep_id)
            return None

    def list_consumer_reports_for_user(self, user_id: str) -> list[ConsumerReport]:
        with self._lock:
            return [r for r in self._consumer_reports.values() if r.submitted_by == user_id]

    def list_all_consumer_reports(self) -> list[ConsumerReport]:
        with self._lock:
            return list(self._consumer_reports.values())

    def clear(self) -> None:
        with self._lock:
            self._inspections.clear()
            self._artifacts.clear()
            self._reports.clear()
            self._ocr_obs.clear()
            self._evidence.clear()
            self._req_results.clear()
            self._facts.clear()
            self._shares.clear()
            self._shares_by_hash.clear()
            self._consumer_reports.clear()
            self._consumer_reports_by_key.clear()


class SupabaseInspectionRepository(InspectionRepository):
    """Production persistent repository integrating with Supabase PostgreSQL tables."""

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        timeout: int = 30,
    ) -> None:
        settings = get_settings()
        self.url = (supabase_url or settings.supabase_url).rstrip("/")
        self.key = supabase_key or settings.supabase_anon_key or ""
        self.timeout = timeout
        self._in_memory_artifacts: dict[str, dict[str, ImageArtifact]] = {}  # inspection_id -> {image_id: artifact}

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        h = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        if prefer:
            h["Prefer"] = prefer
        return h

    def _request(self, method: str, table: str, **kwargs: Any) -> list[dict[str, Any]]:
        url = f"{self.url}/rest/v1/{table}"
        response = getattr(requests, method)(
            url,
            headers={**self._headers(), **kwargs.pop("headers", {})},
            timeout=self.timeout,
            **kwargs,
        )
        if not response.ok:
            raise RuntimeError(
                f"Supabase {method.upper()} on table '{table}' failed ({response.status_code}): {response.text}"
            )
        if response.status_code == 204 or not response.content:
            return []
        data = response.json()
        if isinstance(data, dict):
            return [data]
        return data if isinstance(data, list) else []

    def create_inspection(
        self,
        inspection_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        owner_id: str | None = None,
    ) -> Inspection:
        iid = inspection_id or str(uuid.uuid4())
        meta = dict(metadata or {})
        if owner_id is not None:
            meta["owner_id"] = owner_id
        payload = {
            "id": iid,
            "status": InspectionStatus.COLLECTING.value,
            "metadata": meta,
        }
        res = self._request(
            "post",
            "inspection_sessions",
            headers=self._headers(prefer="return=representation"),
            json=payload,
        )
        if not res:
            raise RuntimeError(f"Failed to create inspection session '{iid}' in Supabase.")
        row = res[0]
        created_at_dt = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        self._in_memory_artifacts[iid] = {}
        row_meta = dict(row.get("metadata", {}))
        return Inspection(
            inspection_id=str(row["id"]),
            created_at=created_at_dt,
            status=InspectionStatus(row["status"]),
            images=[],
            metadata=row_meta,
            owner_id=owner_id or row.get("owner_id") or row_meta.get("owner_id"),
        )

    def get_inspection(self, inspection_id: str) -> Inspection:
        if not inspection_id:
            raise InspectionNotFoundError("Inspection ID is required.")
        res = self._request(
            "get",
            "inspection_sessions",
            params={"id": f"eq.{inspection_id}", "limit": "1"},
        )
        if not res:
            raise InspectionNotFoundError(
                f"Inspection with ID '{inspection_id}' not found in database.",
                details={"inspection_id": inspection_id},
            )
        row = res[0]
        created_at_dt = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))

        # Fetch child image references
        img_rows = self._request(
            "get",
            "inspection_images",
            params={"inspection_id": f"eq.{inspection_id}", "order": "sequence.asc"},
        )
        images = []
        for img in img_rows:
            added_at = datetime.fromisoformat(img["created_at"].replace("Z", "+00:00"))
            images.append(
                InspectionImage(
                    image_id=img["image_id"],
                    sequence=int(img["sequence"]),
                    added_at=added_at,
                    source_hash=img["source_hash"],
                    normalized_hash=img["normalized_hash"],
                    storage_path=img.get("storage_path"),
                )
            )

        row_meta = dict(row.get("metadata", {}))
        return Inspection(
            inspection_id=str(row["id"]),
            created_at=created_at_dt,
            status=InspectionStatus(row["status"]),
            images=images,
            metadata=row_meta,
            owner_id=row.get("owner_id") or row_meta.get("owner_id"),
        )

    def list_inspections_by_owner(
        self,
        owner_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Inspection], int]:
        rows = self._request(
            "get",
            "inspection_sessions",
            params={
                "metadata->>owner_id": f"eq.{owner_id}",
                "order": "created_at.desc",
                "offset": str(offset),
                "limit": str(limit),
            },
            headers=self._headers(),
        )
        inspections = [self.get_inspection(str(r["id"])) for r in rows if "id" in r]
        return inspections, len(inspections)

    def update_inspection_status(
        self,
        inspection_id: str,
        status: InspectionStatus,
        completed_at: datetime | None = None,
    ) -> Inspection:
        payload: dict[str, Any] = {
            "status": status.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if completed_at is not None:
            payload["completed_at"] = completed_at.isoformat()

        res = self._request(
            "patch",
            "inspection_sessions",
            params={"id": f"eq.{inspection_id}"},
            headers=self._headers(prefer="return=representation"),
            json=payload,
        )
        if not res:
            raise InspectionNotFoundError(f"Inspection with ID '{inspection_id}' not found.")
        return self.get_inspection(inspection_id)

    def add_image(
        self,
        inspection_id: str,
        artifact: ImageArtifact,
        added_at: datetime | None = None,
        storage_path: str | None = None,
    ) -> InspectionImage:
        insp = self.get_inspection(inspection_id)
        InspectionLifecycleValidator.assert_can_mutate(insp, operation="add image to")

        if not isinstance(artifact, ImageArtifact) or not artifact.image_id:
            raise InvalidInspectionImageReferenceError(
                "Provided object is not a valid ImageArtifact.",
                details={"type": type(artifact).__name__},
            )

        next_sequence = len(insp.images) + 1
        now = added_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        payload = {
            "inspection_id": inspection_id,
            "image_id": artifact.image_id,
            "sequence": next_sequence,
            "source_hash": artifact.source_hash,
            "normalized_hash": artifact.normalized_hash,
            "source_format": artifact.source_format,
            "normalized_format": artifact.normalized_format,
            "original_width": artifact.original_width,
            "original_height": artifact.original_height,
            "normalized_width": artifact.normalized_width,
            "normalized_height": artifact.normalized_height,
            "file_size_bytes": artifact.file_size_bytes,
            "source_file_size_bytes": artifact.source_file_size_bytes,
            "color_mode": artifact.color_mode,
            "was_resized": artifact.was_resized,
            "was_orientation_corrected": artifact.was_orientation_corrected,
            "storage_path": storage_path,
            "metadata": artifact.metadata,
        }
        res = self._request(
            "post",
            "inspection_images",
            headers=self._headers(prefer="return=representation"),
            json=payload,
        )
        if not res:
            raise RuntimeError("Failed to insert inspection image reference in Supabase.")

        if inspection_id not in self._in_memory_artifacts:
            self._in_memory_artifacts[inspection_id] = {}
        self._in_memory_artifacts[inspection_id][artifact.image_id] = artifact

        return InspectionImage(
            image_id=artifact.image_id,
            sequence=next_sequence,
            added_at=now,
            source_hash=artifact.source_hash,
            normalized_hash=artifact.normalized_hash,
            storage_path=storage_path,
        )

    def list_images(self, inspection_id: str) -> list[InspectionImage]:
        insp = self.get_inspection(inspection_id)
        return insp.images

    def get_artifacts(self, inspection_id: str) -> list[ImageArtifact]:
        insp = self.get_inspection(inspection_id)
        art_map = self._in_memory_artifacts.get(inspection_id, {})
        ordered_refs = sorted(insp.images, key=lambda r: r.sequence)
        artifacts: list[ImageArtifact] = []
        for ref in ordered_refs:
            art = art_map.get(ref.image_id)
            if art is not None:
                artifacts.append(art)
        return artifacts

    def save_report(
        self,
        inspection_id: str,
        report: InspectionReport,
    ) -> None:
        self.get_inspection(inspection_id)
        payload = {
            "inspection_id": inspection_id,
            "overall_status": report.overall_status.value,
            "summary": report.summary,
            "counts": {
                "image_count": report.image_count,
                "evidence_count": report.evidence_count,
                "applicable_requirement_count": report.applicable_requirement_count,
                "pass_count": report.pass_count,
                "fail_count": report.fail_count,
                "not_visible_count": report.not_visible_count,
                "not_applicable_count": report.not_applicable_count,
                "review_required_count": report.review_required_count,
            },
            "report_payload": report.to_dict(),
            "schema_version": "1.0.0",
        }
        # Upsert report on inspection_id
        self._request(
            "post",
            "inspection_reports",
            params={"on_conflict": "inspection_id"},
            headers=self._headers(prefer="resolution=merge-duplicates,return=minimal"),
            json=payload,
        )
        self.update_inspection_status(
            inspection_id,
            InspectionStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
        )

    def get_report(self, inspection_id: str) -> InspectionReport | None:
        self.get_inspection(inspection_id)
        res = self._request(
            "get",
            "inspection_reports",
            params={"inspection_id": f"eq.{inspection_id}", "limit": "1"},
        )
        if not res:
            return None
        row = res[0]
        payload = row["report_payload"]
        v_results = []
        for r_dict in payload.get("verification_results", []):
            v_results.append(
                VerificationResult(
                    verification_id=r_dict.get("verification_id", ""),
                    requirement_id=r_dict["requirement_id"],
                    applicability_decision_id=r_dict.get("applicability_decision_id"),
                    status=VerificationStatus(r_dict["status"]),
                    reason=r_dict.get("reason", ""),
                    confidence=r_dict.get("confidence"),
                    review_required=bool(r_dict.get("review_required", False)),
                    evidence_ids=list(r_dict.get("evidence_ids", [])),
                    source_observation_ids=list(r_dict.get("source_observation_ids", [])),
                    image_ids=list(r_dict.get("image_ids", [])),
                    metadata=dict(r_dict.get("metadata", {})),
                )
            )
        counts = payload.get("counts", {})
        created_at_dt = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        from backend.app.services.inspection_pipeline.annotations import EvidenceAnnotation
        evidence_annotations = [
            EvidenceAnnotation.from_dict(a) if isinstance(a, dict) else a
            for a in payload.get("evidence_annotations", [])
        ]
        return InspectionReport(
            inspection_id=inspection_id,
            overall_status=OverallInspectionStatus(row["overall_status"]),
            verification_results=v_results,
            summary=row.get("summary", ""),
            evidence_count=int(counts.get("evidence_count", 0)),
            image_count=int(counts.get("image_count", 0)),
            applicable_requirement_count=int(counts.get("applicable_requirement_count", 0)),
            pass_count=int(counts.get("pass_count", 0)),
            fail_count=int(counts.get("fail_count", 0)),
            not_visible_count=int(counts.get("not_visible_count", 0)),
            not_applicable_count=int(counts.get("not_applicable_count", 0)),
            review_required_count=int(counts.get("review_required_count", 0)),
            evidence_annotations=evidence_annotations,
            created_at=created_at_dt,
            errors=list(payload.get("errors", [])),
            metadata=dict(payload.get("metadata", {})),
        )

    def save_ocr_observations(
        self,
        inspection_id: str,
        ocr_results: Sequence[OCRResult],
    ) -> None:
        rows = []
        for res in ocr_results:
            for obs in res.observations:
                bbox = obs.bounding_box
                if hasattr(bbox, "to_dict"):
                    bbox = bbox.to_dict()
                rows.append({
                    "inspection_id": inspection_id,
                    "image_id": obs.image_id or res.image_id,
                    "observation_id": obs.observation_id,
                    "raw_text": obs.text,
                    "confidence": obs.confidence,
                    "bounding_box": bbox,
                    "engine": "PaddleOCR",
                    "engine_version": "3.7.0",
                })
        if rows:
            self._request("post", "inspection_ocr_observations", json=rows)

    def save_evidence(
        self,
        inspection_id: str,
        evidence_candidates: Sequence[EvidenceCandidate],
    ) -> None:
        rows = []
        for cand in evidence_candidates:
            d = cand.to_dict()
            rows.append({
                "inspection_id": inspection_id,
                "evidence_id": cand.evidence_id,
                "observation_id": cand.observation_id,
                "image_id": cand.image_id,
                "field": d["field"],
                "raw_text": cand.raw_text,
                "normalized_text": cand.normalized_text,
                "parsed_value": cand.parsed_value,
                "parsed_unit": cand.parsed_unit,
                "ocr_confidence": cand.ocr_confidence,
                "parser_confidence": cand.parser_confidence,
                "confidence": cand.confidence,
                "status": d["status"],
                "parser": cand.parser,
                "parser_version": cand.parser_version,
                "sequence": cand.sequence,
                "bounding_box": d["bounding_box"],
                "metadata": cand.metadata,
            })
        if rows:
            self._request("post", "inspection_evidence", json=rows)

    def save_requirement_results(
        self,
        inspection_id: str,
        results: Sequence[VerificationResult],
    ) -> None:
        rows = []
        for r in results:
            rows.append({
                "inspection_id": inspection_id,
                "verification_id": r.verification_id,
                "requirement_id": r.requirement_id,
                "applicability_decision_id": r.applicability_decision_id,
                "status": r.status.value,
                "reason": r.reason,
                "confidence": r.confidence,
                "review_required": r.review_required,
                "evidence_ids": r.evidence_ids,
                "source_observation_ids": r.source_observation_ids,
                "image_ids": r.image_ids,
                "metadata": r.metadata,
            })
        if rows:
            self._request("post", "inspection_requirement_results", json=rows)

    def save_applicability_facts(
        self,
        inspection_id: str,
        facts: Sequence[InspectionFact],
    ) -> None:
        if not facts:
            return
        # 1. Ensure applicability_run exists for inspection
        run_id = str(facts[0].run_id) if facts else str(uuid.uuid4())
        run_payload = {
            "id": run_id,
            "inspection_reference": inspection_id,
            "engine_version": "1.0.0",
            "status": "evaluated",
        }
        self._request(
            "post",
            "applicability_runs",
            params={"on_conflict": "id"},
            headers=self._headers(prefer="resolution=merge-duplicates,return=minimal"),
            json=run_payload,
        )
        # 2. Insert inspection_facts
        fact_rows = []
        for fact in facts:
            fact_rows.append({
                "id": str(fact.id),
                "run_id": str(fact.run_id),
                "fact_key": fact.fact_key,
                "value": fact.value,
                "unit": fact.unit,
                "fact_status": fact.fact_status,
                "origin": fact.origin,
                "sequence": fact.sequence,
                "review_status": fact.review_status,
            })
        if fact_rows:
            self._request("post", "inspection_facts", json=fact_rows)

    def save_share(self, share: ReportShare) -> None:
        payload = {
            "id": share.id,
            "inspection_id": share.inspection_id,
            "token_hash": share.token_hash,
            "created_at": share.created_at.isoformat(),
            "expires_at": share.expires_at.isoformat() if share.expires_at else None,
            "revoked_at": share.revoked_at.isoformat() if share.revoked_at else None,
            "created_by": share.created_by,
            "metadata": share.metadata,
        }
        self._request(
            "post",
            "inspection_report_shares",
            params={"on_conflict": "id"},
            headers=self._headers(prefer="resolution=merge-duplicates,return=minimal"),
            json=payload,
        )

    def get_share(self, share_id: str) -> ReportShare | None:
        rows = self._request("get", "inspection_report_shares", params={"id": f"eq.{share_id}"})
        if not rows:
            return None
        r = rows[0]
        return ReportShare(
            id=r["id"],
            inspection_id=r["inspection_id"],
            token_hash=r["token_hash"],
            created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
            expires_at=datetime.fromisoformat(r["expires_at"].replace("Z", "+00:00")) if r.get("expires_at") else None,
            revoked_at=datetime.fromisoformat(r["revoked_at"].replace("Z", "+00:00")) if r.get("revoked_at") else None,
            created_by=r.get("created_by"),
            metadata=r.get("metadata", {}),
        )

    def get_share_by_token_hash(self, token_hash: str) -> ReportShare | None:
        rows = self._request("get", "inspection_report_shares", params={"token_hash": f"eq.{token_hash}"})
        if not rows:
            return None
        r = rows[0]
        return ReportShare(
            id=r["id"],
            inspection_id=r["inspection_id"],
            token_hash=r["token_hash"],
            created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
            expires_at=datetime.fromisoformat(r["expires_at"].replace("Z", "+00:00")) if r.get("expires_at") else None,
            revoked_at=datetime.fromisoformat(r["revoked_at"].replace("Z", "+00:00")) if r.get("revoked_at") else None,
            created_by=r.get("created_by"),
            metadata=r.get("metadata", {}),
        )

    def list_shares(self, inspection_id: str) -> list[ReportShare]:
        rows = self._request("get", "inspection_report_shares", params={"inspection_id": f"eq.{inspection_id}", "order": "created_at.desc"})
        shares = []
        for r in rows:
            shares.append(ReportShare(
                id=r["id"],
                inspection_id=r["inspection_id"],
                token_hash=r["token_hash"],
                created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                expires_at=datetime.fromisoformat(r["expires_at"].replace("Z", "+00:00")) if r.get("expires_at") else None,
                revoked_at=datetime.fromisoformat(r["revoked_at"].replace("Z", "+00:00")) if r.get("revoked_at") else None,
                created_by=r.get("created_by"),
                metadata=r.get("metadata", {}),
            ))
        return shares

    def revoke_share(self, share_id: str) -> ReportShare | None:
        now_str = datetime.now(timezone.utc).isoformat()
        rows = self._request(
            "patch",
            "inspection_report_shares",
            params={"id": f"eq.{share_id}"},
            headers=self._headers(prefer="return=representation"),
            json={"revoked_at": now_str},
        )
        if not rows:
            return None
        r = rows[0]
        return ReportShare(
            id=r["id"],
            inspection_id=r["inspection_id"],
            token_hash=r["token_hash"],
            created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
            expires_at=datetime.fromisoformat(r["expires_at"].replace("Z", "+00:00")) if r.get("expires_at") else None,
            revoked_at=datetime.fromisoformat(r["revoked_at"].replace("Z", "+00:00")) if r.get("revoked_at") else None,
            created_by=r.get("created_by"),
            metadata=r.get("metadata", {}),
        )

    def _row_to_consumer_report(self, row: dict[str, Any]) -> ConsumerReport:
        findings_raw = row.get("findings", [])
        findings: list[ReportFindingPackage] = []
        if isinstance(findings_raw, list):
            for f in findings_raw:
                if isinstance(f, dict):
                    findings.append(ReportFindingPackage(
                        finding_id=f.get("finding_id", ""),
                        requirement_id=f.get("requirement_id", ""),
                        canonical_status=f.get("canonical_status", "FAIL"),
                        consumer_title=f.get("consumer_title", ""),
                        consumer_explanation=f.get("consumer_explanation", ""),
                        severity=f.get("severity", "HIGH"),
                        rule_number=f.get("rule_number"),
                        statutory_label=f.get("statutory_label"),
                        section_reference=f.get("section_reference"),
                        evidence_ids=list(f.get("evidence_ids", [])),
                        observation_ids=list(f.get("observation_ids", [])),
                        annotation_ids=list(f.get("annotation_ids", [])),
                        image_ids=list(f.get("image_ids", [])),
                        annotations=list(f.get("annotations", [])),
                    ))

        status_str = row.get("status", "SUBMITTED")
        try:
            status_enum = ConsumerReportStatus(status_str)
        except Exception:
            status_enum = ConsumerReportStatus.SUBMITTED

        return ConsumerReport(
            report_id=row["report_id"],
            inspection_id=str(row["inspection_id"]),
            submitted_by=str(row["user_id"]),
            status=status_enum,
            canonical_overall_status=row.get("canonical_overall_status", "FAIL"),
            consumer_overall_result=row.get("consumer_overall_result", "COMPLIANCE_ISSUE_DETECTED"),
            consumer_description=row.get("consumer_description"),
            product_summary=dict(row.get("product_summary", {})),
            identity_confidence=row.get("identity_confidence", "UNKNOWN"),
            scan_quality=dict(row.get("scan_quality", {})),
            findings=findings,
            priority_score=int(row.get("priority_score", 0)),
            priority_band=row.get("priority_band", "MEDIUM"),
            priority_reasons=list(row.get("priority_reasons", [])),
            risk_signals=list(row.get("risk_signals", [])),
            location=row.get("location"),
            inspection_created_at=row.get("inspection_created_at", ""),
            created_at=row.get("created_at", ""),
            metadata=dict(row.get("metadata", {})),
        )

    def save_consumer_report(self, report: ConsumerReport) -> None:
        payload = {
            "report_id": report.report_id,
            "inspection_id": report.inspection_id,
            "user_id": report.submitted_by,
            "status": report.status.value if hasattr(report.status, "value") else str(report.status),
            "canonical_overall_status": report.canonical_overall_status,
            "consumer_overall_result": report.consumer_overall_result,
            "consumer_description": report.consumer_description,
            "product_summary": report.product_summary,
            "identity_confidence": report.identity_confidence,
            "scan_quality": report.scan_quality,
            "findings": [f.to_dict() for f in report.findings],
            "priority_score": report.priority_score,
            "priority_band": report.priority_band,
            "priority_reasons": report.priority_reasons,
            "risk_signals": report.risk_signals,
            "location": report.location,
            "inspection_created_at": report.inspection_created_at or None,
            "report_snapshot": report.to_dict(),
            "metadata": report.metadata,
        }
        self._request(
            "post",
            "consumer_reports",
            params={"on_conflict": "report_id"},
            headers=self._headers(prefer="resolution=merge-duplicates,return=minimal"),
            json=payload,
        )

    def get_consumer_report(self, report_id: str) -> ConsumerReport | None:
        rows = self._request("get", "consumer_reports", params={"report_id": f"eq.{report_id}", "limit": "1"})
        if not rows:
            return None
        return self._row_to_consumer_report(rows[0])

    def get_consumer_report_by_inspection(self, inspection_id: str, user_id: str) -> ConsumerReport | None:
        rows = self._request(
            "get",
            "consumer_reports",
            params={"inspection_id": f"eq.{inspection_id}", "user_id": f"eq.{user_id}", "limit": "1"},
        )
        if not rows:
            return None
        return self._row_to_consumer_report(rows[0])

    def list_consumer_reports_for_user(self, user_id: str) -> list[ConsumerReport]:
        rows = self._request(
            "get",
            "consumer_reports",
            params={"user_id": f"eq.{user_id}", "order": "created_at.desc"},
        )
        return [self._row_to_consumer_report(r) for r in rows]

    def list_all_consumer_reports(self) -> list[ConsumerReport]:
        rows = self._request(
            "get",
            "consumer_reports",
            params={"order": "created_at.desc"},
        )
        return [self._row_to_consumer_report(r) for r in rows]
