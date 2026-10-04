"""Test suite for T3-4 Authority Case-Management Service and Endpoints (Phase 4).

Verifies:
1. Unauthenticated requests are rejected with HTTP 401.
2. Consumer and inspector roles cannot use authority endpoints (HTTP 403).
3. Unprovisioned or inactive authorities are rejected (HTTP 403).
4. District officers cannot list cases from other districts (strict jurisdiction queue gating).
5. Authorities cannot access another department's cases (department isolation).
6. Unverified or unresolved jurisdiction is denied (fails closed).
7. Inaccessible case details do not leak sensitive information (404 vs 403 distinction).
8. Invalid officer assignment is rejected (non-existent, inactive, wrong department).
9. Cross-jurisdiction assignment is rejected (target officer lacks district authority).
10. Successful assignment records the correct actor and audit event (CASE_ASSIGNED / CASE_REASSIGNED).
11. Internal notes cannot be read by consumers.
12. Empty or oversized notes are rejected (HTTP 422).
13. Invalid status transitions are rejected according to transition matrix.
14. Required resolution notes are validated for terminal and enforcement states.
15. Status changes generate audit events.
16. Concurrent or stale status updates are handled safely with optimistic locking (HTTP 409).
17. Database errors fail closed.
18. Existing T3-1, T3-2, T3-3, and T3-4 tests continue to pass.
"""

from __future__ import annotations

import sys
sys.modules['ujson'] = None  # Bypass Windows App Control policy DLL block for ujson

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    get_authority_case_repository,
    get_authority_case_service,
    get_authority_repository,
    get_user_profile_repository,
)
from backend.app.api.errors import ErrorCode
from backend.app.auth.jwt import create_jwt_token
from backend.app.config import settings
from backend.app.main import app
from backend.app.services.authority.case_repository import (
    AuthorityCaseRepository,
    InMemoryAuthorityCaseRepository,
)
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
from backend.app.services.user_profile.models import UserProfile
from backend.app.services.user_profile.repository import InMemoryUserProfileRepository


