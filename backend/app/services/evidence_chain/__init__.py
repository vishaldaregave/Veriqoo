"""Evidence Trust and Tamper-Evident Chain of Custody (Phase U25).

Provides cryptographic identity, append-oriented provenance event chains,
storage verification, OCR provenance, evidence-to-requirement traceability,
and deterministic integrity verification for Veriqoo inspections.
"""

from __future__ import annotations

from backend.app.services.evidence_chain.models import (
    ChainEventType,
    EvidenceChainEvent,
    EvidenceIntegrityStatus,
    EvidenceIntegrityVerification,
    EvidenceRecord,
)
from backend.app.services.evidence_chain.repository import (
    EvidenceChainRepository,
    InMemoryEvidenceChainRepository,
    SupabaseEvidenceChainRepository,
)
from backend.app.services.evidence_chain.service import EvidenceChainService
from backend.app.services.evidence_chain.verifier import EvidenceChainVerifier

__all__ = [
    "ChainEventType",
    "EvidenceChainEvent",
    "EvidenceChainRepository",
    "EvidenceChainService",
    "EvidenceChainVerifier",
    "EvidenceIntegrityStatus",
    "EvidenceIntegrityVerification",
    "EvidenceRecord",
    "InMemoryEvidenceChainRepository",
    "SupabaseEvidenceChainRepository",
]
