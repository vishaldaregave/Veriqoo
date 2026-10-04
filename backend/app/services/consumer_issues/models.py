"""Domain models for Consumer Issue Reporting (T3-3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any


class IssueType(str, Enum):
    """Supported categories of consumer issue complaints."""
    MISLEADING_LABEL = "MISLEADING_LABEL"
    PRICE_TAMPERING = "PRICE_TAMPERING"
    EXPIRED_PRODUCT = "EXPIRED_PRODUCT"
    WEIGHT_SHORTAGE = "WEIGHT_SHORTAGE"
    MISSING_MANDATORY_INFO = "MISSING_MANDATORY_INFO"
    OTHER = "OTHER"


class IssueStatus(str, Enum):
    """Lifecycle status of consumer issue complaints."""
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACTION_TAKEN = "ACTION_TAKEN"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


@dataclass
class ConsumerIssue:
    """Domain model representing a consumer issue complaint."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    inspection_id: str | None = None
    saved_product_id: str | None = None
    issue_type: str = IssueType.OTHER.value
    title: str = ""
    description: str = ""
    status: str = IssueStatus.SUBMITTED.value
    resolution_notes: str | None = None
    evidence_images: list[dict[str, Any]] = field(default_factory=list)
    # Authority & Jurisdiction workflow extensions (T3-4 & Phase 7.4.1)
    department: str = "LEGAL_METROLOGY"
    state_code: str | None = None
    district_code: str | None = None
    jurisdiction_verified: bool = False
    establishment_id: str | None = None
    jurisdiction_provenance: str = "UNVERIFIED"
    jurisdiction_verified_at: datetime | None = None
    jurisdiction_verified_by: str | None = None
    assigned_officer_id: str | None = None
    assigned_at: datetime | None = None
    assigned_by: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.created_at and self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if self.updated_at and self.updated_at.tzinfo is None:
            self.updated_at = self.updated_at.replace(tzinfo=timezone.utc)
        if self.jurisdiction_verified_at and self.jurisdiction_verified_at.tzinfo is None:
            self.jurisdiction_verified_at = self.jurisdiction_verified_at.replace(tzinfo=timezone.utc)
