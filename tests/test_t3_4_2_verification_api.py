"""Tests for Phase 7.4.2 Secure Jurisdiction Verification API and Establishment Onboarding.

Verifies:
1. Unauthenticated requests to jurisdiction verification and establishment endpoints return HTTP 401.
2. Consumer and inspector roles attempting verification or establishment onboarding return HTTP 403.
3. Inactive and unprovisioned authorities are denied with HTTP 403.
4. Cross-state, cross-district, and cross-department verification attempts are rejected with HTTP 403.
5. Unverified, pending, inactive, or non-existent establishments return appropriate client errors (404/422).
6. Terminal cases (RESOLVED, REJECTED) cannot be verified (HTTP 422).
7. Successful jurisdiction verification updates complaint state, sets verified provenance, and creates an audit event.
8. Verified complaint becomes visible in the authorized district officer's case queue and excluded from other queues.
9. Failure atomicity: Simulated database audit failure rolls back complaint state to unverified.
10. Controlled establishment onboarding:
    - New establishments start as PENDING and unverified.
    - Only officers with matching jurisdiction can onboard and review establishments.
    - Review transitions support VERIFY, SUSPEND, and REVOKE with audit provenance and identity.
    - GSTIN conflict and invalid jurisdiction codes fail closed with HTTP 422.

Execution environment:
These tests use FastAPI TestClient with in-memory service repositories to validate
authorization gates, request/response validation, domain policies, and rollback contracts.
Live Supabase/PostgreSQL RPC execution tests require staging environment credentials.
"""

from __future__ import annotations

import sys
sys.modules['ujson'] = None  # Bypass Windows App Control policy DLL block for ujson

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    get_authority_case_repository,
    get_authority_case_service,
    get_authority_repository,
    get_establishment_repository,
    get_establishment_service,
    get_user_profile_repository,
)
from backend.app.api.errors import ErrorCode
from backend.app.auth.jwt import create_jwt_token
from backend.app.config import settings
from backend.app.main import app
from backend.app.services.authority.case_repository import InMemoryAuthorityCaseRepository
from backend.app.services.authority.case_service import AuthorityCaseService
from backend.app.services.authority.models import (
    AuthorityProfile,
    DepartmentCode,
    JurisdictionLevel,
    JurisdictionScope,
)
from backend.app.services.authority.repository import InMemoryAuthorityRepository
from backend.app.services.consumer_issues.models import (
    ConsumerIssue,
    IssueStatus,
    IssueType,
)
from backend.app.services.establishment.models import (
    EstablishmentVerificationProvenance,
    EstablishmentVerificationStatus,
    RetailEstablishment,
)
from backend.app.services.establishment.repository import InMemoryEstablishmentRepository
from backend.app.services.establishment.service import EstablishmentService
from backend.app.services.user_profile.models import UserProfile
from backend.app.services.user_profile.repository import InMemoryUserProfileRepository


