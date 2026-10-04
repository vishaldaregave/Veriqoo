"""Error definitions for User Profile domain."""

from __future__ import annotations

from typing import Any


class UserProfileError(Exception):
    """Base exception for user profile domain errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UserProfileNotFoundError(UserProfileError):
    """Raised when a requested user profile does not exist."""

    def __init__(self, user_id: str) -> None:
        super().__init__(
            message=f"User profile for user '{user_id}' was not found.",
            details={"user_id": user_id},
        )
