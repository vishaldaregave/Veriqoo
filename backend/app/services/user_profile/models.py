"""Domain dataclass models for User Profile."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


SUPPORTED_LANGUAGES: set[str] = {"en", "hi", "mr", "ta", "te", "kn", "gu", "bn", "pa"}
SUPPORTED_APP_ROLES: set[str] = {"consumer", "inspector", "authority", "admin"}


@dataclass
class UserProfile:
    """Core domain model representing a user profile."""

    user_id: str
    display_name: str | None = None
    language_preference: str = "en"
    app_role: str = "consumer"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert dataclass to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "display_name": self.display_name,
            "language_preference": self.language_preference,
            "app_role": self.app_role,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }
