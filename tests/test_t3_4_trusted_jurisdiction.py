"""Tests for Trusted Consumer Complaint Jurisdiction Resolution (Phase 7.1).

Verifies:
1. Trusted, valid inspection jurisdiction resolves to canonical state and LGD district codes.
2. Untrusted client-supplied jurisdiction codes cannot mark a complaint verified.
3. Missing or ambiguous inspection location leaves the complaint persisted but unverified.
4. Invalid or unknown district codes are left unresolved and unverified.
5. Consumers can still retrieve their own unresolved complaints.
6. Unverified complaints remain strictly excluded from authority case queues.
7. A verified complaint is visible only to an officer whose department, state, and authorized district match.
8. Existing duplicate-reporting and deletion behavior remains intact.
9. Repository failures do not falsely report a complaint as successfully persisted.
"""

from __future__ import annotations

import sys
sys.modules['ujson'] = None  # Bypass Windows App Control policy DLL block for ujson

import unittest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    get_authority_case_repository,
    get_authority_repository,
    get_consumer_issue_repository,
    get_saved_product_repository,
    get_session_store,
    get_user_profile_repository,
    get_verified_location_registry,
)
from backend.app.api.errors import ErrorCode
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth.jwt import create_jwt_token
from backend.app.config import settings
from backend.app.main import app
from backend.app.services.authority.case_repository import InMemoryAuthorityCaseRepository
from backend.app.services.authority.models import (
    AuthorityProfile,
    DepartmentCode,
    JurisdictionLevel,
    JurisdictionScope,
)
from backend.app.services.authority.repository import InMemoryAuthorityRepository
from backend.app.services.consumer_issues.jurisdiction import (
    CANONICAL_LGD_JURISDICTIONS,
    ServerVerifiedLocationRegistry,
    validate_canonical_jurisdiction,
)
from backend.app.services.consumer_issues.models import ConsumerIssue, IssueStatus, IssueType
from backend.app.services.consumer_issues.repository import InMemoryConsumerIssueRepository
from backend.app.services.evidence.models import ImageArtifact
from backend.app.services.saved_products.repository import InMemorySavedProductRepository
from backend.app.services.user_profile.models import UserProfile
from backend.app.services.user_profile.repository import InMemoryUserProfileRepository


