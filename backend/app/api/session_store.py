"""In-Memory Inspection Session Store for Phase 8A FastAPI Integration.

Provides thread-safe in-memory session lifecycle management, storing Inspection
containers, ImageArtifacts, and InspectionReports without database persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
from typing import Any

from backend.app.services.evidence.models import ImageArtifact
from backend.app.services.inspection.errors import (
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
from backend.app.services.inspection_pipeline.report import InspectionReport


@dataclass
class InspectionSession:
    """Encapsulates the complete in-memory state of an active inspection session."""
    inspection: Inspection
    artifacts: dict[str, ImageArtifact] = field(default_factory=dict)
    report: InspectionReport | None = None
    evidence_candidates: list[Any] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if self.updated_at.tzinfo is None:
            self.updated_at = self.updated_at.replace(tzinfo=timezone.utc)


class InMemoryInspectionStore:
    """Thread-safe in-memory storage manager for inspections and artifacts."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, InspectionSession] = {}
        self._shares: dict[str, Any] = {}
        self._shares_by_hash: dict[str, str] = {}  # token_hash -> share_id
        self._consumer_reports: dict[str, Any] = {}  # report_id -> ConsumerReport
        self._consumer_reports_by_key: dict[tuple[str, str], str] = {}  # (inspection_id, user_id) -> report_id

    def create_session(
        self,
        inspection_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        owner_id: str | None = None,
    ) -> InspectionSession:
        """Create a new inspection session initialized in COLLECTING state."""
        with self._lock:
            meta = dict(metadata or {})
            if owner_id is not None:
                meta["owner_id"] = owner_id
            inspection = Inspection(
                inspection_id=inspection_id or Inspection().inspection_id,
                status=InspectionStatus.COLLECTING,
                metadata=meta,
                owner_id=owner_id,
            )
            session = InspectionSession(
                inspection=inspection,
                artifacts={},
                report=None,
            )
            self._sessions[inspection.inspection_id] = session
            return session

    def save_session(self, session: InspectionSession) -> None:
        """Store or update an existing InspectionSession in memory."""
        with self._lock:
            self._sessions[session.inspection.inspection_id] = session

    def get_session(self, inspection_id: str) -> InspectionSession:
        """Retrieve an inspection session by ID. Raises InspectionNotFoundError if missing."""
        with self._lock:
            if not inspection_id or inspection_id not in self._sessions:
                raise InspectionNotFoundError(
                    f"Inspection with ID '{inspection_id}' not found.",
                    details={"inspection_id": inspection_id},
                )
            return self._sessions[inspection_id]

    def get_session_optional(self, inspection_id: str) -> InspectionSession | None:
        """Retrieve an inspection session by ID, returning None if missing."""
        with self._lock:
            if not inspection_id:
                return None
            return self._sessions.get(inspection_id)

    def list_sessions(self) -> list[InspectionSession]:
        """List all active in-memory inspection sessions."""
        with self._lock:
            return list(self._sessions.values())

    def list_sessions_by_owner(
        self,
        owner_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[InspectionSession], int]:
        """List active inspection sessions owned by specific user with reverse-chronological ordering and pagination."""
        with self._lock:
            matched = [
                s for s in self._sessions.values()
                if s.inspection.owner_id == owner_id or s.inspection.metadata.get("owner_id") == owner_id
            ]
            matched.sort(key=lambda s: s.inspection.created_at, reverse=True)
            total = len(matched)
            paginated = matched[offset : offset + limit]
            return paginated, total

    def add_artifact(
        self,
        inspection_id: str,
        artifact: ImageArtifact,
        added_at: datetime | None = None,
        storage_path: str | None = None,
    ) -> InspectionImage:
        """Add an immutable ImageArtifact to an inspection session in sequence."""
        with self._lock:
            session = self.get_session(inspection_id)
            inspection = session.inspection

            # Lifecycle guard: cannot add images if not in COLLECTING state
            InspectionLifecycleValidator.assert_can_mutate(
                inspection, operation="add image to"
            )

            if not isinstance(artifact, ImageArtifact) or not artifact.image_id:
                raise InvalidInspectionImageReferenceError(
                    "Provided object is not a valid Phase 5A ImageArtifact.",
                    details={"type": type(artifact).__name__},
                )

            next_sequence = len(inspection.images) + 1
            ref = InspectionImage.from_artifact(
                artifact=artifact,
                sequence=next_sequence,
                added_at=added_at,
                storage_path=storage_path,
            )

            inspection.images.append(ref)
            session.artifacts[artifact.image_id] = artifact
            session.updated_at = datetime.now(timezone.utc)
            return ref

    def get_artifacts(self, inspection_id: str) -> list[ImageArtifact]:
        """Retrieve all underlying ImageArtifacts for an inspection strictly ordered by sequence."""
        with self._lock:
            session = self.get_session(inspection_id)
            ordered_refs = sorted(session.inspection.images, key=lambda r: r.sequence)
            artifacts: list[ImageArtifact] = []
            for ref in ordered_refs:
                art = session.artifacts.get(ref.image_id)
                if art is not None:
                    artifacts.append(art)
            return artifacts

    def store_report(
        self,
        inspection_id: str,
        report: InspectionReport,
    ) -> None:
        """Store the generated InspectionReport in the session."""
        with self._lock:
            session = self.get_session(inspection_id)
            session.report = report
            session.inspection.status = InspectionStatus.COMPLETED
            session.updated_at = datetime.now(timezone.utc)

    def get_report(self, inspection_id: str) -> InspectionReport | None:
        """Retrieve the latest InspectionReport for an inspection, or None if not run."""
        with self._lock:
            session = self.get_session(inspection_id)
            return session.report

    def store_evidence(self, inspection_id: str, candidates: list[Any]) -> None:
        """Store extracted EvidenceCandidates for an inspection session."""
        with self._lock:
            session = self.get_session(inspection_id)
            session.evidence_candidates = list(candidates)
            session.updated_at = datetime.now(timezone.utc)

    def get_evidence(self, inspection_id: str) -> list[Any]:
        """Retrieve stored EvidenceCandidates for an inspection session."""
        with self._lock:
            session = self.get_session(inspection_id)
            return list(session.evidence_candidates)


    def save_share(self, share: Any) -> None:
        """Store or update a ReportShare record."""
        with self._lock:
            self._shares[share.id] = share
            if getattr(share, "token_hash", None):
                self._shares_by_hash[share.token_hash] = share.id

    def get_share(self, share_id: str) -> Any | None:
        """Retrieve a ReportShare by its unique ID."""
        with self._lock:
            return self._shares.get(share_id)

    def get_share_by_token_hash(self, token_hash: str) -> Any | None:
        """Retrieve a ReportShare by token hash."""
        with self._lock:
            share_id = self._shares_by_hash.get(token_hash)
            if share_id:
                return self._shares.get(share_id)
            return None

    def list_shares(self, inspection_id: str) -> list[Any]:
        """List all shares generated for a given inspection ID."""
        with self._lock:
            return [s for s in self._shares.values() if s.inspection_id == inspection_id]

    def revoke_share(self, share_id: str) -> Any | None:
        """Revoke an active report share by ID."""
        with self._lock:
            share = self._shares.get(share_id)
            if share is not None and share.revoked_at is None:
                share.revoked_at = datetime.now(timezone.utc)
            return share

    def save_consumer_report(self, report: Any) -> None:
        """Store or update a ConsumerReport record."""
        with self._lock:
            self._consumer_reports[report.report_id] = report
            if getattr(report, "inspection_id", None) and getattr(report, "submitted_by", None):
                self._consumer_reports_by_key[(report.inspection_id, report.submitted_by)] = report.report_id

    def get_consumer_report(self, report_id: str) -> Any | None:
        """Retrieve a ConsumerReport by unique report ID."""
        with self._lock:
            return self._consumer_reports.get(report_id)

    def get_consumer_report_by_inspection(self, inspection_id: str, user_id: str) -> Any | None:
        """Retrieve an existing ConsumerReport by inspection ID and submitting user ID."""
        with self._lock:
            report_id = self._consumer_reports_by_key.get((inspection_id, user_id))
            if report_id:
                return self._consumer_reports.get(report_id)
            return None

    def list_consumer_reports_for_user(self, user_id: str) -> list[Any]:
        """List all consumer reports submitted by a specific user."""
        with self._lock:
            return [r for r in self._consumer_reports.values() if r.submitted_by == user_id]

    def list_all_consumer_reports(self) -> list[Any]:
        """List all submitted consumer reports (for authority review)."""
        with self._lock:
            return list(self._consumer_reports.values())

    def clear(self) -> None:
        """Clear all sessions, shares, and reports from memory (used for test isolation)."""
        with self._lock:
            self._sessions.clear()
            self._shares.clear()
            self._shares_by_hash.clear()
            self._consumer_reports.clear()
            self._consumer_reports_by_key.clear()

