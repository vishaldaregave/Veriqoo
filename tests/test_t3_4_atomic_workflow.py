"""Integration and Unit Tests for T3-4 Phase 5: Atomic Authority Workflow and RPC Hardening.

Test Categories:
- Category 1: Unit Tests with Thread-Safe In-Memory Repository (Simulation of Atomic Transactions & Rollbacks)
- Category 2: Mocked Supabase RPC Integration Tests (PostgREST Protocol & Database Exception Translation)
- Category 3: Security & Immutability Verification (Client-Facing API Restrictions & Audit Integrity)
"""

from __future__ import annotations

import sys
# Bypass Windows App Control DLL block on ujson
sys.modules['ujson'] = None

from datetime import datetime, timezone
import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    get_authority_case_repository,
    get_authority_case_service,
    get_authority_repository,
    get_user_profile_repository,
)
from backend.app.api.errors import ErrorCode
from backend.app.auth.jwt import create_jwt_token
from backend.app.config import Settings, settings
from backend.app.main import app
from backend.app.services.authority.case_repository import (
    InMemoryAuthorityCaseRepository,
    SupabaseAuthorityCaseRepository,
)
from backend.app.services.authority.case_service import AuthorityCaseService
from backend.app.services.authority.errors import (
    AuthorityInactiveError,
    AuthorityJurisdictionDeniedError,
    CaseNotFoundError,
    InvalidAssignmentError,
    InvalidCaseNoteError,
    InvalidStatusTransitionError,
)
from backend.app.services.authority.models import (
    AuditEvent,
    AuditEventType,
    AuthorityProfile,
    JurisdictionLevel,
    JurisdictionScope,
)
from backend.app.services.authority.repository import InMemoryAuthorityRepository
from backend.app.services.consumer_issues.models import ConsumerIssue, IssueStatus
from backend.app.services.user_profile.models import UserProfile
from backend.app.services.user_profile.repository import InMemoryUserProfileRepository


class TestT34AtomicWorkflow(unittest.TestCase):
    """Test suite verifying atomic assignment, status transitions, rollbacks, and security boundaries."""

    def setUp(self) -> None:
        self.secret = "test-t3-4-atomic-workflow-secret-32ch!"
        self.audience = "authenticated"
        self.original_secret = settings.supabase_jwt_secret
        self.original_audience = settings.supabase_jwt_audience
        settings.supabase_jwt_secret = self.secret
        settings.supabase_jwt_audience = self.audience

        self.user_repo = InMemoryUserProfileRepository()
        self.auth_repo = InMemoryAuthorityRepository()
        self.case_repo = InMemoryAuthorityCaseRepository()
        self.case_service = AuthorityCaseService(
            case_repository=self.case_repo,
            authority_repository=self.auth_repo,
        )

        app.dependency_overrides[get_user_profile_repository] = lambda: self.user_repo
        app.dependency_overrides[get_authority_repository] = lambda: self.auth_repo
        app.dependency_overrides[get_authority_case_repository] = lambda: self.case_repo
        app.dependency_overrides[get_authority_case_service] = lambda: self.case_service

        self.client = TestClient(app)

        # Authority 1: Pune District (Legal Metrology)
        self.officer_pune_id = "55550000-0000-0000-0000-000000000005"
        self.officer_pune_token = create_jwt_token(
            {"sub": self.officer_pune_id, "email": "pune@gov.in"},
            secret=self.secret,
            audience=self.audience,
        )
        self.user_repo.create_profile(UserProfile(user_id=self.officer_pune_id, app_role="authority"))
        self.auth_repo.save(
            AuthorityProfile(
                user_id=self.officer_pune_id,
                department="LEGAL_METROLOGY",
                designation="Inspector Pune",
                jurisdiction=JurisdictionScope(
                    state_code="MH",
                    level=JurisdictionLevel.DISTRICT,
                    authorized_district_codes={"PUNE"},
                ),
                is_active=True,
            )
        )

        # Authority 2: Secondary Pune Officer (for reassignment)
        self.officer_pune_2_id = "66660000-0000-0000-0000-000000000006"
        self.officer_pune_2_token = create_jwt_token(
            {"sub": self.officer_pune_2_id, "email": "pune2@gov.in"},
            secret=self.secret,
            audience=self.audience,
        )
        self.user_repo.create_profile(UserProfile(user_id=self.officer_pune_2_id, app_role="authority"))
        self.auth_repo.save(
            AuthorityProfile(
                user_id=self.officer_pune_2_id,
                department="LEGAL_METROLOGY",
                designation="Inspector Pune 2",
                jurisdiction=JurisdictionScope(
                    state_code="MH",
                    level=JurisdictionLevel.DISTRICT,
                    authorized_district_codes={"PUNE"},
                ),
                is_active=True,
            )
        )

        # Authority 3: Satara Officer (Cross-District)
        self.officer_satara_id = "77770000-0000-0000-0000-000000000007"
        self.user_repo.create_profile(UserProfile(user_id=self.officer_satara_id, app_role="authority"))
        self.auth_repo.save(
            AuthorityProfile(
                user_id=self.officer_satara_id,
                department="LEGAL_METROLOGY",
                designation="Inspector Satara",
                jurisdiction=JurisdictionScope(
                    state_code="MH",
                    level=JurisdictionLevel.DISTRICT,
                    authorized_district_codes={"SATARA"},
                ),
                is_active=True,
            )
        )

        # Authority 4: Food Safety Officer (Cross-Department)
        self.officer_food_id = "88880000-0000-0000-0000-000000000008"
        self.user_repo.create_profile(UserProfile(user_id=self.officer_food_id, app_role="authority"))
        self.auth_repo.save(
            AuthorityProfile(
                user_id=self.officer_food_id,
                department="FOOD_SAFETY",
                designation="Food Safety Officer Pune",
                jurisdiction=JurisdictionScope(
                    state_code="MH",
                    level=JurisdictionLevel.DISTRICT,
                    authorized_district_codes={"PUNE"},
                ),
                is_active=True,
            )
        )

        # Authority 5: Inactive Officer
        self.officer_inactive_id = "99990000-0000-0000-0000-000000000009"
        self.officer_inactive_token = create_jwt_token(
            {"sub": self.officer_inactive_id, "email": "inactive@gov.in"},
            secret=self.secret,
            audience=self.audience,
        )
        self.user_repo.create_profile(UserProfile(user_id=self.officer_inactive_id, app_role="authority"))
        self.auth_repo.save(
            AuthorityProfile(
                user_id=self.officer_inactive_id,
                department="LEGAL_METROLOGY",
                designation="Suspended Officer",
                jurisdiction=JurisdictionScope(
                    state_code="MH",
                    level=JurisdictionLevel.DISTRICT,
                    authorized_district_codes={"PUNE"},
                ),
                is_active=False,
            )
        )

        # Ordinary Consumer
        self.consumer_id = "11110000-0000-0000-0000-000000000001"
        self.consumer_token = create_jwt_token(
            {"sub": self.consumer_id, "email": "consumer@example.com"},
            secret=self.secret,
            audience=self.audience,
        )
        self.user_repo.create_profile(UserProfile(user_id=self.consumer_id, app_role="consumer"))

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        settings.supabase_jwt_secret = self.original_secret
        settings.supabase_jwt_audience = self.original_audience

    # =====================================================================
    # SECTION 1: Atomic Assignment & Rollback Verification
    # =====================================================================

    def test_01_valid_assignment_updates_case_and_writes_one_audit_event(self) -> None:
        """Requirement 1: Valid assignment updates the case and writes exactly one audit event."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Weights Defect Pune",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        res = self.client.post(
            f"/api/v1/authority/cases/{case.id}/assign",
            json={"expect_unassigned": True},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["case_id"], case.id)
        self.assertEqual(data["assigned_officer_id"], self.officer_pune_id)
        self.assertEqual(data["assigned_by"], self.officer_pune_id)

        # Verify exactly one audit event created
        events = self.case_repo.list_audit_events(case.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "CASE_ASSIGNED")
        self.assertEqual(events[0].actor_id, self.officer_pune_id)
        self.assertEqual(events[0].new_state, self.officer_pune_id)

    def test_02_failed_audit_insertion_rolls_back_assignment(self) -> None:
        """Requirement 2: Failed audit insertion rolls back assignment atomically."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Weights Defect Pune",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
                assigned_officer_id=None,
            )
        )

        # Simulate audit event insertion failure in atomic repository
        self.case_repo.simulate_audit_failure = True

        res = self.client.post(
            f"/api/v1/authority/cases/{case.id}/assign",
            json={"expect_unassigned": True},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        # Service fails closed with 500 error
        self.assertEqual(res.status_code, 500)

        # Verify rollback: case assignment remains unassigned (None)
        persisted_case = self.case_repo.get_case_by_id(case.id)
        self.assertIsNotNone(persisted_case)
        self.assertIsNone(persisted_case.assigned_officer_id)
        self.assertIsNone(persisted_case.assigned_by)

        # Verify no audit event was committed
        events = self.case_repo.list_audit_events(case.id)
        self.assertEqual(len(events), 0)

    # =====================================================================
    # SECTION 2: Atomic Status Transition & Rollback Verification
    # =====================================================================

    def test_03_valid_status_transition_updates_case_and_writes_one_audit_event(self) -> None:
        """Requirement 3: Valid status transition updates the case and writes exactly one audit event."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Expired Package",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
                status=IssueStatus.SUBMITTED.value,
            )
        )

        res = self.client.patch(
            f"/api/v1/authority/cases/{case.id}/status",
            json={"new_status": "UNDER_REVIEW", "expected_status": "SUBMITTED"},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["case_id"], case.id)
        self.assertEqual(data["previous_status"], "SUBMITTED")
        self.assertEqual(data["new_status"], "UNDER_REVIEW")

        # Verify exactly one audit event created
        events = self.case_repo.list_audit_events(case.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "STATUS_CHANGED")
        self.assertEqual(events[0].previous_state, "SUBMITTED")
        self.assertEqual(events[0].new_state, "UNDER_REVIEW")

    def test_04_failed_audit_insertion_rolls_back_status_transition(self) -> None:
        """Requirement 4: Failed audit insertion rolls back the status transition atomically."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Expired Package",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
                status=IssueStatus.SUBMITTED.value,
            )
        )

        # Simulate audit event insertion failure in atomic repository
        self.case_repo.simulate_audit_failure = True

        res = self.client.patch(
            f"/api/v1/authority/cases/{case.id}/status",
            json={"new_status": "UNDER_REVIEW", "expected_status": "SUBMITTED"},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res.status_code, 500)

        # Verify rollback: case status remains SUBMITTED
        persisted_case = self.case_repo.get_case_by_id(case.id)
        self.assertIsNotNone(persisted_case)
        self.assertEqual(persisted_case.status, IssueStatus.SUBMITTED.value)

        # Verify no audit event was committed
        events = self.case_repo.list_audit_events(case.id)
        self.assertEqual(len(events), 0)

    # =====================================================================
    # SECTION 3: Concurrency Protection & Stale State
    # =====================================================================

    def test_05_concurrent_transitions_conflict_handling(self) -> None:
        """Requirement 5: Two concurrent transitions cannot both succeed against the same stale state."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Tare Defect",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
                status=IssueStatus.SUBMITTED.value,
            )
        )

        # Officer A transitions from SUBMITTED -> UNDER_REVIEW with expected_status=SUBMITTED
        res_a = self.client.patch(
            f"/api/v1/authority/cases/{case.id}/status",
            json={"new_status": "UNDER_REVIEW", "expected_status": "SUBMITTED"},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_a.status_code, 200)

        # Officer B attempts transition based on stale view (expected_status=SUBMITTED)
        res_b = self.client.patch(
            f"/api/v1/authority/cases/{case.id}/status",
            json={"new_status": "REJECTED", "resolution_notes": "Duplicate report", "expected_status": "SUBMITTED"},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        # Returns HTTP 409 Conflict with INVALID_INSPECTION_STATE
        self.assertEqual(res_b.status_code, 409)
        self.assertEqual(res_b.json()["error"]["code"], ErrorCode.INVALID_INSPECTION_STATE.value)
        self.assertIn("conflict", res_b.json()["error"]["message"].lower())

    def test_06_concurrent_assignments_cannot_corrupt_assignment_metadata(self) -> None:
        """Requirement 6: Two concurrent assignments with expected assigned officer tokens prevent corruption."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Label Defect",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
                assigned_officer_id=None,
            )
        )

        # Directly call atomic_assign_officer with expect_unassigned=True
        updated_1, audit_1 = self.case_repo.atomic_assign_officer(
            case_id=case.id,
            actor_id=self.officer_pune_id,
            actor_role="authority",
            target_officer_id=self.officer_pune_id,
            expect_unassigned=True,
        )
        self.assertEqual(updated_1.assigned_officer_id, self.officer_pune_id)

        # Concurrent call expecting old/stale assigned officer (e.g. expected_assigned_officer_id=self.officer_satara_id)
        with self.assertRaises(InvalidAssignmentError) as ctx:
            self.case_repo.atomic_assign_officer(
                case_id=case.id,
                actor_id=self.officer_pune_id,
                actor_role="authority",
                target_officer_id=self.officer_pune_id,
                expected_assigned_officer_id=self.officer_satara_id,
            )
        self.assertIn("conflict", str(ctx.exception).lower())

        # Concurrent call expecting unassigned on already assigned case fails with conflict
        with self.assertRaises(InvalidAssignmentError) as ctx2:
            self.case_repo.atomic_assign_officer(
                case_id=case.id,
                actor_id=self.officer_pune_id,
                actor_role="authority",
                target_officer_id=self.officer_pune_id,
                expect_unassigned=True,
            )
        self.assertIn("conflict", str(ctx2.exception).lower())

    # =====================================================================
    # SECTION 4: Authorization, Jurisdiction, and Validation Gating
    # =====================================================================

    def test_07_unauthorized_actors_cannot_assign_or_transition_case(self) -> None:
        """Requirement 7: Unauthenticated actors (401) and consumers (403) cannot assign or transition."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="MRP Tampering",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        # Unauthenticated -> 401
        res_unauth = self.client.post(f"/api/v1/authority/cases/{case.id}/assign", json={})
        self.assertEqual(res_unauth.status_code, 401)

        res_unauth_patch = self.client.patch(
            f"/api/v1/authority/cases/{case.id}/status",
            json={"new_status": "UNDER_REVIEW", "expected_status": "SUBMITTED"},
        )
        self.assertEqual(res_unauth_patch.status_code, 401)

        # Consumer -> 403
        res_consumer = self.client.post(
            f"/api/v1/authority/cases/{case.id}/assign",
            json={},
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(res_consumer.status_code, 403)

        res_consumer_patch = self.client.patch(
            f"/api/v1/authority/cases/{case.id}/status",
            json={"new_status": "UNDER_REVIEW", "expected_status": "SUBMITTED"},
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(res_consumer_patch.status_code, 403)

    def test_08_cross_department_and_cross_district_assignments_rejected(self) -> None:
        """Requirement 8 & Phase 5.2: Cross-officer reassignments are rejected with HTTP 403."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Underweight Salt",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        # Cross-department (Food safety officer) with valid concurrency token -> 403 Forbidden
        res_food = self.client.post(
            f"/api/v1/authority/cases/{case.id}/assign",
            json={"officer_user_id": self.officer_food_id, "expect_unassigned": True},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_food.status_code, 403)
        self.assertIn("Cross-officer reassignment is disabled", res_food.json()["error"]["message"])

        # Cross-district (Satara officer for Pune case) -> 403 Forbidden
        res_dist = self.client.post(
            f"/api/v1/authority/cases/{case.id}/assign",
            json={"officer_user_id": self.officer_satara_id, "expect_unassigned": True},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_dist.status_code, 403)
        self.assertIn("Cross-officer reassignment is disabled", res_dist.json()["error"]["message"])

        # Peer officer in same district -> 403 Forbidden
        res_peer = self.client.post(
            f"/api/v1/authority/cases/{case.id}/assign",
            json={"officer_user_id": self.officer_pune_2_id, "expect_unassigned": True},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_peer.status_code, 403)
        self.assertIn("Cross-officer reassignment is disabled", res_peer.json()["error"]["message"])

        # Calling database repository RPC directly with target != actor raises AuthorityJurisdictionDeniedError
        with self.assertRaises(AuthorityJurisdictionDeniedError) as rpc_ctx:
            self.case_repo.atomic_assign_officer(
                case_id=case.id,
                actor_id=self.officer_pune_id,
                actor_role="authority",
                target_officer_id=self.officer_pune_2_id,
                expect_unassigned=True,
            )
        self.assertIn("CROSS_OFFICER_ASSIGNMENT_DENIED", str(rpc_ctx.exception))

    def test_09_unverified_jurisdiction_remains_inaccessible(self) -> None:
        """Requirement 9: Unverified jurisdiction cases fail closed with 403."""
        case_unverified = self.case_repo.save_case(
            ConsumerIssue(
                title="Unverified Case",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=False,
            )
        )

        res = self.client.patch(
            f"/api/v1/authority/cases/{case_unverified.id}/status",
            json={"new_status": "UNDER_REVIEW", "expected_status": "SUBMITTED"},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("unverified or unresolved", res.json()["error"]["message"])

    def test_10_inactive_or_unprovisioned_authority_is_rejected(self) -> None:
        """Requirement 10: Inactive or unprovisioned authority accounts are rejected with 403."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Valid Case",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        res = self.client.post(
            f"/api/v1/authority/cases/{case.id}/assign",
            json={},
            headers={"Authorization": f"Bearer {self.officer_inactive_token}"},
        )
        self.assertEqual(res.status_code, 403)

    def test_11_invalid_status_transitions_are_rejected(self) -> None:
        """Requirement 11: Transitions violating the lifecycle matrix return 422."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Submitted Case",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
                status=IssueStatus.SUBMITTED.value,
            )
        )

        # SUBMITTED cannot transition directly to ACTION_TAKEN or RESOLVED
        res_invalid = self.client.patch(
            f"/api/v1/authority/cases/{case.id}/status",
            json={"new_status": "RESOLVED", "expected_status": "SUBMITTED", "resolution_notes": "Premature resolution"},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_invalid.status_code, 422)
        self.assertIn("Cannot transition case from status 'SUBMITTED' to 'RESOLVED'", res_invalid.json()["error"]["message"])

    def test_12_missing_required_resolution_notes_are_rejected(self) -> None:
        """Requirement 12: Terminal and actionable outcomes require substantive resolution notes (>=5 chars)."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Under Review Case",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
                status=IssueStatus.UNDER_REVIEW.value,
            )
        )

        # Transitioning to RESOLVED without notes
        res_no_notes = self.client.patch(
            f"/api/v1/authority/cases/{case.id}/status",
            json={"new_status": "RESOLVED", "expected_status": "UNDER_REVIEW"},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_no_notes.status_code, 422)
        self.assertIn("requires substantive resolution notes", res_no_notes.json()["error"]["message"])

        # Notes too short (<5 chars)
        res_short_notes = self.client.patch(
            f"/api/v1/authority/cases/{case.id}/status",
            json={"new_status": "RESOLVED", "expected_status": "UNDER_REVIEW", "resolution_notes": "ok"},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_short_notes.status_code, 422)

    def test_13_audit_events_immutability_and_client_protection(self) -> None:
        """Requirements 14 & 15: Ordinary clients cannot write, edit, or delete audit events directly."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Audited Case",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        # 1. No POST /audit endpoint exists
        res_post = self.client.post(f"/api/v1/authority/cases/{case.id}/audit-timeline", json={})
        self.assertEqual(res_post.status_code, 405)  # Method Not Allowed

        # 2. No PUT /audit endpoint exists
        res_put = self.client.put(f"/api/v1/authority/cases/{case.id}/audit-timeline", json={})
        self.assertEqual(res_put.status_code, 405)

        # 3. No DELETE /audit endpoint exists
        res_del = self.client.delete(f"/api/v1/authority/cases/{case.id}/audit-timeline")
        self.assertEqual(res_del.status_code, 405)

    def test_14_database_errors_fail_closed(self) -> None:
        """Requirement 16: Infrastructure/database failures fail closed with 500 error."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Database Crash Case",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        self.case_repo.simulate_case_failure = True
        res = self.client.post(
            f"/api/v1/authority/cases/{case.id}/assign",
            json={"expect_unassigned": True},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res.status_code, 500)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.INTERNAL_ERROR.value)

    # =====================================================================
    # SECTION 5: Mocked Supabase RPC Integration Tests
    # =====================================================================

    def test_15_mocked_supabase_rpc_atomic_assignment_success(self) -> None:
        """Mocked RPC: SupabaseAuthorityCaseRepository successfully maps atomic assignment RPC response."""
        settings = Settings(supabase_url="https://mock.supabase.co", supabase_service_role_key="mock-key")
        repo = SupabaseAuthorityCaseRepository(settings=settings)

        mock_case_row = {
            "id": "11111111-1111-1111-1111-111111111111",
            "user_id": "22222222-2222-2222-2222-222222222222",
            "issue_type": "MISLEADING_LABEL",
            "title": "Mock Title",
            "description": "Mock Desc",
            "status": "SUBMITTED",
            "department": "LEGAL_METROLOGY",
            "state_code": "MH",
            "district_code": "PUNE",
            "jurisdiction_verified": True,
            "assigned_officer_id": self.officer_pune_id,
            "assigned_at": "2026-10-09T10:00:00+00:00",
            "assigned_by": self.officer_pune_id,
            "created_at": "2026-10-09T09:00:00+00:00",
            "updated_at": "2026-10-09T10:00:00+00:00",
        }
        mock_audit_row = {
            "id": "33333333-3333-3333-3333-333333333333",
            "issue_id": "11111111-1111-1111-1111-111111111111",
            "actor_id": self.officer_pune_id,
            "actor_role": "authority",
            "event_type": "CASE_ASSIGNED",
            "previous_state": None,
            "new_state": self.officer_pune_id,
            "metadata": {},
            "created_at": "2026-10-09T10:00:00+00:00",
        }

        with patch.object(repo, "_rpc") as mock_rpc:
            mock_rpc.return_value = {"case": mock_case_row, "audit_event": mock_audit_row}
            case, audit = repo.atomic_assign_officer(
                case_id=mock_case_row["id"],
                actor_id=self.officer_pune_id,
                actor_role="authority",
                target_officer_id=self.officer_pune_id,
                expect_unassigned=True,
            )
            mock_rpc.assert_called_once_with(
                "authority_assign_case",
                {
                    "p_case_id": mock_case_row["id"],
                    "p_target_officer_id": self.officer_pune_id,
                    "p_actor_id": self.officer_pune_id,
                    "p_expected_assigned_officer_id": None,
                    "p_expect_unassigned": True,
                },
            )
            self.assertEqual(case.id, mock_case_row["id"])
            self.assertEqual(case.assigned_officer_id, self.officer_pune_id)
            self.assertEqual(audit.event_type, "CASE_ASSIGNED")

    def test_16_mocked_supabase_rpc_error_translation(self) -> None:
        """Mocked RPC: SupabaseAuthorityCaseRepository correctly translates PostgreSQL RPC errors."""
        settings = Settings(supabase_url="https://mock.supabase.co", supabase_service_role_key="mock-key")
        repo = SupabaseAuthorityCaseRepository(settings=settings)

        def mock_error_response(message: str) -> MagicMock:
            resp = MagicMock()
            resp.status_code = 400
            resp.text = json.dumps({"message": message})
            resp.json.return_value = {"message": message}
            return resp

        # 1. CASE_NOT_FOUND
        with patch("requests.post", return_value=mock_error_response("CASE_NOT_FOUND: Case not found")):
            with self.assertRaises(CaseNotFoundError):
                repo.atomic_transition_status("c1", "a1", "authority", "UNDER_REVIEW", expected_status="SUBMITTED")

        # 2. CONCURRENT_UPDATE_CONFLICT
        with patch("requests.post", return_value=mock_error_response("CONCURRENT_UPDATE_CONFLICT: Status stale")):
            with self.assertRaises(InvalidStatusTransitionError) as ctx:
                repo.atomic_transition_status("c1", "a1", "authority", "UNDER_REVIEW", expected_status="SUBMITTED")
            self.assertTrue(ctx.exception.details.get("conflict"))

        # 3. ACTOR_JURISDICTION_DENIED
        with patch("requests.post", return_value=mock_error_response("ACTOR_JURISDICTION_DENIED: Out of scope")):
            with self.assertRaises(AuthorityJurisdictionDeniedError):
                repo.atomic_transition_status("c1", "a1", "authority", "UNDER_REVIEW", expected_status="SUBMITTED")

        # 4. INVALID_STATUS_TRANSITION
        with patch("requests.post", return_value=mock_error_response("INVALID_STATUS_TRANSITION: Illegal")):
            with self.assertRaises(InvalidStatusTransitionError):
                repo.atomic_transition_status("c1", "a1", "authority", "RESOLVED", expected_status="SUBMITTED")

        # 5. CONCURRENCY_TOKEN_REQUIRED
        with patch("requests.post", return_value=mock_error_response("CONCURRENCY_TOKEN_REQUIRED: expected_status token is mandatory")):
            with self.assertRaises(InvalidStatusTransitionError) as ctx:
                repo.atomic_transition_status("c1", "a1", "authority", "UNDER_REVIEW", expected_status="DUMMY")
            self.assertEqual(ctx.exception.details.get("code"), "CONCURRENCY_TOKEN_REQUIRED")

    # =====================================================================
    # SECTION 6: Phase 5.1 Hardened Concurrency & Direct RPC Security Audit
    # =====================================================================

    def test_17_missing_or_invalid_concurrency_tokens_rejected(self) -> None:
        """Phase 5.1: Missing or blank expected_status concurrency token is rejected with HTTP 422."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Concurrency Test Case",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
                status=IssueStatus.SUBMITTED.value,
            )
        )

        # 1. Missing expected_status
        res_missing = self.client.patch(
            f"/api/v1/authority/cases/{case.id}/status",
            json={"new_status": "UNDER_REVIEW"},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_missing.status_code, 422)

        # 2. Empty string expected_status
        res_empty = self.client.patch(
            f"/api/v1/authority/cases/{case.id}/status",
            json={"new_status": "UNDER_REVIEW", "expected_status": ""},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_empty.status_code, 422)

        # 3. Whitespace-only expected_status
        res_whitespace = self.client.patch(
            f"/api/v1/authority/cases/{case.id}/status",
            json={"new_status": "UNDER_REVIEW", "expected_status": "   "},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_whitespace.status_code, 422)

    def test_18_assignment_concurrency_conflict_returns_409(self) -> None:
        """Phase 5.1: Assignment with conflicting expected_assigned_officer_id returns HTTP 409 Conflict."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Assignment Conflict Case",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
                assigned_officer_id=self.officer_pune_id,
            )
        )

        # Attempt assignment claiming expected officer was officer_pune_2_id (mismatch!)
        res_conflict = self.client.post(
            f"/api/v1/authority/cases/{case.id}/assign",
            json={
                "officer_user_id": self.officer_pune_2_id,
                "expected_assigned_officer_id": self.officer_pune_2_id,
            },
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_conflict.status_code, 409)
        self.assertEqual(res_conflict.json()["error"]["code"], ErrorCode.INVALID_INSPECTION_STATE.value)
        self.assertIn("conflict", res_conflict.json()["error"]["message"].lower())

    def test_19_direct_rpc_authorization_boundary_audit(self) -> None:
        """Phase 5.1: Audit SQL migration to verify execution grants and security boundary restrictions.

        NOTE: This test verifies the static definitions and security contracts of the proposed migration file.
        It distinguishes mocked/unit verification from live PostgreSQL integration testing.
        """
        import os
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "supabase",
            "migrations",
            "20261010000000_t3_4_atomic_authority_rpc.sql",
        )
        self.assertTrue(os.path.exists(migration_path), f"Migration file not found: {migration_path}")

        with open(migration_path, "r", encoding="utf-8") as f:
            sql_content = f.read()

        # 1. SECURITY DEFINER with fixed search_path
        self.assertIn("SECURITY DEFINER", sql_content)
        self.assertIn("SET search_path = public, pg_temp", sql_content)

        # 2. REVOKE ALL FROM PUBLIC, authenticated (prevents direct PostgREST client invocation)
        self.assertIn(
            "REVOKE ALL ON FUNCTION public.authority_assign_case(uuid, uuid, uuid, uuid, boolean) FROM PUBLIC, authenticated;",
            sql_content,
        )
        self.assertIn(
            "REVOKE ALL ON FUNCTION public.authority_transition_status(uuid, text, uuid, text, text) FROM PUBLIC, authenticated;",
            sql_content,
        )

        # 3. GRANT EXECUTE EXCLUSIVELY TO service_role (trusted backend boundary)
        self.assertIn(
            "GRANT EXECUTE ON FUNCTION public.authority_assign_case(uuid, uuid, uuid, uuid, boolean) TO service_role;",
            sql_content,
        )
        self.assertIn(
            "GRANT EXECUTE ON FUNCTION public.authority_transition_status(uuid, text, uuid, text, text) TO service_role;",
            sql_content,
        )

        # 4. Mandatory concurrency token validation in SQL
        self.assertIn("CONCURRENCY_TOKEN_REQUIRED", sql_content)

        # 5. Actor spoofing prevention
        self.assertIn("ACTOR_MISMATCH", sql_content)
        self.assertIn("auth.uid() IS NOT NULL AND p_actor_id != auth.uid()", sql_content)

        # 6. Admin does not receive global bypass (strict jurisdiction required)
        self.assertIn("ACTOR_JURISDICTION_DENIED", sql_content)

    # =====================================================================
    # SECTION 7: Phase 5.2 Atomic Notes, Concurrency & Least-Privilege
    # =====================================================================

    def test_20_investigation_note_atomic_creation_and_audit_event(self) -> None:
        """Phase 5.2: Investigation note creation writes note and NOTE_ADDED audit record atomically."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Weights Inspection Pune",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        note_content = "Confidential observation: Verified discrepancy in calibrated weigh scales."
        res = self.client.post(
            f"/api/v1/authority/cases/{case.id}/notes",
            json={"note_text": note_content},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["issue_id"], case.id)
        self.assertEqual(data["author_id"], self.officer_pune_id)
        self.assertEqual(data["note_text"], note_content)

        # Verify note is persisted
        notes = self.case_repo.list_notes(case.id)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].note_text, note_content)

        # Verify exactly one NOTE_ADDED audit event was recorded atomically
        events = self.case_repo.list_audit_events(case.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "NOTE_ADDED")
        self.assertEqual(events[0].actor_id, self.officer_pune_id)

        # Verify audit metadata does NOT expose the full confidential investigation note
        self.assertNotIn("note_text", events[0].metadata)
        self.assertEqual(events[0].metadata.get("note_id"), data["id"])
        self.assertEqual(events[0].metadata.get("note_length"), len(note_content))

    def test_21_investigation_note_audit_failure_rolls_back_note(self) -> None:
        """Phase 5.2: Simulated audit insertion failure rolls back note creation in in-memory simulator."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Scale Check Pune",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        # Trigger simulated audit event failure
        self.case_repo.simulate_audit_failure = True

        res = self.client.post(
            f"/api/v1/authority/cases/{case.id}/notes",
            json={"note_text": "This note should be rolled back on audit failure."},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res.status_code, 500)

        # Verify rollback: 0 notes and 0 audit events persisted
        self.assertEqual(len(self.case_repo.list_notes(case.id)), 0)
        self.assertEqual(len(self.case_repo.list_audit_events(case.id)), 0)

    def test_22_mocked_supabase_rpc_atomic_note_creation(self) -> None:
        """Phase 5.2: Mocked SupabaseAuthorityCaseRepository calls authority_create_case_note RPC correctly."""
        settings = Settings(supabase_url="https://mock.supabase.co", supabase_service_role_key="mock-key")
        repo = SupabaseAuthorityCaseRepository(settings=settings)

        mock_note_row = {
            "id": "44444444-4444-4444-4444-444444444444",
            "issue_id": "11111111-1111-1111-1111-111111111111",
            "author_id": self.officer_pune_id,
            "note_text": "Confidential note content",
            "is_internal": True,
            "created_at": "2026-10-10T12:00:00+00:00",
            "updated_at": "2026-10-10T12:00:00+00:00",
        }
        mock_audit_row = {
            "id": "55555555-5555-5555-5555-555555555555",
            "issue_id": "11111111-1111-1111-1111-111111111111",
            "actor_id": self.officer_pune_id,
            "actor_role": "authority",
            "event_type": "NOTE_ADDED",
            "previous_state": None,
            "new_state": "CONFIDENTIAL_NOTE",
            "metadata": {"note_id": mock_note_row["id"], "author_id": self.officer_pune_id, "note_length": 25},
            "created_at": "2026-10-10T12:00:00+00:00",
        }

        with patch.object(repo, "_rpc") as mock_rpc:
            mock_rpc.return_value = {"note": mock_note_row, "audit_event": mock_audit_row}
            note, audit = repo.atomic_create_note(
                case_id=mock_note_row["issue_id"],
                actor_id=self.officer_pune_id,
                actor_role="authority",
                note_text="Confidential note content",
            )
            mock_rpc.assert_called_once_with(
                "authority_create_case_note",
                {
                    "p_case_id": mock_note_row["issue_id"],
                    "p_actor_id": self.officer_pune_id,
                    "p_note_text": "Confidential note content",
                    "p_metadata": {},
                },
            )
            self.assertEqual(note.id, mock_note_row["id"])
            self.assertEqual(audit.event_type, "NOTE_ADDED")

        # Verify error translation for NOTE_EMPTY and NOTE_TOO_LONG
        def mock_error_response(message: str) -> MagicMock:
            resp = MagicMock()
            resp.status_code = 400
            resp.text = json.dumps({"message": message})
            resp.json.return_value = {"message": message}
            return resp

        with patch("requests.post", return_value=mock_error_response("NOTE_EMPTY: Note text cannot be empty")):
            with self.assertRaises(InvalidCaseNoteError):
                repo.atomic_create_note("c1", "a1", "authority", "text")

        with patch("requests.post", return_value=mock_error_response("CROSS_OFFICER_ASSIGNMENT_DENIED: Denied")):
            with self.assertRaises(AuthorityJurisdictionDeniedError):
                repo.atomic_assign_officer("c1", "a1", "authority", "a2", expect_unassigned=True)

    def test_23_consumer_cannot_write_notes_or_audit_events_via_public_apis(self) -> None:
        """Phase 5.2: Consumers cannot access internal investigation notes or write arbitrary audit events."""
        case = self.case_repo.save_case(
            ConsumerIssue(
                title="Privacy Test Case",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        # Consumer cannot post notes (403)
        res_consumer = self.client.post(
            f"/api/v1/authority/cases/{case.id}/notes",
            json={"note_text": "Unauthorized note injection attempt."},
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(res_consumer.status_code, 403)

        # Unauthenticated cannot post notes (401)
        res_unauth = self.client.post(
            f"/api/v1/authority/cases/{case.id}/notes",
            json={"note_text": "Unauthenticated note."},
        )
        self.assertEqual(res_unauth.status_code, 401)

        # No generic public audit event writing endpoint exists
        res_bogus_audit = self.client.post(
            f"/api/v1/authority/cases/{case.id}/audit-timeline",
            json={"event_type": "BOGUS_AUDIT"},
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertIn(res_bogus_audit.status_code, (404, 405))

    def test_24_phase_5_2_migration_audit(self) -> None:
        """Phase 5.2: Audit SQL migration 20261010000001_t3_4_phase5_2_hardening.sql."""
        import os
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "supabase",
            "migrations",
            "20261010000001_t3_4_phase5_2_hardening.sql",
        )
        self.assertTrue(os.path.exists(migration_path), f"Migration file not found: {migration_path}")

        with open(migration_path, "r", encoding="utf-8") as f:
            sql = f.read()

        # 1. SECURITY DEFINER with fixed search_path
        self.assertIn("SECURITY DEFINER", sql)
        self.assertIn("SET search_path = public, pg_temp", sql)

        # 2. Revocation of previous authority_assign_case signature
        self.assertIn("DROP FUNCTION IF EXISTS public.authority_assign_case(uuid, uuid, uuid, uuid, boolean);", sql)

        # 3. New authority_assign_case signature with p_expect_unassigned
        self.assertIn("p_expect_unassigned boolean", sql)

        # 4. Cross-officer assignment denial in RPC
        self.assertIn("CROSS_OFFICER_ASSIGNMENT_DENIED", sql)
        self.assertIn("p_target_officer_id IS DISTINCT FROM p_actor_id", sql)

        # 5. Atomic authority_create_case_note RPC definition
        self.assertIn("FUNCTION public.authority_create_case_note", sql)
        self.assertIn("NOTE_EMPTY", sql)
        self.assertIn("NOTE_TOO_LONG", sql)
        self.assertIn("length(v_clean_text) > 5000", sql)
        self.assertIn("INSERT INTO public.consumer_issue_notes", sql)
        self.assertIn("INSERT INTO public.consumer_issue_audit_events", sql)

        # 6. Strict service_role grants and public revocation
        self.assertIn("REVOKE ALL ON FUNCTION public.authority_assign_case(uuid, uuid, uuid, uuid, boolean) FROM PUBLIC, authenticated;", sql)
        self.assertIn("GRANT EXECUTE ON FUNCTION public.authority_assign_case(uuid, uuid, uuid, uuid, boolean) TO service_role;", sql)
        self.assertIn("REVOKE ALL ON FUNCTION public.authority_create_case_note(uuid, uuid, text, jsonb) FROM PUBLIC, authenticated;", sql)
        self.assertIn("GRANT EXECUTE ON FUNCTION public.authority_create_case_note(uuid, uuid, text, jsonb) TO service_role;", sql)


if __name__ == "__main__":
    unittest.main()
