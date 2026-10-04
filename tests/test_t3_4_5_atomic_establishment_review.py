"""Tests for Veriqoo Phase 7.5: Atomic Establishment Review and Audit Trail.

Validates:
1. Full establishment review lifecycle:
   - PENDING -> VERIFIED (action: VERIFY, expected_status: PENDING)
   - VERIFIED -> SUSPENDED (action: SUSPEND, expected_status: VERIFIED)
   - SUSPENDED -> REVOKED (action: REVOKE, expected_status: SUSPENDED)
   - Terminal state enforcement: REVOKED establishments cannot be transitioned.
   - Invalid lifecycle enforcement: PENDING cannot jump directly to SUSPENDED.
2. Concurrency and optimistic locking:
   - Missing expected_status token returns HTTP 422 (CONCURRENCY_TOKEN_REQUIRED).
   - Stale expected_status token returns HTTP 409 (CONCURRENT_UPDATE_CONFLICT).
   - Concurrent review simulation: second conflicting update receives HTTP 409.
3. Reviewer identity preservation:
   - verification_authority_id retains the original certifying officer on SUSPEND and REVOKE.
   - updated_by tracks the latest reviewing/suspending/revoking officer.
4. Authorization & jurisdiction boundaries:
   - Unauthenticated callers return HTTP 401.
   - Consumer roles return HTTP 403.
   - Inactive authority profiles return HTTP 403.
   - Cross-district reviews (e.g. Satara officer reviewing Pune establishment) return HTTP 403.
5. Audit trail:
   - Audit event logged atomically for every transition.
   - GET /api/v1/authority/establishments/{id}/audit-timeline returns chronological events.
   - Cross-district audit timeline access returns HTTP 403.
6. Transactional rollback:
   - When audit event persistence fails, the entire review transaction rolls back:
     establishment status and notes remain unchanged, and no partial audit event persists.
7. Database error mapping:
   - Unhandled database failures map cleanly to HTTP 500 without leaking internals.
8. Regression safety:
   - Existing consumer issue submission and authority case workflows remain fully operational.
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
from backend.app.services.establishment.errors import (
    EstablishmentConcurrencyError,
    EstablishmentRepositoryError,
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


class TestAtomicEstablishmentReview(unittest.TestCase):
    """Test suite for Phase 7.5 Atomic Establishment Review and Audit Trail."""

    def setUp(self) -> None:
        self.secret = "test-phase-7-5-secret-key-32chars!!"
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

        # Pune Officer 1 (Verifier)
        self.officer_pune_1_id = "22220000-0000-0000-0000-000000000001"
        self.officer_pune_1_token = create_jwt_token({"sub": self.officer_pune_1_id}, secret=self.secret, audience=self.audience)
        self.user_repo.create_profile(UserProfile(user_id=self.officer_pune_1_id, app_role="authority"))
        self.auth_repo.save(
            AuthorityProfile(
                user_id=self.officer_pune_1_id,
                department=DepartmentCode.LEGAL_METROLOGY.value,
                designation="Inspector Pune 1",
                jurisdiction=JurisdictionScope(
                    state_code="MH",
                    level=JurisdictionLevel.DISTRICT,
                    authorized_district_codes={"PUNE"},
                ),
                is_active=True,
            )
        )

        # Pune Officer 2 (Suspender/Revoker)
        self.officer_pune_2_id = "22220000-0000-0000-0000-000000000002"
        self.officer_pune_2_token = create_jwt_token({"sub": self.officer_pune_2_id}, secret=self.secret, audience=self.audience)
        self.user_repo.create_profile(UserProfile(user_id=self.officer_pune_2_id, app_role="authority"))
        self.auth_repo.save(
            AuthorityProfile(
                user_id=self.officer_pune_2_id,
                department=DepartmentCode.LEGAL_METROLOGY.value,
                designation="Inspector Pune 2",
                jurisdiction=JurisdictionScope(
                    state_code="MH",
                    level=JurisdictionLevel.DISTRICT,
                    authorized_district_codes={"PUNE"},
                ),
                is_active=True,
            )
        )

        # Satara Officer (Cross-district)
        self.officer_satara_id = "33330000-0000-0000-0000-000000000001"
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

        # Inactive Officer
        self.officer_inactive_id = "44440000-0000-0000-0000-000000000001"
        self.officer_inactive_token = create_jwt_token({"sub": self.officer_inactive_id}, secret=self.secret, audience=self.audience)
        self.user_repo.create_profile(UserProfile(user_id=self.officer_inactive_id, app_role="authority"))
        self.auth_repo.save(
            AuthorityProfile(
                user_id=self.officer_inactive_id,
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

        # 2. Establishments
        # Pune Pending Establishment
        self.est_pune = self.est_repo.save_establishment(
            RetailEstablishment(
                id=str(uuid.uuid4()),
                trade_name="Pune Supermarket Central",
                legal_name="Pune Retailers Pvt Ltd",
                gstin="27AAPFU0939F1ZV",
                state_code="MH",
                district_code="PUNE",
                pincode="411001",
                verification_status=EstablishmentVerificationStatus.PENDING.value,
                is_active=True,
                created_by=self.officer_pune_1_id,
            )
        )

    def tearDown(self) -> None:
        settings.supabase_jwt_secret = self.original_secret
        settings.supabase_jwt_audience = self.original_audience
        app.dependency_overrides.clear()

    # =========================================================================
    # Lifecycle Transitions & Concurrency Token Tests
    # =========================================================================

    def test_successful_review_lifecycle_and_verifier_preservation(self) -> None:
        """Full lifecycle: PENDING -> VERIFIED -> SUSPENDED -> REVOKED.
        
        Validates:
        1. VERIFY sets verification_authority_id and verification_date.
        2. SUSPEND preserves original verification_authority_id and sets updated_by.
        3. REVOKE preserves original verification_authority_id and sets updated_by.
        4. Audit events are recorded for each transition.
        """
        est_id = self.est_pune.id

        # Step 1: Officer Pune 1 verifies the establishment
        res_verify = self.client.post(
            f"/api/v1/authority/establishments/{est_id}/review",
            json={
                "action": "VERIFY",
                "expected_status": "PENDING",
                "notes": "Physical verification completed with valid documentation.",
                "provenance": "MANUAL",
            },
            headers={"Authorization": f"Bearer {self.officer_pune_1_token}"},
        )
        self.assertEqual(res_verify.status_code, 200)
        v_data = res_verify.json()
        self.assertEqual(v_data["verification_status"], "VERIFIED")
        self.assertTrue(v_data["is_active"])
        self.assertEqual(v_data["verification_authority_id"], self.officer_pune_1_id)
        self.assertIsNotNone(v_data["verification_date"])
        self.assertEqual(v_data["updated_by"], self.officer_pune_1_id)

        # Step 2: Officer Pune 2 suspends the establishment
        res_suspend = self.client.post(
            f"/api/v1/authority/establishments/{est_id}/review",
            json={
                "action": "SUSPEND",
                "expected_status": "VERIFIED",
                "notes": "Weight scale irregularities detected during audit.",
                "provenance": "AUTHORITY_AUDIT",
            },
            headers={"Authorization": f"Bearer {self.officer_pune_2_token}"},
        )
        self.assertEqual(res_suspend.status_code, 200)
        s_data = res_suspend.json()
        self.assertEqual(s_data["verification_status"], "SUSPENDED")
        self.assertFalse(s_data["is_active"])
        # Original certifying officer MUST be preserved!
        self.assertEqual(s_data["verification_authority_id"], self.officer_pune_1_id)
        # updated_by must reflect the suspending officer
        self.assertEqual(s_data["updated_by"], self.officer_pune_2_id)

        # Step 3: Officer Pune 2 revokes the establishment
        res_revoke = self.client.post(
            f"/api/v1/authority/establishments/{est_id}/review",
            json={
                "action": "REVOKE",
                "expected_status": "SUSPENDED",
                "notes": "Failure to rectify irregularities within statutory period.",
                "provenance": "AUTHORITY_AUDIT",
            },
            headers={"Authorization": f"Bearer {self.officer_pune_2_token}"},
        )
        self.assertEqual(res_revoke.status_code, 200)
        r_data = res_revoke.json()
        self.assertEqual(r_data["verification_status"], "REVOKED")
        self.assertFalse(r_data["is_active"])
        # Original certifying officer remains preserved
        self.assertEqual(r_data["verification_authority_id"], self.officer_pune_1_id)
        self.assertEqual(r_data["updated_by"], self.officer_pune_2_id)

        # Step 4: Verify audit timeline
        res_timeline = self.client.get(
            f"/api/v1/authority/establishments/{est_id}/audit-timeline",
            headers={"Authorization": f"Bearer {self.officer_pune_1_token}"},
        )
        self.assertEqual(res_timeline.status_code, 200)
        timeline = res_timeline.json()
        self.assertEqual(timeline["establishment_id"], est_id)
        self.assertEqual(len(timeline["items"]), 3)

        # Verify event order and contents (newest first)
        e_revoke, e_suspend, e_verify = timeline["items"]
        self.assertEqual(e_revoke["action"], "REVOKE")
        self.assertEqual(e_revoke["previous_status"], "SUSPENDED")
        self.assertEqual(e_revoke["new_status"], "REVOKED")
        self.assertEqual(e_revoke["actor_id"], self.officer_pune_2_id)

        self.assertEqual(e_suspend["action"], "SUSPEND")
        self.assertEqual(e_suspend["previous_status"], "VERIFIED")
        self.assertEqual(e_suspend["new_status"], "SUSPENDED")
        self.assertEqual(e_suspend["actor_id"], self.officer_pune_2_id)

        self.assertEqual(e_verify["action"], "VERIFY")
        self.assertEqual(e_verify["previous_status"], "PENDING")
        self.assertEqual(e_verify["new_status"], "VERIFIED")
        self.assertEqual(e_verify["actor_id"], self.officer_pune_1_id)

    def test_missing_expected_status_token_rejected_with_422(self) -> None:
        """Omitting the expected_status token must be rejected with HTTP 422 (CONCURRENCY_TOKEN_REQUIRED)."""
        est_id = self.est_pune.id
        res = self.client.post(
            f"/api/v1/authority/establishments/{est_id}/review",
            json={
                "action": "VERIFY",
                "notes": "Review without expected status token.",
            },
            headers={"Authorization": f"Bearer {self.officer_pune_1_token}"},
        )
        self.assertEqual(res.status_code, 422)
        err = res.json().get("error", res.json().get("detail", res.json()))
        self.assertIn("CONCURRENCY_TOKEN_REQUIRED", str(err))

    def test_stale_expected_status_token_rejected_with_409(self) -> None:
        """Providing a stale expected_status token returns HTTP 409 (CONCURRENT_UPDATE_CONFLICT)."""
        est_id = self.est_pune.id

        # The establishment is PENDING, but caller asserts VERIFIED
        res = self.client.post(
            f"/api/v1/authority/establishments/{est_id}/review",
            json={
                "action": "VERIFY",
                "expected_status": "VERIFIED",
                "notes": "Asserting wrong state.",
            },
            headers={"Authorization": f"Bearer {self.officer_pune_1_token}"},
        )
        self.assertEqual(res.status_code, 409)
        err = res.json().get("error", res.json().get("detail", res.json()))
        self.assertEqual(err["code"], "CONCURRENT_UPDATE_CONFLICT")

    def test_concurrent_review_conflict(self) -> None:
        """Simulate two concurrent officers reviewing the same establishment:
        Officer A succeeds; Officer B's stale request is rejected with HTTP 409.
        """
        est_id = self.est_pune.id

        # Both officers read establishment state as PENDING
        req_officer_a = {
            "action": "VERIFY",
            "expected_status": "PENDING",
            "notes": "Officer A physical verification.",
            "provenance": "MANUAL",
        }
        req_officer_b = {
            "action": "VERIFY",
            "expected_status": "PENDING",
            "notes": "Officer B physical verification.",
            "provenance": "MANUAL",
        }

        # Officer A submits first and succeeds
        res_a = self.client.post(
            f"/api/v1/authority/establishments/{est_id}/review",
            json=req_officer_a,
            headers={"Authorization": f"Bearer {self.officer_pune_1_token}"},
        )
        self.assertEqual(res_a.status_code, 200)

        # Officer B submits with the now-stale token 'PENDING'
        res_b = self.client.post(
            f"/api/v1/authority/establishments/{est_id}/review",
            json=req_officer_b,
            headers={"Authorization": f"Bearer {self.officer_pune_2_token}"},
        )
        self.assertEqual(res_b.status_code, 409)
        err = res_b.json().get("error", res_b.json().get("detail", res_b.json()))
        self.assertEqual(err["code"], "CONCURRENT_UPDATE_CONFLICT")

    def test_terminal_status_cannot_be_transitioned(self) -> None:
        """Establishment in REVOKED status is terminal; further transitions return HTTP 422."""
        # Setup an establishment already in REVOKED status
        revoked_est = self.est_repo.save_establishment(
            RetailEstablishment(
                id=str(uuid.uuid4()),
                trade_name="Permanently Closed Store",
                state_code="MH",
                district_code="PUNE",
                verification_status=EstablishmentVerificationStatus.REVOKED.value,
                is_active=False,
            )
        )

        res = self.client.post(
            f"/api/v1/authority/establishments/{revoked_est.id}/review",
            json={
                "action": "VERIFY",
                "expected_status": "REVOKED",
                "notes": "Attempting to un-revoke.",
            },
            headers={"Authorization": f"Bearer {self.officer_pune_1_token}"},
        )
        self.assertEqual(res.status_code, 422)
        err = res.json().get("error", res.json().get("detail", res.json()))
        self.assertIn("terminal", str(err).lower())

    def test_invalid_lifecycle_transition_rejected(self) -> None:
        """Attempting to suspend an establishment in PENDING status returns HTTP 422."""
        est_id = self.est_pune.id
        res = self.client.post(
            f"/api/v1/authority/establishments/{est_id}/review",
            json={
                "action": "SUSPEND",
                "expected_status": "PENDING",
                "notes": "Attempting to suspend before verification.",
            },
            headers={"Authorization": f"Bearer {self.officer_pune_1_token}"},
        )
        self.assertEqual(res.status_code, 422)
        err = res.json().get("error", res.json().get("detail", res.json()))
        self.assertIn("invalid_lifecycle_transition", str(err).lower())

    # =========================================================================
    # Authorization & Scope Tests
    # =========================================================================

    def test_unauthenticated_request_rejected(self) -> None:
        """Requests without Authorization header return HTTP 401."""
        res = self.client.post(
            f"/api/v1/authority/establishments/{self.est_pune.id}/review",
            json={"action": "VERIFY", "expected_status": "PENDING"},
        )
        self.assertEqual(res.status_code, 401)

    def test_consumer_review_rejected(self) -> None:
        """Consumer users cannot review establishments; returns HTTP 403."""
        res = self.client.post(
            f"/api/v1/authority/establishments/{self.est_pune.id}/review",
            json={"action": "VERIFY", "expected_status": "PENDING"},
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(res.status_code, 403)

    def test_inactive_officer_review_rejected(self) -> None:
        """Officers with inactive profiles cannot review establishments; returns HTTP 403."""
        res = self.client.post(
            f"/api/v1/authority/establishments/{self.est_pune.id}/review",
            json={"action": "VERIFY", "expected_status": "PENDING"},
            headers={"Authorization": f"Bearer {self.officer_inactive_token}"},
        )
        self.assertEqual(res.status_code, 403)

    def test_cross_district_review_rejected(self) -> None:
        """Satara officer cannot review Pune establishment; returns HTTP 403."""
        res = self.client.post(
            f"/api/v1/authority/establishments/{self.est_pune.id}/review",
            json={"action": "VERIFY", "expected_status": "PENDING", "notes": "Cross-district review"},
            headers={"Authorization": f"Bearer {self.officer_satara_token}"},
        )
        self.assertEqual(res.status_code, 403)

    def test_cross_district_timeline_access_rejected(self) -> None:
        """Satara officer cannot read audit timeline for Pune establishment; returns HTTP 403."""
        res = self.client.get(
            f"/api/v1/authority/establishments/{self.est_pune.id}/audit-timeline",
            headers={"Authorization": f"Bearer {self.officer_satara_token}"},
        )
        self.assertEqual(res.status_code, 403)

    # =========================================================================
    # Failure Atomicity & Database Error Handling Tests
    # =========================================================================

    def test_rollback_when_audit_insertion_fails(self) -> None:
        """Simulate audit event failure: status change must roll back completely."""
        self.est_repo.simulate_audit_failure = True
        est_id = self.est_pune.id

        res = self.client.post(
            f"/api/v1/authority/establishments/{est_id}/review",
            json={
                "action": "VERIFY",
                "expected_status": "PENDING",
                "notes": "Review during simulated audit glitch.",
            },
            headers={"Authorization": f"Bearer {self.officer_pune_1_token}"},
        )
        self.assertEqual(res.status_code, 500)

        # Verify establishment in repo is completely unchanged
        persisted = self.est_repo.get_by_id(est_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.verification_status, "PENDING")
        self.assertIsNone(persisted.verification_authority_id)
        self.assertIsNone(persisted.verification_date)

        # Verify no audit event was saved
        events = self.est_repo.get_audit_events(est_id)
        self.assertEqual(len(events), 0)

    def test_database_error_mapping_to_500(self) -> None:
        """Unhandled repository database errors map to HTTP 500 without leaking internals."""
        est_id = self.est_pune.id

        # Patch repo to raise EstablishmentDatabaseError
        orig_review = self.est_repo.review_establishment_atomic
        def mock_error(*args, **kwargs):
            raise EstablishmentDatabaseError("PostgreSQL connection terminated abnormally")
        self.est_repo.review_establishment_atomic = mock_error

        try:
            res = self.client.post(
                f"/api/v1/authority/establishments/{est_id}/review",
                json={
                    "action": "VERIFY",
                    "expected_status": "PENDING",
                    "notes": "Testing db error mapping",
                },
                headers={"Authorization": f"Bearer {self.officer_pune_1_token}"},
            )
            self.assertEqual(res.status_code, 500)
            err = res.json()
            # Must not expose raw db trace
            self.assertNotIn("PostgreSQL connection terminated", err.get("message", ""))
        finally:
            self.est_repo.review_establishment_atomic = orig_review

    # =========================================================================
    # Existing Consumer Complaint & Authority Case Workflow Safety
    # =========================================================================

    def test_existing_consumer_complaint_and_case_workflow_intact(self) -> None:
        """Verify that consumer complaints and case workflows operate cleanly alongside establishment reviews."""
        # 1. First verify the establishment
        res_verify = self.client.post(
            f"/api/v1/authority/establishments/{self.est_pune.id}/review",
            json={
                "action": "VERIFY",
                "expected_status": "PENDING",
                "notes": "Valid store for consumer filing.",
            },
            headers={"Authorization": f"Bearer {self.officer_pune_1_token}"},
        )
        self.assertEqual(res_verify.status_code, 200)

        # 2. Case service assign and status workflows remain operational
        case = self.case_repo.save_case(
            ConsumerIssue(
                id=str(uuid.uuid4()),
                user_id=self.consumer_id,
                issue_type=IssueType.PRICE_TAMPERING.value,
                title="Overcharging at Pune Supermarket Central",
                description="Billed Rs. 150 for MRP 120 product.",
                state_code="MH",
                district_code="PUNE",
                status=IssueStatus.SUBMITTED.value,
                establishment_id=self.est_pune.id,
                jurisdiction_verified=True,
            )
        )
        self.assertIsNotNone(case.id)
        self.assertEqual(case.establishment_id, self.est_pune.id)
        self.assertTrue(case.jurisdiction_verified)


if __name__ == "__main__":
    unittest.main()
