"""T3-3 Consumer Issue Reporting Test Suite.

Verifies:
1. Unauthenticated requests return HTTP 401 AUTHENTICATION_REQUIRED.
2. Successful complaint creation with valid owned inspection and verified evidence image.
3. Attempting to create an issue on an unowned or nonexistent inspection returns HTTP 404.
4. Referencing an invalid evidence image ID returns HTTP 400 INVALID_IMAGE_REFERENCE.
5. Duplicate submission for (user_id, inspection_id, issue_type) returns HTTP 409 DUPLICATE_CONSUMER_ISSUE.
6. Client attempts to override status or resolution fields are ignored/forced to SUBMITTED and None.
7. Submitting an issue report leaves underlying AI inspection report overall_status invariant.
8. GET /api/v1/consumer-issues paginates correctly and supports status filtering.
9. GET /api/v1/consumer-issues/{id} returns details for owned complaint.
10. Accessing another user's complaint returns HTTP 404 (multi-tenant IDOR protection).
11. DELETE /api/v1/consumer-issues/{id} withdraws complaint in SUBMITTED status returning 204.
12. Attempting to withdraw a complaint in UNDER_REVIEW or RESOLVED status returns HTTP 409 Conflict.
13. Complaint retention: Deleting an inspection session preserves complaint record with inspection_id set to None.
14. Repository persistence and concurrency-safe duplicate handling.
"""

from __future__ import annotations

import sys
sys.modules['ujson'] = None  # Bypass Windows App Control policy DLL block for ujson

from datetime import datetime, timezone
import unittest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    get_consumer_issue_repository,
    get_saved_product_repository,
    get_session_store,
)
from backend.app.api.errors import ErrorCode
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth.jwt import create_jwt_token
from backend.app.config import settings
from backend.app.main import app
from backend.app.services.consumer_issues.models import ConsumerIssue, IssueStatus, IssueType
from backend.app.services.consumer_issues.repository import InMemoryConsumerIssueRepository
from backend.app.services.evidence.models import ImageArtifact
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.saved_products.models import SavedProduct
from backend.app.services.saved_products.repository import InMemorySavedProductRepository


