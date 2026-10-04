"""Data models and schemas for Phase U4 QR Detailed Report Sharing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class ShareStatus(str, Enum):
    """Lifecycle status of a report share reference."""
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


@dataclass
class ReportShare:
    """Persistent entity representing a shared inspection report reference."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    inspection_id: str = ""
    token_hash: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            self.expires_at = self.expires_at.replace(tzinfo=timezone.utc)
        if self.revoked_at is not None and self.revoked_at.tzinfo is None:
            self.revoked_at = self.revoked_at.replace(tzinfo=timezone.utc)

    @property
    def is_revoked(self) -> bool:
        """Whether the share token has been explicitly revoked."""
        return self.revoked_at is not None

    def is_expired(self, now: datetime | None = None) -> bool:
        """Whether the share token has passed its expiration timestamp."""
        if self.expires_at is None:
            return False
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        return current_time >= self.expires_at

    def is_valid(self, now: datetime | None = None) -> bool:
        """Whether the share reference is currently active and eligible for resolution."""
        return (not self.is_revoked) and (not self.is_expired(now))

    def status(self, now: datetime | None = None) -> ShareStatus:
        """Compute the current ShareStatus."""
        if self.is_revoked:
            return ShareStatus.REVOKED
        if self.is_expired(now):
            return ShareStatus.EXPIRED
        return ShareStatus.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        """Convert share record to serialized representation (never exposing raw tokens)."""
        return {
            "id": self.id,
            "inspection_id": self.inspection_id,
            "token_hash": self.token_hash,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "created_by": self.created_by,
            "metadata": dict(self.metadata),
            "status": self.status().value,
        }


@dataclass
class QRPayload:
    """Structured QR payload metadata suitable for Flutter consumption."""
    url: str
    token_id: str
    format: str = "url"
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "token_id": self.token_id,
            "format": self.format,
            "version": self.version,
        }


@dataclass
class PublicInspectionReport:
    """Sanitized public projection of an InspectionReport.

    Strictly excludes:
    - owner_id
    - authenticated user data / JWT claims
    - private storage paths
    - internal filesystem paths
    - internal exceptions / service diagnostics
    """
    report_id: str
    inspection_id: str
    overall_status: str
    language: str
    summary: str
    counts: dict[str, int]
    verification_results: list[dict[str, Any]]
    evidence_annotations: list[dict[str, Any]]
    created_at: str
    share_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "inspection_id": self.inspection_id,
            "overall_status": self.overall_status,
            "language": self.language,
            "summary": self.summary,
            "counts": self.counts,
            "verification_results": self.verification_results,
            "evidence_annotations": self.evidence_annotations,
            "created_at": self.created_at,
            "share_metadata": self.share_metadata,
        }
