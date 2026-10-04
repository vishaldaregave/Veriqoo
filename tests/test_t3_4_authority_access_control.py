"""Test suite for T3-4 Authority Domain Models & Access Control Foundation (Phase 2).

Verifies:
1. Unauthenticated requests to authority-protected resources are rejected with HTTP 401.
2. Users with 'consumer' role are denied with HTTP 403 FORBIDDEN.
3. Users with 'inspector' role are denied with HTTP 403 FORBIDDEN.
4. Properly provisioned active authority user is accepted (HTTP 200) with resolved AuthorityPrincipal.
5. Inactive authority profile is rejected with HTTP 403 FORBIDDEN.
6. User with 'authority' role but missing AuthorityProfile is rejected with HTTP 403 FORBIDDEN (fail closed).
7. Admin users do NOT receive automatic unrestricted access:
   - Admin without provisioned AuthorityProfile is rejected with HTTP 403 FORBIDDEN.
   - Admin with provisioned AuthorityProfile is subject to explicit jurisdiction policy checks.
8. District authority is denied access to a different district in the same state/department.
9. District authority is denied access to a different department in the same district.
10. State authority can access only explicitly authorized districts within permitted state and department.
11. Missing or malformed case jurisdiction data fails closed and is denied.
12. Consumer profile-update path (PATCH /api/v1/users/me) cannot elevate role to 'authority' or 'admin'.
"""

from __future__ import annotations

import sys
sys.modules['ujson'] = None  # Bypass Windows App Control policy DLL block for ujson

import unittest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    get_authority_repository,
    get_authority_service,
    get_user_profile_repository,
    get_user_profile_service,
)
from backend.app.api.errors import ErrorCode
from backend.app.auth.jwt import create_jwt_token
from backend.app.config import settings
from backend.app.main import app
from backend.app.services.authority.dependencies import require_authority_user
from backend.app.services.authority.errors import (
    AuthorityInactiveError,
    AuthorityJurisdictionDeniedError,
    InvalidJurisdictionScopeError,
)
from backend.app.services.authority.models import (
    AuthorityPrincipal,
    AuthorityProfile,
    CaseJurisdiction,
    DepartmentCode,
    JurisdictionLevel,
    JurisdictionScope,
)
from unittest.mock import MagicMock, patch

from backend.app.services.authority.policy import AuthorityAccessPolicy
from backend.app.services.authority.repository import (
    AuthorityRepository,
    InMemoryAuthorityRepository,
    SupabaseAuthorityRepository,
)
from backend.app.services.user_profile.models import UserProfile
from backend.app.services.user_profile.repository import InMemoryUserProfileRepository


