"""Service layer for Authority domain logic and provisioning (T3-4 Phase 2)."""

from __future__ import annotations

import logging
from typing import Any

from backend.app.services.authority.errors import AuthorityNotProvisionedError
from backend.app.services.authority.models import AuthorityProfile, JurisdictionScope
from backend.app.services.authority.repository import AuthorityRepository

logger = logging.getLogger(__name__)


class AuthorityService:
    """Coordinator for authority profile management and jurisdiction retrieval."""

    def __init__(self, repository: AuthorityRepository) -> None:
        self.repository = repository

    def get_authority_profile(self, user_id: str) -> AuthorityProfile | None:
        """Fetch authority profile by user UUID. Returns None if unprovisioned."""
        return self.repository.get_by_user_id(user_id)

    def provision_authority(
        self,
        user_id: str,
        department: str,
        designation: str,
        jurisdiction: JurisdictionScope,
        badge_number: str | None = None,
        is_active: bool = True,
    ) -> AuthorityProfile:
        """Admin/seed provisioning helper for authority credentials.

        Strict security boundary: Authority accounts must be explicitly provisioned
        with an authoritative JurisdictionScope.
        """
        logger.info("Provisioning authority profile for user '%s', department='%s'", user_id, department)
        profile = AuthorityProfile(
            user_id=user_id,
            department=department,
            designation=designation,
            jurisdiction=jurisdiction,
            is_active=is_active,
            badge_number=badge_number,
        )
        return self.repository.save(profile)

    def set_active_status(self, user_id: str, is_active: bool) -> AuthorityProfile:
        """Update active status of an authority profile."""
        profile = self.get_authority_profile(user_id)
        if not profile:
            raise AuthorityNotProvisionedError(f"Authority profile not found for user '{user_id}'.")
        profile.is_active = is_active
        return self.repository.save(profile)
