"""Phase 9D Authentication & Authorization package for Veriqoo."""

from __future__ import annotations

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.errors import AuthErrorCode, AuthException
from backend.app.auth.jwt import validate_supabase_jwt
from backend.app.auth.models import AuthenticatedUser

__all__ = [
    "AuthenticatedUser",
    "AuthErrorCode",
    "AuthException",
    "get_current_user",
    "validate_supabase_jwt",
]
