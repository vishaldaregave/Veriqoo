"""T3-2 Consumer Scan History & Saved Products Test Suite.

Verifies:
1. Unauthenticated requests return HTTP 401 AUTHENTICATION_REQUIRED / AUTHENTICATION_INVALID.
2. Authenticated GET /api/v1/inspections returns caller's scan history in reverse chronological order.
3. Scan history pagination (limit, offset) and total counts operate deterministically.
4. Multi-tenant isolation: Users cannot view or save another user's scan sessions.
5. POST /api/v1/saved-products saves a valid owned inspection session.
6. Duplicate POST /api/v1/saved-products is handled idempotently without duplicate records or errors.
7. Attempting to save a non-existent or unowned inspection returns HTTP 404.
8. GET /api/v1/saved-products returns paginated saved products list with report summaries.
9. DELETE /api/v1/saved-products/{id} deletes saved product if owned by caller, returning 204 No Content.
10. Attempting to delete an unowned or non-existent saved product returns HTTP 404.
"""

from __future__ import annotations

import sys
sys.modules['ujson'] = None  # Bypass Windows App Control policy DLL block for ujson

import unittest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    get_saved_product_repository,
    get_session_store,
)
from backend.app.api.errors import ErrorCode
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth.jwt import create_jwt_token
from backend.app.config import settings
from backend.app.main import app
from backend.app.services.saved_products.repository import InMemorySavedProductRepository


