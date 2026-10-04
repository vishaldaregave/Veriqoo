"""Domain models and contracts for Evidence Identity and Chain of Custody (Phase U25).

Defines:
1. EvidenceIntegrityStatus (controlled integrity vocabulary, distinct from legal compliance)
2. ChainEventType (append-oriented lifecycle events)
3. EvidenceRecord (canonical cryptographic evidence identity)
4. EvidenceChainEvent (tamper-evident hashed event node)
5. EvidenceIntegrityVerification (structured audit receipt)
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any
import uuid


def _canonical_json(data: Any) -> str:
    """Produce deterministic UTF-8 JSON representation."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class EvidenceIntegrityStatus(str, Enum):
    """Explicit integrity status of evidence artifacts.

    CRITICAL: This is an evidence byte/chain integrity status, NOT a legal compliance status.
    Compliance statuses remain strictly: PASS, FAIL, NOT_VISIBLE, NOT_APPLICABLE, REVIEW_REQUIRED.
    """
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    MISSING = "MISSING"
    HASH_MISMATCH = "HASH_MISMATCH"
    CORRUPTED = "CORRUPTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ChainEventType(str, Enum):
    """Controlled vocabulary of append-oriented evidence provenance events."""
    CAPTURED = "CAPTURED"
    RECEIVED = "RECEIVED"
    STORED = "STORED"
    HASHED = "HASHED"
    OCR_STARTED = "OCR_STARTED"
    OCR_COMPLETED = "OCR_COMPLETED"
    EVIDENCE_EXTRACTED = "EVIDENCE_EXTRACTED"
    FACT_DERIVED = "FACT_DERIVED"
    REQUIREMENT_EVALUATED = "REQUIREMENT_EVALUATED"
    REPORT_GENERATED = "REPORT_GENERATED"
    REVALIDATED = "REVALIDATED"
    INTEGRITY_CHECKED = "INTEGRITY_CHECKED"
    HASH_MISMATCH_DETECTED = "HASH_MISMATCH_DETECTED"


