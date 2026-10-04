"""Domain models and value objects for Retail Establishment Registry (Phase 7.4.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid


class EstablishmentVerificationStatus(str, Enum):
    """Lifecycle verification state of a retail commercial establishment."""
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class EstablishmentVerificationProvenance(str, Enum):
    """Authoritative source or method through which establishment was verified."""
    MANUAL = "MANUAL"
    ESTABLISHMENT_QR = "ESTABLISHMENT_QR"
    VERIFIED_GSTIN_INVOICE = "VERIFIED_GSTIN_INVOICE"
    ADMIN_TRIAGE_VERIFICATION = "ADMIN_TRIAGE_VERIFICATION"
    OFFICIAL_REGISTRY = "OFFICIAL_REGISTRY"


@dataclass
class RetailEstablishment:
    """Domain model representing a physical commercial premises or registered dealer."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trade_name: str = ""
    legal_name: str | None = None
    gstin: str | None = None
    lm_license_number: str | None = None
    shop_establishment_number: str | None = None
    state_code: str = ""
    district_code: str = ""
    pincode: str | None = None
    physical_address: str | None = None
    verification_status: str = EstablishmentVerificationStatus.PENDING.value
    verification_provenance: str = EstablishmentVerificationProvenance.MANUAL.value
    verification_authority_id: str | None = None
    verification_date: datetime | None = None
    verification_notes: str | None = None
    is_active: bool = True
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.created_at and self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if self.updated_at and self.updated_at.tzinfo is None:
            self.updated_at = self.updated_at.replace(tzinfo=timezone.utc)
        if self.verification_date and self.verification_date.tzinfo is None:
            self.verification_date = self.verification_date.replace(tzinfo=timezone.utc)
        if self.state_code:
            self.state_code = self.state_code.strip().upper()
        if self.district_code:
            self.district_code = self.district_code.strip().upper()
