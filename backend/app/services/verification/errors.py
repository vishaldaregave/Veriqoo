"""Error hierarchy for Phase 5E Verification Contract."""

from __future__ import annotations


class VerificationError(Exception):
    """Base exception for all verification domain errors."""
    pass


class MissingRequirementError(VerificationError):
    """Raised when a verification request lacks a valid, mandatory requirement_id."""
    pass


class InvalidApplicabilityError(VerificationError):
    """Raised when an unrecognized or invalid applicability state is provided."""
    pass


class InvalidVerificationStateError(VerificationError):
    """Raised when verification state invariants are violated."""
    pass


class TraceabilityError(VerificationError):
    """Raised when provenance links between verification, evidence, and images are broken."""
    pass


class ContradictoryEvidenceError(VerificationError):
    """Raised when deterministic verification detects mutually exclusive evidence candidates."""
    pass

