"""Exceptions and error definitions for Retail Establishment Registry (Phase 7.4.1)."""

from __future__ import annotations

from typing import Any


class EstablishmentError(Exception):
    """Base exception for establishment domain errors."""
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class EstablishmentNotFoundError(EstablishmentError):
    """Raised when an establishment is not found by ID, GSTIN, or query."""
    pass


class EstablishmentInactiveError(EstablishmentError):
    """Raised when an establishment is inactive, archived, or disabled."""
    pass


class EstablishmentUnverifiedError(EstablishmentError):
    """Raised when attempting jurisdiction binding against an unverified establishment."""
    pass


class InvalidEstablishmentDataError(EstablishmentError):
    """Raised when establishment fields fail validation or canonical directory checks."""
    pass


class DuplicateEstablishmentError(EstablishmentError):
    """Raised when an establishment unique identifier (e.g. GSTIN) conflicts with an existing record."""
    pass


class EstablishmentRepositoryError(EstablishmentError):
    """Raised when the repository encounters an underlying database or network failure."""
    pass


# Backward compatibility alias
EstablishmentDatabaseError = EstablishmentRepositoryError



class EstablishmentConcurrencyError(EstablishmentError):
    """Raised when an establishment review encounters an optimistic concurrency token mismatch or race condition."""
    pass

