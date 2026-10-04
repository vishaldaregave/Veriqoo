"""Pydantic request and response schemas for Retail Establishment Registry (Phase 7.4.2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
import re
from pydantic import BaseModel, Field, field_validator, model_validator

# Standard 15-character Indian GSTIN pattern:
# 2 state digits + 5 PAN letters + 4 PAN digits + 1 PAN letter + 1 entity code + 'Z' + 1 check code.
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")

# Standard 6-digit Indian PIN code (digits 0-9, first digit 1-9)
PINCODE_REGEX = re.compile(r"^[1-9][0-9]{5}$")


class CreateEstablishmentRequest(BaseModel):
    """Payload to onboard a new commercial premises in PENDING status.

    Note: Format validation of GSTIN or postal codes ensures structural integrity
    and does NOT constitute legal proof of business authenticity or registration.
    """
    trade_name: str = Field(..., min_length=1, max_length=200, description="Commercial trade name")
    legal_name: str | None = Field(default=None, max_length=200, description="Registered corporate legal entity name")
    gstin: str | None = Field(default=None, description="15-character Goods & Services Tax Identification Number")
    lm_license_number: str | None = Field(default=None, max_length=100, description="Legal Metrology dealer/manufacturer license")
    shop_establishment_number: str | None = Field(default=None, max_length=100, description="Municipal Shop & Establishment Act registration")
    state_code: str = Field(..., min_length=2, max_length=10, description="Canonical ISO 3166-2:IN state code (e.g. MH, DL)")
    district_code: str = Field(..., min_length=2, max_length=50, description="Canonical LGD district code (e.g. PUNE)")
    pincode: str | None = Field(default=None, description="6-digit Indian postal code")
    physical_address: str | None = Field(default=None, max_length=500, description="Detailed physical address")

    @field_validator("gstin", mode="before")
    @classmethod
    def validate_and_normalize_gstin(cls, v: Any) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("GSTIN must be a string.")
        clean = v.strip().upper()
        if not clean:
            return None
        if not GSTIN_REGEX.match(clean):
            raise ValueError(
                f"Invalid GSTIN structure '{clean}'. Must be a 15-character alphanumeric GSTIN matching format 22AAAAA0000A1Z5."
            )
        return clean

    @field_validator("pincode", mode="before")
    @classmethod
    def validate_pincode(cls, v: Any) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            v = str(v)
        clean = v.strip()
        if not clean:
            return None
        if not PINCODE_REGEX.match(clean):
            raise ValueError(
                f"Invalid pincode '{clean}'. Must be a 6-digit Indian postal PIN code."
            )
        return clean


class ReviewEstablishmentRequest(BaseModel):
    """Payload for an authorized officer to review, verify, suspend, or revoke an establishment."""
    action: str = Field(..., description="Review action: VERIFY, SUSPEND, or REVOKE")
    expected_status: str | None = Field(
        default=None,
        description="Mandatory optimistic concurrency token: the exact status observed before review (PENDING, VERIFIED, SUSPENDED).",
    )
    notes: str | None = Field(default=None, max_length=1000, description="Audited review justification notes")
    verification_notes: str | None = Field(default=None, max_length=1000, description="Audited review justification notes alias")
    provenance: str = Field(default="MANUAL", description="Verification source (MANUAL, OFFICIAL_REGISTRY, VERIFIED_GSTIN_INVOICE, ADMIN_TRIAGE_VERIFICATION)")

    @model_validator(mode="after")
    def sync_notes_fields(self) -> ReviewEstablishmentRequest:
        effective_note = self.notes or self.verification_notes
        self.notes = effective_note
        self.verification_notes = effective_note
        return self

    def get_notes(self) -> str | None:
        return self.notes or self.verification_notes


class EstablishmentResponse(BaseModel):
    """Response payload representing a retail commercial establishment."""
    id: str
    trade_name: str
    legal_name: str | None = None
    gstin: str | None = None
    lm_license_number: str | None = None
    shop_establishment_number: str | None = None
    state_code: str
    district_code: str
    pincode: str | None = None
    physical_address: str | None = None
    verification_status: str
    verification_provenance: str
    verification_authority_id: str | None = None
    verification_date: datetime | None = None
    verification_notes: str | None = None
    is_active: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime


class EstablishmentAuditEventResponse(BaseModel):
    """Audited state change entry for a retail establishment."""
    id: str
    establishment_id: str
    actor_id: str
    actor_role: str
    action: str
    event_type: str
    previous_status: str
    new_status: str
    previous_is_active: bool
    new_is_active: bool
    notes: str | None = None
    provenance: str = "MANUAL"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class EstablishmentAuditTimelineResponse(BaseModel):
    """List response for establishment audit events."""
    establishment_id: str
    items: list[EstablishmentAuditEventResponse]
    total: int


class PaginatedEstablishmentsResponse(BaseModel):
    """Paginated list response for establishments."""
    items: list[EstablishmentResponse]
    total: int
    limit: int
    offset: int


EstablishmentListResponse = PaginatedEstablishmentsResponse

