"""Pydantic schemas for User Profile request and response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.services.user_profile.models import SUPPORTED_LANGUAGES


class UserProfileResponse(BaseModel):
    """API response model for user profile."""

    user_id: str = Field(..., description="Supabase user identifier (JWT sub)")
    email: str | None = Field(None, description="User email address from auth identity")
    display_name: str | None = Field(None, description="Human-readable display name")
    language_preference: str = Field("en", description="Preferred ISO 639-1 language code")
    app_role: str = Field("consumer", description="Application authorization role")
    created_at: datetime = Field(..., description="Profile creation timestamp")
    updated_at: datetime = Field(..., description="Profile last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class UpdateUserProfileRequest(BaseModel):
    """API request model for updating user profile.

    Strict security boundary: user_id, app_role, id, and timestamp fields
    are intentionally excluded from this schema to prevent client privilege escalation.
    """

    display_name: str | None = Field(None, max_length=100, description="Updated display name")
    language_preference: str | None = Field(None, description="Updated language code")

    model_config = ConfigDict(extra="ignore")

    @field_validator("language_preference")
    @classmethod
    def validate_language(cls, v: str | None) -> str | None:
        if v is not None:
            v_clean = v.strip().lower()
            if v_clean not in SUPPORTED_LANGUAGES:
                raise ValueError(
                    f"Unsupported language code '{v}'. Allowed language codes: {sorted(SUPPORTED_LANGUAGES)}"
                )
            return v_clean
        return v
