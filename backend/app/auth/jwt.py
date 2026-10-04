"""Cryptographic Supabase Auth JWT validation service."""

from __future__ import annotations

import logging
import time
from typing import Any
import jwt

from backend.app.auth.errors import AuthErrorCode, AuthException
from backend.app.auth.models import AuthenticatedUser
from backend.app.config import Settings, get_settings

logger = logging.getLogger(__name__)


def create_jwt_token(
    payload: dict[str, Any],
    secret: str,
    algorithm: str = "HS256",
    audience: str = "authenticated",
    expires_in_seconds: int = 3600,
) -> str:
    """Create a signed JWT token with standard claims (used for test simulation and internal helpers)."""
    now = int(time.time())
    token_payload = {
        "iat": now,
        "nbf": now - 10,
        "exp": now + expires_in_seconds,
        "aud": audience,
        **payload,
    }
    return jwt.encode(token_payload, secret, algorithm=algorithm)


def validate_supabase_jwt(
    token: str,
    settings: Settings | None = None,
    secret_override: str | None = None,
) -> AuthenticatedUser:
    """Cryptographically validate a Supabase Auth JWT access token and return AuthenticatedUser.

    Guarantees:
    1. Rejects missing, empty, or non-string tokens with AUTHENTICATION_REQUIRED.
    2. Validates JWT cryptographic signature using configured Supabase secrets.
    3. Verifies token expiration timestamp ('exp') and not-before ('nbf') claims.
    4. Validates audience ('aud') if configured.
    5. Extracts subject ('sub') as the authenticated user UUID.
    """
    if not token or not isinstance(token, str):
        raise AuthException(
            code=AuthErrorCode.AUTHENTICATION_REQUIRED,
            message="Authentication token is missing.",
        )

    token_str = token.strip()
    if not token_str:
        raise AuthException(
            code=AuthErrorCode.AUTHENTICATION_REQUIRED,
            message="Authentication token is empty.",
        )

    cfg = settings or get_settings()

    # Determine cryptographic verification secret
    # Priority: secret_override -> supabase_jwt_secret -> supabase_service_role_key -> supabase_anon_key
    verification_key = (
        secret_override
        or getattr(cfg, "supabase_jwt_secret", "")
        or cfg.supabase_service_role_key
        or cfg.supabase_anon_key
    )

    if not verification_key:
        logger.error("Supabase JWT verification key is not configured in settings.")
        raise AuthException(
            code=AuthErrorCode.AUTHENTICATION_INVALID,
            message="Authentication verification key is not configured on server.",
        )

    try:
        unverified_header = jwt.get_unverified_header(token_str)
        alg = unverified_header.get("alg", "HS256")
    except Exception as exc:
        raise AuthException(
            code=AuthErrorCode.AUTHENTICATION_INVALID,
            message="Malformed or unreadable authentication token header.",
        )

    try:
        # Cryptographically decode and verify signature & claims
        aud = getattr(cfg, "supabase_jwt_audience", "authenticated") or None
        payload: dict[str, Any] = jwt.decode(
            token_str,
            verification_key,
            algorithms=[alg, "HS256", "RS256", "ES256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "require": ["sub", "exp"],
            },
            audience=aud,
        )
    except jwt.ExpiredSignatureError:
        raise AuthException(
            code=AuthErrorCode.AUTHENTICATION_EXPIRED,
            message="Authentication token has expired.",
        )
    except jwt.InvalidTokenError as exc:
        raise AuthException(
            code=AuthErrorCode.AUTHENTICATION_INVALID,
            message=f"Invalid authentication token: {str(exc)}",
        )
    except Exception as exc:
        logger.warning("Unexpected JWT validation error: %s", exc)
        raise AuthException(
            code=AuthErrorCode.AUTHENTICATION_INVALID,
            message="Authentication token validation failed.",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise AuthException(
            code=AuthErrorCode.AUTHENTICATION_INVALID,
            message="Authentication token is missing required 'sub' identity claim.",
        )

    return AuthenticatedUser(
        user_id=str(user_id),
        email=payload.get("email"),
        role=str(payload.get("role", "authenticated")),
        claims=payload,
    )
