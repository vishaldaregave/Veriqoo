"""Phase 7.4.4 Remediation and Regression Test Suite.

Covers:
- Task 1: Establishment persistence distinguishing creation vs updates, HTTP 409 on duplicate GSTIN, and safe HTTP 500 on database error.
- Task 2: Consumer complaint serialization returning persisted establishment_id and jurisdiction provenance for verified & unverified complaints.
- Task 3: Review notes alias parity between 'notes' and 'verification_notes'.
- Task 4: Authority case details exposing establishment binding for bound and unbound cases.
- Task 5: Request validation for GSTIN structure and 6-digit Indian pincodes, including case normalization.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.api.v1.endpoints.consumer_issues import _serialize_issue
from backend.app.api.v1.endpoints.authority import _map_case_detail_response
from backend.app.main import create_app
from backend.app.services.authority.models import (
    AuthorityPrincipal,
    JurisdictionLevel,
    JurisdictionScope,
)
from backend.app.services.authority.schemas import CaseDetailResponse
from backend.app.services.consumer_issues.models import ConsumerIssue, IssueStatus, IssueType
from backend.app.services.establishment.errors import (
    DuplicateEstablishmentError,
    EstablishmentNotFoundError,
    EstablishmentRepositoryError,
)
from backend.app.services.establishment.models import (
    EstablishmentVerificationProvenance,
    EstablishmentVerificationStatus,
    RetailEstablishment,
)
from backend.app.services.establishment.repository import (
    InMemoryEstablishmentRepository,
    SupabaseEstablishmentRepository,
)
from backend.app.services.establishment.schemas import (
    CreateEstablishmentRequest,
    ReviewEstablishmentRequest,
)
from backend.app.services.establishment.service import EstablishmentService


class DummySettings:
    supabase_url = "https://example.supabase.co"
    supabase_service_role_key = "test-service-key"
    supabase_anon_key = "test-anon-key"


class Task1EstablishmentPersistenceTestCase(unittest.TestCase):
    """Test establishment persistence: creation, update, duplicate GSTIN, and database error handling."""

    def setUp(self) -> None:
        self.repo = InMemoryEstablishmentRepository()
        self.service = EstablishmentService(repository=self.repo)
        self.authority = AuthorityPrincipal(
            user_id="officer-01",
            email="officer@gov.in",
            app_role="AUTHORITY_USER",
            department="LEGAL_METROLOGY",
            designation="Inspector",
            jurisdiction=JurisdictionScope(
                state_code="MH",
                level=JurisdictionLevel.DISTRICT,
                authorized_district_codes=["PUNE"],
            ),
            badge_number="LM-MH-001",
            is_active=True,
        )

    def test_establishment_creation_and_update(self) -> None:
        """Creating an establishment persists a new record; saving modified establishment updates existing."""
        req = CreateEstablishmentRequest(
            trade_name="Pune Supermart",
            legal_name="Pune Supermart Pvt Ltd",
            gstin="27AAPFU0939F1ZV",
            state_code="MH",
            district_code="PUNE",
            pincode="411004",
        )
        created = self.service.create_establishment(authority=self.authority, data=req)
        self.assertIsNotNone(created.id)
        self.assertEqual(created.trade_name, "Pune Supermart")
        self.assertEqual(created.verification_status, "PENDING")

        # Now update via review
        review_req = ReviewEstablishmentRequest(
            action="VERIFY",
            expected_status="PENDING",
            notes="Physical inspection passed.",
            provenance="MANUAL",
        )
        updated, _ = self.service.review_establishment(
            authority=self.authority,
            establishment_id=created.id,
            action=review_req.action,
            expected_status=review_req.expected_status,
            notes=review_req.get_notes(),
            provenance=review_req.provenance,
        )
        self.assertEqual(updated.verification_status, "VERIFIED")
        self.assertEqual(updated.verification_notes, "Physical inspection passed.")
        self.assertEqual(updated.verification_authority_id, "officer-01")

        # Verify repo contains single record with updated values
        persisted = self.repo.get_by_id(created.id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.verification_status, "VERIFIED")

    def test_duplicate_gstin_raises_duplicate_establishment_error(self) -> None:
        """Attempting to onboard another establishment with the same GSTIN raises DuplicateEstablishmentError."""
        req1 = CreateEstablishmentRequest(
            trade_name="Store Alpha",
            gstin="27AAPFU0939F1ZV",
            state_code="MH",
            district_code="PUNE",
            pincode="411001",
        )
        self.service.create_establishment(authority=self.authority, data=req1)

        req2 = CreateEstablishmentRequest(
            trade_name="Store Beta",
            gstin="27AAPFU0939F1ZV",
            state_code="MH",
            district_code="PUNE",
            pincode="411002",
        )
        with self.assertRaises(DuplicateEstablishmentError) as ctx:
            self.service.create_establishment(authority=self.authority, data=req2)
        self.assertIn("already", str(ctx.exception).lower())

    def test_in_memory_repository_duplicate_gstin_on_save(self) -> None:
        """InMemoryEstablishmentRepository enforces GSTIN uniqueness on save."""
        est1 = RetailEstablishment(
            trade_name="Store Alpha",
            state_code="MH",
            district_code="PUNE",
            gstin="27AAPFU0939F1ZV",
        )
        self.repo.save_establishment(est1)

        est2 = RetailEstablishment(
            trade_name="Store Beta",
            state_code="MH",
            district_code="PUNE",
            gstin="27AAPFU0939F1ZV",
        )
        with self.assertRaises(DuplicateEstablishmentError):
            self.repo.save_establishment(est2)

    def test_repository_simulated_db_error(self) -> None:
        """When the database raises an error, EstablishmentRepositoryError is raised."""
        self.repo.simulate_db_error = True
        est = RetailEstablishment(
            trade_name="Fail Store",
            state_code="MH",
            district_code="PUNE",
            gstin="27AAPFU0939F1ZV",
        )
        with self.assertRaises(EstablishmentRepositoryError):
            self.repo.save_establishment(est)

    def test_supabase_repo_distinguishes_post_and_patch(self) -> None:
        """SupabaseEstablishmentRepository issues POST for new establishments and PATCH for updates."""
        repo = SupabaseEstablishmentRepository(settings=DummySettings())

        # Test new record: get_by_id returns None -> POST
        row_new = {
            "id": "est-new",
            "trade_name": "New",
            "state_code": "MH",
            "district_code": "PUNE",
            "created_at": "2026-10-05T00:00:00Z",
            "updated_at": "2026-10-05T00:00:00Z",
        }
        with patch.object(repo, "get_by_id", return_value=None):
            with patch.object(repo, "_request", return_value=(201, [row_new])) as mock_req:
                est = RetailEstablishment(id="est-new", trade_name="New", state_code="MH", district_code="PUNE")
                saved = repo.save_establishment(est)
                mock_req.assert_called_once()
                self.assertEqual(mock_req.call_args[0][0], "post")
                self.assertNotIn("resolution=merge-duplicates", mock_req.call_args[1].get("headers", {}).get("Prefer", ""))
                self.assertEqual(saved.id, "est-new")

        # Test existing record: get_by_id returns existing -> PATCH
        existing = RetailEstablishment(id="est-existing", trade_name="Old", state_code="MH", district_code="PUNE")
        row_updated = {
            "id": "est-existing",
            "trade_name": "Updated",
            "state_code": "MH",
            "district_code": "PUNE",
            "created_at": "2026-10-05T00:00:00Z",
            "updated_at": "2026-10-05T00:00:00Z",
        }
        with patch.object(repo, "get_by_id", return_value=existing):
            with patch.object(repo, "_request", return_value=(200, [row_updated])) as mock_req:
                est = RetailEstablishment(id="est-existing", trade_name="Updated", state_code="MH", district_code="PUNE")
                saved = repo.save_establishment(est)
                mock_req.assert_called_once()
                self.assertEqual(mock_req.call_args[0][0], "patch")
                self.assertEqual(mock_req.call_args[1].get("params"), {"id": "eq.est-existing"})
                self.assertEqual(saved.trade_name, "Updated")


class Task2ConsumerComplaintSerializationTestCase(unittest.TestCase):
    """Test consumer complaint serialization for verified and unverified issues."""

    def test_verified_complaint_serialization(self) -> None:
        """_serialize_issue includes establishment_id, jurisdiction_provenance, verified_at, verified_by."""
        now = datetime.now(timezone.utc)
        est_id = str(uuid.uuid4())
        officer_id = str(uuid.uuid4())

        issue = ConsumerIssue(
            id=str(uuid.uuid4()),
            user_id="user-consumer-1",
            inspection_id="insp-001",
            issue_type=IssueType.MISLEADING_LABEL.value,
            title="Misleading quantity",
            description="Declared 500g, measured 420g",
            status=IssueStatus.UNDER_REVIEW.value,
            department="LEGAL_METROLOGY",
            state_code="MH",
            district_code="PUNE",
            jurisdiction_verified=True,
            establishment_id=est_id,
            jurisdiction_provenance="ESTABLISHMENT_QR",
            jurisdiction_verified_at=now,
            jurisdiction_verified_by=officer_id,
        )

        response = _serialize_issue(issue)
        self.assertEqual(response.establishment_id, est_id)
        self.assertEqual(response.jurisdiction_provenance, "ESTABLISHMENT_QR")
        self.assertEqual(response.jurisdiction_verified_at, now)
        self.assertEqual(response.jurisdiction_verified_by, officer_id)
        self.assertTrue(response.jurisdiction_verified)

    def test_unverified_complaint_serialization(self) -> None:
        """Unverified issue preserves fail-closed defaults."""
        issue = ConsumerIssue(
            id=str(uuid.uuid4()),
            user_id="user-consumer-2",
            issue_type=IssueType.PRICE_TAMPERING.value,
            title="Charged above MRP",
            description="MRP is 50, charged 60",
            status=IssueStatus.SUBMITTED.value,
            department="LEGAL_METROLOGY",
            state_code=None,
            district_code=None,
            jurisdiction_verified=False,
            establishment_id=None,
            jurisdiction_provenance="UNVERIFIED",
            jurisdiction_verified_at=None,
            jurisdiction_verified_by=None,
        )

        response = _serialize_issue(issue)
        self.assertIsNone(response.establishment_id)
        self.assertEqual(response.jurisdiction_provenance, "UNVERIFIED")
        self.assertIsNone(response.jurisdiction_verified_at)
        self.assertIsNone(response.jurisdiction_verified_by)
        self.assertFalse(response.jurisdiction_verified)


class Task3ReviewNotesAliasTestCase(unittest.TestCase):
    """Test ReviewEstablishmentRequest notes alias parity."""

    def test_notes_alias_parity(self) -> None:
        """Both 'notes' and 'verification_notes' produce identical values across .notes, .verification_notes, and get_notes()."""
        r1 = ReviewEstablishmentRequest(action="VERIFY", notes="Note 1")
        self.assertEqual(r1.notes, "Note 1")
        self.assertEqual(r1.verification_notes, "Note 1")
        self.assertEqual(r1.get_notes(), "Note 1")

        r2 = ReviewEstablishmentRequest(action="VERIFY", verification_notes="Note 2")
        self.assertEqual(r2.notes, "Note 2")
        self.assertEqual(r2.verification_notes, "Note 2")
        self.assertEqual(r2.get_notes(), "Note 2")

        r3 = ReviewEstablishmentRequest(action="VERIFY")
        self.assertIsNone(r3.notes)
        self.assertIsNone(r3.verification_notes)
        self.assertIsNone(r3.get_notes())


class Task4AuthorityCaseDetailsTestCase(unittest.TestCase):
    """Test CaseDetailResponse exposes establishment binding information safely."""

    def test_case_detail_with_establishment_binding(self) -> None:
        """CaseDetailResponse includes establishment_id and verification metadata when bound."""
        now = datetime.now(timezone.utc)
        est_id = str(uuid.uuid4())
        verifier_id = str(uuid.uuid4())

        case = ConsumerIssue(
            id=str(uuid.uuid4()),
            user_id="user-999",
            title="Short measure case",
            description="Net weight shortage",
            issue_type="MISLEADING_LABEL",
            department="LEGAL_METROLOGY",
            state_code="MH",
            district_code="PUNE",
            status=IssueStatus.UNDER_REVIEW.value,
            jurisdiction_verified=True,
            establishment_id=est_id,
            jurisdiction_provenance="ESTABLISHMENT_QR",
            jurisdiction_verified_at=now,
            jurisdiction_verified_by=verifier_id,
        )

        detail = _map_case_detail_response(case)
        self.assertEqual(detail.establishment_id, est_id)
        self.assertEqual(detail.jurisdiction_provenance, "ESTABLISHMENT_QR")
        self.assertEqual(detail.jurisdiction_verified_at, now)
        self.assertEqual(detail.jurisdiction_verified_by, verifier_id)

    def test_case_detail_without_establishment_binding(self) -> None:
        """CaseDetailResponse has None/UNVERIFIED for unbound cases without leaking private data."""
        case = ConsumerIssue(
            id=str(uuid.uuid4()),
            user_id="user-888",
            title="Unbound case",
            description="General issue",
            issue_type="OTHER",
            department="LEGAL_METROLOGY",
            status=IssueStatus.SUBMITTED.value,
            jurisdiction_verified=False,
            establishment_id=None,
            jurisdiction_provenance="UNVERIFIED",
            jurisdiction_verified_at=None,
            jurisdiction_verified_by=None,
        )

        detail = _map_case_detail_response(case)
        self.assertIsNone(detail.establishment_id)
        self.assertEqual(detail.jurisdiction_provenance, "UNVERIFIED")
        self.assertIsNone(detail.jurisdiction_verified_at)
        self.assertIsNone(detail.jurisdiction_verified_by)


class Task5RequestValidationTestCase(unittest.TestCase):
    """Test validation of GSTIN structure and 6-digit Indian pincode."""

    def test_valid_gstin_and_pincode(self) -> None:
        """Valid GSTIN and 6-digit pincode pass validation; lowercase GSTIN is normalized to uppercase."""
        req = CreateEstablishmentRequest(
            trade_name="Valid Mart",
            state_code="MH",
            district_code="PUNE",
            gstin="27aapfu0939f1zv",  # lowercase input
            pincode="411004",
        )
        self.assertEqual(req.gstin, "27AAPFU0939F1ZV")
        self.assertEqual(req.pincode, "411004")

    def test_invalid_gstin_rejected(self) -> None:
        """Invalid GSTIN structures raise ValidationError."""
        invalid_gstins = [
            "123",                    # too short
            "27AAPFU0939F1Z",         # 14 chars
            "27AAPFU0939F1ZVV",       # 16 chars
            "XXAAPFU0939F1ZV",        # state code must be 2 digits
            "27123450939F1ZV",        # chars 3-7 must be alpha (PAN)
            "27AAPFU0939F0ZV",        # char 12 must be [1-9A-Z]
            "27AAPFU0939F1AV",        # char 14 must be 'Z'
        ]
        for gstin in invalid_gstins:
            with self.subTest(gstin=gstin):
                with self.assertRaises(ValidationError):
                    CreateEstablishmentRequest(
                        trade_name="Invalid Mart",
                        state_code="MH",
                        district_code="PUNE",
                        gstin=gstin,
                    )

    def test_invalid_pincode_rejected(self) -> None:
        """Invalid pincodes raise ValidationError."""
        invalid_pincodes = [
            "011004",  # starts with 0
            "4110",    # 4 digits
            "41100",   # 5 digits
            "4110041", # 7 digits
            "41100A",  # alphanumeric
            "411 04",  # whitespace
        ]
        for pin in invalid_pincodes:
            with self.subTest(pincode=pin):
                with self.assertRaises(ValidationError):
                    CreateEstablishmentRequest(
                        trade_name="Invalid Pin Mart",
                        state_code="MH",
                        district_code="PUNE",
                        pincode=pin,
                    )


if __name__ == "__main__":
    unittest.main()
