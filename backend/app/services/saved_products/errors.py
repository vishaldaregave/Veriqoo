"""Error definitions for Saved Products domain."""

from __future__ import annotations

from typing import Any


class SavedProductError(Exception):
    """Base exception for saved product domain errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SavedProductNotFoundError(SavedProductError):
    """Raised when a requested saved product record is not found."""

    def __init__(self, saved_product_id: str) -> None:
        super().__init__(
            message=f"Saved product with ID '{saved_product_id}' was not found.",
            details={"saved_product_id": saved_product_id},
        )
