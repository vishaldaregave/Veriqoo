"""Data models and reference contracts for Phase 5B Multi-Image Inspection Management."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from backend.app.services.evidence.models import ImageArtifact


class InspectionStatus(str, Enum):
    """Lifecycle statuses for inspection containers."""
    COLLECTING = "COLLECTING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class InspectionImage:
    """Explicit, lightweight reference linking a Phase 5A ImageArtifact to an Inspection.

    Does NOT duplicate raw image bytes or redefine image identity.
    """
    image_id: str
    sequence: int
    added_at: datetime
    source_hash: str
    normalized_hash: str
    storage_path: str | None = None

    @classmethod
    def from_artifact(
        cls,
        artifact: ImageArtifact,
        sequence: int,
        added_at: datetime | None = None,
        storage_path: str | None = None,
    ) -> InspectionImage:
        """Create an InspectionImage reference from an existing Phase 5A ImageArtifact."""
        now = added_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return cls(
            image_id=artifact.image_id,
            sequence=sequence,
            added_at=now,
            source_hash=artifact.source_hash,
            normalized_hash=artifact.normalized_hash,
            storage_path=storage_path,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize reference metadata deterministically."""
        return {
            "image_id": self.image_id,
            "sequence": self.sequence,
            "added_at": self.added_at.isoformat(),
            "source_hash": self.source_hash,
            "normalized_hash": self.normalized_hash,
            "storage_path": self.storage_path,
        }


@dataclass
class Inspection:
    """Logical inspection container holding ordered references to Phase 5A ImageArtifacts."""
    inspection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: InspectionStatus = InspectionStatus.COLLECTING
    images: list[InspectionImage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    owner_id: str | None = None

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if self.owner_id is None and "owner_id" in self.metadata:
            self.owner_id = str(self.metadata["owner_id"])
        elif self.owner_id is not None and "owner_id" not in self.metadata:
            self.metadata["owner_id"] = self.owner_id

    @property
    def image_count(self) -> int:
        """Return total number of image references in this inspection."""
        return len(self.images)

    @property
    def image_ids(self) -> list[str]:
        """Return ordered list of referenced image IDs."""
        return [ref.image_id for ref in self.images]

    @property
    def is_collecting(self) -> bool:
        return self.status == InspectionStatus.COLLECTING

    @property
    def is_ready(self) -> bool:
        return self.status == InspectionStatus.READY

    @property
    def is_running(self) -> bool:
        return self.status == InspectionStatus.RUNNING

    @property
    def is_completed(self) -> bool:
        return self.status == InspectionStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status == InspectionStatus.FAILED

    def get_image_by_sequence(self, sequence: int) -> InspectionImage | None:
        """Retrieve an image reference by its 1-based sequence index."""
        for ref in self.images:
            if ref.sequence == sequence:
                return ref
        return None

    def get_images_by_id(self, image_id: str) -> list[InspectionImage]:
        """Retrieve all membership references for a specific image ID (handles duplicate membership)."""
        return [ref for ref in self.images if ref.image_id == image_id]

    def to_dict(self) -> dict[str, Any]:
        """Deterministic serialization of inspection container."""
        d = {
            "inspection_id": self.inspection_id,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "image_count": self.image_count,
            "images": [ref.to_dict() for ref in self.images],
            "metadata": dict(self.metadata),
        }
        if self.owner_id is not None:
            d["owner_id"] = self.owner_id
        return d