class T34AuthorityCaseWorkflowTestCase(unittest.TestCase):
    """Integration and unit tests for Authority Case Management API."""

    def setUp(self) -> None:
        self.secret = "test-t3-4-case-workflow-secret-32ch!"
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

        # 1. Identities
        self.consumer_id = "11110000-0000-0000-0000-000000000001"
        self.consumer_token = create_jwt_token({"sub": self.consumer_id}, secret=self.secret, audience=self.audience)
        self.user_repo.create_profile(UserProfile(user_id=self.consumer_id, app_role="consumer"))

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
                designation="Food Safety Officer",
                jurisdiction=JurisdictionScope(
                    state_code="MH",
                    level=JurisdictionLevel.DISTRICT,
                    authorized_district_codes={"PUNE"},
                ),
                is_active=True,
            )
        )

        # Inactive Officer
        self.officer_inactive_id = "77770000-0000-0000-0000-000000000007"
        self.officer_inactive_token = create_jwt_token({"sub": self.officer_inactive_id}, secret=self.secret, audience=self.audience)
        self.user_repo.create_profile(UserProfile(user_id=self.officer_inactive_id, app_role="authority"))
        self.auth_repo.save(
            AuthorityProfile(
                user_id=self.officer_inactive_id,
                department=DepartmentCode.LEGAL_METROLOGY.value,
                designation="Suspended Inspector",
                jurisdiction=JurisdictionScope(
                    state_code="MH",
                    level=JurisdictionLevel.DISTRICT,
                    authorized_district_codes={"PUNE"},
                ),
                is_active=False,
            )
        )

    def tearDown(self) -> None:
        settings.supabase_jwt_secret = self.original_secret
        settings.supabase_jwt_audience = self.original_audience
        app.dependency_overrides.clear()
        self.user_repo.clear()
        self.auth_repo.clear()
        self.case_repo.clear()

    # =====================================================================
    # 1. Unauthenticated & Role Gating Tests
    # =====================================================================

    def test_unauthenticated_requests_rejected(self) -> None:
        """Authority endpoints reject callers without Authorization header with HTTP 401."""
        endpoints = [
            ("GET", "/api/v1/authority/cases"),
            ("GET", "/api/v1/authority/cases/c1"),
            ("POST", "/api/v1/authority/cases/c1/assign"),
            ("GET", "/api/v1/authority/cases/c1/notes"),
            ("POST", "/api/v1/authority/cases/c1/notes"),
            ("PATCH", "/api/v1/authority/cases/c1/status"),
            ("GET", "/api/v1/authority/cases/c1/audit-timeline"),
        ]
        for method, path in endpoints:
            if method == "GET":
                res = self.client.get(path)
            elif method == "POST":
                res = self.client.post(path, json={})
            elif method == "PATCH":
                res = self.client.patch(path, json={})
            self.assertEqual(res.status_code, 401, f"Expected 401 on {method} {path}")
            self.assertEqual(res.json()["error"]["code"], ErrorCode.AUTHENTICATION_REQUIRED.value)

    def test_consumer_and_inspector_roles_rejected(self) -> None:
        """Callers with 'consumer' or 'inspector' roles receive HTTP 403 FORBIDDEN."""
        for token in (self.consumer_token, self.inspector_token):
            res = self.client.get(
                "/api/v1/authority/cases",
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(res.status_code, 403)
            self.assertEqual(res.json()["error"]["code"], ErrorCode.FORBIDDEN.value)

    def test_unprovisioned_and_inactive_authorities_rejected(self) -> None:
        """Authorities without profile or with is_active=False receive HTTP 403 FORBIDDEN."""
        # Inactive officer
        res = self.client.get(
            "/api/v1/authority/cases",
            headers={"Authorization": f"Bearer {self.officer_inactive_token}"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.FORBIDDEN.value)

        # Unprovisioned officer (app_role=authority, but no AuthorityProfile in repo)
        unprovisioned_id = "88880000-0000-0000-0000-000000000008"
        unprovisioned_token = create_jwt_token({"sub": unprovisioned_id}, secret=self.secret, audience=self.audience)
        self.user_repo.create_profile(UserProfile(user_id=unprovisioned_id, app_role="authority"))
        res = self.client.get(
            "/api/v1/authority/cases",
            headers={"Authorization": f"Bearer {unprovisioned_token}"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.FORBIDDEN.value)

    # =====================================================================
    # 2. Queue Gating & Department Isolation Tests
    # =====================================================================

    def test_district_officers_cannot_list_cases_from_other_districts(self) -> None:
        """Case queue strictly returns complaints in the officer's authorized district."""
        # Case 1: Pune (Legal Metrology, Verified)
        c_pune = self.case_repo.save_case(
            ConsumerIssue(
                title="Pune Weight Issue",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )
        # Case 2: Satara (Legal Metrology, Verified)
        c_satara = self.case_repo.save_case(
            ConsumerIssue(
                title="Satara Label Issue",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="SATARA",
                jurisdiction_verified=True,
            )
        )

        res = self.client.get(
            "/api/v1/authority/cases",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["id"], c_pune.id)
        self.assertEqual(data["items"][0]["district_code"], "PUNE")

    def test_authorities_cannot_access_other_departments_cases(self) -> None:
        """Authorities cannot see or access complaints filed under different statutory departments."""
        c_food = self.case_repo.save_case(
            ConsumerIssue(
                title="Adulterated Food Complaint",
                department="FOOD_SAFETY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        # Legal Metrology officer cannot see Food Safety complaint in queue
        res_queue = self.client.get(
            "/api/v1/authority/cases",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_queue.status_code, 200)
        self.assertEqual(res_queue.json()["total"], 0)

        # Direct access to Food Safety complaint is denied with 403
        res_detail = self.client.get(
            f"/api/v1/authority/cases/{c_food.id}",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_detail.status_code, 403)
        self.assertEqual(res_detail.json()["error"]["code"], ErrorCode.FORBIDDEN.value)

    def test_unverified_or_unresolved_jurisdiction_denied(self) -> None:
        """Complaints with jurisdiction_verified=False fail closed and are excluded from queue and details."""
        c_unverified = self.case_repo.save_case(
            ConsumerIssue(
                title="Unverified GPS Location",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=False,  # Unresolved!
            )
        )

        # Not in queue
        res_queue = self.client.get(
            "/api/v1/authority/cases",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_queue.json()["total"], 0)

        # Direct access denied (fails closed)
        res_detail = self.client.get(
            f"/api/v1/authority/cases/{c_unverified.id}",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_detail.status_code, 403)
        self.assertIn("unverified or unresolved", res_detail.json()["error"]["message"])

    def test_inaccessible_case_details_404_vs_403(self) -> None:
        """Non-existent cases return 404; existing cases in forbidden jurisdictions return 403."""
        # Non-existent
        res_404 = self.client.get(
            "/api/v1/authority/cases/00000000-0000-0000-0000-000000000999",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_404.status_code, 404)
        self.assertEqual(res_404.json()["error"]["code"], ErrorCode.CONSUMER_ISSUE_NOT_FOUND.value)

        # Existing case in Satara (outside Pune officer's jurisdiction)
        c_satara = self.case_repo.save_case(
            ConsumerIssue(
                title="Satara Case",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="SATARA",
                jurisdiction_verified=True,
            )
        )
        res_403 = self.client.get(
            f"/api/v1/authority/cases/{c_satara.id}",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_403.status_code, 403)
        self.assertEqual(res_403.json()["error"]["code"], ErrorCode.FORBIDDEN.value)

    # =====================================================================
    # 3. Primary Officer Assignment Tests
    # =====================================================================

    def test_invalid_and_cross_jurisdiction_officer_assignment_rejected(self) -> None:
        """Phase 5.2: Missing concurrency returns 422; cross-officer reassignment returns 403."""
        c_pune = self.case_repo.save_case(
            ConsumerIssue(
                title="Pune Case",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        # 1. Missing concurrency precondition returns 422
        res_no_concurrency = self.client.post(
            f"/api/v1/authority/cases/{c_pune.id}/assign",
            json={"officer_user_id": self.officer_satara_id},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_no_concurrency.status_code, 422)

        # 2. Blank concurrency token returns 422
        res_blank = self.client.post(
            f"/api/v1/authority/cases/{c_pune.id}/assign",
            json={"expected_assigned_officer_id": "   "},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_blank.status_code, 422)

        # 3. Cross-officer reassignment is denied (403 Forbidden)
        res_cross_dist = self.client.post(
            f"/api/v1/authority/cases/{c_pune.id}/assign",
            json={"officer_user_id": self.officer_satara_id, "expect_unassigned": True},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_cross_dist.status_code, 403)
        self.assertIn("Cross-officer reassignment is disabled", res_cross_dist.json()["error"]["message"])

        # 4. Cross-department officer returns 403 Forbidden
        res_cross_dept = self.client.post(
            f"/api/v1/authority/cases/{c_pune.id}/assign",
            json={"officer_user_id": self.officer_food_id, "expect_unassigned": True},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_cross_dept.status_code, 403)

        # 5. Peer officer in same district returns 403 Forbidden
        res_peer = self.client.post(
            f"/api/v1/authority/cases/{c_pune.id}/assign",
            json={"officer_user_id": "77770000-0000-0000-0000-000000000007", "expect_unassigned": True},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_peer.status_code, 403)
        self.assertIn("Cross-officer reassignment is disabled", res_peer.json()["error"]["message"])

    def test_successful_assignment_records_actor_and_audit_event(self) -> None:
        """Self-assignment succeeds with explicit unassigned token and records immutable audit records."""
        c_pune = self.case_repo.save_case(
            ConsumerIssue(
                title="Pune Case",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        # Missing concurrency token is rejected (422)
        res_missing = self.client.post(
            f"/api/v1/authority/cases/{c_pune.id}/assign",
            json={},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_missing.status_code, 422)

        # Self-assignment with expect_unassigned=True succeeds (200)
        res = self.client.post(
            f"/api/v1/authority/cases/{c_pune.id}/assign",
            json={"expect_unassigned": True},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["case_id"], c_pune.id)
        self.assertEqual(data["assigned_officer_id"], self.officer_pune_id)
        self.assertEqual(data["assigned_by"], self.officer_pune_id)

        # Verify audit event in timeline
        timeline = self.client.get(
            f"/api/v1/authority/cases/{c_pune.id}/audit-timeline",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        ).json()
        self.assertEqual(timeline["total"], 1)
        self.assertEqual(timeline["items"][0]["event_type"], "CASE_ASSIGNED")
        self.assertEqual(timeline["items"][0]["actor_id"], self.officer_pune_id)
        self.assertEqual(timeline["items"][0]["new_state"], self.officer_pune_id)

    # =====================================================================
    # 4. Confidential Investigation Notes Tests
    # =====================================================================

    def test_internal_notes_confidentiality_and_validation(self) -> None:
        """Notes are private to authority, validated for length, and generate audit records."""
        c_pune = self.case_repo.save_case(
            ConsumerIssue(
                title="Pune Case",
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        # Consumer cannot access notes endpoint (blocked by require_authority_user with 403)
        res_consumer = self.client.get(
            f"/api/v1/authority/cases/{c_pune.id}/notes",
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(res_consumer.status_code, 403)

        # Empty note rejected
        res_empty = self.client.post(
            f"/api/v1/authority/cases/{c_pune.id}/notes",
            json={"note_text": "   "},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_empty.status_code, 422)

        # Oversized note (>5000 chars) rejected
        res_huge = self.client.post(
            f"/api/v1/authority/cases/{c_pune.id}/notes",
            json={"note_text": "x" * 5001},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_huge.status_code, 422)

        # Valid note creates note and records NOTE_ADDED audit event
        res_valid = self.client.post(
            f"/api/v1/authority/cases/{c_pune.id}/notes",
            json={"note_text": "Retailer verification conducted on site. Stock inspected."},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_valid.status_code, 201)
        note_data = res_valid.json()
        self.assertEqual(note_data["author_id"], self.officer_pune_id)
        self.assertTrue(note_data["is_internal"])

        # Notes list contains the note
        notes_list = self.client.get(
            f"/api/v1/authority/cases/{c_pune.id}/notes",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        ).json()
        self.assertEqual(notes_list["total"], 1)
        self.assertEqual(notes_list["items"][0]["note_text"], "Retailer verification conducted on site. Stock inspected.")

    # =====================================================================
    # 5. Status Lifecycle Transition Tests
    # =====================================================================

    def test_status_transitions_and_resolution_notes_validation(self) -> None:
        """Status transitions strictly follow transition matrix and require notes where appropriate."""
        c = self.case_repo.save_case(
            ConsumerIssue(
                title="Pune Case",
                status=IssueStatus.SUBMITTED.value,
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        # 1. Invalid jump from SUBMITTED directly to RESOLVED -> 422
        res_invalid_jump = self.client.patch(
            f"/api/v1/authority/cases/{c.id}/status",
            json={"new_status": "RESOLVED", "expected_status": "SUBMITTED", "resolution_notes": "All resolved directly."},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_invalid_jump.status_code, 422)

        # 2. Valid transition: SUBMITTED -> UNDER_REVIEW
        res_review = self.client.patch(
            f"/api/v1/authority/cases/{c.id}/status",
            json={"new_status": "UNDER_REVIEW", "expected_status": "SUBMITTED"},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_review.status_code, 200)
        self.assertEqual(res_review.json()["new_status"], "UNDER_REVIEW")

        # 3. Transition UNDER_REVIEW -> ACTION_TAKEN without resolution notes fails (422)
        res_no_notes = self.client.patch(
            f"/api/v1/authority/cases/{c.id}/status",
            json={"new_status": "ACTION_TAKEN", "expected_status": "UNDER_REVIEW"},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_no_notes.status_code, 422)
        self.assertIn("substantive resolution notes", res_no_notes.json()["error"]["message"])

        # 4. Valid transition UNDER_REVIEW -> ACTION_TAKEN with substantive notes
        res_action = self.client.patch(
            f"/api/v1/authority/cases/{c.id}/status",
            json={
                "new_status": "ACTION_TAKEN",
                "expected_status": "UNDER_REVIEW",
                "resolution_notes": "Statutory inspection notice issued to manufacturer under Rule 6.",
            },
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_action.status_code, 200)
        self.assertEqual(res_action.json()["new_status"], "ACTION_TAKEN")

        # 5. Terminal transition ACTION_TAKEN -> RESOLVED
        res_resolved = self.client.patch(
            f"/api/v1/authority/cases/{c.id}/status",
            json={
                "new_status": "RESOLVED",
                "expected_status": "ACTION_TAKEN",
                "resolution_notes": "Manufacturer provided proof of label rectification and paid compounding fee.",
            },
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_resolved.status_code, 200)
        self.assertEqual(res_resolved.json()["new_status"], "RESOLVED")

        # 6. Attempt to transition from terminal state RESOLVED -> UNDER_REVIEW -> 422
        res_terminal = self.client.patch(
            f"/api/v1/authority/cases/{c.id}/status",
            json={"new_status": "UNDER_REVIEW", "expected_status": "RESOLVED"},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_terminal.status_code, 422)

    def test_missing_or_empty_expected_status_token_rejected_with_422(self) -> None:
        """Requirement: Missing or empty expected_status concurrency token is rejected with 422."""
        c = self.case_repo.save_case(
            ConsumerIssue(
                title="Pune Case",
                status=IssueStatus.SUBMITTED.value,
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        # Missing expected_status entirely
        res_missing = self.client.patch(
            f"/api/v1/authority/cases/{c.id}/status",
            json={"new_status": "UNDER_REVIEW"},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_missing.status_code, 422)

        # Empty whitespace expected_status
        res_empty = self.client.patch(
            f"/api/v1/authority/cases/{c.id}/status",
            json={"new_status": "UNDER_REVIEW", "expected_status": "   "},
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res_empty.status_code, 422)

    def test_concurrent_or_stale_status_update_rejected(self) -> None:
        """When expected_status does not match current state, returns HTTP 409 Conflict."""
        c = self.case_repo.save_case(
            ConsumerIssue(
                title="Pune Case",
                status=IssueStatus.UNDER_REVIEW.value,
                department="LEGAL_METROLOGY",
                state_code="MH",
                district_code="PUNE",
                jurisdiction_verified=True,
            )
        )

        res = self.client.patch(
            f"/api/v1/authority/cases/{c.id}/status",
            json={
                "new_status": "ACTION_TAKEN",
                "resolution_notes": "Action taken notes here.",
                "expected_status": "SUBMITTED",  # Stale client!
            },
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.INVALID_INSPECTION_STATE.value)

    # =====================================================================
    # 6. Database Error Fail-Closed Test
    # =====================================================================

    def test_database_error_fails_closed(self) -> None:
        """If database repository raises an infrastructure error, returns controlled HTTP 500."""
        broken_repo = MagicMock(spec=AuthorityCaseRepository)
        broken_repo.list_cases.side_effect = RuntimeError("Database connection pool exhausted.")

        broken_service = AuthorityCaseService(case_repository=broken_repo, authority_repository=self.auth_repo)
        app.dependency_overrides[get_authority_case_service] = lambda: broken_service

        res = self.client.get(
            "/api/v1/authority/cases",
            headers={"Authorization": f"Bearer {self.officer_pune_token}"},
        )
        self.assertEqual(res.status_code, 500)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.INTERNAL_ERROR.value)


if __name__ == "__main__":
    unittest.main()
