"""Pydantic API schemas and response models for Phase 8A FastAPI layer."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Service health response."""
    status: str = Field(default="ok", description="Health check status")
    service: str = Field(default="LegalMetrologyAI Backend", description="Service name")
    api_version: str = Field(default="1.0.0", description="API version")


class CreateInspectionRequest(BaseModel):
    """Optional payload when creating a new inspection session."""
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom metadata for the inspection session")
    inspection_date: str | None = Field(default=None, description="Optional date of physical inspection (YYYY-MM-DD)")


class InspectionImageResponse(BaseModel):
    """Lightweight representation of an image reference in an inspection."""
    image_id: str
    sequence: int
    added_at: str
    source_hash: str
    normalized_hash: str
    storage_path: str | None = None


class ImageUploadResponse(BaseModel):
    """Detailed metadata returned upon successful image ingestion into an inspection."""
    image_id: str
    sequence: int
    source_hash: str
    normalized_hash: str
    source_format: str
    normalized_format: str
    original_width: int
    original_height: int
    normalized_width: int
    normalized_height: int
    file_size_bytes: int
    source_file_size_bytes: int
    color_mode: str
    was_resized: bool
    was_orientation_corrected: bool
    storage_path: str | None = None


class InspectionResponse(BaseModel):
    """Complete inspection container state including image references."""
    inspection_id: str
    created_at: str
    status: str
    image_count: int
    images: list[InspectionImageResponse] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    has_report: bool = False
    owner_id: str | None = Field(default=None, description="Authenticated owner identity (UUID)")


class InspectionListResponse(BaseModel):
    """Paginated list response for user inspection history."""
    items: list[InspectionResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total count of matching inspections")
    limit: int = Field(..., description="Pagination limit")
    offset: int = Field(..., description="Pagination offset")


class RunInspectionRequest(BaseModel):
    """Parameters passed when triggering the end-to-end inspection pipeline."""
    inspection_facts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of factual declarations observed on commodity (e.g. {'fact_key': 'is_prepackaged', 'value': True})",
    )
    applicability_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Pre-evaluated or explicit applicability overrides",
    )
    target_requirements: list[str] = Field(
        default_factory=list,
        description="Target legal requirement IDs to verify against evidence (e.g. ['R-6-1-a', 'R-6-1-b'])",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Run-specific metadata",
    )


class RunInspectionResponse(BaseModel):
    """Immediate response returned when scheduling background inspection execution."""
    inspection_id: str = Field(..., description="Unique inspection identifier")
    status: str = Field(..., description="Current inspection execution status (RUNNING, COMPLETED, FAILED)")
    message: str = Field(default="Inspection execution started.", description="Human-readable status message")


class CountsResponse(BaseModel):
    """Summary counts of pipeline verification results."""
    image_count: int = 0
    evidence_count: int = 0
    applicable_requirement_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    not_visible_count: int = 0
    not_applicable_count: int = 0
    review_required_count: int = 0


class VerificationResultResponse(BaseModel):
    """Individual legal requirement verification outcome."""
    verification_id: str | None = None
    requirement_id: str
    applicability_decision_id: str | None = None
    status: str
    reason: str
    confidence: float | None = None
    review_required: bool = False
    evidence_ids: list[str] = Field(default_factory=list)
    source_observation_ids: list[str] = Field(default_factory=list)
    image_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class InspectionReportResponse(BaseModel):
    """Authoritative output of the unified inspection orchestrator."""
    inspection_id: str
    overall_status: str
    summary: str
    counts: CountsResponse
    verification_results: list[VerificationResultResponse] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)
