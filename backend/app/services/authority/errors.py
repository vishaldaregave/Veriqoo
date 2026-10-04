"""Authority domain exceptions and access-control errors (T3-4 Phase 2)."""

from __future__ import annotations

from typing import Any


class AuthorityError(Exception):
    """Base exception for all authority domain and authorization errors."""
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class AuthorityRoleDeniedError(AuthorityError):
    """Raised when caller's app_role is not an authorized authority role."""
    pass


AuthorityAccessDeniedError = AuthorityRoleDeniedError



class AuthorityNotProvisionedError(AuthorityError):
    """Raised when caller has authority role but lacks a provisioned AuthorityProfile."""
    pass


class AuthorityInactiveError(AuthorityError):
    """Raised when an authority account is marked inactive or suspended."""
    pass


class AuthorityJurisdictionDeniedError(AuthorityError):
    """Raised when an authority attempts to access a case outside their authorized scope."""
    pass


class InvalidJurisdictionScopeError(AuthorityError):
    """Raised when jurisdiction parameters are missing, empty, or malformed."""
    pass


class CaseNotFoundError(AuthorityError):
    """Raised when a requested case is not found."""
    pass


class InvalidAssignmentError(AuthorityError):
    """Raised when case assignment or reassignment violates authority rules."""
    pass


class InvalidStatusTransitionError(AuthorityError):
    """Raised when an invalid case status transition is attempted."""
    pass


class InvalidCaseNoteError(AuthorityError):
    """Raised when case note content is invalid, empty, or exceeds allowed limits."""
    pass
