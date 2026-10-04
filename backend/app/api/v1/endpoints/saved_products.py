"""FastAPI endpoints for Consumer Saved Products Management (T3-2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from backend.app.api.dependencies import get_saved_product_service
from backend.app.api.errors import ErrorCode
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.services.inspection.errors import InspectionNotFoundError
from backend.app.services.saved_products.errors import SavedProductNotFoundError
from backend.app.services.saved_products.schemas import (
    PaginatedSavedProductsResponse,
    SavedProductResponse,
    SaveProductRequest,
)
from backend.app.services.saved_products.service import SavedProductService

router = APIRouter(prefix="/saved-products", tags=["Saved Products"])


@router.post(
    "",
    response_model=SavedProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save Product Inspection",
    description="Save/bookmark a verified package scan for the authenticated user.",
)
def save_product(
    request: SaveProductRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SavedProductService = Depends(get_saved_product_service),
) -> SavedProductResponse:
    """Save an inspection session as a consumer product bookmark."""
    try:
        saved = service.save_product(
            user_id=current_user.user_id,
            inspection_id=request.inspection_id,
            product_name=request.product_name,
            notes=request.notes,
        )
        return SavedProductResponse(
            id=saved.id,
            user_id=saved.user_id,
            inspection_id=saved.inspection_id,
            product_name=saved.product_name,
            notes=saved.notes,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )
    except InspectionNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": str(err.message if hasattr(err, "message") else err),
                "details": getattr(err, "details", {}),
            },
        )


@router.get(
    "",
    response_model=PaginatedSavedProductsResponse,
    status_code=status.HTTP_200_OK,
    summary="List Saved Products",
    description="Retrieve paginated list of saved product bookmarks for current authenticated user.",
)
def list_saved_products(
    limit: int = Query(20, ge=1, le=100, description="Number of items to return (1-100)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SavedProductService = Depends(get_saved_product_service),
) -> PaginatedSavedProductsResponse:
    """List caller's saved products with reverse-chronological ordering and pagination."""
    items_data, total = service.list_saved_products(
        user_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )
    items = [SavedProductResponse(**item) for item in items_data]
    return PaginatedSavedProductsResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete(
    "/{saved_product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unsave Product Inspection",
    description="Remove a saved product bookmark owned by current authenticated user.",
)
def delete_saved_product(
    saved_product_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SavedProductService = Depends(get_saved_product_service),
) -> Response:
    """Delete a saved product bookmark if owned by caller."""
    try:
        service.delete_saved_product(
            user_id=current_user.user_id,
            saved_product_id=saved_product_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except SavedProductNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ErrorCode.INSPECTION_NOT_FOUND.value,
                "message": err.message,
                "details": err.details,
            },
        )