class TrustedJurisdictionTestCase(unittest.TestCase):
    """Test suite verifying trusted jurisdiction resolution for consumer complaints."""

    def setUp(self) -> None:
        self.secret = "test-phase7-trusted-jurisdiction-secret-32ch!"
        self.audience = "authenticated"
        self.original_secret = settings.supabase_jwt_secret
        self.original_audience = settings.supabase_jwt_audience

        settings.supabase_jwt_secret = self.secret
        settings.supabase_jwt_audience = self.audience

        self.store = InMemoryInspectionStore()
        self.issue_repo = InMemoryConsumerIssueRepository()
        self.saved_repo = InMemorySavedProductRepository()
        self.user_repo = InMemoryUserProfileRepository()
        self.auth_repo = InMemoryAuthorityRepository()
        self.location_registry = ServerVerifiedLocationRegistry()

        # Connect AuthorityCaseRepository to the same underlying issues repository
        self.case_repo = InMemoryAuthorityCaseRepository()
        self.case_repo._cases = self.issue_repo._items

        app.dependency_overrides[get_session_store] = lambda: self.store
        app.dependency_overrides[get_consumer_issue_repository] = lambda: self.issue_repo
        app.dependency_overrides[get_saved_product_repository] = lambda: self.saved_repo
        app.dependency_overrides[get_user_profile_repository] = lambda: self.user_repo
        app.dependency_overrides[get_authority_repository] = lambda: self.auth_repo
        app.dependency_overrides[get_authority_case_repository] = lambda: self.case_repo
        app.dependency_overrides[get_verified_location_registry] = lambda: self.location_registry

        self.client = TestClient(app)

        # Consumer Alice
        self.consumer_id = "11110000-0000-0000-0000-000000000001"
        self.consumer_token = create_jwt_token(
            {"sub": self.consumer_id, "role": "authenticated"},
            secret=self.secret,
            audience=self.audience,
        )
        self.user_repo.create_profile(UserProfile(user_id=self.consumer_id, app_role="consumer"))

        # District Officer 1: Legal Metrology, MH, PUNE
        self.officer_pune_id = "22220000-0000-0000-0000-000000000002"
        self.officer_pune_token = create_jwt_token(
            {"sub": self.officer_pune_id, "role": "authenticated"},
            secret=self.secret,
            audience=self.audience,
        )
        self.user_repo.create_profile(UserProfile(user_id=self.officer_pune_id, app_role="authority"))
        self.auth_repo.save(
            AuthorityProfile(
                user_id=self.officer_pune_id,
                department=DepartmentCode.LEGAL_METROLOGY.value,
                designation="Inspector Pune",
                jurisdiction=JurisdictionScope(
                    state_code="MH",
                    level=JurisdictionLevel.DISTRICT,
                    authorized_district_codes={"PUNE"},
                ),
                is_active=True,
            )
        )

        # District Officer 2: Legal Metrology, MH, SATARA
        self.officer_satara_id = "33330000-0000-0000-0000-000000000003"
        self.officer_satara_token = create_jwt_token(
            {"sub": self.officer_satara_id, "role": "authenticated"},
            secret=self.secret,
            audience=self.audience,
        )
        self.user_repo.create_profile(UserProfile(user_id=self.officer_satara_id, app_role="authority"))
        self.auth_repo.save(
            AuthorityProfile(
                user_id=self.officer_satara_id,
                department=DepartmentCode.LEGAL_METROLOGY.value,
                designation="Inspector Satara",
                jurisdiction=JurisdictionScope(
                    state_code="MH",
                    level=JurisdictionLevel.DISTRICT,
                    authorized_district_codes={"SATARA"},
                ),
                is_active=True,
            )
        )

        # District Officer 3: Legal Metrology, DL, NEW_DELHI
        self.officer_delhi_id = "44440000-0000-0000-0000-000000000004"
        self.officer_delhi_token = create_jwt_token(
            {"sub": self.officer_delhi_id, "role": "authenticated"},
            secret=self.secret,
            audience=self.audience,
        )
        self.user_repo.create_profile(UserProfile(user_id=self.officer_delhi_id, app_role="authority"))
        self.auth_repo.save(
            AuthorityProfile(
                user_id=self.officer_delhi_id,
                department=DepartmentCode.LEGAL_METROLOGY.value,
                designation="Inspector Delhi",
                jurisdiction=JurisdictionScope(
                    state_code="DL",
                    level=JurisdictionLevel.DISTRICT,
                    authorized_district_codes={"NEW_DELHI"},
                ),
                is_active=True,
            )
        )

    def tearDown(self) -> None:
        settings.supabase_jwt_secret = self.original_secret
        settings.supabase_jwt_audience = self.original_audience
        app.dependency_overrides.clear()
        self.store.clear()
        self.issue_repo.clear()
        self.saved_repo.clear()
        self.user_repo.clear()
        self.auth_repo.clear()
        self.location_registry.clear()

    def _create_inspection(self, user_token: str) -> str:
        """Helper to create an owned inspection container."""
        resp = self.client.post(
            "/api/v1/inspections",
            json={"metadata": {"location_hint": "untrusted client string"}},
            headers={"Authorization": f"Bearer {user_token}"},
        ).json()
        return resp["inspection_id"]

    # =====================================================================
    # 1. Trusted, Valid Inspection Jurisdiction Resolves to Canonical Codes
    # =====================================================================

    def test_trusted_valid_jurisdiction_resolves_to_canonical_codes(self) -> None:
        """Verified location in authoritative registry resolves to canonical state and district."""
        insp_id = self._create_inspection(self.consumer_token)

        # Authoritatively register server-verified location for this inspection
        self.location_registry.register_verified_location(
            inspection_id=insp_id,
            state_code="mh",  # test normalization from lowercase
            district_code="pune",
            verification_source="OFFICIAL_ESTABLISHMENT_REGISTRY",
        )

        res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "issue_type": "WEIGHT_SHORTAGE",
                "title": "Short weight on packaged flour",
                "description": "Bag claims 1kg, actual mass 850g.",
            },
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()

        self.assertTrue(data["jurisdiction_verified"])
        self.assertEqual(data["state_code"], "MH")
        self.assertEqual(data["district_code"], "PUNE")
        self.assertEqual(data["department"], "LEGAL_METROLOGY")

    # =====================================================================
    # 2. Untrusted Client-Supplied Jurisdiction Cannot Mark Complaint Verified
    # =====================================================================

    def test_untrusted_client_supplied_jurisdiction_cannot_verify(self) -> None:
        """Client-supplied state/district codes in request cannot fabricate jurisdiction verification."""
        insp_id = self._create_inspection(self.consumer_token)

        # Client attempts to pass state and district in request without server-verified record
        res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "issue_type": "PRICE_TAMPERING",
                "title": "MRP sticker altered",
                "description": "Higher price printed over original MRP.",
                "state_code": "MH",
                "district_code": "PUNE",
            },
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()

        # Invariant: untrusted client input MUST NOT mark complaint verified or set trusted codes
        self.assertFalse(data["jurisdiction_verified"])
        self.assertIsNone(data["state_code"])
        self.assertIsNone(data["district_code"])

    # =====================================================================
    # 3. Missing or Ambiguous Location Leaves Complaint Persisted but Unverified
    # =====================================================================

    def test_missing_inspection_location_leaves_unverified(self) -> None:
        """Complaint without authoritative location persists safely in unverified state."""
        insp_id = self._create_inspection(self.consumer_token)

        res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "issue_type": "MISLEADING_LABEL",
                "title": "Missing manufacturer address",
                "description": "No name or address of manufacturer on label.",
            },
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()

        self.assertFalse(data["jurisdiction_verified"])
        self.assertIsNone(data["state_code"])
        self.assertIsNone(data["district_code"])
        self.assertEqual(data["status"], "SUBMITTED")

    # =====================================================================
    # 4. Invalid or Unknown District Code Leaves District Unresolved
    # =====================================================================

    def test_invalid_district_code_leaves_unresolved(self) -> None:
        """If server registry contains an unknown/invalid district, it remains unverified."""
        insp_id = self._create_inspection(self.consumer_token)

        self.location_registry.register_verified_location(
            inspection_id=insp_id,
            state_code="MH",
            district_code="NONEXISTENT_DISTRICT_XYZ",
        )

        res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "issue_type": "EXPIRED_PRODUCT",
                "title": "Expired stock",
                "description": "Best before date passed 3 months ago.",
            },
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()

        self.assertFalse(data["jurisdiction_verified"])
        self.assertIsNone(data["district_code"])
        # State was trusted, but district could not be validated
        self.assertEqual(data["state_code"], "MH")

    # =====================================================================
    # 5. Consumers Can Still Retrieve Their Own Unresolved Complaints
    # =====================================================================

    def test_consumer_can_retrieve_unresolved_complaint(self) -> None:
        """Complaints remain accessible in the consumer's history even when unverified."""
        insp_id = self._create_inspection(self.consumer_token)

        create_res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "issue_type": "OTHER",
                "title": "Non-standard package size",
                "description": "Odd quantity not conforming to Second Schedule.",
            },
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        issue_id = create_res.json()["id"]

        # List caller's issues
        list_res = self.client.get(
            "/api/v1/consumer-issues",
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(list_res.status_code, 200)
        items = list_res.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], issue_id)
        self.assertFalse(items[0]["jurisdiction_verified"])

        # Detail fetch
        get_res = self.client.get(
            f"/api/v1/consumer-issues/{issue_id}",
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["id"], issue_id)
        self.assertFalse(get_res.json()["jurisdiction_verified"])

    # =====================================================================
    # 6. Unverified Complaints Remain Excluded from Authority Case Queues
    # =====================================================================

    def test_unverified_complaint_excluded_from_authority_queue(self) -> None:
        """Complaints with jurisdiction_verified=False never appear in authority queues."""
        insp_id = self._create_inspection(self.consumer_token)

        create_res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "issue_type": "WEIGHT_SHORTAGE",
                "title": "Unverified location complaint",
                "description": "Short weight claim.",
            },
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        issue_id = create_res.json()["id"]

        # Authority officer in Pune queries their queue
        res = self.client.get(
            "/api/v1/authority/cases",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["total"], 0)
        self.assertEqual(len(res.json()["items"]), 0)

        # Direct access to unverified case detail is denied
        detail_res = self.client.get(
            f"/api/v1/authority/cases/{issue_id}",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(detail_res.status_code, 403)
        self.assertEqual(detail_res.json()["error"]["code"], ErrorCode.FORBIDDEN.value)

    # =====================================================================
    # 7. Verified Complaint Visible Only to Matching Authority Officer
    # =====================================================================

    def test_verified_complaint_scoped_strictly_to_matching_officer(self) -> None:
        """A verified complaint for MH/PUNE is visible to Pune officer, but hidden from Satara and Delhi."""
        insp_id = self._create_inspection(self.consumer_token)

        self.location_registry.register_verified_location(
            inspection_id=insp_id,
            state_code="MH",
            district_code="PUNE",
        )

        res = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "issue_type": "PRICE_TAMPERING",
                "title": "Dual pricing violation",
                "description": "Sold above printed retail price.",
            },
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        issue_id = res.json()["id"]

        # 1. Pune officer queries queue -> SHOULD see it
        pune_res = self.client.get(
            "/api/v1/authority/cases",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(pune_res.status_code, 200)
        self.assertEqual(pune_res.json()["total"], 1)
        self.assertEqual(pune_res.json()["items"][0]["id"], issue_id)

        # 2. Satara officer queries queue -> MUST NOT see it (district mismatch)
        satara_res = self.client.get(
            "/api/v1/authority/cases",
            headers={"Authorization": f"Bearer {self.officer_satara_token}"},
        )
        self.assertEqual(satara_res.status_code, 200)
        self.assertEqual(satara_res.json()["total"], 0)

        # 3. Delhi officer queries queue -> MUST NOT see it (state mismatch)
        delhi_res = self.client.get(
            "/api/v1/authority/cases",
            headers={"Authorization": f"Bearer {self.officer_delhi_token}"},
        )
        self.assertEqual(delhi_res.status_code, 200)
        self.assertEqual(delhi_res.json()["total"], 0)

    # =====================================================================
    # 8. Duplicate Reporting and Deletion Behavior Remains Intact
    # =====================================================================

    def test_duplicate_reporting_and_deletion_intact(self) -> None:
        """Duplicate submission raises 409, and deletion works in SUBMITTED status."""
        insp_id = self._create_inspection(self.consumer_token)

        payload = {
            "inspection_id": insp_id,
            "issue_type": "WEIGHT_SHORTAGE",
            "title": "Underweight butter",
            "description": "100g labeled, actual 75g.",
        }

        # First submission
        res1 = self.client.post(
            "/api/v1/consumer-issues",
            json=payload,
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(res1.status_code, 201)
        issue_id = res1.json()["id"]

        # Duplicate submission -> 409 Conflict
        res2 = self.client.post(
            "/api/v1/consumer-issues",
            json=payload,
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(res2.status_code, 409)
        self.assertEqual(res2.json()["error"]["code"], ErrorCode.DUPLICATE_CONSUMER_ISSUE.value)

        # Delete / withdraw complaint -> 204 No Content
        del_res = self.client.delete(
            f"/api/v1/consumer-issues/{issue_id}",
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(del_res.status_code, 204)

        # Subsequent fetch -> 404 Not Found
        get_res = self.client.get(
            f"/api/v1/consumer-issues/{issue_id}",
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(get_res.status_code, 404)

    # =====================================================================
    # 9. Repository Failures Do Not Falsely Report Success
    # =====================================================================

    def test_repository_failure_does_not_falsely_report_persisted(self) -> None:
        """When repository encounters an error, it is not falsely reported as 201 Created."""
        insp_id = self._create_inspection(self.consumer_token)

        # Mock repository failure on create_issue
        self.issue_repo.create_issue = MagicMock(side_effect=RuntimeError("Simulated DB connection failure"))

        with self.assertRaises(RuntimeError):
            self.client.post(
                "/api/v1/consumer-issues",
                json={
                    "inspection_id": insp_id,
                    "issue_type": "MISLEADING_LABEL",
                    "title": "Label issue",
                    "description": "Desc.",
                },
                headers={"Authorization": f"Bearer {self.consumer_token}"},
            )

    # =====================================================================
    # 10. End-to-End Consumer Inspection Session to Issue Reporting Contract
    # =====================================================================

    def test_e2e_consumer_inspection_to_issue_contract(self) -> None:
        """Verify contract compatibility from inspection creation to consumer complaint filing and authority queue isolation."""
        # 1. Consumer Alice creates an inspection container via POST /api/v1/inspections
        insp_resp = self.client.post(
            "/api/v1/inspections",
            json={
                "metadata": {
                    "product_name": "Britannia Good Day",
                    "mrp": "30",
                    "net_quantity": "100g",
                }
            },
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(insp_resp.status_code, 201)
        insp_data = insp_resp.json()
        self.assertIn("inspection_id", insp_data)
        self.assertEqual(insp_data["status"], "COLLECTING")
        self.assertEqual(insp_data["owner_id"], self.consumer_id)
        insp_id = insp_data["inspection_id"]

        # 2. Another consumer (Bob) attempts to file a complaint using Alice's inspection_id -> 404 IDOR protected
        bob_id = "55550000-0000-0000-0000-000000000005"
        bob_token = create_jwt_token(
            {"sub": bob_id, "role": "authenticated"},
            secret=self.secret,
            audience=self.audience,
        )
        self.user_repo.create_profile(UserProfile(user_id=bob_id, app_role="consumer"))

        bob_resp = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "issue_type": "PRICE_TAMPERING",
                "title": "Bob spoof attempt",
                "description": "Unauthorized access to Alice's inspection",
            },
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        self.assertEqual(bob_resp.status_code, 404)
        self.assertEqual(bob_resp.json()["error"]["code"], ErrorCode.INSPECTION_NOT_FOUND.value)

        # 3. Legitimate consumer Alice files complaint linking her inspection_id
        issue_resp = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "issue_type": "PRICE_TAMPERING",
                "title": "Dual MRP detected",
                "description": "Sticker pasted on packaging",
            },
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(issue_resp.status_code, 201)
        issue_data = issue_resp.json()
        issue_id = issue_data["id"]
        self.assertEqual(issue_data["user_id"], self.consumer_id)
        self.assertEqual(issue_data["inspection_id"], insp_id)
        self.assertEqual(issue_data["status"], "SUBMITTED")
        self.assertFalse(issue_data["jurisdiction_verified"])
        self.assertIsNone(issue_data["state_code"])
        self.assertIsNone(issue_data["district_code"])

        # 4. Authority Officer (Pune) cannot see this unverified case in the queue
        auth_queue_resp = self.client.get(
            "/api/v1/authority/cases",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(auth_queue_resp.status_code, 200)
        self.assertEqual(auth_queue_resp.json()["total"], 0)

        # 5. Authority Officer cannot directly access unverified case details -> 403 Forbidden
        auth_detail_resp = self.client.get(
            f"/api/v1/authority/cases/{issue_id}",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(auth_detail_resp.status_code, 403)

        # 6. Consumer Alice can view her submitted complaint
        consumer_get_resp = self.client.get(
            f"/api/v1/consumer-issues/{issue_id}",
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(consumer_get_resp.status_code, 200)
        self.assertEqual(consumer_get_resp.json()["id"], issue_id)
        self.assertEqual(consumer_get_resp.json()["status"], "SUBMITTED")

        # 7. Duplicate submission with same inspection_id and issue_type -> 409 Conflict
        dup_resp = self.client.post(
            "/api/v1/consumer-issues",
            json={
                "inspection_id": insp_id,
                "issue_type": "PRICE_TAMPERING",
                "title": "Duplicate attempt",
                "description": "Retrying submission",
            },
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(dup_resp.status_code, 409)
        self.assertEqual(dup_resp.json()["error"]["code"], ErrorCode.DUPLICATE_CONSUMER_ISSUE.value)


if __name__ == "__main__":
    unittest.main()
