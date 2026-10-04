"""Service layer for Saved Products business logic."""

from __future__ import annotations

import logging
from typing import Any

from backend.app.services.inspection.errors import InspectionNotFoundError
from backend.app.services.inspection.repository import InspectionRepository
from backend.app.services.saved_products.errors import SavedProductNotFoundError
from backend.app.services.saved_products.models import SavedProduct
from backend.app.services.saved_products.repository import SavedProductRepository

logger = logging.getLogger(__name__)


class SavedProductService:
    """Coordinator for consumer saved product domain operations."""

    def __init__(
        self,
        repository: SavedProductRepository,
        inspection_repository: InspectionRepository | None = None,
        session_store: Any | None = None,
    ) -> None:
        self.repository = repository
        self.inspection_repository = inspection_repository
        self.session_store = session_store

    def _verify_inspection_ownership(self, user_id: str, inspection_id: str) -> Any:
        """Verify inspection exists and is owned by caller."""
        # First check session store if available
        if self.session_store is not None:
            session = None
            try:
                session = self.session_store.get_session(inspection_id)
            except InspectionNotFoundError:
                session = None

            if session is not None:
                owner = getattr(session.inspection, "owner_id", None) or (
                    session.inspection.metadata.get("owner_id") if hasattr(session.inspection, "metadata") else None
                )
                if owner != user_id:
                    raise InspectionNotFoundError(f"Inspection '{inspection_id}' not found for user '{user_id}'.")
                return session

        # Then check persistent inspection repository if available
        if self.inspection_repository is not None:
            insp = None
            try:
                insp = self.inspection_repository.get_inspection(inspection_id)
            except InspectionNotFoundError:
                insp = None

            if insp is not None:
                owner = getattr(insp, "owner_id", None) or (
                    insp.metadata.get("owner_id") if hasattr(insp, "metadata") else None
                )
                if owner != user_id:
                    raise InspectionNotFoundError(f"Inspection '{inspection_id}' not found for user '{user_id}'.")
                return insp

        raise InspectionNotFoundError(f"Inspection '{inspection_id}' not found.")

    def save_product(
        self,
        user_id: str,
        inspection_id: str,
        product_name: str | None = None,
        notes: str | None = None,
    ) -> SavedProduct:
        """Save/bookmark a verified package scan for the authenticated user.

        Verifies inspection existence and ownership to prevent IDOR attacks.
        Prevents duplicate records cleanly via repository upsert logic.
        """
        # Enforce ownership check
        self._verify_inspection_ownership(user_id=user_id, inspection_id=inspection_id)

        new_saved_product = SavedProduct(
            user_id=user_id,
            inspection_id=inspection_id,
            product_name=product_name,
            notes=notes,
        )
        return self.repository.save_product(new_saved_product)

    def list_saved_products(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List paginated saved products for authenticated caller, attaching report summary if available."""
        items, total = self.repository.list_by_user(user_id=user_id, limit=limit, offset=offset)
        results = []
        for item in items:
            d = item.to_dict()
            # Attempt to attach report summary
            overall_status = None
            summary = None
            if self.session_store is not None:
                try:
                    s = self.session_store.get_session(item.inspection_id)
                    if s.report:
                        overall_status = s.report.overall_status.value
                        summary = s.report.summary
                except Exception:
                    pass

            if overall_status is None and self.inspection_repository is not None:
                try:
                    rep = self.inspection_repository.get_report(item.inspection_id)
                    if rep:
                        overall_status = rep.overall_status.value
                        summary = rep.summary
                except Exception:
                    pass

            d["overall_status"] = overall_status
            d["summary"] = summary
            results.append(d)

        return results, total

    def delete_saved_product(self, user_id: str, saved_product_id: str) -> None:
        """Delete a saved product bookmark if owned by authenticated user."""
        success = self.repository.delete_by_id(saved_product_id=saved_product_id, user_id=user_id)
        if not success:
            raise SavedProductNotFoundError(saved_product_id=saved_product_id)
