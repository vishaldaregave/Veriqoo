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

    def get_session(self, inspection_id: str) -> InspectionSession:
        """Retrieve an inspection session by ID. Raises InspectionNotFoundError if missing."""
        with self._lock:
            if not inspection_id or inspection_id not in self._sessions:
                raise InspectionNotFoundError(
                    f"Inspection with ID '{inspection_id}' not found.",
                    details={"inspection_id": inspection_id},
                )
            return self._sessions[inspection_id]

    def list_sessions(self) -> list[InspectionSession]:
        """List all active in-memory inspection sessions."""
        with self._lock:
            return list(self._sessions.values())

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

    def clear(self) -> None:
        """Clear all sessions from memory (used for test isolation)."""
        with self._lock:
            self._sessions.clear()

