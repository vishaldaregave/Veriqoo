"""Data models for authenticated Supabase identity in Phase 9D."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AuthenticatedUser:
    """Typed representation of an authenticated Supabase identity.

    Derived exclusively from cryptographically validated JWT access tokens.
    """
    user_id: str
    email: str | None = None
    role: str = "authenticated"
    claims: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize user representation without exposing sensitive claims."""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "role": self.role,
        }
