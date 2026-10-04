"""FastAPI endpoints for User Profile Management (T3-1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from backend.app.api.dependencies import get_user_profile_service
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.services.user_profile.schemas import (
    UpdateUserProfileRequest,
    UserProfileResponse,
)
from backend.app.services.user_profile.service import UserProfileService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Authenticated User Profile",
    description="Retrieve current user's profile. Auto-creates default consumer profile if none exists.",
)
def get_my_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: UserProfileService = Depends(get_user_profile_service),
) -> UserProfileResponse:
    """Retrieve or auto-create profile for authenticated caller."""
    profile = service.get_or_create_profile(user_id=current_user.user_id)
    return UserProfileResponse(
        user_id=profile.user_id,
        email=current_user.email,
        display_name=profile.display_name,
        language_preference=profile.language_preference,
        app_role=profile.app_role,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.patch(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Authenticated User Profile",
    description="Update permitted profile fields (display_name, language_preference) for current user.",
)
def update_my_profile(
    request: UpdateUserProfileRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: UserProfileService = Depends(get_user_profile_service),
) -> UserProfileResponse:
    """Update permitted fields for authenticated caller's profile."""
    updates = request.model_dump(exclude_unset=True)
    updated_profile = service.update_profile(
        user_id=current_user.user_id,
        updates=updates,
    )
    return UserProfileResponse(
        user_id=updated_profile.user_id,
        email=current_user.email,
        display_name=updated_profile.display_name,
        language_preference=updated_profile.language_preference,
        app_role=updated_profile.app_role,
        created_at=updated_profile.created_at,
        updated_at=updated_profile.updated_at,
    )
