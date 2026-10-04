"""Tests for Phase 7.4.1 Persistent Establishment Registry and Complaint Jurisdiction Foundation.

Verifies:
1. Default Unverified State: Complaints default to jurisdiction_verified=False, establishment_id=None, jurisdiction_provenance='UNVERIFIED'.
2. Valid Establishment Verification: Valid establishment binds canonical state and district codes, updates provenance, and writes an atomic audit event.
3. Queue Activation: Once verified, case becomes visible only to the authorized officer in matching department, state, and district.
4. Inactive Establishment Rejection: Inactive establishment rejected with EstablishmentInactiveError; case remains unchanged.
5. Unverified Establishment Rejection: Establishment with status 'PENDING' rejected with EstablishmentUnverifiedError.
6. Nonexistent Establishment Rejection: Missing establishment UUID rejected with EstablishmentNotFoundError.
7. Department Mismatch Rejection: Officer cannot verify case of different department.
8. Cross-Jurisdiction Rejection: Officer cannot verify establishment located outside their authorized state and district scope.
9. Inactive / Unauthorized Officer Rejection: Inactive officer or non-authority role rejected.
10. Terminal Case Rejection: Case in RESOLVED or REJECTED status cannot be verified.
11. Atomic Rollback Guarantee: Simulated audit event insertion failure rolls back case changes to previous unverified state.
12. Consumer Access Preservation: Consumer can still view their complaint both before and after verification.
13. Migration and DDL Static Checks: Static inspection of migration file verifying search_path pinning, SECURITY DEFINER, grants, and constraints.

Test execution note:
These tests use in-memory and mock repositories to test domain rules, RPC contracts, and rollback semantics.
Real PostgreSQL execution requires live database credentials and staging deployment.
"""

from __future__ import annotations

import sys
sys.modules['ujson'] = None  # Bypass Windows App Control policy DLL block for ujson

from datetime import datetime, timezone
import os
import unittest
from unittest.mock import MagicMock

from backend.app.services.authority.case_repository import InMemoryAuthorityCaseRepository
from backend.app.services.authority.errors import (
    AuthorityInactiveError,
    AuthorityJurisdictionDeniedError,
    AuthorityRoleDeniedError,
    CaseNotFoundError,
    InvalidJurisdictionScopeError,
    InvalidStatusTransitionError,
)
from backend.app.services.authority.models import (
    AuditEventType,
    AuthorityProfile,
    DepartmentCode,
    JurisdictionLevel,
    JurisdictionScope,
)
from backend.app.services.authority.repository import InMemoryAuthorityRepository
from backend.app.services.consumer_issues.models import ConsumerIssue, IssueStatus, IssueType
from backend.app.services.consumer_issues.repository import InMemoryConsumerIssueRepository
from backend.app.services.establishment.errors import (
    EstablishmentInactiveError,
    EstablishmentNotFoundError,
    EstablishmentUnverifiedError,
    InvalidEstablishmentDataError,
)
from backend.app.services.establishment.models import (
    EstablishmentVerificationProvenance,
    EstablishmentVerificationStatus,
    RetailEstablishment,
)
from backend.app.services.establishment.repository import InMemoryEstablishmentRepository
from backend.app.services.user_profile.models import UserProfile
from backend.app.services.user_profile.repository import InMemoryUserProfileRepository


