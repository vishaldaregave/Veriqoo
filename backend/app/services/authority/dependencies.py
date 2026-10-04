"""FastAPI security dependencies for authority role and jurisdiction authorization (T3-4 Phase 2)."""

from __future__ import annotations

import logging
from fastapi import Depends, HTTPException, status

from backend.app.api.dependencies import (
    get_authority_service,
    get_user_profile_service,
)
from backend.app.api.errors import ErrorCode
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.services.authority.models import AuthorityPrincipal
from backend.app.services.authority.service import AuthorityService
from backend.app.services.user_profile.service import UserProfileService

logger = logging.getLogger(__name__)

# Permitted roles that can be evaluated for authority resource access
AUTHORIZED_AUTHORITY_ROLES: frozenset[str] = frozenset({"authority", "admin"})


async def require_authority_user(
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_profile_service: UserProfileService = Depends(get_user_profile_service),
    authority_service: AuthorityService = Depends(get_authority_service),
) -> AuthorityPrincipal:
    """Validate that the authenticated caller has an active, provisioned authority profile.

    Enforces strict access control:
    1. Authenticated Supabase identity required (via get_current_user -> HTTP 401).
    2. Role must be 'authority' or 'admin' in user_profiles (-> HTTP 403 FORBIDDEN).
    3. AuthorityProfile must exist and be provisioned (-> HTTP 403 FORBIDDEN).
    4. AuthorityProfile must be active (-> HTTP 403 FORBIDDEN).
    5. JurisdictionScope must be non-empty and well-formed (-> HTTP 403 FORBIDDEN).

    Admins do NOT bypass authority provisioning; role authorization and jurisdiction
    authorization remain strictly distinct.
    """
    profile = user_profile_service.get_or_create_profile(current_user.user_id)

    # 1. Role Authorization
    if profile.app_role not in AUTHORIZED_AUTHORITY_ROLES:
        logger.warning(
            "Access denied: User '%s' has role '%s', required one of %s",
            current_user.user_id,
            profile.app_role,
            sorted(AUTHORIZED_AUTHORITY_ROLES),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": f"User role '{profile.app_role}' is not authorized to access authority resources.",
                "details": {
                    "user_id": current_user.user_id,
                    "actual_role": profile.app_role,
                    "required_roles": sorted(AUTHORIZED_AUTHORITY_ROLES),
                },
            },
        )

    # 2. Authority Profile & Scope Provisioning
    try:
        authority_profile = authority_service.get_authority_profile(current_user.user_id)
    except Exception as exc:
        logger.error("Error retrieving authority profile for user '%s': %s", current_user.user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": "Authority profile data is invalid or corrupted. Access denied.",
                "details": {"user_id": current_user.user_id},
            },
        )
    if authority_profile is None:
        logger.warning(
            "Access denied: User '%s' has role '%s' but lacks a provisioned AuthorityProfile.",
            current_user.user_id,
            profile.app_role,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": "Authority profile has not been provisioned for this account.",
                "details": {"user_id": current_user.user_id},
            },
        )

    # 3. Active Status Check
    if not authority_profile.is_active:
        logger.warning("Access denied: Authority account for user '%s' is inactive.", current_user.user_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": "Authority account is inactive or suspended.",
                "details": {"user_id": current_user.user_id},
            },
        )

    # 4. Scope Validity Check (Fail closed if scope is empty or invalid)
    if (
        not authority_profile.jurisdiction
        or not authority_profile.jurisdiction.state_code
        or not authority_profile.jurisdiction.authorized_district_codes
    ):
        logger.warning("Access denied: Authority account for user '%s' has invalid scope.", current_user.user_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": ErrorCode.FORBIDDEN.value,
                "message": "Authority profile lacks valid jurisdiction authorization scope.",
                "details": {"user_id": current_user.user_id},
            },
        )

    return AuthorityPrincipal(
        user_id=current_user.user_id,
        email=current_user.email,
        app_role=profile.app_role,
        department=authority_profile.department,
        designation=authority_profile.designation,
        jurisdiction=authority_profile.jurisdiction,
        is_active=authority_profile.is_active,
        badge_number=authority_profile.badge_number,
    )
