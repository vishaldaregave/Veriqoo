"""User Profile domain package."""

from __future__ import annotations

from backend.app.services.user_profile.errors import UserProfileError, UserProfileNotFoundError
from backend.app.services.user_profile.models import UserProfile
from backend.app.services.user_profile.repository import (
    InMemoryUserProfileRepository,
    SupabaseUserProfileRepository,
    UserProfileRepository,
)
from backend.app.services.user_profile.schemas import UpdateUserProfileRequest, UserProfileResponse
from backend.app.services.user_profile.service import UserProfileService

__all__ = [
    "UserProfile",
    "UserProfileError",
    "UserProfileNotFoundError",
    "UserProfileRepository",
    "InMemoryUserProfileRepository",
    "SupabaseUserProfileRepository",
    "UserProfileService",
    "UserProfileResponse",
    "UpdateUserProfileRequest",
]