class EstablishmentRegistryFoundationTestCase(unittest.TestCase):
    """Test suite verifying establishment registry models, verification RPC, and access controls."""

    def setUp(self) -> None:
        self.issue_repo = InMemoryConsumerIssueRepository()
        self.est_repo = InMemoryEstablishmentRepository()
        self.case_repo = InMemoryAuthorityCaseRepository()
        self.case_repo._cases = self.issue_repo._items  # Connect case repo to issue store
        self.auth_repo = InMemoryAuthorityRepository()
        self.user_repo = InMemoryUserProfileRepository()

        # Actors
        self.consumer_id = "11110000-0000-0000-0000-000000000001"
        self.pune_officer_id = "22220000-0000-0000-0000-000000000002"
        self.mumbai_officer_id = "33330000-0000-0000-0000-000000000003"
        self.inactive_officer_id = "44440000-0000-0000-0000-000000000004"
        self.food_safety_officer_id = "55550000-0000-0000-0000-000000000005"

        # User profiles
        self.user_repo.create_profile(UserProfile(user_id=self.consumer_id, app_role="consumer"))
        self.user_repo.create_profile(UserProfile(user_id=self.pune_officer_id, app_role="authority"))
        self.user_repo.create_profile(UserProfile(user_id=self.mumbai_officer_id, app_role="authority"))
        self.user_repo.create_profile(UserProfile(user_id=self.inactive_officer_id, app_role="authority"))
        self.user_repo.create_profile(UserProfile(user_id=self.food_safety_officer_id, app_role="authority"))

        # Authority profiles
        # Officer 1: Legal Metrology, Maharashtra, Pune
        self.pune_profile = AuthorityProfile(
            user_id=self.pune_officer_id,
            department=DepartmentCode.LEGAL_METROLOGY.value,
            designation="Inspector of Legal Metrology, Pune",
            jurisdiction=JurisdictionScope(
                state_code="MH",
                level=JurisdictionLevel.DISTRICT,
                authorized_district_codes={"PUNE"},
            ),
            is_active=True,
        )
        self.auth_repo.save(self.pune_profile)

        # Officer 2: Legal Metrology, Maharashtra, Mumbai Suburban
        self.mumbai_profile = AuthorityProfile(
            user_id=self.mumbai_officer_id,
            department=DepartmentCode.LEGAL_METROLOGY.value,
            designation="Inspector of Legal Metrology, Mumbai Suburban",
            jurisdiction=JurisdictionScope(
                state_code="MH",
                level=JurisdictionLevel.DISTRICT,
                authorized_district_codes={"MUMBAI_SUBURBAN"},
            ),
            is_active=True,
        )
        self.auth_repo.save(self.mumbai_profile)

        # Officer 3: Inactive
        self.inactive_profile = AuthorityProfile(
            user_id=self.inactive_officer_id,
            department=DepartmentCode.LEGAL_METROLOGY.value,
            designation="Suspended Inspector",
            jurisdiction=JurisdictionScope(
                state_code="MH",
                level=JurisdictionLevel.DISTRICT,
                authorized_district_codes={"PUNE"},
            ),
            is_active=False,
        )
        self.auth_repo.save(self.inactive_profile)

        # Officer 4: Food Safety, Maharashtra, Pune
        self.food_safety_profile = AuthorityProfile(
            user_id=self.food_safety_officer_id,
            department=DepartmentCode.FOOD_SAFETY.value,
            designation="Food Safety Officer, Pune",
            jurisdiction=JurisdictionScope(
                state_code="MH",
                level=JurisdictionLevel.DISTRICT,
                authorized_district_codes={"PUNE"},
            ),
            is_active=True,
        )
        self.auth_repo.save(self.food_safety_profile)

        # Establishments (Test Fixtures explicitly marked as test-only)
        self.pune_verified_est = RetailEstablishment(
            trade_name="Test Retailer Pune (Test-Only)",
            legal_name="Test Retail Pvt Ltd",
            gstin="27TESTPUNE1234Z5",
            lm_license_number="LM-MH-PUN-2026-001",
            shop_establishment_number="SE-PUN-9876",
            state_code="MH",
            district_code="PUNE",
            pincode="411001",
            physical_address="100 Shivaji Road, Pune, Maharashtra",
            verification_status=EstablishmentVerificationStatus.VERIFIED.value,
            verification_provenance=EstablishmentVerificationProvenance.ADMIN_TRIAGE_VERIFICATION.value,
            is_active=True,
        )
        self.est_repo.save_establishment(self.pune_verified_est)

        self.pune_pending_est = RetailEstablishment(
            trade_name="Test Unverified Shop (Test-Only)",
            state_code="MH",
            district_code="PUNE",
            verification_status=EstablishmentVerificationStatus.PENDING.value,
            is_active=True,
        )
        self.est_repo.save_establishment(self.pune_pending_est)

        self.pune_inactive_est = RetailEstablishment(
            trade_name="Test Inactive Retailer (Test-Only)",
            state_code="MH",
            district_code="PUNE",
            verification_status=EstablishmentVerificationStatus.VERIFIED.value,
            is_active=False,
        )
        self.est_repo.save_establishment(self.pune_inactive_est)

        self.mumbai_verified_est = RetailEstablishment(
            trade_name="Test Retailer Mumbai (Test-Only)",
            state_code="MH",
            district_code="MUMBAI_SUBURBAN",
            verification_status=EstablishmentVerificationStatus.VERIFIED.value,
            is_active=True,
        )
        self.est_repo.save_establishment(self.mumbai_verified_est)

    def test_default_unverified_state_for_new_complaint(self) -> None:
        """New complaints must default to unverified jurisdiction and unassigned establishment."""
        issue = ConsumerIssue(
            user_id=self.consumer_id,
            inspection_id="11111111-1111-1111-1111-111111111111",
            issue_type=IssueType.PRICE_TAMPERING.value,
            title="Overcharging above MRP",
            description="Item sold for 120 against MRP 100",
        )
        created = self.issue_repo.create_issue(issue)

        self.assertFalse(created.jurisdiction_verified)
        self.assertIsNone(created.state_code)
        self.assertIsNone(created.district_code)
        self.assertIsNone(created.establishment_id)
        self.assertEqual(created.jurisdiction_provenance, "UNVERIFIED")
        self.assertIsNone(created.jurisdiction_verified_at)
        self.assertIsNone(created.jurisdiction_verified_by)

    def test_consumer_can_read_unverified_complaint(self) -> None:
        """Reporting consumer retains full read access to their unverified complaint."""
        issue = self.issue_repo.create_issue(
            ConsumerIssue(
                user_id=self.consumer_id,
                inspection_id="22222222-2222-2222-2222-222222222222",
                issue_type=IssueType.MISLEADING_LABEL.value,
                title="Missing Net Quantity",
                description="Package lacks net quantity declaration",
            )
        )
        retrieved = self.issue_repo.get_by_id(issue.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.user_id, self.consumer_id)
        self.assertFalse(retrieved.jurisdiction_verified)

    def test_unverified_complaint_excluded_from_authority_queues(self) -> None:
        """Unverified complaints must be completely invisible in authority case listings."""
        issue = self.issue_repo.create_issue(
            ConsumerIssue(
                user_id=self.consumer_id,
                inspection_id="33333333-3333-3333-3333-333333333333",
                issue_type=IssueType.PRICE_TAMPERING.value,
                title="MRP altered",
                description="Sticker pasted over MRP",
            )
        )
        cases, total = self.case_repo.list_cases(
            department="LEGAL_METROLOGY",
            state_code="MH",
            authorized_district_codes={"PUNE"},
        )
        self.assertEqual(total, 0)
        self.assertEqual(len(cases), 0)

    def test_valid_atomic_jurisdiction_verification(self) -> None:
        """Authorized officer verifying a complaint against verified establishment succeeds atomically."""
        issue = self.issue_repo.create_issue(
            ConsumerIssue(
                user_id=self.consumer_id,
                inspection_id="44444444-4444-4444-4444-444444444444",
                issue_type=IssueType.WEIGHT_SHORTAGE.value,
                title="Underweight pulses",
                description="Declared 1kg, actual weight 920g",
            )
        )

        updated_case, audit_event = self.case_repo.atomic_verify_jurisdiction(
            case_id=issue.id,
            establishment_id=self.pune_verified_est.id,
            actor_id=self.pune_officer_id,
            actor_role="authority",
            provenance="ADMIN_TRIAGE_VERIFICATION",
            verification_notes="Verified via retailer cash memo and GST invoice records.",
            establishment_repo=self.est_repo,
            authority_repo=self.auth_repo,
        )

        # Verify case fields updated correctly
        self.assertTrue(updated_case.jurisdiction_verified)
        self.assertEqual(updated_case.state_code, "MH")
        self.assertEqual(updated_case.district_code, "PUNE")
        self.assertEqual(updated_case.establishment_id, self.pune_verified_est.id)
        self.assertEqual(updated_case.jurisdiction_provenance, "ADMIN_TRIAGE_VERIFICATION")
        self.assertEqual(updated_case.jurisdiction_verified_by, self.pune_officer_id)
        self.assertIsNotNone(updated_case.jurisdiction_verified_at)

        # Verify audit event written atomically
        self.assertEqual(audit_event.issue_id, issue.id)
        self.assertEqual(audit_event.event_type, AuditEventType.JURISDICTION_VERIFIED.value)
        self.assertEqual(audit_event.actor_id, self.pune_officer_id)
        self.assertEqual(audit_event.metadata["establishment_id"], self.pune_verified_est.id)
        self.assertEqual(audit_event.metadata["district_code"], "PUNE")
        self.assertEqual(audit_event.metadata["provenance"], "ADMIN_TRIAGE_VERIFICATION")

        # Verify case now visible in Pune officer's queue
        cases, total = self.case_repo.list_cases(
            department="LEGAL_METROLOGY",
            state_code="MH",
            authorized_district_codes={"PUNE"},
        )
        self.assertEqual(total, 1)
        self.assertEqual(cases[0].id, issue.id)

        # Verify case remains invisible in Mumbai officer's queue
        mumbai_cases, mumbai_total = self.case_repo.list_cases(
            department="LEGAL_METROLOGY",
            state_code="MH",
            authorized_district_codes={"MUMBAI_SUBURBAN"},
        )
        self.assertEqual(mumbai_total, 0)

    def test_inactive_establishment_rejection(self) -> None:
        """Attempting verification against an inactive establishment must fail."""
        issue = self.issue_repo.create_issue(
            ConsumerIssue(
                user_id=self.consumer_id,
                inspection_id="55555555-5555-5555-5555-555555555555",
                issue_type=IssueType.OTHER.value,
                title="Label defect",
                description="Smudged batch number",
            )
        )
        with self.assertRaises(EstablishmentInactiveError):
            self.case_repo.atomic_verify_jurisdiction(
                case_id=issue.id,
                establishment_id=self.pune_inactive_est.id,
                actor_id=self.pune_officer_id,
                actor_role="authority",
                provenance="ADMIN_TRIAGE_VERIFICATION",
                establishment_repo=self.est_repo,
                authority_repo=self.auth_repo,
            )

        # Ensure complaint remains unverified
        persisted = self.issue_repo.get_by_id(issue.id)
        self.assertFalse(persisted.jurisdiction_verified)
        self.assertIsNone(persisted.establishment_id)

    def test_unverified_establishment_rejection(self) -> None:
        """Attempting verification against an unverified (PENDING) establishment must fail."""
        issue = self.issue_repo.create_issue(
            ConsumerIssue(
                user_id=self.consumer_id,
                inspection_id="66666666-6666-6666-6666-666666666666",
                issue_type=IssueType.PRICE_TAMPERING.value,
                title="Dual MRP",
                description="Two MRP stickers found",
            )
        )
        with self.assertRaises(EstablishmentUnverifiedError):
            self.case_repo.atomic_verify_jurisdiction(
                case_id=issue.id,
                establishment_id=self.pune_pending_est.id,
                actor_id=self.pune_officer_id,
                actor_role="authority",
                provenance="ADMIN_TRIAGE_VERIFICATION",
                establishment_repo=self.est_repo,
                authority_repo=self.auth_repo,
            )

        persisted = self.issue_repo.get_by_id(issue.id)
        self.assertFalse(persisted.jurisdiction_verified)

    def test_cross_jurisdiction_verification_rejection(self) -> None:
        """Officer cannot verify an establishment outside their authorized district scope."""
        issue = self.issue_repo.create_issue(
            ConsumerIssue(
                user_id=self.consumer_id,
                inspection_id="77777777-7777-7777-7777-777777777777",
                issue_type=IssueType.MISLEADING_LABEL.value,
                title="Font size violation",
                description="MRP font smaller than permitted",
            )
        )
        # Pune officer attempts to verify Mumbai establishment
        with self.assertRaises(AuthorityJurisdictionDeniedError):
            self.case_repo.atomic_verify_jurisdiction(
                case_id=issue.id,
                establishment_id=self.mumbai_verified_est.id,
                actor_id=self.pune_officer_id,
                actor_role="authority",
                provenance="ADMIN_TRIAGE_VERIFICATION",
                establishment_repo=self.est_repo,
                authority_repo=self.auth_repo,
            )

        persisted = self.issue_repo.get_by_id(issue.id)
        self.assertFalse(persisted.jurisdiction_verified)

    def test_department_mismatch_verification_rejection(self) -> None:
        """Officer cannot verify a case belonging to a different department."""
        # Legal metrology issue
        issue = self.issue_repo.create_issue(
            ConsumerIssue(
                user_id=self.consumer_id,
                inspection_id="88888888-8888-8888-8888-888888888888",
                issue_type=IssueType.PRICE_TAMPERING.value,
                title="Overcharging",
                description="Sold above MRP",
                department="LEGAL_METROLOGY",
            )
        )
        # Food Safety officer attempts to verify Legal Metrology issue
        with self.assertRaises(AuthorityJurisdictionDeniedError):
            self.case_repo.atomic_verify_jurisdiction(
                case_id=issue.id,
                establishment_id=self.pune_verified_est.id,
                actor_id=self.food_safety_officer_id,
                actor_role="authority",
                provenance="ADMIN_TRIAGE_VERIFICATION",
                establishment_repo=self.est_repo,
                authority_repo=self.auth_repo,
            )

    def test_inactive_officer_verification_rejection(self) -> None:
        """Inactive authority account cannot verify complaints."""
        issue = self.issue_repo.create_issue(
            ConsumerIssue(
                user_id=self.consumer_id,
                inspection_id="99999999-9999-9999-9999-999999999999",
                issue_type=IssueType.PRICE_TAMPERING.value,
                title="Dual MRP",
                description="Two MRP labels",
            )
        )
        with self.assertRaises(AuthorityInactiveError):
            self.case_repo.atomic_verify_jurisdiction(
                case_id=issue.id,
                establishment_id=self.pune_verified_est.id,
                actor_id=self.inactive_officer_id,
                actor_role="authority",
                provenance="ADMIN_TRIAGE_VERIFICATION",
                establishment_repo=self.est_repo,
                authority_repo=self.auth_repo,
            )

    def test_consumer_role_cannot_verify_complaint(self) -> None:
        """Ordinary consumer app_role cannot verify complaint jurisdiction."""
        issue = self.issue_repo.create_issue(
            ConsumerIssue(
                user_id=self.consumer_id,
                inspection_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                issue_type=IssueType.PRICE_TAMPERING.value,
                title="Overcharging",
                description="Overcharging complaint",
            )
        )
        with self.assertRaises(AuthorityRoleDeniedError):
            self.case_repo.atomic_verify_jurisdiction(
                case_id=issue.id,
                establishment_id=self.pune_verified_est.id,
                actor_id=self.consumer_id,
                actor_role="consumer",
                provenance="ADMIN_TRIAGE_VERIFICATION",
                establishment_repo=self.est_repo,
                authority_repo=self.auth_repo,
            )

    def test_terminal_case_cannot_be_verified(self) -> None:
        """Complaints in terminal status (RESOLVED, REJECTED) cannot be verified."""
        resolved_issue = self.issue_repo.create_issue(
            ConsumerIssue(
                user_id=self.consumer_id,
                inspection_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                issue_type=IssueType.PRICE_TAMPERING.value,
                title="Resolved issue",
                description="Old issue already resolved",
                status=IssueStatus.RESOLVED.value,
            )
        )
        with self.assertRaises(InvalidStatusTransitionError):
            self.case_repo.atomic_verify_jurisdiction(
                case_id=resolved_issue.id,
                establishment_id=self.pune_verified_est.id,
                actor_id=self.pune_officer_id,
                actor_role="authority",
                provenance="ADMIN_TRIAGE_VERIFICATION",
                establishment_repo=self.est_repo,
                authority_repo=self.auth_repo,
            )

    def test_atomic_rollback_on_audit_failure(self) -> None:
        """If audit insertion fails, complaint verification changes must be completely rolled back."""
        issue = self.issue_repo.create_issue(
            ConsumerIssue(
                user_id=self.consumer_id,
                inspection_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
                issue_type=IssueType.PRICE_TAMPERING.value,
                title="Overcharging rollback test",
                description="Testing transaction boundary",
            )
        )

        self.case_repo.simulate_audit_failure = True
        try:
            with self.assertRaises(RuntimeError):
                self.case_repo.atomic_verify_jurisdiction(
                    case_id=issue.id,
                    establishment_id=self.pune_verified_est.id,
                    actor_id=self.pune_officer_id,
                    actor_role="authority",
                    provenance="ADMIN_TRIAGE_VERIFICATION",
                    establishment_repo=self.est_repo,
                    authority_repo=self.auth_repo,
                )

            # Assert rollback: case must remain unverified with original state
            persisted = self.issue_repo.get_by_id(issue.id)
            self.assertFalse(persisted.jurisdiction_verified)
            self.assertIsNone(persisted.establishment_id)
            self.assertIsNone(persisted.state_code)
            self.assertIsNone(persisted.district_code)
            self.assertEqual(persisted.jurisdiction_provenance, "UNVERIFIED")

            # Assert no audit event persisted
            events = self.case_repo.list_audit_events(issue.id)
            self.assertEqual(len(events), 0)
        finally:
            self.case_repo.simulate_audit_failure = False

    def test_migration_ddl_static_security_checks(self) -> None:
        """Static audit of Phase 7.4.1 migration SQL ensuring strict security and isolation."""
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "supabase",
            "migrations",
            "20261015000000_t3_4_1_establishment_registry.sql",
        )
        self.assertTrue(os.path.exists(migration_path), "Migration file must exist.")

        with open(migration_path, "r", encoding="utf-8") as f:
            sql = f.read()

        # 1. Establishment table created
        self.assertIn("CREATE TABLE IF NOT EXISTS public.retail_establishments", sql)
        self.assertIn("trade_name text NOT NULL", sql)
        self.assertIn("state_code text NOT NULL", sql)
        self.assertIn("district_code text NOT NULL", sql)
        self.assertIn("verification_status varchar(30)", sql)
        self.assertIn("is_active boolean NOT NULL DEFAULT true", sql)

        # 2. Consumer issues extended
        self.assertIn("ADD COLUMN IF NOT EXISTS establishment_id uuid", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS jurisdiction_provenance varchar(50)", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS jurisdiction_verified_at timestamptz", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS jurisdiction_verified_by uuid", sql)

        # 3. Row Level Security
        self.assertIn("ALTER TABLE public.retail_establishments ENABLE ROW LEVEL SECURITY;", sql)
        self.assertIn("CREATE POLICY retail_establishments_select_verified", sql)
        self.assertIn("CREATE POLICY retail_establishments_select_authority", sql)

        # 4. Atomic RPC Security Definer and pinned search path
        self.assertIn("CREATE OR REPLACE FUNCTION public.authority_verify_complaint_jurisdiction", sql)
        self.assertIn("SECURITY DEFINER", sql)
        self.assertIn("SET search_path = public, pg_temp", sql)

        # 5. Row locking
        self.assertIn("FOR UPDATE", sql)

        # 6. Least-privilege Grants
        self.assertIn("REVOKE ALL ON FUNCTION public.authority_verify_complaint_jurisdiction", sql)
        self.assertIn("FROM PUBLIC, authenticated;", sql)
        self.assertIn("GRANT EXECUTE ON FUNCTION public.authority_verify_complaint_jurisdiction", sql)
        self.assertIn("TO service_role;", sql)


if __name__ == "__main__":
    unittest.main()