@dataclasses.dataclass
class EvidenceRecord:
    """Canonical cryptographic identity and provenance header for an evidence artifact.

    The original evidence content_hash is computed over the exact original bytes and
    is permanently immutable.
    """
    evidence_id: str = dataclasses.field(default_factory=lambda: f"ev-{uuid.uuid4()}")
    inspection_id: str = ""
    image_id: str | None = None
    source_id: str | None = None
    content_hash: str = ""
    hash_algorithm: str = "SHA-256"
    byte_size: int = 0
    media_type: str = "image/png"
    original_filename: str | None = None
    storage_reference: str | None = None
    captured_at: str | None = None
    received_at: str = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_at: str = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    submitted_by: str | None = None
    source_type: str = "upload"
    integrity_status: EvidenceIntegrityStatus = EvidenceIntegrityStatus.UNVERIFIED
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.evidence_id:
            self.evidence_id = f"ev-{uuid.uuid4()}"
        if not self.inspection_id:
            raise ValueError("EvidenceRecord requires a non-empty inspection_id.")
        if not self.content_hash:
            raise ValueError("EvidenceRecord requires a non-empty content_hash.")

        self.content_hash = str(self.content_hash).strip().lower()
        self.hash_algorithm = str(self.hash_algorithm).strip().upper()
        if isinstance(self.integrity_status, str):
            try:
                self.integrity_status = EvidenceIntegrityStatus(self.integrity_status)
            except ValueError:
                self.integrity_status = EvidenceIntegrityStatus.UNVERIFIED

    @staticmethod
    def compute_content_hash(data: bytes) -> str:
        """Compute lowercase hex SHA-256 digest of byte sequence."""
        return hashlib.sha256(data).hexdigest().lower()

    def to_dict(self) -> dict[str, Any]:
        """Convert evidence record to dictionary."""
        return {
            "evidence_id": self.evidence_id,
            "inspection_id": self.inspection_id,
            "image_id": self.image_id,
            "source_id": self.source_id,
            "content_hash": self.content_hash,
            "hash_algorithm": self.hash_algorithm,
            "byte_size": self.byte_size,
            "media_type": self.media_type,
            "original_filename": self.original_filename,
            "storage_reference": self.storage_reference,
            "captured_at": self.captured_at,
            "received_at": self.received_at,
            "created_at": self.created_at,
            "submitted_by": self.submitted_by,
            "source_type": self.source_type,
            "integrity_status": self.integrity_status.value if hasattr(self.integrity_status, "value") else str(self.integrity_status),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceRecord:
        """Instantiate evidence record from dictionary."""
        return cls(
            evidence_id=data.get("evidence_id", ""),
            inspection_id=data.get("inspection_id", ""),
            image_id=data.get("image_id"),
            source_id=data.get("source_id"),
            content_hash=data.get("content_hash", ""),
            hash_algorithm=data.get("hash_algorithm", "SHA-256"),
            byte_size=int(data.get("byte_size", 0)),
            media_type=data.get("media_type", "image/png"),
            original_filename=data.get("original_filename"),
            storage_reference=data.get("storage_reference"),
            captured_at=data.get("captured_at"),
            received_at=data.get("received_at", datetime.now(timezone.utc).isoformat()),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            submitted_by=data.get("submitted_by"),
            source_type=data.get("source_type", "upload"),
            integrity_status=data.get("integrity_status", EvidenceIntegrityStatus.UNVERIFIED),
            metadata=data.get("metadata", {}),
        )


@dataclasses.dataclass
class EvidenceChainEvent:
    """Tamper-evident, append-oriented provenance event in the evidence custody chain.

    Each event cryptographically references the previous event's SHA-256 hash, forming
    an immutable cryptographic chain back to initial reception.
    """
    event_id: str = dataclasses.field(default_factory=lambda: f"evt-{uuid.uuid4()}")
    evidence_id: str = ""
    inspection_id: str = ""
    event_type: ChainEventType = ChainEventType.RECEIVED
    actor_type: str = "system"
    actor_id: str | None = None
    timestamp: str = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    previous_event_hash: str | None = None
    event_hash: str = ""
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)
    operation_id: str | None = None

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = f"evt-{uuid.uuid4()}"
        if not self.evidence_id:
            raise ValueError("EvidenceChainEvent requires a non-empty evidence_id.")
        if not self.inspection_id:
            raise ValueError("EvidenceChainEvent requires a non-empty inspection_id.")

        if isinstance(self.event_type, str):
            try:
                self.event_type = ChainEventType(self.event_type)
            except ValueError:
                self.event_type = ChainEventType.RECEIVED

        if not self.event_hash:
            self.event_hash = self.compute_event_hash()

    def compute_event_hash(self) -> str:
        """Compute deterministic SHA-256 digest of the event payload."""
        payload = {
            "event_id": self.event_id,
            "evidence_id": self.evidence_id,
            "inspection_id": self.inspection_id,
            "event_type": self.event_type.value if hasattr(self.event_type, "value") else str(self.event_type),
            "actor_type": str(self.actor_type),
            "actor_id": str(self.actor_id) if self.actor_id is not None else None,
            "timestamp": str(self.timestamp),
            "previous_event_hash": str(self.previous_event_hash) if self.previous_event_hash is not None else None,
            "metadata": self.metadata,
            "operation_id": str(self.operation_id) if self.operation_id is not None else None,
        }
        canonical_str = _canonical_json(payload)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def verify_hash_integrity(self) -> bool:
        """Verify that the declared event_hash matches the computed event_hash."""
        return self.event_hash == self.compute_event_hash()

    def to_dict(self) -> dict[str, Any]:
        """Convert chain event to dictionary."""
        return {
            "event_id": self.event_id,
            "evidence_id": self.evidence_id,
            "inspection_id": self.inspection_id,
            "event_type": self.event_type.value if hasattr(self.event_type, "value") else str(self.event_type),
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "timestamp": self.timestamp,
            "previous_event_hash": self.previous_event_hash,
            "event_hash": self.event_hash,
            "metadata": dict(self.metadata),
            "operation_id": self.operation_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceChainEvent:
        """Instantiate chain event from dictionary."""
        return cls(
            event_id=data.get("event_id", ""),
            evidence_id=data.get("evidence_id", ""),
            inspection_id=data.get("inspection_id", ""),
            event_type=data.get("event_type", ChainEventType.RECEIVED),
            actor_type=data.get("actor_type", "system"),
            actor_id=data.get("actor_id"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            previous_event_hash=data.get("previous_event_hash"),
            event_hash=data.get("event_hash", ""),
            metadata=data.get("metadata", {}),
            operation_id=data.get("operation_id"),
        )


@dataclasses.dataclass
class EvidenceIntegrityVerification:
    """Structured result of an evidence integrity and custody chain verification audit."""
    evidence_id: str
    inspection_id: str
    integrity_status: EvidenceIntegrityStatus
    content_hash_valid: bool
    chain_valid: bool
    event_count: int
    first_event_at: str | None = None
    last_event_at: str | None = None
    broken_event_id: str | None = None
    error_codes: list[str] = dataclasses.field(default_factory=list)
    details: dict[str, Any] = dataclasses.field(default_factory=dict)
    verified_at: str = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_valid(self) -> bool:
        """Return True if both content hash and provenance chain are valid."""
        return self.content_hash_valid and self.chain_valid and not self.error_codes

    def to_dict(self) -> dict[str, Any]:
        """Convert verification result to dictionary."""
        return {
            "evidence_id": self.evidence_id,
            "inspection_id": self.inspection_id,
            "integrity_status": self.integrity_status.value if hasattr(self.integrity_status, "value") else str(self.integrity_status),
            "content_hash_valid": self.content_hash_valid,
            "chain_valid": self.chain_valid,
            "is_valid": self.is_valid,
            "event_count": self.event_count,
            "first_event_at": self.first_event_at,
            "last_event_at": self.last_event_at,
            "broken_event_id": self.broken_event_id,
            "error_codes": list(self.error_codes),
            "details": dict(self.details),
            "verified_at": self.verified_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceIntegrityVerification:
        """Instantiate verification result from dictionary."""
        return cls(
            evidence_id=data.get("evidence_id", ""),
            inspection_id=data.get("inspection_id", ""),
            integrity_status=data.get("integrity_status", EvidenceIntegrityStatus.UNVERIFIED),
            content_hash_valid=bool(data.get("content_hash_valid", False)),
            chain_valid=bool(data.get("chain_valid", False)),
            event_count=int(data.get("event_count", 0)),
            first_event_at=data.get("first_event_at"),
            last_event_at=data.get("last_event_at"),
            broken_event_id=data.get("broken_event_id"),
            error_codes=list(data.get("error_codes", [])),
            details=dict(data.get("details", {})),
            verified_at=data.get("verified_at", datetime.now(timezone.utc).isoformat()),
        )