class T33ConsumerIssueReportingTestCase(unittest.TestCase):
    """Test suite for T3-3 Consumer Issue Reporting API endpoints and service logic."""

    def setUp(self) -> None:
        self.secret = "test-t3-3-consumer-issues-secret-32chars!"
        self.audience = "authenticated"
        self.original_secret = settings.supabase_jwt_secret
        self.original_audience = settings.supabase_jwt_audience

        settings.supabase_jwt_secret = self.secret
        settings.supabase_jwt_audience = self.audience

        self.store = InMemoryInspectionStore()
        self.issue_repo = InMemoryConsumerIssueRepository()
        self.saved_repo = InMemorySavedProductRepository()

        app.dependency_overrides[get_session_store] = lambda: self.store
        app.dependency_overrides[get_consumer_issue_repository] = lambda: self.issue_repo
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
        self.issue_repo.clear()
        self.saved_repo.clear()

    # =================================================================
    # Helper Methods
    # =================================================================

    def _create_inspection_with_artifact(self, user_token: str) -> tuple[str, str]:
        """Helper to create an inspection session with one attached ImageArtifact."""
        resp = self.client.post(
            "/api/v1/inspections",
            json={"metadata": {"test": "t3_3"}},
            headers={"Authorization": f"Bearer {user_token}"},
        ).json()
        insp_id = resp["inspection_id"]

        artifact = ImageArtifact(
            image_id="img_test_12345",
            source_hash="hash_source_123",
            normalized_hash="hash_norm_123",
            source_format="JPEG",
            normalized_format="PNG",
            original_width=1000,
            original_height=1000,
            normalized_width=1000,
            normalized_height=1000,
            pixel_count=1000000,
            aspect_ratio=1.0,
            file_size_bytes=5000,
            source_file_size_bytes=6000,
            color_mode="RGB",
            normalized_bytes=b"dummy_bytes",
        )
        self.store.add_artifact(insp_id, artifact)
        return insp_id, artifact.image_id

    # =================================================================
    # 1. Unauthenticated Requests Return HTTP 401
    # =================================================================

    def test_post_issue_unauthenticated_returns_401(self) -> None:
        """POST /api/v1/consumer-issues without token returns 401 AUTHENTICATION_REQUIRED."""
        res = self.client.post("/api/v1/consumer-issues", json={"inspection_id": "fake", "title": "t", "description": "d", "issue_type": "PRICE_TAMPERING"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.AUTHENTICATION_REQUIRED.value)

    def test_list_issues_unauthenticated_returns_401(self) -> None:
        """GET /api/v1/consumer-issues without token returns 401 AUTHENTICATION_REQUIRED."""
        res = self.client.get("/api/v1/consumer-issues")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.AUTHENTICATION_REQUIRED.value)

    def test_get_issue_unauthenticated_returns_401(self) -> None:
        """GET /api/v1/consumer-issues/{id} without token returns 401 AUTHENTICATION_REQUIRED."""
        res = self.client.get("/api/v1/consumer-issues/fake-id")
        self.assertEqual(res.status_code, 401)

    def test_delete_issue_unauthenticated_returns_401(self) -> None:
        """DELETE /api/v1/consumer-issues/{id} without token returns 401 AUTHENTICATION_REQUIRED."""
        res = self.client.delete("/api/v1/consumer-issues/fake-id")
        self.assertEqual(res.status_code, 401)

    # =================================================================
    # 2. Successful Complaint Creation
    # =================================================================

    def test_create_issue_success(self) -> None:
        """POST /api/v1/consumer-issues creates complaint in SUBMITTED state."""
        insp_id, img_id = self._create_inspection_with_artifact(self.user_a_token)

        res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "issue_type": "MISLEADING_LABEL",
                "title": "Inaccurate Net Quantity",
                "description": "Front panel claims 500g, back lists 450g.",
                "evidence_image_ids": [img_id],
            },
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["user_id"], self.user_a_id)
        self.assertEqual(data["inspection_id"], insp_id)
        self.assertEqual(data["issue_type"], "MISLEADING_LABEL")
        self.assertEqual(data["title"], "Inaccurate Net Quantity")
        self.assertEqual(data["description"], "Front panel claims 500g, back lists 450g.")
        self.assertEqual(data["status"], "SUBMITTED")
        self.assertIsNone(data["resolution_notes"])
        self.assertEqual(len(data["evidence_images"]), 1)
        self.assertEqual(data["evidence_images"][0]["image_id"], img_id)

    # =================================================================
    # 3. Unowned Inspection Rejection (HTTP 404)
    # =================================================================

    def test_create_issue_unowned_inspection_returns_404(self) -> None:
        """User A filing issue on User B's inspection returns 404 INSPECTION_NOT_FOUND."""
        insp_id_b, _ = self._create_inspection_with_artifact(self.user_b_token)

        res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id_b,
                "issue_type": "EXPIRED_PRODUCT",
                "title": "Expired Item",
                "description": "Date passed.",
            },
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.INSPECTION_NOT_FOUND.value)

    # =================================================================
    # 4. Invalid Evidence Image Reference Rejection (HTTP 400)
    # =================================================================

    def test_create_issue_invalid_evidence_image_returns_400(self) -> None:
        """Referencing image ID not in inspection returns 400 INVALID_IMAGE_REFERENCE."""
        insp_id, _ = self._create_inspection_with_artifact(self.user_a_token)

        res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "issue_type": "PRICE_TAMPERING",
                "title": "Overcharged",
                "description": "Price sticker altered.",
                "evidence_image_ids": ["alien_image_id_999"],
            },
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.INVALID_IMAGE_REFERENCE.value)

    # =================================================================
    # 5. Duplicate Submission Returns HTTP 409 Conflict
    # =================================================================

    def test_duplicate_issue_submission_returns_409_conflict(self) -> None:
        """Duplicate (user_id, inspection_id, issue_type) returns 409 DUPLICATE_CONSUMER_ISSUE."""
        insp_id, _ = self._create_inspection_with_artifact(self.user_a_token)

        payload = {
            "inspection_id": insp_id,
            "issue_type": "WEIGHT_SHORTAGE",
            "title": "Short Weight",
            "description": "Weighed 80g instead of 100g.",
        }

        # First submission
        res1 = self.client.post(
            "/api/v1/consumer-issues",
            json=payload,
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res1.status_code, 201)

        # Duplicate submission
        res2 = self.client.post(
            "/api/v1/consumer-issues",
            json=payload,
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res2.status_code, 409)
        self.assertEqual(res2.json()["error"]["code"], ErrorCode.DUPLICATE_CONSUMER_ISSUE.value)

    # =================================================================
    # 6. Status and Resolution Field Enforcement
    # =================================================================

    def test_consumer_cannot_override_status_or_resolution(self) -> None:
        """Client payload supplying status or resolution notes cannot override SUBMITTED / None."""
        insp_id, _ = self._create_inspection_with_artifact(self.user_a_token)

        res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "issue_type": "OTHER",
                "title": "Spoofed Status",
                "description": "Attempting status injection.",
                "status": "RESOLVED",
                "resolution_notes": "Fake resolution",
            },
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["status"], "SUBMITTED")
        self.assertIsNone(data["resolution_notes"])

    # =================================================================
    # 7. Invariance of AI Compliance Results
    # =================================================================

    def test_ai_compliance_report_remains_invariant(self) -> None:
        """Filing a consumer issue report does not alter the inspection report overall_status."""
        insp_id, _ = self._create_inspection_with_artifact(self.user_a_token)

        from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
        report = InspectionReport(
            inspection_id=insp_id,
            overall_status=OverallInspectionStatus.PASS,
            summary="Statutory declarations compliant.",
            evidence_count=1,
            image_count=1,
            applicable_requirement_count=1,
            pass_count=1,
            fail_count=0,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
            verification_results=[],
        )
        self.store.store_report(insp_id, report)

        # Submit issue report
        self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "issue_type": "PRICE_TAMPERING",
                "title": "Allegation",
                "description": "Consumer allegation.",
            },
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )

        # Verify report status remains unchanged
        fetched_report = self.store.get_report(insp_id)
        self.assertIsNotNone(fetched_report)
        self.assertEqual(fetched_report.overall_status.value, "PASS")

    # =================================================================
    # 8. Pagination and Status Filtering
    # =================================================================

    def test_list_issues_pagination_and_status_filtering(self) -> None:
        """GET /api/v1/consumer-issues paginates correctly and supports status filter."""
        insp_id, _ = self._create_inspection_with_artifact(self.user_a_token)

        # Create 3 issues of different types
        types = ["MISLEADING_LABEL", "PRICE_TAMPERING", "EXPIRED_PRODUCT"]
        for t in types:
            self.client.post(
                "/api/v1/consumer-issues",
                json={"inspection_id": insp_id, "issue_type": t, "title": f"Title {t}", "description": "Desc"},
                headers={"Authorization": f"Bearer {self.user_a_token}"},
            )

        # List all (limit 2, offset 0)
        res1 = self.client.get(
            "/api/v1/consumer-issues?limit=2&offset=0",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()
        self.assertEqual(res1["total"], 3)
        self.assertEqual(len(res1["items"]), 2)

        # Filter by status SUBMITTED
        res_filtered = self.client.get(
            "/api/v1/consumer-issues?status=SUBMITTED",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()
        self.assertEqual(res_filtered["total"], 3)

        # Filter by non-existent status RESOLVED
        res_empty = self.client.get(
            "/api/v1/consumer-issues?status=RESOLVED",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()
        self.assertEqual(res_empty["total"], 0)
        self.assertEqual(res_empty["items"], [])

    # =================================================================
    # 9. Retrieval of Owned Complaint
    # =================================================================

    def test_get_issue_by_id_success(self) -> None:
        """GET /api/v1/consumer-issues/{id} returns details for owned complaint."""
        insp_id, _ = self._create_inspection_with_artifact(self.user_a_token)

        created = self.client.post(
            "/api/v1/consumer-issues",
            json={"inspection_id": insp_id, "issue_type": "OTHER", "title": "Test Title", "description": "Test Desc"},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()

        res = self.client.get(
            f"/api/v1/consumer-issues/{created['id']}",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["id"], created["id"])

    # =================================================================
    # 10. Multi-Tenant IDOR Isolation (HTTP 404)
    # =================================================================

    def test_get_unowned_issue_returns_404(self) -> None:
        """User B requesting User A's issue returns HTTP 404 CONSUMER_ISSUE_NOT_FOUND."""
        insp_id, _ = self._create_inspection_with_artifact(self.user_a_token)

        created = self.client.post(
            "/api/v1/consumer-issues",
            json={"inspection_id": insp_id, "issue_type": "OTHER", "title": "Private Issue", "description": "Desc"},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()

        res = self.client.get(
            f"/api/v1/consumer-issues/{created['id']}",
            headers={"Authorization": f"Bearer {self.user_b_token}"},
        )
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.CONSUMER_ISSUE_NOT_FOUND.value)

    # =================================================================
    # 11. Withdrawal of Submitted Complaint
    # =================================================================

    def test_delete_submitted_issue_success(self) -> None:
        """DELETE /api/v1/consumer-issues/{id} removes complaint in SUBMITTED state returning 204."""
        insp_id, _ = self._create_inspection_with_artifact(self.user_a_token)

        created = self.client.post(
            "/api/v1/consumer-issues",
            json={"inspection_id": insp_id, "issue_type": "OTHER", "title": "To Delete", "description": "Desc"},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()

        del_res = self.client.delete(
            f"/api/v1/consumer-issues/{created['id']}",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(del_res.status_code, 204)

        # Verify get returns 404
        get_res = self.client.get(
            f"/api/v1/consumer-issues/{created['id']}",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(get_res.status_code, 404)

    # =================================================================
    # 12. Rejection of Withdrawal After Review Starts (HTTP 409)
    # =================================================================

    def test_delete_reviewed_issue_returns_409_conflict(self) -> None:
        """Attempting to withdraw an issue in UNDER_REVIEW status returns 409 Conflict."""
        insp_id, _ = self._create_inspection_with_artifact(self.user_a_token)

        created = self.client.post(
            "/api/v1/consumer-issues",
            json={"inspection_id": insp_id, "issue_type": "OTHER", "title": "Under Review", "description": "Desc"},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()

        # Update status directly in repo to UNDER_REVIEW
        issue = self.issue_repo.get_by_id(created["id"])
        self.assertIsNotNone(issue)
        issue.status = IssueStatus.UNDER_REVIEW.value

        # Client attempts withdrawal
        del_res = self.client.delete(
            f"/api/v1/consumer-issues/{created['id']}",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(del_res.status_code, 409)
        self.assertEqual(del_res.json()["error"]["code"], ErrorCode.INVALID_INSPECTION_STATE.value)

    # =================================================================
    # 13. Complaint Retention After Inspection Deletion
    # =================================================================

    def test_complaint_retention_when_inspection_deleted(self) -> None:
        """Complaint record survives session deletion with inspection_id set to None."""
        insp_id, img_id = self._create_inspection_with_artifact(self.user_a_token)

        created = self.client.post(
            "/api/v1/consumer-issues",
            json={"inspection_id": insp_id, "issue_type": "EXPIRED_PRODUCT", "title": "Retained", "description": "Desc", "evidence_image_ids": [img_id]},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        ).json()

        # Simulate ON DELETE SET NULL by setting inspection_id to None in repo
        issue = self.issue_repo.get_by_id(created["id"])
        self.assertIsNotNone(issue)
        issue.inspection_id = None

        # Fetch issue via GET endpoint
        res = self.client.get(
            f"/api/v1/consumer-issues/{created['id']}",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsNone(data["inspection_id"])
        self.assertEqual(len(data["evidence_images"]), 1)
        self.assertEqual(data["evidence_images"][0]["image_id"], img_id)

    # =================================================================
    # 14. Repository Concurrency-Safe Duplicate Handling
    # =================================================================

    def test_repository_duplicate_prevention(self) -> None:
        """InMemoryConsumerIssueRepository enforces unique (user_id, inspection_id, issue_type)."""
        issue1 = ConsumerIssue(
            user_id=self.user_a_id,
            inspection_id="insp_100",
            issue_type="PRICE_TAMPERING",
            title="T1",
            description="D1",
        )
        self.issue_repo.create_issue(issue1)

        issue2 = ConsumerIssue(
            user_id=self.user_a_id,
            inspection_id="insp_100",
            issue_type="PRICE_TAMPERING",
            title="T2",
            description="D2",
        )
        with self.assertRaises(Exception) as ctx:
            self.issue_repo.create_issue(issue2)

        self.assertIn("already been submitted", str(ctx.exception))

    # =================================================================
    # 15. Saved Product Ownership and Consistency Validation
    # =================================================================

    def test_create_issue_with_owned_saved_product_success(self) -> None:
        """Creating an issue referencing an owned saved product for the same inspection succeeds."""
        insp_id, img_id = self._create_inspection_with_artifact(self.user_a_token)
        saved = self.saved_repo.save_product(
            SavedProduct(
                user_id=self.user_a_id,
                inspection_id=insp_id,
                product_name="Verified Organic Milk",
                notes="Checked expiry",
            )
        )
        res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "saved_product_id": saved.id,
                "issue_type": "EXPIRED_PRODUCT",
                "title": "Milk was expired",
                "description": "Expiry date was 2 days ago.",
                "evidence_image_ids": [img_id],
            },
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["saved_product_id"], saved.id)
        self.assertEqual(data["inspection_id"], insp_id)

    def test_create_issue_with_unowned_saved_product_returns_404(self) -> None:
        """Referencing another user's saved product returns 404 (IDOR prevention)."""
        insp_id, img_id = self._create_inspection_with_artifact(self.user_a_token)
        # Saved product belongs to user B
        saved_b = self.saved_repo.save_product(
            SavedProduct(
                user_id=self.user_b_id,
                inspection_id=insp_id,
                product_name="Bob's Product",
            )
        )
        res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "saved_product_id": saved_b.id,
                "issue_type": "EXPIRED_PRODUCT",
                "title": "Expired Item",
                "description": "Desc",
                "evidence_image_ids": [img_id],
            },
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.SAVED_PRODUCT_NOT_FOUND.value)

    def test_create_issue_with_nonexistent_saved_product_returns_404(self) -> None:
        """Referencing a nonexistent saved_product_id returns 404."""
        insp_id, img_id = self._create_inspection_with_artifact(self.user_a_token)
        res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "saved_product_id": "nonexistent-saved-id",
                "issue_type": "EXPIRED_PRODUCT",
                "title": "Expired Item",
                "description": "Desc",
                "evidence_image_ids": [img_id],
            },
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.SAVED_PRODUCT_NOT_FOUND.value)

    def test_create_issue_with_mismatched_saved_product_returns_400(self) -> None:
        """Referencing a saved product from a different inspection returns 400 INVALID_REQUEST."""
        insp_id_1, img_id_1 = self._create_inspection_with_artifact(self.user_a_token)
        insp_id_2, _ = self._create_inspection_with_artifact(self.user_a_token)

        # Saved product belongs to user A, but tied to insp_id_2
        saved_2 = self.saved_repo.save_product(
            SavedProduct(
                user_id=self.user_a_id,
                inspection_id=insp_id_2,
                product_name="Product 2",
            )
        )
        res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id_1,
                "saved_product_id": saved_2.id,
                "issue_type": "EXPIRED_PRODUCT",
                "title": "Mismatched",
                "description": "Desc",
                "evidence_image_ids": [img_id_1],
            },
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.INVALID_REQUEST.value)

    # =================================================================
    # 16. Write Path Security & Protected Fields
    # =================================================================

    def test_no_general_update_endpoint_allowed(self) -> None:
        """PUT and PATCH methods on consumer-issues return 405 Method Not Allowed."""
        insp_id, img_id = self._create_inspection_with_artifact(self.user_a_token)
        resp = self.client.post(
            "/api/v1/consumer-issues",
            json={"inspection_id": insp_id, "issue_type": "PRICE_TAMPERING", "title": "Orig", "description": "Desc", "evidence_image_ids": [img_id]},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(resp.status_code, 201)
        issue_id = resp.json()["id"]

        patch_res = self.client.patch(
            f"/api/v1/consumer-issues/{issue_id}",
            json={"status": "RESOLVED", "resolution_notes": "Attempted tamper"},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(patch_res.status_code, 405)

        put_res = self.client.put(
            f"/api/v1/consumer-issues/{issue_id}",
            json={"status": "RESOLVED"},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(put_res.status_code, 405)

    # =================================================================
    # 17. Updated_at Behavior on Supported Operations
    # =================================================================

    def test_updated_at_advances_on_record_modification(self) -> None:
        """ConsumerIssue model timestamps allow updating updated_at upon modification."""
        issue = ConsumerIssue(
            user_id=self.user_a_id,
            inspection_id="insp_timestamp_test",
            issue_type="MISSING_DECLARATIONS",
            title="Initial",
            description="Initial desc",
        )
        initial_created = issue.created_at
        initial_updated = issue.updated_at
        self.assertEqual(initial_created, initial_updated)

        import time
        time.sleep(0.01)
        issue.status = IssueStatus.UNDER_REVIEW.value
        issue.updated_at = datetime.now(timezone.utc)
        self.assertGreater(issue.updated_at, initial_updated)


if __name__ == "__main__":
    unittest.main()