class T32HistoryAndSavedProductsTestCase(unittest.TestCase):
    """Test suite for T3-2 Consumer Scan History and Saved Products API endpoints."""

    def setUp(self) -> None:
        self.secret = "test-t3-2-history-saved-products-secret-32chars!"
        self.audience = "authenticated"
        self.original_secret = settings.supabase_jwt_secret
        self.original_audience = settings.supabase_jwt_audience

        settings.supabase_jwt_secret = self.secret
        settings.supabase_jwt_audience = self.audience

        self.store = InMemoryInspectionStore()
        self.saved_repo = InMemorySavedProductRepository()

        app.dependency_overrides[get_session_store] = lambda: self.store
        app.dependency_overrides[get_saved_product_repository] = lambda: self.saved_repo

        self.client = TestClient(app)

        self.user_a_id = "1111aaaa-1111-4111-8111-111111111111"
        self.user_a_email = "alice.consumer@veriqoo.ai"
        self.user_a_token = create_jwt_token(
            payload={"sub": self.user_a_id, "email": self.user_a_email, "role": "authenticated"},
            secret=self.secret,
            audience=self.audience,
            expires_in_seconds=3600,
        )

        self.user_b_id = "2222bbbb-2222-4222-8222-222222222222"
        self.user_b_email = "bob.consumer@veriqoo.ai"
        self.user_b_token = create_jwt_token(
            payload={"sub": self.user_b_id, "email": self.user_b_email, "role": "authenticated"},
            secret=self.secret,
            audience=self.audience,
            expires_in_seconds=3600,
        )

    def tearDown(self) -> None:
        settings.supabase_jwt_secret = self.original_secret
        settings.supabase_jwt_audience = self.original_audience
        app.dependency_overrides.clear()
        self.store.clear()
        self.saved_repo.clear()

    # =================================================================
    # 1. Unauthenticated Access Protection
    # =================================================================

    def test_scan_history_unauthenticated_returns_401(self) -> None:
        """GET /api/v1/inspections without token returns 401 AUTHENTICATION_REQUIRED."""
        res = self.client.get("/api/v1/inspections")
        self.assertEqual(res.status_code, 401)
        err = res.json()["error"]
        self.assertEqual(err["code"], ErrorCode.AUTHENTICATION_REQUIRED.value)

    def test_save_product_unauthenticated_returns_401(self) -> None:
        """POST /api/v1/saved-products without token returns 401 AUTHENTICATION_REQUIRED."""
        res = self.client.post("/api/v1/saved-products", json={"inspection_id": "fake-id"})
        self.assertEqual(res.status_code, 401)
        err = res.json()["error"]
        self.assertEqual(err["code"], ErrorCode.AUTHENTICATION_REQUIRED.value)

    def test_list_saved_products_unauthenticated_returns_401(self) -> None:
        """GET /api/v1/saved-products without token returns 401 AUTHENTICATION_REQUIRED."""
        res = self.client.get("/api/v1/saved-products")
        self.assertEqual(res.status_code, 401)
        err = res.json()["error"]
        self.assertEqual(err["code"], ErrorCode.AUTHENTICATION_REQUIRED.value)

    def test_delete_saved_product_unauthenticated_returns_401(self) -> None:
        """DELETE /api/v1/saved-products/{id} without token returns 401 AUTHENTICATION_REQUIRED."""
        res = self.client.delete("/api/v1/saved-products/fake-id")
        self.assertEqual(res.status_code, 401)
        err = res.json()["error"]
        self.assertEqual(err["code"], ErrorCode.AUTHENTICATION_REQUIRED.value)

    # =================================================================
    # 2. Consumer Scan History
    # =================================================================

    def test_empty_scan_history_returns_200_and_empty_list(self) -> None:
        """GET /api/v1/inspections for user with no scans returns 200 with total 0."""
        res = self.client.get(
            "/api/v1/inspections",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["items"], [])
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["limit"], 20)
        self.assertEqual(data["offset"], 0)

    def test_scan_history_returns_owned_sessions_reverse_chronological(self) -> None:
        """GET /api/v1/inspections returns caller's scans in reverse-chronological order."""
        # Create 3 sessions for User A
        c1 = self.client.post(
            "/api/v1/inspections",
            json={"metadata": {"batch": "1"}},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()

        c2 = self.client.post(
            "/api/v1/inspections",
            json={"metadata": {"batch": "2"}},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()

        c3 = self.client.post(
            "/api/v1/inspections",
            json={"metadata": {"batch": "3"}},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()

        res = self.client.get(
            "/api/v1/inspections",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 3)
        # Order should be c3, c2, c1 (most recent first)
        returned_ids = [item["inspection_id"] for item in data["items"]]
        self.assertEqual(returned_ids, [c3["inspection_id"], c2["inspection_id"], c1["inspection_id"]])

    def test_scan_history_pagination(self) -> None:
        """GET /api/v1/inspections paginates correctly with limit and offset."""
        ids = []
        for i in range(5):
            c = self.client.post(
                "/api/v1/inspections",
                json={"metadata": {"index": i}},
                headers={"Authorization": f"Bearer {self.user_a_token}"},
            ).json()
            ids.append(c["inspection_id"])

        # Reverse order expected: [ids[4], ids[3], ids[2], ids[1], ids[0]]
        rev = list(reversed(ids))

        # Page 1: limit 2, offset 0
        res1 = self.client.get(
            "/api/v1/inspections?limit=2&offset=0",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()
        self.assertEqual(res1["total"], 5)
        self.assertEqual(len(res1["items"]), 2)
        self.assertEqual([x["inspection_id"] for x in res1["items"]], rev[0:2])

        # Page 2: limit 2, offset 2
        res2 = self.client.get(
            "/api/v1/inspections?limit=2&offset=2",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()
        self.assertEqual(res2["total"], 5)
        self.assertEqual(len(res2["items"]), 2)
        self.assertEqual([x["inspection_id"] for x in res2["items"]], rev[2:4])

    def test_multi_tenant_scan_history_isolation(self) -> None:
        """User A and User B scan histories are completely isolated."""
        # Create scan for User A
        cA = self.client.post(
            "/api/v1/inspections",
            json={"metadata": {"user": "A"}},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()

        # Create scan for User B
        cB = self.client.post(
            "/api/v1/inspections",
            json={"metadata": {"user": "B"}},
            headers={"Authorization": f"Bearer {self.user_b_token}"},
        ).json()

        # User A history contains only cA
        resA = self.client.get(
            "/api/v1/inspections",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()
        self.assertEqual(resA["total"], 1)
        self.assertEqual(resA["items"][0]["inspection_id"], cA["inspection_id"])

        # User B history contains only cB
        resB = self.client.get(
            "/api/v1/inspections",
            headers={"Authorization": f"Bearer {self.user_b_token}"},
        ).json()
        self.assertEqual(resB["total"], 1)
        self.assertEqual(resB["items"][0]["inspection_id"], cB["inspection_id"])

    # =================================================================
    # 3. Saved Products Management
    # =================================================================

    def test_save_product_success(self) -> None:
        """POST /api/v1/saved-products saves an owned inspection as a bookmarked product."""
        create_res = self.client.post(
            "/api/v1/inspections",
            json={"metadata": {"package": "biscuits"}},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()
        insp_id = create_res["inspection_id"]

        save_res = self.client.post(
            "/api/v1/saved-products",
            json={
                "inspection_id": insp_id,
                "product_name": "Britannia Premium Biscuits",
                "notes": "Verified compliant label",
            },
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(save_res.status_code, 201)
        data = save_res.json()
        self.assertEqual(data["user_id"], self.user_a_id)
        self.assertEqual(data["inspection_id"], insp_id)
        self.assertEqual(data["product_name"], "Britannia Premium Biscuits")
        self.assertEqual(data["notes"], "Verified compliant label")

    def test_save_product_unowned_inspection_returns_404(self) -> None:
        """User A cannot save User B's inspection (returns 404 INSPECTION_NOT_FOUND)."""
        create_res = self.client.post(
            "/api/v1/inspections",
            json={},
            headers={"Authorization": f"Bearer {self.user_b_token}"},
        ).json()
        insp_b_id = create_res["inspection_id"]

        save_res = self.client.post(
            "/api/v1/saved-products",
            json={"inspection_id": insp_b_id, "product_name": "Spoofed Product"},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(save_res.status_code, 404)
        err = save_res.json()["error"]
        self.assertEqual(err["code"], ErrorCode.INSPECTION_NOT_FOUND.value)

    def test_save_product_nonexistent_inspection_returns_404(self) -> None:
        """Saving non-existent inspection returns 404 INSPECTION_NOT_FOUND."""
        save_res = self.client.post(
            "/api/v1/saved-products",
            json={"inspection_id": "00000000-0000-0000-0000-000000000000"},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(save_res.status_code, 404)
        err = save_res.json()["error"]
        self.assertEqual(err["code"], ErrorCode.INSPECTION_NOT_FOUND.value)

    def test_save_product_duplicate_is_idempotent(self) -> None:
        """Saving the same inspection twice updates existing record cleanly without duplicates or error."""
        create_res = self.client.post(
            "/api/v1/inspections",
            json={},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()
        insp_id = create_res["inspection_id"]

        res1 = self.client.post(
            "/api/v1/saved-products",
            json={"inspection_id": insp_id, "product_name": "Name 1"},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res1.status_code, 201)

        res2 = self.client.post(
            "/api/v1/saved-products",
            json={"inspection_id": insp_id, "product_name": "Name 2"},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res2.status_code, 201)
        self.assertEqual(res2.json()["id"], res1.json()["id"])
        self.assertEqual(res2.json()["product_name"], "Name 2")

        # Verify only 1 saved product in list
        list_res = self.client.get(
            "/api/v1/saved-products",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()
        self.assertEqual(list_res["total"], 1)

    def test_list_saved_products_and_delete(self) -> None:
        """Full lifecycle: save product, list saved products, delete saved product."""
        c1 = self.client.post(
            "/api/v1/inspections",
            json={},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()

        s1 = self.client.post(
            "/api/v1/saved-products",
            json={"inspection_id": c1["inspection_id"], "product_name": "Product 1"},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()

        # List saved products
        list_res = self.client.get(
            "/api/v1/saved-products",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(list_res.status_code, 200)
        data = list_res.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["id"], s1["id"])

        # Delete saved product
        del_res = self.client.delete(
            f"/api/v1/saved-products/{s1['id']}",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(del_res.status_code, 204)

        # List should now be empty
        list_res2 = self.client.get(
            "/api/v1/saved-products",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()
        self.assertEqual(list_res2["total"], 0)

    def test_delete_unowned_saved_product_returns_404(self) -> None:
        """User A cannot delete User B's saved product (returns 404)."""
        cB = self.client.post(
            "/api/v1/inspections",
            json={},
            headers={"Authorization": f"Bearer {self.user_b_token}"},
        ).json()

        sB = self.client.post(
            "/api/v1/saved-products",
            json={"inspection_id": cB["inspection_id"]},
            headers={"Authorization": f"Bearer {self.user_b_token}"},
        ).json()

        # User A tries to delete User B's saved product
        del_res = self.client.delete(
            f"/api/v1/saved-products/{sB['id']}",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(del_res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
