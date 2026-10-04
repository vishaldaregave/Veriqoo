"""Pydantic schemas for Saved Products request and response validation."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SaveProductRequest(BaseModel):
    """API request model for saving/bookmarking a product inspection."""

    inspection_id: str = Field(..., description="UUID of completed inspection session to save")
    product_name: str | None = Field(None, max_length=150, description="Optional custom product name")
    notes: str | None = Field(None, max_length=500, description="Optional personal notes")

    model_config = ConfigDict(extra="ignore")


class SavedProductResponse(BaseModel):
    """API response model for a saved product bookmark."""

    id: str = Field(..., description="Unique saved product record ID")
    user_id: str = Field(..., description="Owner Supabase user identifier")
    inspection_id: str = Field(..., description="Associated inspection UUID")
    product_name: str | None = Field(None, description="Custom product name")
    notes: str | None = Field(None, description="Personal notes")
    created_at: datetime = Field(..., description="Bookmark creation timestamp")
    updated_at: datetime = Field(..., description="Bookmark last update timestamp")
    overall_status: str | None = Field(None, description="Overall inspection status (PASS, FAIL, REVIEW_REQUIRED) if report exists")
    summary: str | None = Field(None, description="Inspection summary if report exists")

    model_config = ConfigDict(from_attributes=True)


class PaginatedSavedProductsResponse(BaseModel):
    """Paginated list response for saved products."""

    items: list[SavedProductResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total count of saved products")
    limit: int = Field(..., description="Pagination limit")
    offset: int = Field(..., description="Pagination offset")
