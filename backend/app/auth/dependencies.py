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
    """Validate incoming Bearer JWT token and return AuthenticatedUser.

    Rejects unauthenticated or invalid callers with standardized HTTP 401 envelopes.
    """
    token: str | None = None

    if credentials is not None and credentials.credentials:
        token = credentials.credentials
    else:
        # Check raw Authorization header if HTTPBearer did not parse
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": AuthErrorCode.AUTHENTICATION_REQUIRED.value,
                    "message": "Authentication is required.",
                    "details": {},
                },
            )
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": AuthErrorCode.AUTHENTICATION_INVALID.value,
                    "message": "Invalid Authorization header format. Expected 'Bearer <token>'.",
                    "details": {},
                },
            )
        token = parts[1]

    try:
        return validate_supabase_jwt(token=token, settings=settings)
    except AuthException as auth_err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": auth_err.code.value,
                "message": auth_err.message,
                "details": auth_err.details,
            },
        )
