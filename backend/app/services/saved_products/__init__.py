"""Saved Products domain package."""

from __future__ import annotations

from backend.app.services.saved_products.errors import SavedProductError, SavedProductNotFoundError
from backend.app.services.saved_products.models import SavedProduct
from backend.app.services.saved_products.repository import (
    InMemorySavedProductRepository,
    SavedProductRepository,
    SupabaseSavedProductRepository,
)
from backend.app.services.saved_products.schemas import (
    PaginatedSavedProductsResponse,
    SavedProductResponse,
    SaveProductRequest,
)
from backend.app.services.saved_products.service import SavedProductService

__all__ = [
    "SavedProduct",
    "SavedProductError",
    "SavedProductNotFoundError",
    "SavedProductRepository",
    "InMemorySavedProductRepository",
    "SupabaseSavedProductRepository",
    "SavedProductService",
    "SaveProductRequest",
    "SavedProductResponse",
    "PaginatedSavedProductsResponse",
]
