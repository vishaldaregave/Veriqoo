"""Domain dataclass models for Saved Products."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass
class SavedProduct:
    """Core domain model representing a consumer saved product bookmark."""

    user_id: str
    inspection_id: str
    product_name: str | None = None
    notes: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert dataclass to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "inspection_id": self.inspection_id,
            "product_name": self.product_name,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }
