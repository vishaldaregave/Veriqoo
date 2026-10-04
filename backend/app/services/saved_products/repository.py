"""Repository abstractions and implementations for Saved Products."""

from __future__ import annotations

import abc
from datetime import datetime, timezone
import logging
import threading
from typing import Any

import requests

from backend.app.config import Settings, get_settings
from backend.app.services.saved_products.models import SavedProduct

logger = logging.getLogger(__name__)


class SavedProductRepository(abc.ABC):
    """Abstract repository for persisting saved products."""

    @abc.abstractmethod
    def save_product(self, saved_product: SavedProduct) -> SavedProduct:
        """Create or update a saved product record."""
        pass

    @abc.abstractmethod
    def get_by_id(self, saved_product_id: str) -> SavedProduct | None:
        """Retrieve a saved product record by ID."""
        pass

    @abc.abstractmethod
    def get_by_user_and_inspection(self, user_id: str, inspection_id: str) -> SavedProduct | None:
        """Retrieve a saved product by user ID and inspection ID."""
        pass

    @abc.abstractmethod
    def list_by_user(self, user_id: str, limit: int = 20, offset: int = 0) -> tuple[list[SavedProduct], int]:
        """List paginated saved products for a specific user."""
        pass

    @abc.abstractmethod
    def delete_by_id(self, saved_product_id: str, user_id: str) -> bool:
        """Delete a saved product record if owned by user_id."""
        pass


class InMemorySavedProductRepository(SavedProductRepository):
    """Thread-safe in-memory repository for unit testing and development."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: dict[str, SavedProduct] = {}

    def save_product(self, saved_product: SavedProduct) -> SavedProduct:
        with self._lock:
            # Check for existing duplicate (user_id, inspection_id)
            existing = self.get_by_user_and_inspection(saved_product.user_id, saved_product.inspection_id)
            if existing:
                existing.product_name = saved_product.product_name or existing.product_name
                existing.notes = saved_product.notes or existing.notes
                existing.updated_at = datetime.now(timezone.utc)
                return existing

            self._items[saved_product.id] = saved_product
            return saved_product

    def get_by_id(self, saved_product_id: str) -> SavedProduct | None:
        with self._lock:
            return self._items.get(saved_product_id)

    def get_by_user_and_inspection(self, user_id: str, inspection_id: str) -> SavedProduct | None:
        with self._lock:
            for item in self._items.values():
                if item.user_id == user_id and item.inspection_id == inspection_id:
                    return item
            return None

    def list_by_user(self, user_id: str, limit: int = 20, offset: int = 0) -> tuple[list[SavedProduct], int]:
        with self._lock:
            matched = [item for item in self._items.values() if item.user_id == user_id]
            matched.sort(key=lambda x: x.created_at, reverse=True)
            total = len(matched)
            paginated = matched[offset : offset + limit]
            return paginated, total

    def delete_by_id(self, saved_product_id: str, user_id: str) -> bool:
        with self._lock:
            item = self._items.get(saved_product_id)
            if item and item.user_id == user_id:
                del self._items[saved_product_id]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


class SupabaseSavedProductRepository(SavedProductRepository):
    """Supabase REST API implementation for saved products persistence."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = f"{self.settings.supabase_url.rstrip('/')}/rest/v1"

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        key = self.settings.supabase_service_role_key or self.settings.supabase_anon_key
        h = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        if prefer:
            h["Prefer"] = prefer
        return h

    def _request(self, method: str, table: str, **kwargs: Any) -> list[dict[str, Any]]:
        url = f"{self.base_url}/{table}"
        resp = requests.request(method, url, timeout=10, **kwargs)
        if resp.status_code >= 400:
            logger.error("Supabase API error %d on %s %s: %s", resp.status_code, method, url, resp.text)
            resp.raise_for_status()
        if not resp.text or resp.text.strip() == "":
            return []
        try:
            data = resp.json()
            return data if isinstance(data, list) else [data]
        except Exception:
            return []

    def _map_row(self, r: dict[str, Any]) -> SavedProduct:
        return SavedProduct(
            id=str(r["id"]),
            user_id=str(r["user_id"]),
            inspection_id=str(r["inspection_id"]),
            product_name=r.get("product_name"),
            notes=r.get("notes"),
            created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
        )

    def save_product(self, saved_product: SavedProduct) -> SavedProduct:
        existing = self.get_by_user_and_inspection(saved_product.user_id, saved_product.inspection_id)
        if existing:
            payload = {
                "product_name": saved_product.product_name or existing.product_name,
                "notes": saved_product.notes or existing.notes,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            res = self._request(
                "patch",
                "saved_products",
                headers=self._headers(prefer="return=representation"),
                params={"id": f"eq.{existing.id}"},
                json=payload,
            )
            if res:
                return self._map_row(res[0])
            return existing

        payload = {
            "user_id": saved_product.user_id,
            "inspection_id": saved_product.inspection_id,
            "product_name": saved_product.product_name,
            "notes": saved_product.notes,
        }
        res = self._request(
            "post",
            "saved_products",
            headers=self._headers(prefer="return=representation"),
            json=payload,
        )
        if res:
            return self._map_row(res[0])
        return saved_product

    def get_by_id(self, saved_product_id: str) -> SavedProduct | None:
        rows = self._request(
            "get",
            "saved_products",
            headers=self._headers(),
            params={"id": f"eq.{saved_product_id}", "limit": "1"},
        )
        if not rows:
            return None
        return self._map_row(rows[0])

    def get_by_user_and_inspection(self, user_id: str, inspection_id: str) -> SavedProduct | None:
        rows = self._request(
            "get",
            "saved_products",
            headers=self._headers(),
            params={
                "user_id": f"eq.{user_id}",
                "inspection_id": f"eq.{inspection_id}",
                "limit": "1",
            },
        )
        if not rows:
            return None
        return self._map_row(rows[0])

    def list_by_user(self, user_id: str, limit: int = 20, offset: int = 0) -> tuple[list[SavedProduct], int]:
        rows = self._request(
            "get",
            "saved_products",
            headers=self._headers(),
            params={
                "user_id": f"eq.{user_id}",
                "order": "created_at.desc",
                "offset": str(offset),
                "limit": str(limit),
            },
        )
        items = [self._map_row(r) for r in rows]
        return items, len(items)

    def delete_by_id(self, saved_product_id: str, user_id: str) -> bool:
        item = self.get_by_id(saved_product_id)
        if not item or item.user_id != user_id:
            return False

        self._request(
            "delete",
            "saved_products",
            headers=self._headers(),
            params={"id": f"eq.{saved_product_id}", "user_id": f"eq.{user_id}"},
        )
        return True
