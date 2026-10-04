"""Service layer for User Profile business logic."""

from __future__ import annotations

import logging
from typing import Any

from backend.app.services.user_profile.errors import UserProfileNotFoundError
from backend.app.services.user_profile.models import UserProfile
from backend.app.services.user_profile.repository import UserProfileRepository

logger = logging.getLogger(__name__)

# Permitted fields for user profile updates via API
PERMITTED_UPDATE_FIELDS: set[str] = {"display_name", "language_preference"}


class UserProfileService:
    """Coordinator for user profile domain logic."""

    def __init__(self, repository: UserProfileRepository) -> None:
        self.repository = repository

    def get_or_create_profile(self, user_id: str) -> UserProfile:
        """Fetch existing user profile or auto-create a default consumer profile.

        Upsert-on-read logic ensures seamless onboarding for authenticated users.
        """
        profile = self.repository.get_by_user_id(user_id)
        if profile is not None:
            return profile

        # Create default profile
        # CRITICAL SECURITY GUARD: New profiles ALWAYS default to app_role='consumer'.
        logger.info("Auto-creating user profile for user '%s'", user_id)
        new_profile = UserProfile(
            user_id=user_id,
            display_name=None,
            language_preference="en",
            app_role="consumer",
        )
        return self.repository.create_profile(new_profile)

    def update_profile(self, user_id: str, updates: dict[str, Any]) -> UserProfile:
        """Apply permitted field updates to a user profile.

        Strict security boundary: Strips unpermitted fields (e.g. app_role, user_id)
        to prevent privilege escalation attacks.
        """
        # Ensure profile exists
        existing_profile = self.get_or_create_profile(user_id)

        # Filter to permitted update keys only
        sanitized_updates = {
            k: v for k, v in updates.items() if k in PERMITTED_UPDATE_FIELDS and v is not None or k == "display_name"
        }

        updated = self.repository.update_profile(user_id, sanitized_updates)
        if updated is None:
            # Fallback in case repository update failed
            return existing_profile

        return updated