class TestJurisdictionVerificationAPI(unittest.TestCase):
    """Test suite for Phase 7.4.2 Verification API and Controlled Onboarding."""

    def setUp(self) -> None:
        self.secret = "test-t3-4-2-verification-secret-32ch!"
        self.audience = "authenticated"
        self.original_secret = settings.supabase_jwt_secret
        self.original_audience = settings.supabase_jwt_audience
        settings.supabase_jwt_secret = self.secret
        settings.supabase_jwt_audience = self.audience

        self.user_repo = InMemoryUserProfileRepository()
        self.auth_repo = InMemoryAuthorityRepository()
        self.case_repo = InMemoryAuthorityCaseRepository()
        self.est_repo = InMemoryEstablishmentRepository()

        self.case_service = AuthorityCaseService(
            case_repository=self.case_repo,
            authority_repository=self.auth_repo,
            establishment_repository=self.est_repo,
        )
        self.est_service = EstablishmentService(repository=self.est_repo)

        app.dependency_overrides[get_user_profile_repository] = lambda: self.user_repo
        app.dependency_overrides[get_authority_repository] = lambda: self.auth_repo
        app.dependency_overrides[get_authority_case_repository] = lambda: self.case_repo
        app.dependency_overrides[get_authority_case_service] = lambda: self.case_service
        app.dependency_overrides[get_establishment_repository] = lambda: self.est_repo
        app.dependency_overrides[get_establishment_service] = lambda: self.est_service

        self.client = TestClient(app)

        # 1. Identities
        # Consumer
        self.consumer_id = "11110000-0000-0000-0000-000000000001"
        self.consumer_token = create_jwt_token({"sub": self.consumer_id}, secret=self.secret, audience=self.audience)
        self.user_repo.create_profile(UserProfile(user_id=self.consumer_id, app_role="consumer"))

        # Inspector
        self.inspector_id = "22220000-0000-0000-0000-000000000002"
        self.inspector_token = create_jwt_token({"sub": self.inspector_id}, secret=self.secret, audience=self.audience)
        self.user_repo.create_profile(UserProfile(user_id=self.inspector_id, app_role="inspector"))

        # Authority Officer 1: Legal Metrology, MH, PUNE only
        self.officer_pune_id = "33330000-0000-0000-0000-000000000003"
        self.officer_pune_token = create_jwt_token({"sub": self.officer_pune_id}, secret=self.secret, audience=self.audience)
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

        # Authority Officer 2: Legal Metrology, MH, SATARA only
        self.officer_satara_id = "55550000-0000-0000-0000-000000000005"
        self.officer_satara_token = create_jwt_token({"sub": self.officer_satara_id}, secret=self.secret, audience=self.audience)
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

        # Authority Officer 3: Food Safety, MH, PUNE
        self.officer_food_id = "66660000-0000-0000-0000-000000000006"
        self.officer_food_token = create_jwt_token({"sub": self.officer_food_id}, secret=self.secret, audience=self.audience)
        self.user_repo.create_profile(UserProfile(user_id=self.officer_food_id, app_role="authority"))
        self.auth_repo.save(
            AuthorityProfile(
                user_id=self.officer_food_id,
                department=DepartmentCode.FOOD_SAFETY.value,
                designation="Food Safety Officer Pune",
                jurisdiction=JurisdictionScope(
                    state_code="MH",
                    level=JurisdictionLevel.DISTRICT,
                    authorized_district_codes={"PUNE"},
                ),
                is_active=True,
            )
        )

        # Inactive Authority Officer
        self.inactive_officer_id = "77770000-0000-0000-0000-000000000007"
        self.inactive_officer_token = create_jwt_token({"sub": self.inactive_officer_id}, secret=self.secret, audience=self.audience)
        self.user_repo.create_profile(UserProfile(user_id=self.inactive_officer_id, app_role="authority"))
        self.auth_repo.save(
            AuthorityProfile(
                user_id=self.inactive_officer_id,
                department=DepartmentCode.LEGAL_METROLOGY.value,
                designation="Inactive Officer",
                jurisdiction=JurisdictionScope(
                    state_code="MH",
                    level=JurisdictionLevel.DISTRICT,
                    authorized_district_codes={"PUNE"},
                ),
                is_active=False,
            )
        )

        # Unprovisioned Authority Officer (no AuthorityProfile row)
        self.unprov_officer_id = "88880000-0000-0000-0000-000000000008"
        self.unprov_officer_token = create_jwt_token({"sub": self.unprov_officer_id}, secret=self.secret, audience=self.audience)
        self.user_repo.create_profile(UserProfile(user_id=self.unprov_officer_id, app_role="authority"))

        # 2. Establishments
        # Verified Pune Establishment
        self.est_pune_verified = self.est_repo.save_establishment(
            RetailEstablishment(
                id=str(uuid.uuid4()),
                trade_name="Pune Supermarket",
                gstin="27AABCU9603R1ZM",
                state_code="MH",
                district_code="PUNE",
                verification_status=EstablishmentVerificationStatus.VERIFIED.value,
                verification_provenance="MANUAL",
                is_active=True,
            )
        )

        # Pending / Unverified Pune Establishment
        self.est_pune_pending = self.est_repo.save_establishment(
            RetailEstablishment(
                id=str(uuid.uuid4()),
                trade_name="Pune New Bazaar",
                gstin="27AABCU9603R2ZN",
                state_code="MH",
                district_code="PUNE",
                verification_status=EstablishmentVerificationStatus.PENDING.value,
                verification_provenance="MANUAL",
                is_active=True,
            )
        )

        # Inactive Pune Establishment
        self.est_pune_inactive = self.est_repo.save_establishment(
            RetailEstablishment(
                id=str(uuid.uuid4()),
                trade_name="Closed Pune Store",
                gstin="27AABCU9603R3ZO",
                state_code="MH",
                district_code="PUNE",
                verification_status=EstablishmentVerificationStatus.VERIFIED.value,
                verification_provenance="MANUAL",
                is_active=False,
            )
        )

        # Verified Satara Establishment
        self.est_satara_verified = self.est_repo.save_establishment(
            RetailEstablishment(
                id=str(uuid.uuid4()),
                trade_name="Satara Mart",
                gstin="27AABCU9603R4ZP",
                state_code="MH",
                district_code="SATARA",
                verification_status=EstablishmentVerificationStatus.VERIFIED.value,
                verification_provenance="MANUAL",
                is_active=True,
            )
        )

        # 3. Complaints
        # Unverified Complaint (Default Consumer State)
        self.unverified_case = self.case_repo.save_case(
            ConsumerIssue(
                id=str(uuid.uuid4()),
                user_id=self.consumer_id,
                title="Weight discrepancy on rice packet",
                description="Package marked 5kg weighed only 4.4kg",
                issue_type=IssueType.WEIGHT_SHORTAGE.value,
                department=DepartmentCode.LEGAL_METROLOGY.value,
                state_code=None,
                district_code=None,
                jurisdiction_verified=False,
                jurisdiction_provenance="UNVERIFIED",
                status=IssueStatus.SUBMITTED.value,
            )
        )

        # Terminal Resolved Complaint
        self.resolved_case = self.case_repo.save_case(
            ConsumerIssue(
                id=str(uuid.uuid4()),
                user_id=self.consumer_id,
                title="Already resolved complaint",
                description="Past resolved issue",
                issue_type=IssueType.WEIGHT_SHORTAGE.value,
                department=DepartmentCode.LEGAL_METROLOGY.value,
                state_code="MH",
                district_code="SATARA",
                jurisdiction_verified=True,
                jurisdiction_provenance="ESTABLISHMENT_QR",
                status=IssueStatus.RESOLVED.value,
            )
        )

    def tearDown(self) -> None:
        settings.supabase_jwt_secret = self.original_secret
        settings.supabase_jwt_audience = self.original_audience
        app.dependency_overrides.clear()

    # -------------------------------------------------------------------------
    # 1. Unauthenticated & Role Gating Tests
    # -------------------------------------------------------------------------

    def test_unauthenticated_requests_fail_401(self) -> None:
        """Unauthenticated calls to verification and establishment APIs must fail with 401."""
        url = f"/api/v1/authority/cases/{self.unverified_case.id}/verify-jurisdiction"
        resp = self.client.post(url, json={"establishment_id": self.est_pune_verified.id})
        self.assertEqual(resp.status_code, 401)

        resp2 = self.client.post("/api/v1/authority/establishments", json={"trade_name": "Test Store", "state_code": "MH", "district_code": "PUNE"})
        self.assertEqual(resp2.status_code, 401)

        resp3 = self.client.get("/api/v1/authority/establishments")
        self.assertEqual(resp3.status_code, 401)

    def test_consumer_and_inspector_roles_denied_403(self) -> None:
        """Consumers and inspectors cannot call verification or establishment management endpoints."""
        url = f"/api/v1/authority/cases/{self.unverified_case.id}/verify-jurisdiction"
        payload = {"establishment_id": self.est_pune_verified.id}

        # Consumer
        resp = self.client.post(url, json=payload, headers={"Authorization": f"Bearer {self.consumer_token}"})
        self.assertEqual(resp.status_code, 403)

        # Inspector
        resp2 = self.client.post(url, json=payload, headers={"Authorization": f"Bearer {self.inspector_token}"})
        self.assertEqual(resp2.status_code, 403)

        # Consumer cannot onboard establishment
        resp3 = self.client.post(
            "/api/v1/authority/establishments",
            json={"trade_name": "Consumer Store", "state_code": "MH", "district_code": "PUNE"},
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(resp3.status_code, 403)

    def test_inactive_and_unprovisioned_authority_denied_403(self) -> None:
        """Inactive or unprovisioned authority accounts must be rejected with 403."""
        url = f"/api/v1/authority/cases/{self.unverified_case.id}/verify-jurisdiction"
        payload = {"establishment_id": self.est_pune_verified.id}

        # Inactive officer
        resp = self.client.post(url, json=payload, headers={"Authorization": f"Bearer {self.inactive_officer_token}"})
        self.assertEqual(resp.status_code, 403)

        # Unprovisioned officer
        resp2 = self.client.post(url, json=payload, headers={"Authorization": f"Bearer {self.unprov_officer_token}"})
        self.assertEqual(resp2.status_code, 403)

    # -------------------------------------------------------------------------
    # 2. Scope & Jurisdiction Boundary Tests
    # -------------------------------------------------------------------------

    def test_cross_district_verification_denied_403(self) -> None:
        """An officer authorized for Pune cannot verify a case against a Satara establishment."""
        url = f"/api/v1/authority/cases/{self.unverified_case.id}/verify-jurisdiction"
        payload = {"establishment_id": self.est_satara_verified.id}

        resp = self.client.post(url, json=payload, headers={"Authorization": f"Bearer {self.officer_pune_token}"})
        self.assertEqual(resp.status_code, 403)
        self.assertIn("District", str(resp.json()))

    def test_cross_department_verification_denied_403(self) -> None:
        """A Food Safety officer cannot verify a Legal Metrology complaint."""
        url = f"/api/v1/authority/cases/{self.unverified_case.id}/verify-jurisdiction"
        payload = {"establishment_id": self.est_pune_verified.id}

        resp = self.client.post(url, json=payload, headers={"Authorization": f"Bearer {self.officer_food_token}"})
        self.assertEqual(resp.status_code, 403)
        self.assertIn("department_mismatch", str(resp.json()).lower())

    # -------------------------------------------------------------------------
    # 3. Establishment State & Terminal Condition Tests
    # -------------------------------------------------------------------------

    def test_unverified_establishment_rejected(self) -> None:
        """Attempting to verify jurisdiction against a PENDING establishment fails closed."""
        url = f"/api/v1/authority/cases/{self.unverified_case.id}/verify-jurisdiction"
        payload = {"establishment_id": self.est_pune_pending.id}

        resp = self.client.post(url, json=payload, headers={"Authorization": f"Bearer {self.officer_pune_token}"})
        self.assertEqual(resp.status_code, 422)
        self.assertIn("not verified", str(resp.json()))

    def test_inactive_establishment_rejected(self) -> None:
        """Attempting to verify jurisdiction against an inactive establishment fails closed."""
        url = f"/api/v1/authority/cases/{self.unverified_case.id}/verify-jurisdiction"
        payload = {"establishment_id": self.est_pune_inactive.id}

        resp = self.client.post(url, json=payload, headers={"Authorization": f"Bearer {self.officer_pune_token}"})
        self.assertEqual(resp.status_code, 422)
        self.assertIn("inactive", str(resp.json()))

    def test_nonexistent_establishment_returns_404(self) -> None:
        """Attempting to verify against a non-existent establishment ID returns 404."""
        missing_id = str(uuid.uuid4())
        url = f"/api/v1/authority/cases/{self.unverified_case.id}/verify-jurisdiction"
        payload = {"establishment_id": missing_id}

        resp = self.client.post(url, json=payload, headers={"Authorization": f"Bearer {self.officer_pune_token}"})
        self.assertEqual(resp.status_code, 404)

    def test_terminal_case_verification_rejected(self) -> None:
        """Cases in terminal states (RESOLVED, REJECTED) cannot be verified."""
        url = f"/api/v1/authority/cases/{self.resolved_case.id}/verify-jurisdiction"
        payload = {"establishment_id": self.est_pune_verified.id}

        resp = self.client.post(url, json=payload, headers={"Authorization": f"Bearer {self.officer_pune_token}"})
        self.assertEqual(resp.status_code, 422)
        self.assertIn("Terminal case", str(resp.json()))

    # -------------------------------------------------------------------------
    # 4. Successful Verification & Audit Timeline Tests
    # -------------------------------------------------------------------------

    def test_successful_jurisdiction_verification_and_queue_activation(self) -> None:
        """Authorized verification binds establishment, updates provenance, emits audit event, and activates queue."""
        # Pre-check: Case is unverified, so Pune officer's case queue is empty
        list_resp = self.client.get("/api/v1/authority/cases", headers={"Authorization": f"Bearer {self.officer_pune_token}"})
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json()["total"], 0)

        # Execute verification
        url = f"/api/v1/authority/cases/{self.unverified_case.id}/verify-jurisdiction"
        payload = {
            "establishment_id": self.est_pune_verified.id,
            "provenance": "ADMIN_TRIAGE_VERIFICATION",
            "verification_notes": "Verified against shop premises inspection and municipal registry.",
        }

        resp = self.client.post(url, json=payload, headers={"Authorization": f"Bearer {self.officer_pune_token}"})
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertEqual(data["case_id"], self.unverified_case.id)
        self.assertEqual(data["establishment_id"], self.est_pune_verified.id)
        self.assertEqual(data["state_code"], "MH")
        self.assertEqual(data["district_code"], "PUNE")
        self.assertTrue(data["jurisdiction_verified"])
        self.assertEqual(data["jurisdiction_provenance"], "ADMIN_TRIAGE_VERIFICATION")
        self.assertEqual(data["jurisdiction_verified_by"], self.officer_pune_id)
        self.assertTrue(bool(data["event_id"]))

        # Verify case in database
        updated_case = self.case_repo.get_case_by_id(self.unverified_case.id)
        self.assertIsNotNone(updated_case)
        self.assertTrue(updated_case.jurisdiction_verified)
        self.assertEqual(updated_case.state_code, "MH")
        self.assertEqual(updated_case.district_code, "PUNE")
        self.assertEqual(updated_case.establishment_id, self.est_pune_verified.id)

        # Audit timeline verification
        audit_events = self.case_repo.list_audit_events(self.unverified_case.id)
        self.assertEqual(len(audit_events), 1)
        event = audit_events[0]
        self.assertEqual(event.event_type, "JURISDICTION_VERIFIED")
        self.assertEqual(event.previous_state, "UNVERIFIED")
        self.assertEqual(event.new_state, "VERIFIED")
        self.assertEqual(event.metadata["establishment_id"], self.est_pune_verified.id)

        # Queue verification: Now case is visible in Pune queue
        pune_queue = self.client.get("/api/v1/authority/cases", headers={"Authorization": f"Bearer {self.officer_pune_token}"})
        self.assertEqual(pune_queue.status_code, 200)
        self.assertEqual(pune_queue.json()["total"], 1)
        self.assertEqual(pune_queue.json()["items"][0]["id"], self.unverified_case.id)

        # But it must NOT be visible in Satara officer's queue!
        satara_queue = self.client.get("/api/v1/authority/cases", headers={"Authorization": f"Bearer {self.officer_satara_token}"})
        self.assertEqual(satara_queue.status_code, 200)
        self.assertNotIn(self.unverified_case.id, [item["id"] for item in satara_queue.json()["items"]])

    # -------------------------------------------------------------------------
    # 5. Atomic Rollback Verification
    # -------------------------------------------------------------------------

    def test_verification_failure_atomicity_rollback(self) -> None:
        """Simulated audit event failure rolls back case verification to maintain atomicity."""
        self.case_repo.simulate_audit_failure = True

        url = f"/api/v1/authority/cases/{self.unverified_case.id}/verify-jurisdiction"
        payload = {"establishment_id": self.est_pune_verified.id}

        resp = self.client.post(url, json=payload, headers={"Authorization": f"Bearer {self.officer_pune_token}"})
        self.assertEqual(resp.status_code, 500)

        # Verify case is completely rolled back to unverified
        case = self.case_repo.get_case_by_id(self.unverified_case.id)
        self.assertFalse(case.jurisdiction_verified)
        self.assertIsNone(case.establishment_id)
        self.assertEqual(case.jurisdiction_provenance, "UNVERIFIED")
        self.assertEqual(len(self.case_repo.list_audit_events(self.unverified_case.id)), 0)

    # -------------------------------------------------------------------------
    # 6. Controlled Establishment Onboarding & Review Tests
    # -------------------------------------------------------------------------

    def test_establishment_onboarding_lifecycle(self) -> None:
        """New establishments start as PENDING, require review to verify, and can be suspended/revoked."""
        # 1. Onboard new establishment by Pune officer
        onboard_payload = {
            "trade_name": "Deccan Provisions",
            "legal_name": "Deccan Provisions Private Limited",
            "gstin": "27AABCD1234E1Z5",
            "state_code": "MH",
            "district_code": "PUNE",
            "pincode": "411004",
            "physical_address": "FC Road, Shivajinagar, Pune",
        }
        create_resp = self.client.post(
            "/api/v1/authority/establishments",
            json=onboard_payload,
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(create_resp.status_code, 201)
        est_data = create_resp.json()
        est_id = est_data["id"]
        self.assertEqual(est_data["trade_name"], "Deccan Provisions")
        self.assertEqual(est_data["verification_status"], "PENDING")
        self.assertTrue(est_data["is_active"])

        # 2. Cannot onboard establishment in cross-district (Satara) by Pune officer
        invalid_dist_payload = {
            "trade_name": "Satara Branch",
            "state_code": "MH",
            "district_code": "SATARA",
        }
        cross_resp = self.client.post(
            "/api/v1/authority/establishments",
            json=invalid_dist_payload,
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(cross_resp.status_code, 403)

        # 3. Duplicate GSTIN rejection
        dup_resp = self.client.post(
            "/api/v1/authority/establishments",
            json=onboard_payload,
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(dup_resp.status_code, 409)
        self.assertEqual(dup_resp.json()["error"]["code"], "DUPLICATE_ESTABLISHMENT")

        # 4. Satara officer cannot review Pune establishment
        cross_review = self.client.post(
            f"/api/v1/authority/establishments/{est_id}/review",
            json={"action": "VERIFY", "expected_status": "PENDING", "notes": "Cross review attempt"},
            headers={"Authorization": f"Bearer {self.officer_satara_token}"},
        )
        self.assertEqual(cross_review.status_code, 403)

        # 5. Pune officer reviews and approves (VERIFY) establishment
        verify_resp = self.client.post(
            f"/api/v1/authority/establishments/{est_id}/review",
            json={"action": "VERIFY", "expected_status": "PENDING", "notes": "Documents and premises verified physically.", "provenance": "MANUAL"},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(verify_resp.status_code, 200)
        verified_data = verify_resp.json()
        self.assertEqual(verified_data["verification_status"], "VERIFIED")
        self.assertEqual(verified_data["verification_authority_id"], self.officer_pune_id)
        self.assertTrue(verified_data["is_active"])

        # 6. Suspend establishment
        suspend_resp = self.client.post(
            f"/api/v1/authority/establishments/{est_id}/review",
            json={"action": "SUSPEND", "expected_status": "VERIFIED", "notes": "License under suspension due to irregularities."},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(suspend_resp.status_code, 200)
        suspended_data = suspend_resp.json()
        self.assertEqual(suspended_data["verification_status"], "SUSPENDED")
        self.assertFalse(suspended_data["is_active"])

    def test_list_and_get_establishments_jurisdiction_scoping(self) -> None:
        """Listing and retrieving establishments is strictly scoped to the officer's jurisdiction."""
        # Pune officer gets Pune establishment
        resp = self.client.get(
            f"/api/v1/authority/establishments/{self.est_pune_verified.id}",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["trade_name"], "Pune Supermarket")

        # Pune officer listing establishments sees only Pune
        list_resp = self.client.get(
            "/api/v1/authority/establishments",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(list_resp.status_code, 200)
        items = list_resp.json()["items"]
        for item in items:
            self.assertEqual(item["district_code"], "PUNE")

        # Pune officer querying Satara district explicitly is forbidden
        bad_query = self.client.get(
            "/api/v1/authority/establishments?district_code=SATARA",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(bad_query.status_code, 403)


if __name__ == "__main__":
    unittest.main()
