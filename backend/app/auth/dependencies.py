"""FastAPI dependency for authenticating callers with Supabase Auth JWT tokens."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.auth.errors import AuthErrorCode, AuthException
from backend.app.auth.jwt import validate_supabase_jwt
from backend.app.auth.models import AuthenticatedUser
from backend.app.config import Settings, get_settings

# Declare HTTPBearer with auto_error=False to provide consistent JSON error envelopes
_BEARER_SECURITY = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_BEARER_SECURITY),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """Mock authentication for local testing."""
    return AuthenticatedUser(
        user_id="test-user-1234",
        email="test@example.com",
        role="authenticated",
        claims={},
    )
