"""Phase 5E — Evidence-to-Requirement Verification Module."""

from backend.app.services.verification.deterministic import DeterministicVerifier
from backend.app.services.verification.errors import (
    ContradictoryEvidenceError,
    InvalidApplicabilityError,
    InvalidVerificationStateError,
    MissingRequirementError,
    TraceabilityError,
    VerificationError,
)
from backend.app.services.verification.evidence_matcher import EvidenceMatcher
from backend.app.services.verification.models import (
    RequirementReference,
    VerificationResult,
    VerificationStatus,
)
from backend.app.services.verification.service import VerificationService

__all__ = [
    "VerificationStatus",
    "RequirementReference",
    "VerificationResult",
    "EvidenceMatcher",
    "DeterministicVerifier",
    "VerificationService",
    "VerificationError",
    "MissingRequirementError",
    "InvalidApplicabilityError",
    "InvalidVerificationStateError",
    "TraceabilityError",
    "ContradictoryEvidenceError",
]

