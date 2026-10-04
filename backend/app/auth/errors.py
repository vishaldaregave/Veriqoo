"""Authentication and Authorization exception definitions."""

from __future__ import annotations

from enum import Enum
from typing import Any


class AuthErrorCode(str, Enum):
    """Specific error codes for authentication and authorization failures."""
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    AUTHENTICATION_INVALID = "AUTHENTICATION_INVALID"
    AUTHENTICATION_EXPIRED = "AUTHENTICATION_EXPIRED"
    INSPECTION_ACCESS_DENIED = "INSPECTION_ACCESS_DENIED"
    FORBIDDEN = "FORBIDDEN"


class AuthException(Exception):
    """Base exception for authentication and token validation errors."""

    def __init__(
        self,
        code: AuthErrorCode | str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code if isinstance(code, AuthErrorCode) else AuthErrorCode(code)
        self.message = message
        self.details = details or {}
        super().__init__(message)
