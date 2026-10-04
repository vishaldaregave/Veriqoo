"""Pydantic request and response schemas for Consumer Issue Reporting (T3-3)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.app.services.consumer_issues.models import IssueStatus, IssueType


class CreateConsumerIssueRequest(BaseModel):
    """Client payload to submit a consumer issue complaint."""
    inspection_id: str = Field(..., description="UUID of the owned inspection session")
    saved_product_id: str | None = Field(default=None, description="Optional UUID of linked saved product bookmark")
    issue_type: IssueType = Field(..., description="Category of reported consumer issue")
    title: str = Field(..., min_length=1, max_length=200, description="Short summary title")
    description: str = Field(..., min_length=1, max_length=2000, description="Detailed explanation of the issue")
    evidence_image_ids: list[str] = Field(default_factory=list, description="Optional image IDs belonging to inspection session")
    state_code: str | None = Field(default=None, description="Client-claimed state code (untrusted)")
    district_code: str | None = Field(default=None, description="Client-claimed district code (untrusted)")


class ConsumerIssueResponse(BaseModel):
    """Response payload representing a consumer issue complaint."""
    id: str
    user_id: str
    inspection_id: str | None = None
    saved_product_id: str | None = None
    issue_type: IssueType
    title: str
    description: str
    status: IssueStatus
    resolution_notes: str | None = None
    evidence_images: list[dict[str, Any]] = Field(default_factory=list)
    department: str = "LEGAL_METROLOGY"
    state_code: str | None = None
    district_code: str | None = None
    jurisdiction_verified: bool = False
    establishment_id: str | None = None
    jurisdiction_provenance: str = "UNVERIFIED"
    jurisdiction_verified_at: datetime | None = None
    jurisdiction_verified_by: str | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedConsumerIssuesResponse(BaseModel):
    """Paginated list response for consumer issue complaints."""
    items: list[ConsumerIssueResponse]
    total: int
    limit: int
    offset: int
