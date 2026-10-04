"""Pydantic request and response schemas for Authority Case Management API (T3-4 Phase 4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, model_validator


class CaseSummaryResponse(BaseModel):
    """Summary representation of a case for authority queue listing."""
    id: str
    user_id: str
    inspection_id: str | None = None
    saved_product_id: str | None = None
    issue_type: str
    title: str
    status: str
    department: str
    state_code: str | None = None
    district_code: str | None = None
    jurisdiction_verified: bool
    establishment_id: str | None = None
    jurisdiction_provenance: str = "UNVERIFIED"
    jurisdiction_verified_at: datetime | None = None
    jurisdiction_verified_by: str | None = None
    assigned_officer_id: str | None = None
    assigned_at: datetime | None = None
    assigned_by: str | None = None
    created_at: datetime
    updated_at: datetime


class CaseDetailResponse(BaseModel):
    """Detailed representation of an investigation case for authorized authority inspection."""
    id: str
    user_id: str
    inspection_id: str | None = None
    saved_product_id: str | None = None
    issue_type: str
    title: str
    description: str
    status: str
    resolution_notes: str | None = None
    evidence_images: list[dict[str, Any]] = Field(default_factory=list)
    department: str
    state_code: str | None = None
    district_code: str | None = None
    jurisdiction_verified: bool
    establishment_id: str | None = None
    jurisdiction_provenance: str = "UNVERIFIED"
    jurisdiction_verified_at: datetime | None = None
    jurisdiction_verified_by: str | None = None
    assigned_officer_id: str | None = None
    assigned_at: datetime | None = None
    assigned_by: str | None = None
    created_at: datetime
    updated_at: datetime


class CaseListResponse(BaseModel):
    """Paginated list envelope for authority case queue."""
    items: list[CaseSummaryResponse]
    total: int
    limit: int
    offset: int


class CaseAssignRequest(BaseModel):
    """Request payload for assigning or reassigning primary case officer."""
    officer_user_id: str | None = Field(
        None,
        description="Target authority officer user UUID. If omitted or null, self-assigns to the authenticated authority principal.",
    )
    expected_assigned_officer_id: str | None = Field(
        None,
        description="Expected current assigned officer UUID, or 'UNASSIGNED'. Required unless expect_unassigned=true.",
    )
    expect_unassigned: bool = Field(
        False,
        description="Explicit declaration that the case is expected to be currently unassigned.",
    )

    @model_validator(mode="after")
    def validate_concurrency_precondition(self) -> CaseAssignRequest:
        token = self.expected_assigned_officer_id
        if token is not None:
            token = token.strip()
            if not token:
                raise ValueError("expected_assigned_officer_id cannot be blank.")
            if token.upper() == "UNASSIGNED":
                self.expected_assigned_officer_id = None
                self.expect_unassigned = True
            else:
                self.expected_assigned_officer_id = token

        if not self.expect_unassigned and self.expected_assigned_officer_id is None:
            raise ValueError(
                "Missing concurrency precondition: must provide expected_assigned_officer_id or set expect_unassigned=true."
            )
        return self


class CaseAssignResponse(BaseModel):
    """Response confirming officer assignment."""
    case_id: str
    assigned_officer_id: str
    assigned_by: str
    assigned_at: datetime
    event_id: str


class CreateCaseNoteRequest(BaseModel):
    """Request payload for creating a confidential internal note."""
    note_text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Confidential investigation note content (1-5000 characters).",
    )


class CaseNoteResponse(BaseModel):
    """Representation of an internal investigation note."""
    id: str
    issue_id: str
    author_id: str
    note_text: str
    is_internal: bool = True
    created_at: datetime
    updated_at: datetime


class CaseNotesListResponse(BaseModel):
    """List envelope for internal case notes."""
    items: list[CaseNoteResponse]
    total: int


class CaseStatusTransitionRequest(BaseModel):
    """Request payload for performing a controlled status transition."""
    new_status: str = Field(..., description="Target status (UNDER_REVIEW, ACTION_TAKEN, RESOLVED, REJECTED).")
    expected_status: str = Field(
        ...,
        min_length=1,
        description="Mandatory optimistic locking guard: current case status. Transition fails with HTTP 409 if status does not match.",
    )
    resolution_notes: str | None = Field(
        None,
        description="Mandatory substantive explanation for ACTION_TAKEN, RESOLVED, and REJECTED states.",
    )


class CaseStatusTransitionResponse(BaseModel):
    """Response confirming status transition."""
    case_id: str
    previous_status: str
    new_status: str
    resolution_notes: str | None = None
    updated_at: datetime
    event_id: str


class AuditEventResponse(BaseModel):
    """Representation of a case audit history entry."""
    id: str
    issue_id: str | None = None
    actor_id: str
    actor_role: str
    event_type: str
    previous_state: str | None = None
    new_state: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class CaseAuditTimelineResponse(BaseModel):
    """Timeline envelope for case audit events."""
    items: list[AuditEventResponse]
    total: int


class VerifyCaseJurisdictionRequest(BaseModel):
    """Request payload to verify case jurisdiction against an establishment."""
    establishment_id: str = Field(..., description="UUID of verified commercial establishment")
    provenance: str = Field(
        default="ADMIN_TRIAGE_VERIFICATION",
        description="Verification provenance: ADMIN_TRIAGE_VERIFICATION, VERIFIED_GSTIN_INVOICE, or ESTABLISHMENT_QR",
    )
    verification_notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Audited justification notes for jurisdiction verification",
    )


class VerifyCaseJurisdictionResponse(BaseModel):
    """Response payload confirming atomic complaint jurisdiction verification."""
    case_id: str
    establishment_id: str
    state_code: str
    district_code: str
    jurisdiction_verified: bool = True
    jurisdiction_provenance: str
    verified_at: datetime
    verified_by: str
    audit_event_id: str
    jurisdiction_verified_at: datetime | None = None
    jurisdiction_verified_by: str | None = None
    event_id: str | None = None