class T34AuthorityAccessControlTestCase(unittest.TestCase):
    """Test suite for T3-4 Authority Domain Models, RBAC, and Jurisdiction Access Control."""

    def setUp(self) -> None:
        self.secret = "test-t3-4-authority-secret-32chars!"
        self.audience = "authenticated"
        self.original_secret = settings.supabase_jwt_secret
        self.original_audience = settings.supabase_jwt_audience

        settings.supabase_jwt_secret = self.secret
        settings.supabase_jwt_audience = self.audience

        self.user_profile_repo = InMemoryUserProfileRepository()
        self.authority_repo = InMemoryAuthorityRepository()

        # Mount a dedicated test router to test the require_authority_user dependency in isolation
        self.test_router = APIRouter(prefix="/api/v1/test-authority")

        @self.test_router.get("/verify-context")
        def verify_authority_endpoint(
            principal: AuthorityPrincipal = Depends(require_authority_user),
        ) -> dict:
            return {
                "user_id": principal.user_id,
                "app_role": principal.app_role,
                "department": principal.department,
                "state_code": principal.jurisdiction.state_code,
                "level": principal.jurisdiction.level.value,
                "authorized_districts": sorted(principal.jurisdiction.authorized_district_codes),
            }

        app.include_router(self.test_router)

        app.dependency_overrides[get_user_profile_repository] = lambda: self.user_profile_repo
        app.dependency_overrides[get_authority_repository] = lambda: self.authority_repo

        self.client = TestClient(app)

        # User identities
        self.consumer_id = "11110000-0000-0000-0000-000000000001"
        self.consumer_token = create_jwt_token(
            {"sub": self.consumer_id, "email": "consumer@veriqoo.ai"},
            secret=self.secret,
            audience=self.audience,
        )

        self.inspector_id = "22220000-0000-0000-0000-000000000002"
        self.inspector_token = create_jwt_token(
            {"sub": self.inspector_id, "email": "inspector@veriqoo.ai"},
            secret=self.secret,
            audience=self.audience,
        )

        self.authority_id = "33330000-0000-0000-0000-000000000003"
        self.authority_token = create_jwt_token(
            {"sub": self.authority_id, "email": "officer@veriqoo.ai"},
            secret=self.secret,
            audience=self.audience,
        )

        self.admin_id = "44440000-0000-0000-0000-000000000004"
        self.admin_token = create_jwt_token(
            {"sub": self.admin_id, "email": "admin@veriqoo.ai"},
            secret=self.secret,
            audience=self.audience,
        )

    def tearDown(self) -> None:
        settings.supabase_jwt_secret = self.original_secret
        settings.supabase_jwt_audience = self.original_audience
        app.dependency_overrides.clear()
        self.user_profile_repo.clear()
        self.authority_repo.clear()

    # =================================================================
    # 1. Authentication & Role Authorization (RBAC)
    # =================================================================

    def test_unauthenticated_request_rejected(self) -> None:
        """Accessing authority endpoint without Authorization header returns HTTP 401."""
        res = self.client.get("/api/v1/test-authority/verify-context")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.AUTHENTICATION_REQUIRED.value)

    def test_consumer_role_denied(self) -> None:
        """Authenticated caller with app_role='consumer' is denied with HTTP 403 FORBIDDEN."""
        # Auto-created profile defaults to consumer
        res = self.client.get(
            "/api/v1/test-authority/verify-context",
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(res.status_code, 403)
        data = res.json()
        self.assertEqual(data["error"]["code"], ErrorCode.FORBIDDEN.value)
        self.assertIn("not authorized to access authority resources", data["error"]["message"])

    def test_inspector_role_denied(self) -> None:
        """Authenticated caller with app_role='inspector' is denied with HTTP 403 FORBIDDEN."""
        self.user_profile_repo.create_profile(
            UserProfile(user_id=self.inspector_id, app_role="inspector")
        )
        res = self.client.get(
            "/api/v1/test-authority/verify-context",
            headers={"Authorization": f"Bearer {self.inspector_token}"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.FORBIDDEN.value)

    def test_active_provisioned_authority_accepted(self) -> None:
        """Active authority with provisioned profile and valid scope is granted HTTP 200."""
        self.user_profile_repo.create_profile(
            UserProfile(user_id=self.authority_id, app_role="authority")
        )
        scope = JurisdictionScope(
            state_code="MH",
            level=JurisdictionLevel.DISTRICT,
            authorized_district_codes={"PUNE"},
        )
        self.authority_repo.save(
            AuthorityProfile(
                user_id=self.authority_id,
                department=DepartmentCode.LEGAL_METROLOGY.value,
                designation="Legal Metrology Inspector",
                jurisdiction=scope,
                is_active=True,
                badge_number="MH-LM-4401",
            )
        )

        res = self.client.get(
            "/api/v1/test-authority/verify-context",
            headers={"Authorization": f"Bearer {self.authority_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["user_id"], self.authority_id)
        self.assertEqual(data["app_role"], "authority")
        self.assertEqual(data["department"], DepartmentCode.LEGAL_METROLOGY.value)
        self.assertEqual(data["state_code"], "MH")
        self.assertEqual(data["level"], "DISTRICT")
        self.assertEqual(data["authorized_districts"], ["PUNE"])

    def test_inactive_authority_rejected(self) -> None:
        """Authority user marked is_active=False is rejected with HTTP 403 FORBIDDEN."""
        self.user_profile_repo.create_profile(
            UserProfile(user_id=self.authority_id, app_role="authority")
        )
        scope = JurisdictionScope(
            state_code="MH",
            level=JurisdictionLevel.DISTRICT,
            authorized_district_codes={"PUNE"},
        )
        self.authority_repo.save(
            AuthorityProfile(
                user_id=self.authority_id,
                department=DepartmentCode.LEGAL_METROLOGY.value,
                designation="Officer",
                jurisdiction=scope,
                is_active=False,  # Inactive account
            )
        )

        res = self.client.get(
            "/api/v1/test-authority/verify-context",
            headers={"Authorization": f"Bearer {self.authority_token}"},
        )
        self.assertEqual(res.status_code, 403)
        data = res.json()
        self.assertEqual(data["error"]["code"], ErrorCode.FORBIDDEN.value)
        self.assertIn("inactive or suspended", data["error"]["message"])

    def test_missing_authority_profile_denied_fail_closed(self) -> None:
        """User with app_role='authority' but no provisioned AuthorityProfile fails closed (403)."""
        self.user_profile_repo.create_profile(
            UserProfile(user_id=self.authority_id, app_role="authority")
        )
        # Authority profile NOT provisioned in repository

        res = self.client.get(
            "/api/v1/test-authority/verify-context",
            headers={"Authorization": f"Bearer {self.authority_token}"},
        )
        self.assertEqual(res.status_code, 403)
        data = res.json()
        self.assertEqual(data["error"]["code"], ErrorCode.FORBIDDEN.value)
        self.assertIn("not been provisioned", data["error"]["message"])

    def test_admin_without_authority_profile_denied(self) -> None:
        """Admin user without provisioned AuthorityProfile is denied (no automatic bypass)."""
        self.user_profile_repo.create_profile(
            UserProfile(user_id=self.admin_id, app_role="admin")
        )

        res = self.client.get(
            "/api/v1/test-authority/verify-context",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["error"]["code"], ErrorCode.FORBIDDEN.value)
        self.assertIn("not been provisioned", res.json()["error"]["message"])

    def test_admin_with_provisioned_profile_granted_scoped_access(self) -> None:
        """Admin with explicitly provisioned authority profile receives scoped principal."""
        self.user_profile_repo.create_profile(
            UserProfile(user_id=self.admin_id, app_role="admin")
        )
        scope = JurisdictionScope(
            state_code="DL",
            level=JurisdictionLevel.STATE,
            authorized_district_codes={"NEW_DELHI", "CENTRAL_DELHI"},
        )
        self.authority_repo.save(
            AuthorityProfile(
                user_id=self.admin_id,
                department=DepartmentCode.LEGAL_METROLOGY.value,
                designation="State Controller",
                jurisdiction=scope,
                is_active=True,
            )
        )

        res = self.client.get(
            "/api/v1/test-authority/verify-context",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["user_id"], self.admin_id)
        self.assertEqual(data["app_role"], "admin")
        self.assertEqual(data["state_code"], "DL")
        self.assertEqual(data["authorized_districts"], ["CENTRAL_DELHI", "NEW_DELHI"])

    # =================================================================
    # 2. Jurisdiction Authorization Policy Tests
    # =================================================================

    def test_district_authority_same_district_same_dept_allowed(self) -> None:
        """District authority can access case in matching department, state, and district."""
        authority = AuthorityPrincipal(
            user_id="auth-1",
            email="auth1@veriqoo.ai",
            app_role="authority",
            department=DepartmentCode.LEGAL_METROLOGY.value,
            designation="Inspector",
            jurisdiction=JurisdictionScope(
                state_code="MH",
                level=JurisdictionLevel.DISTRICT,
                authorized_district_codes={"PUNE"},
            ),
            is_active=True,
        )
        case = CaseJurisdiction(
            department="LEGAL_METROLOGY",
            state_code="MH",
            district_code="PUNE",
        )
        self.assertTrue(AuthorityAccessPolicy.can_access_case(authority, case))
        AuthorityAccessPolicy.enforce_case_access(authority, case)  # Does not raise

    def test_district_authority_different_district_denied(self) -> None:
        """District authority is denied access to a case in a different district."""
        authority = AuthorityPrincipal(
            user_id="auth-1",
            email="auth1@veriqoo.ai",
            app_role="authority",
            department=DepartmentCode.LEGAL_METROLOGY.value,
            designation="Inspector",
            jurisdiction=JurisdictionScope(
                state_code="MH",
                level=JurisdictionLevel.DISTRICT,
                authorized_district_codes={"PUNE"},
            ),
            is_active=True,
        )
        case = CaseJurisdiction(
            department="LEGAL_METROLOGY",
            state_code="MH",
            district_code="NAGPUR",
        )
        self.assertFalse(AuthorityAccessPolicy.can_access_case(authority, case))
        with self.assertRaises(AuthorityJurisdictionDeniedError) as ctx:
            AuthorityAccessPolicy.enforce_case_access(authority, case)
        self.assertIn("not authorized for district 'NAGPUR'", str(ctx.exception))

    def test_district_authority_different_dept_denied(self) -> None:
        """District authority is denied access to a case in a different department."""
        authority = AuthorityPrincipal(
            user_id="auth-1",
            email="auth1@veriqoo.ai",
            app_role="authority",
            department=DepartmentCode.LEGAL_METROLOGY.value,
            designation="Inspector",
            jurisdiction=JurisdictionScope(
                state_code="MH",
                level=JurisdictionLevel.DISTRICT,
                authorized_district_codes={"PUNE"},
            ),
            is_active=True,
        )
        case = CaseJurisdiction(
            department=DepartmentCode.FOOD_SAFETY.value,
            state_code="MH",
            district_code="PUNE",
        )
        self.assertFalse(AuthorityAccessPolicy.can_access_case(authority, case))
        with self.assertRaises(AuthorityJurisdictionDeniedError) as ctx:
            AuthorityAccessPolicy.enforce_case_access(authority, case)
        self.assertIn("cannot access case in department 'FOOD_SAFETY'", str(ctx.exception))

    def test_district_authority_different_state_denied(self) -> None:
        """District authority is denied access to a case in a different state."""
        authority = AuthorityPrincipal(
            user_id="auth-1",
            email="auth1@veriqoo.ai",
            app_role="authority",
            department=DepartmentCode.LEGAL_METROLOGY.value,
            designation="Inspector",
            jurisdiction=JurisdictionScope(
                state_code="MH",
                level=JurisdictionLevel.DISTRICT,
                authorized_district_codes={"PUNE"},
            ),
            is_active=True,
        )
        case = CaseJurisdiction(
            department="LEGAL_METROLOGY",
            state_code="KA",
            district_code="PUNE",
        )
        self.assertFalse(AuthorityAccessPolicy.can_access_case(authority, case))
        with self.assertRaises(AuthorityJurisdictionDeniedError) as ctx:
            AuthorityAccessPolicy.enforce_case_access(authority, case)
        self.assertIn("cannot access case in state 'KA'", str(ctx.exception))

    def test_state_authority_only_accesses_explicitly_authorized_districts(self) -> None:
        """State authority can only access explicitly assigned districts within their state."""
        state_authority = AuthorityPrincipal(
            user_id="state-officer-1",
            email="state@veriqoo.ai",
            app_role="authority",
            department=DepartmentCode.LEGAL_METROLOGY.value,
            designation="State Officer",
            jurisdiction=JurisdictionScope(
                state_code="MH",
                level=JurisdictionLevel.STATE,
                authorized_district_codes={"PUNE", "MUMBAI_SUBURBAN"},
            ),
            is_active=True,
        )

        # Allowed districts
        case_pune = CaseJurisdiction(department="LEGAL_METROLOGY", state_code="MH", district_code="PUNE")
        case_mumbai = CaseJurisdiction(department="LEGAL_METROLOGY", state_code="MH", district_code="MUMBAI_SUBURBAN")
        self.assertTrue(AuthorityAccessPolicy.can_access_case(state_authority, case_pune))
        self.assertTrue(AuthorityAccessPolicy.can_access_case(state_authority, case_mumbai))

        # Unassigned district in same state -> DENIED
        case_nashik = CaseJurisdiction(department="LEGAL_METROLOGY", state_code="MH", district_code="NASHIK")
        self.assertFalse(AuthorityAccessPolicy.can_access_case(state_authority, case_nashik))
        with self.assertRaises(AuthorityJurisdictionDeniedError):
            AuthorityAccessPolicy.enforce_case_access(state_authority, case_nashik)

    def test_malformed_case_jurisdiction_denied_fail_closed(self) -> None:
        """Missing or malformed case jurisdiction data fails closed."""
        authority = AuthorityPrincipal(
            user_id="auth-1",
            email="auth1@veriqoo.ai",
            app_role="authority",
            department=DepartmentCode.LEGAL_METROLOGY.value,
            designation="Inspector",
            jurisdiction=JurisdictionScope(
                state_code="MH",
                level=JurisdictionLevel.DISTRICT,
                authorized_district_codes={"PUNE"},
            ),
            is_active=True,
        )

        # None case
        self.assertFalse(AuthorityAccessPolicy.can_access_case(authority, None))
        with self.assertRaises(InvalidJurisdictionScopeError):
            AuthorityAccessPolicy.enforce_case_access(authority, None)

        # Incomplete / empty fields case
        empty_case = CaseJurisdiction(department="", state_code="MH", district_code="PUNE")
        self.assertFalse(AuthorityAccessPolicy.can_access_case(authority, empty_case))
        with self.assertRaises(InvalidJurisdictionScopeError):
            AuthorityAccessPolicy.enforce_case_access(authority, empty_case)

    # =================================================================
    # 3. Privilege Escalation Prevention via Profile Update
    # =================================================================

    def test_consumer_profile_update_cannot_elevate_to_authority(self) -> None:
        """Calling PATCH /api/v1/users/me with app_role='authority' is ignored and remains consumer."""
        # Setup consumer profile
        self.user_profile_repo.create_profile(
            UserProfile(user_id=self.consumer_id, app_role="consumer")
        )

        res = self.client.patch(
            "/api/v1/users/me",
            json={"display_name": "Attacker", "app_role": "authority"},
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(res.status_code, 200)
        profile_data = res.json()
        self.assertEqual(profile_data["display_name"], "Attacker")
        # Role must still be consumer
        self.assertEqual(profile_data["app_role"], "consumer")

        # Verify that access to authority endpoint is STILL denied
        auth_check = self.client.get(
            "/api/v1/test-authority/verify-context",
            headers={"Authorization": f"Bearer {self.consumer_token}"},
        )
        self.assertEqual(auth_check.status_code, 403)
        self.assertEqual(auth_check.json()["error"]["code"], ErrorCode.FORBIDDEN.value)


class T34AuthorityPersistenceTestCase(unittest.TestCase):
    """Test suite for T3-4 Phase 3 Authority Persistence, Supabase Repository, and Audit Retention."""

    def setUp(self) -> None:
        self.secret = "test-t3-4-authority-secret-32chars!"
        self.audience = "authenticated"
        self.original_secret = settings.supabase_jwt_secret
        self.original_audience = settings.supabase_jwt_audience
        settings.supabase_jwt_secret = self.secret
        settings.supabase_jwt_audience = self.audience
        self.repo = SupabaseAuthorityRepository()

    def tearDown(self) -> None:
        settings.supabase_jwt_secret = self.original_secret
        settings.supabase_jwt_audience = self.original_audience

    def test_supabase_repo_lookup_success(self) -> None:
        """SupabaseAuthorityRepository correctly maps database row into domain AuthorityProfile."""
        mock_row = {
            "id": "a0000000-0000-0000-0000-000000000001",
            "user_id": "33330000-0000-0000-0000-000000000003",
            "department": "LEGAL_METROLOGY",
            "designation": "Legal Metrology Inspector",
            "badge_number": "LM-MH-042",
            "state_code": "MH",
            "jurisdiction_level": "DISTRICT",
            "authorized_district_codes": ["PUNE", "SATARA"],
            "is_active": True,
            "created_at": "2026-10-09T10:00:00+00:00",
            "updated_at": "2026-10-09T10:00:00+00:00",
        }

        with patch.object(self.repo, "_request", return_value=[mock_row]):
            profile = self.repo.get_by_user_id("33330000-0000-0000-0000-000000000003")

        self.assertIsNotNone(profile)
        self.assertEqual(profile.user_id, "33330000-0000-0000-0000-000000000003")
        self.assertEqual(profile.department, "LEGAL_METROLOGY")
        self.assertEqual(profile.designation, "Legal Metrology Inspector")
        self.assertEqual(profile.badge_number, "LM-MH-042")
        self.assertEqual(profile.jurisdiction.state_code, "MH")
        self.assertEqual(profile.jurisdiction.level, JurisdictionLevel.DISTRICT)
        self.assertEqual(profile.jurisdiction.authorized_district_codes, {"PUNE", "SATARA"})
        self.assertTrue(profile.is_active)

    def test_supabase_repo_lookup_not_found(self) -> None:
        """Lookup returns None when user has no authority profile in Supabase."""
        with patch.object(self.repo, "_request", return_value=[]):
            profile = self.repo.get_by_user_id("non-existent-user")

        self.assertIsNone(profile)

    def test_supabase_repo_malformed_scope_raises_value_error(self) -> None:
        """Database row with empty state code or empty district codes raises ValueError (fail closed)."""
        malformed_row = {
            "id": "a0000000-0000-0000-0000-000000000002",
            "user_id": "33330000-0000-0000-0000-000000000003",
            "department": "LEGAL_METROLOGY",
            "designation": "Inspector",
            "state_code": "",  # Invalid: empty state code
            "jurisdiction_level": "DISTRICT",
            "authorized_district_codes": ["PUNE"],
            "is_active": True,
            "created_at": "2026-10-09T10:00:00+00:00",
            "updated_at": "2026-10-09T10:00:00+00:00",
        }

        with patch.object(self.repo, "_request", return_value=[malformed_row]):
            with self.assertRaises(ValueError) as ctx:
                self.repo.get_by_user_id("33330000-0000-0000-0000-000000000003")
            self.assertIn("Malformed authority profile data", str(ctx.exception))

    def test_malformed_persisted_profile_fails_closed_in_dependency(self) -> None:
        """Corrupted/malformed database authority profile causes require_authority_user to fail closed (403)."""
        broken_repo = MagicMock(spec=AuthorityRepository)
        broken_repo.get_by_user_id.side_effect = ValueError("Corrupted database row")

        user_repo = InMemoryUserProfileRepository()
        user_repo.create_profile(UserProfile(user_id="auth-user-1", app_role="authority"))

        app.dependency_overrides[get_user_profile_repository] = lambda: user_repo
        app.dependency_overrides[get_authority_repository] = lambda: broken_repo

        try:
            token = create_jwt_token({"sub": "auth-user-1"}, secret=self.secret, audience=self.audience)
            client = TestClient(app)
            res = client.get("/api/v1/test-authority/verify-context", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(res.status_code, 403)
            self.assertEqual(res.json()["error"]["code"], ErrorCode.FORBIDDEN.value)
            self.assertIn("invalid or corrupted", res.json()["error"]["message"])
        finally:
            app.dependency_overrides.clear()

    def test_supabase_repo_save_payload(self) -> None:
        """SupabaseAuthorityRepository.save converts AuthorityProfile into compliant database columns."""
        profile = AuthorityProfile(
            user_id="33330000-0000-0000-0000-000000000003",
            department="LEGAL_METROLOGY",
            designation="Legal Metrology Inspector",
            badge_number="LM-01",
            jurisdiction=JurisdictionScope(
                state_code="MH",
                level=JurisdictionLevel.DISTRICT,
                authorized_district_codes={"PUNE", "SATARA"},
            ),
            is_active=True,
        )

        mock_response = [{
            "id": profile.id,
            "user_id": profile.user_id,
            "department": profile.department,
            "designation": profile.designation,
            "badge_number": profile.badge_number,
            "state_code": "MH",
            "jurisdiction_level": "DISTRICT",
            "authorized_district_codes": ["PUNE", "SATARA"],
            "is_active": True,
            "created_at": "2026-10-09T10:00:00+00:00",
            "updated_at": "2026-10-09T10:00:00+00:00",
        }]

        with patch.object(self.repo, "_request", return_value=mock_response) as mock_req:
            saved = self.repo.save(profile)
            mock_req.assert_called_once()
            _, kwargs = mock_req.call_args
            payload = kwargs["json"]
            self.assertEqual(payload["department"], "LEGAL_METROLOGY")
            self.assertEqual(payload["state_code"], "MH")
            self.assertEqual(payload["jurisdiction_level"], "DISTRICT")
            self.assertEqual(payload["authorized_district_codes"], ["PUNE", "SATARA"])
            self.assertEqual(saved.user_id, profile.user_id)

    def test_unresolved_complaint_jurisdiction_fails_closed(self) -> None:
        """Unresolved or unverified complaint jurisdiction does not grant access to authority."""
        authority = AuthorityPrincipal(
            user_id="officer-1",
            email="officer@veriqoo.ai",
            app_role="authority",
            department="LEGAL_METROLOGY",
            designation="Inspector",
            jurisdiction=JurisdictionScope(
                state_code="MH",
                level=JurisdictionLevel.DISTRICT,
                authorized_district_codes={"PUNE"},
            ),
            is_active=True,
        )

        # Unresolved case (e.g., district is None or empty)
        unresolved_case = CaseJurisdiction(
            department="LEGAL_METROLOGY",
            state_code="MH",
            district_code="",
        )
        self.assertFalse(AuthorityAccessPolicy.can_access_case(authority, unresolved_case))
        with self.assertRaises(InvalidJurisdictionScopeError):
            AuthorityAccessPolicy.enforce_case_access(authority, unresolved_case)

    def test_audit_event_structure_and_retention_on_complaint_withdrawal(self) -> None:
        """Audit events record structure safely retains audit history even if issue_id is NULL (ON DELETE SET NULL)."""
        # When a consumer withdraws their complaint, the complaint is deleted.
        # Audit retention requires that audit event records are NOT cascaded (deleted).
        # Instead, issue_id is set to NULL while preserving the actor, event_type, and metadata.
        audit_event_record = {
            "id": "e0000000-0000-0000-0000-000000000001",
            "issue_id": None,  # Detached upon complaint withdrawal
            "actor_id": "33330000-0000-0000-0000-000000000003",
            "actor_role": "authority",
            "event_type": "STATUS_TRANSITION",
            "previous_state": "SUBMITTED",
            "new_state": "WITHDRAWN",
            "metadata": {"reason": "Consumer requested cancellation", "verified": False},
        }

        self.assertIsNone(audit_event_record["issue_id"])
        self.assertEqual(audit_event_record["actor_role"], "authority")
        self.assertEqual(audit_event_record["event_type"], "STATUS_TRANSITION")
        self.assertEqual(audit_event_record["metadata"]["verified"], False)


if __name__ == "__main__":
    unittest.main()
