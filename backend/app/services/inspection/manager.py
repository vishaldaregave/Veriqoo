"""In-memory Inspection Manager for Phase 5B Multi-Image Inspection Management."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from backend.app.services.evidence.models import ImageArtifact
from backend.app.services.inspection.errors import (
    ImageNotFoundInInspectionError,
    InspectionNotFoundError,
    InvalidInspectionError,
    InvalidInspectionImageReferenceError,
)
from backend.app.services.inspection.lifecycle import InspectionLifecycleValidator
from backend.app.services.inspection.models import (
    Inspection,
    InspectionImage,
    InspectionStatus,
)


class InspectionManager:
    """In-memory service managing inspection containers and ordered image memberships."""

    def __init__(self) -> None:
        self._inspections: dict[str, Inspection] = {}
        self._artifacts: dict[str, ImageArtifact] = {}

    def create_inspection(
        self,
        inspection_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Inspection:
        """Create a new inspection starting in the COLLECTING state."""
        inspection = Inspection(
            inspection_id=inspection_id or Inspection().inspection_id,
            status=InspectionStatus.COLLECTING,
            metadata=dict(metadata or {}),
        )
        self._inspections[inspection.inspection_id] = inspection
        return inspection

    def get_inspection(self, inspection_id: str) -> Inspection:
        """Retrieve an inspection by its ID. Raises InspectionNotFoundError if missing."""
        if not inspection_id or inspection_id not in self._inspections:
            raise InspectionNotFoundError(
                f"Inspection with ID '{inspection_id}' not found.",
                details={"inspection_id": inspection_id},
            )
        return self._inspections[inspection_id]

    def list_inspections(self) -> list[Inspection]:
        """List all active in-memory inspections."""
        return list(self._inspections.values())

    def add_image(
        self,
        inspection_id: str,
        artifact: ImageArtifact,
        added_at: datetime | None = None,
    ) -> InspectionImage:
        """Add an immutable Phase 5A ImageArtifact reference to an inspection in deterministic sequence."""
        inspection = self.get_inspection(inspection_id)
        InspectionLifecycleValidator.assert_can_mutate(inspection, operation="add image to")

        if not isinstance(artifact, ImageArtifact) or not artifact.image_id:
            raise InvalidInspectionImageReferenceError(
                "Provided object is not a valid Phase 5A ImageArtifact.",
                details={"type": type(artifact).__name__},
            )

        # Calculate next deterministic sequence index
        next_sequence = len(inspection.images) + 1

        # Create reference without duplicating raw image bytes
        ref = InspectionImage.from_artifact(
            artifact=artifact,
            sequence=next_sequence,
            added_at=added_at,
        )

        inspection.images.append(ref)
        self._artifacts[artifact.image_id] = artifact
        return ref

    def add_images(
        self,
        inspection_id: str,
        artifacts: Sequence[ImageArtifact],
    ) -> list[InspectionImage]:
        """Add multiple ImageArtifacts to an inspection preserving exact input order."""
        return [self.add_image(inspection_id, art) for art in artifacts]

    def get_ordered_image_references(self, inspection_id: str) -> list[InspectionImage]:
        """Return image references for an inspection strictly ordered by sequence."""
        inspection = self.get_inspection(inspection_id)
        return list(sorted(inspection.images, key=lambda r: r.sequence))

    def get_artifact(self, image_id: str) -> ImageArtifact | None:
        """Retrieve the underlying in-memory ImageArtifact for an image ID."""
        return self._artifacts.get(image_id)

    def remove_image_by_sequence(
        self,
        inspection_id: str,
        sequence: int,
    ) -> InspectionImage:
        """Remove an image reference by its sequence index while preserving remaining references' order."""
        inspection = self.get_inspection(inspection_id)
        InspectionLifecycleValidator.assert_can_mutate(inspection, operation="remove image from")

        target_idx = None
        for idx, ref in enumerate(inspection.images):
            if ref.sequence == sequence:
                target_idx = idx
                break

        if target_idx is None:
            raise ImageNotFoundInInspectionError(
                f"No image reference found with sequence {sequence} in inspection '{inspection_id}'.",
                details={"inspection_id": inspection_id, "sequence": sequence},
            )

        removed_ref = inspection.images.pop(target_idx)
        return removed_ref

    def mark_ready(
        self,
        inspection_id: str,
        allow_empty: bool = True,
    ) -> Inspection:
        """Transition inspection from COLLECTING to READY state."""
        inspection = self.get_inspection(inspection_id)

        if not allow_empty and inspection.image_count == 0:
            raise InvalidInspectionError(
                f"Cannot mark inspection '{inspection_id}' as READY because it contains zero images and allow_empty is False.",
                details={"inspection_id": inspection_id, "image_count": 0},
            )

        InspectionLifecycleValidator.validate_transition(inspection.status, InspectionStatus.READY)
        inspection.status = InspectionStatus.READY
        return inspection

    def reopen_inspection(self, inspection_id: str) -> Inspection:
        """Transition inspection from READY back to COLLECTING state."""
        inspection = self.get_inspection(inspection_id)
        InspectionLifecycleValidator.validate_transition(inspection.status, InspectionStatus.COLLECTING)
        inspection.status = InspectionStatus.COLLECTING
        return inspection

