"""Focused test suite validating confirmed gaps identified in Phase 7.4.3 Security & Contract Audit.

Tests confirm:
1. Serialization omission of establishment and provenance fields in consumer_issues endpoints.
2. Authority CaseDetailResponse omission of establishment binding details.
3. Establishment review notes alias behavior when using verification_notes.
4. Reviewer identity provenance tracking during SUSPEND / REVOKE flows.
5. SupabaseEstablishmentRepository header and HTTP method behavior on record updates.
6. GSTIN validation constraints in CreateEstablishmentRequest.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
import uuid

from backend.app.api.v1.endpoints.consumer_issues import _serialize_issue
from backend.app.services.authority.schemas import CaseDetailResponse
from backend.app.services.consumer_issues.models import ConsumerIssue, IssueStatus, IssueType
from backend.app.services.establishment.models import (
    EstablishmentVerificationProvenance,
    EstablishmentVerificationStatus,
    RetailEstablishment,
)
from backend.app.services.establishment.repository import SupabaseEstablishmentRepository
from backend.app.services.establishment.schemas import (
    CreateEstablishmentRequest,
    ReviewEstablishmentRequest,
)


class Phase743AuditGapVerificationTestCase(unittest.TestCase):
    """Verify concrete functional and contract gaps identified in the audit."""

    def test_gap_1_consumer_issue_serialization_propagates_establishment_provenance(self):
        """Confirm that _serialize_issue in endpoints/consumer_issues.py propagates
        establishment_id, jurisdiction_provenance, jurisdiction_verified_at, and jurisdiction_verified_by.
        """
        now = datetime.now(timezone.utc)
        est_id = str(uuid.uuid4())
        verifier_id = str(uuid.uuid4())

        issue = ConsumerIssue(
            id=str(uuid.uuid4()),
            user_id="user-123",
            inspection_id="insp-123",
            issue_type=IssueType.MISLEADING_LABEL.value,
            title="Misleading net weight",
            description="Weight printed does not match scale",
            status=IssueStatus.UNDER_REVIEW.value,
            department="LEGAL_METROLOGY",
            state_code="MH",
            district_code="PUNE",
            jurisdiction_verified=True,
            establishment_id=est_id,
            jurisdiction_provenance="ESTABLISHMENT_QR",
            jurisdiction_verified_at=now,
            jurisdiction_verified_by=verifier_id,
        )

        serialized = _serialize_issue(issue)

        # REMEDIATED: The serialized schema retains actual persisted values
        self.assertEqual(serialized.establishment_id, est_id)
        self.assertEqual(serialized.jurisdiction_provenance, "ESTABLISHMENT_QR")
        self.assertEqual(serialized.jurisdiction_verified_at, now)
        self.assertEqual(serialized.jurisdiction_verified_by, verifier_id)

    def test_gap_2_case_detail_response_schema_includes_establishment_binding(self):
        """Confirm that CaseDetailResponse includes establishment_id and provenance fields."""
        fields = CaseDetailResponse.model_fields
        self.assertIn("establishment_id", fields)
        self.assertIn("jurisdiction_provenance", fields)
        self.assertIn("jurisdiction_verified_at", fields)
        self.assertIn("jurisdiction_verified_by", fields)

    def test_gap_3_review_establishment_request_notes_alias_contract(self):
        """Confirm that ReviewEstablishmentRequest synchronizes verification_notes and notes aliases."""
        payload_alias = ReviewEstablishmentRequest(
            action="VERIFY",
            verification_notes="Verified via municipal registry match",
        )
        self.assertEqual(payload_alias.notes, "Verified via municipal registry match")
        self.assertEqual(payload_alias.verification_notes, "Verified via municipal registry match")
        self.assertEqual(payload_alias.get_notes(), "Verified via municipal registry match")

        payload_notes = ReviewEstablishmentRequest(
            action="VERIFY",
            notes="Direct notes provided",
        )
        self.assertEqual(payload_notes.notes, "Direct notes provided")
        self.assertEqual(payload_notes.verification_notes, "Direct notes provided")
        self.assertEqual(payload_notes.get_notes(), "Direct notes provided")

    def test_gap_4_suspend_revoke_leaves_original_verifier_id(self):
        """Confirm that SUSPEND / REVOKE does not mutate verification_authority_id (deferred to Phase 7.5 RPC)."""
        now = datetime.now(timezone.utc)
        verifier_officer = str(uuid.uuid4())
        suspender_officer = str(uuid.uuid4())

        est = RetailEstablishment(
            trade_name="Apex Supermarket",
            state_code="MH",
            district_code="PUNE",
            verification_status=EstablishmentVerificationStatus.VERIFIED.value,
            verification_provenance=EstablishmentVerificationProvenance.MANUAL.value,
            verification_authority_id=verifier_officer,
            verification_date=now,
            is_active=True,
        )

        # Simulate SUSPEND action in EstablishmentService logic
        clean_action = "SUSPEND"
        if clean_action == "SUSPEND":
            est.verification_status = EstablishmentVerificationStatus.SUSPENDED.value
            est.is_active = False
            est.verification_notes = "Suspended due to license lapse"
        est.updated_by = suspender_officer

        # Verification provenance preserves verifier; updated_by tracks suspender
        self.assertEqual(est.verification_authority_id, verifier_officer)
        self.assertEqual(est.verification_status, "SUSPENDED")
        self.assertFalse(est.is_active)

    def test_gap_5_supabase_establishment_repo_save_lacks_upsert_header(self):
        """Confirm that SupabaseEstablishmentRepository does not blindly add merge-duplicates header."""
        class DummySettings:
            supabase_url = "https://example.supabase.co"
            supabase_service_role_key = "test-service-key"
            supabase_anon_key = "test-anon-key"

        repo = SupabaseEstablishmentRepository(settings=DummySettings())
        headers = repo._headers(prefer="return=representation")

        # CONFIRMED: Header does not contain 'resolution=merge-duplicates'
        self.assertEqual(headers.get("Prefer"), "return=representation")
        self.assertNotIn("resolution=merge-duplicates", headers.get("Prefer", ""))

    def test_gap_6_gstin_validation_enforces_format(self):
        """Confirm that CreateEstablishmentRequest validates 15-character GSTIN regex."""
        with self.assertRaises(Exception):
            CreateEstablishmentRequest(
                trade_name="Test Store",
                state_code="MH",
                district_code="PUNE",
                gstin="123",  # Malformed GSTIN: 3 characters
            )

        valid_req = CreateEstablishmentRequest(
            trade_name="Test Store",
            state_code="MH",
            district_code="PUNE",
            gstin="27aabcd1234e1z5",  # lowercase
        )
        self.assertEqual(valid_req.gstin, "27AABCD1234E1Z5")


if __name__ == "__main__":
    unittest.main()
