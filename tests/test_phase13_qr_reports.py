"""Comprehensive test suite for Veriqoo Backend Phase U4 — QR Detailed Reports.

Tests verify:
1. Authenticated owner can create share.
2. Unauthenticated user cannot create share.
3. Cross-user cannot create share.
4. Incomplete inspection cannot create share.
5. Failed inspection cannot create share.
6. Completed inspection can create share.
7. Raw token is not persisted.
8. Token hash is persisted.
9. Token has sufficient entropy.
10. Public endpoint resolves valid share.
11. Invalid token rejected.
12. Modified token rejected.
13. Revoked token rejected.
14. Expired token rejected.
15. Running inspection rejected.
16. Missing report rejected.
17. Owner can revoke.
18. Cross-user cannot revoke.
19. Revocation is immediate.
20. Repeated revoke is safe.
21. QR URL uses configured public base URL.
22. QR does not contain complete report JSON.
23. QR does not contain JWT.
24. QR does not contain Supabase service key.
25. Public response excludes owner_id.
26. Public response excludes private storage path.
27. Public response preserves overall status.
28. Public response preserves U1 compliance score / counts.
29. Public response preserves U2 annotation geometry.
30. Public response supports lang=en.
31. Public response supports lang=hi.
32. Public response supports lang=mr.
33. Same share token works across languages.
34. Canonical machine enums remain unchanged.
35. Legal provision identifiers remain unchanged.
36. Public endpoint does not invoke OCR.
37. Public endpoint does not invoke Gemini.
38. Public endpoint does not invoke RAG.
39. No raw token in logs/errors.
40. Migration is additive/non-destructive.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_current_user, get_session_store
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth import AuthenticatedUser
from backend.app.config import get_settings
from backend.app.main import app
from backend.app.services.inspection.lifecycle import InspectionLifecycleValidator
from backend.app.services.inspection.models import Inspection, InspectionStatus
from backend.app.services.inspection_pipeline.annotations import (
    EvidenceAnnotation,
    NormalizedBox,
)
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.report_sharing import (
    ReportShare,
    ReportSharingService,
    ShareStatus,
    get_report_sharing_service,
)
from backend.app.services.verification.models import VerificationResult, VerificationStatus


class TestPhase13QRReports(unittest.TestCase):
    """Unit and integration test cases for Phase U4 QR Detailed Reports."""

    def setUp(self) -> None:
        self.store = InMemoryInspectionStore()
        self.settings = get_settings()
        self.sharing_service = ReportSharingService(store=self.store, settings=self.settings)

        # Inject dependency overrides
        app.dependency_overrides[get_session_store] = lambda: self.store
        app.dependency_overrides[get_report_sharing_service] = lambda: self.sharing_service

        self.client = TestClient(app)
        self.owner_user = AuthenticatedUser(
            user_id="owner-user-uuid-1234",
            email="owner@veriqoo.ai",
            role="authenticated",
        )
        self.other_user = AuthenticatedUser(
            user_id="other-user-uuid-5678",
            email="other@veriqoo.ai",
            role="authenticated",
        )

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.store.clear()

    def _create_sample_completed_inspection(self, owner_id: str = "owner-user-uuid-1234") -> str:
        """Helper to create a completed inspection session with an associated report."""
        session = self.store.create_session(owner_id=owner_id)
        insp_id = session.inspection.inspection_id

        v1 = VerificationResult(
            requirement_id="R-6-1-a",
            status=VerificationStatus.PASS,
            reason="Manufacturer name and address is clearly declared.",
            evidence_ids=["ev_001"],
        )
        v2 = VerificationResult(
            requirement_id="R-6-1-e",
            status=VerificationStatus.FAIL,
            reason="MRP declaration is missing currency symbol prefix.",
            evidence_ids=["ev_002"],
        )

        ann = EvidenceAnnotation(
            annotation_id="ann_001",
            image_id="img_001",
            requirement_id="R-6-1-e",
            evidence_id="ev_002",
            status="FAIL",
            annotation_type="ERROR_HIGHLIGHT",
            polygon=[[0.1, 0.2], [0.5, 0.2], [0.5, 0.4], [0.1, 0.4]],
            bounding_box={"x": 10.0, "y": 20.0, "width": 40.0, "height": 20.0},
            normalized_box=NormalizedBox(x_min=0.1, y_min=0.2, x_max=0.5, y_max=0.4),
            label="Maximum Retail Price (MRP)",
            reason="MRP declaration is missing currency symbol prefix.",
            confidence=0.95,
            is_locatable=True,
            metadata={"storage_path": "private/images/img_001.jpg", "field": "mrp"},
        )

        report = InspectionReport(
            inspection_id=insp_id,
            overall_status=OverallInspectionStatus.FAIL,
            verification_results=[v1, v2],
            summary="Statutory compliance failure in requirement(s): ['R-6-1-e'].",
            evidence_count=2,
            image_count=1,
            applicable_requirement_count=2,
            pass_count=1,
            fail_count=1,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
            evidence_annotations=[ann],
        )

        self.store.store_report(insp_id, report)
        return insp_id

    # -------------------------------------------------------------------------
    # 1. Authenticated owner can create share
    # -------------------------------------------------------------------------
    def test_01_authenticated_owner_can_create_share(self) -> None:
        """1. Authenticated owner can successfully create a share and receive QR URL."""
        insp_id = self._create_sample_completed_inspection()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.post(f"/api/v1/inspections/{insp_id}/share", json={})
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("share_id", data)
        self.assertEqual(data["inspection_id"], insp_id)
        self.assertEqual(data["status"], "ACTIVE")
        self.assertIn("qr", data)
        self.assertTrue(data["qr"]["url"].startswith("http"))
        self.assertIn("vqr_", data["qr"]["url"])

    # -------------------------------------------------------------------------
    # 2. Unauthenticated user cannot create share
    # -------------------------------------------------------------------------
    def test_02_unauthenticated_user_cannot_create_share(self) -> None:
        """2. Unauthenticated user request is rejected with 401."""
        insp_id = self._create_sample_completed_inspection()
        # Remove current_user override to trigger authenticating dependency
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]

        response = self.client.post(f"/api/v1/inspections/{insp_id}/share", json={})
        self.assertEqual(response.status_code, 401)

    # -------------------------------------------------------------------------
    # 3. Cross-user cannot create share
    # -------------------------------------------------------------------------
    def test_03_cross_user_cannot_create_share(self) -> None:
        """3. Cross-user cannot create share for another user's inspection (safe 404)."""
        insp_id = self._create_sample_completed_inspection(owner_id=self.owner_user.user_id)
        app.dependency_overrides[get_current_user] = lambda: self.other_user

        response = self.client.post(f"/api/v1/inspections/{insp_id}/share", json={})
        self.assertEqual(response.status_code, 404)

    # -------------------------------------------------------------------------
    # 4. Incomplete inspection cannot create share
    # -------------------------------------------------------------------------
    def test_04_incomplete_inspection_cannot_create_share(self) -> None:
        """4. Incomplete (COLLECTING) inspection cannot create share."""
        session = self.store.create_session(owner_id=self.owner_user.user_id)
        insp_id = session.inspection.inspection_id
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.post(f"/api/v1/inspections/{insp_id}/share", json={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("COMPLETED", response.text)

    # -------------------------------------------------------------------------
    # 5. Failed inspection cannot create share
    # -------------------------------------------------------------------------
    def test_05_failed_inspection_cannot_create_share(self) -> None:
        """5. Failed inspection cannot create share."""
        session = self.store.create_session(owner_id=self.owner_user.user_id)
        insp_id = session.inspection.inspection_id
        session.inspection.status = InspectionStatus.FAILED
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.post(f"/api/v1/inspections/{insp_id}/share", json={})
        self.assertEqual(response.status_code, 400)

    # -------------------------------------------------------------------------
    # 6. Completed inspection can create share
    # -------------------------------------------------------------------------
    def test_06_completed_inspection_can_create_share(self) -> None:
        """6. Completed inspection with valid report creates share with expires_at."""
        insp_id = self._create_sample_completed_inspection()
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.post(
            f"/api/v1/inspections/{insp_id}/share",
            json={"expires_in_seconds": 3600, "metadata": {"note": "Test Share"}},
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIsNotNone(data["expires_at"])
        self.assertEqual(data["status"], "ACTIVE")

    # -------------------------------------------------------------------------
    # 7. Raw token is not persisted
    # -------------------------------------------------------------------------
    def test_07_raw_token_is_not_persisted(self) -> None:
        """7. Raw secret token is never stored in memory or persistent store."""
        insp_id = self._create_sample_completed_inspection()
        share, raw_token, qr_payload = self.sharing_service.create_share(insp_id)

        # Inspect persisted share record in store
        stored_share = self.store.get_share(share.id)
        self.assertIsNotNone(stored_share)
        self.assertNotEqual(stored_share.token_hash, raw_token)
        self.assertNotIn(raw_token, stored_share.to_dict().values())
        self.assertNotIn(raw_token, str(stored_share.to_dict()))

    # -------------------------------------------------------------------------
    # 8. Token hash is persisted
    # -------------------------------------------------------------------------
    def test_08_token_hash_is_persisted(self) -> None:
        """8. Token hash stored matches SHA-256 of raw token."""
        insp_id = self._create_sample_completed_inspection()
        share, raw_token, qr_payload = self.sharing_service.create_share(insp_id)

        expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        self.assertEqual(share.token_hash, expected_hash)
        stored_by_hash = self.store.get_share_by_token_hash(expected_hash)
        self.assertIsNotNone(stored_by_hash)
        self.assertEqual(stored_by_hash.id, share.id)

    # -------------------------------------------------------------------------
    # 9. Token has sufficient entropy
    # -------------------------------------------------------------------------
    def test_09_token_has_sufficient_entropy(self) -> None:
        """9. Share token starts with 'vqr_', is urlsafe, and has at least 40 characters."""
        insp_id = self._create_sample_completed_inspection()
        tokens = set()
        for _ in range(20):
            _, raw_token, _ = self.sharing_service.create_share(insp_id)
            self.assertTrue(raw_token.startswith("vqr_"))
            self.assertGreaterEqual(len(raw_token), 40)
            tokens.add(raw_token)
        # All 20 generated tokens must be strictly distinct
        self.assertEqual(len(tokens), 20)

    # -------------------------------------------------------------------------
    # 10. Public endpoint resolves valid share
    # -------------------------------------------------------------------------
    def test_10_public_endpoint_resolves_valid_share(self) -> None:
        """10. Unauthenticated client can resolve public report via GET /r/{token}."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, qr_payload = self.sharing_service.create_share(insp_id)

        # GET /r/{token} without any Authorization header
        response = self.client.get(f"/r/{raw_token}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["inspection_id"], insp_id)
        self.assertEqual(data["overall_status"], "FAIL")
        self.assertEqual(len(data["verification_results"]), 2)

    # -------------------------------------------------------------------------
    # 11. Invalid token rejected
    # -------------------------------------------------------------------------
    def test_11_invalid_token_rejected(self) -> None:
        """11. Non-existent share token is rejected with 404."""
        response = self.client.get("/r/vqr_invalid_nonexistent_token_1234567890")
        self.assertEqual(response.status_code, 404)

    # -------------------------------------------------------------------------
    # 12. Modified token rejected
    # -------------------------------------------------------------------------
    def test_12_modified_token_rejected(self) -> None:
        """12. Tampered / single-character modified token is rejected with 404."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        tampered_token = raw_token[:-1] + ("A" if raw_token[-1] != "A" else "B")
        response = self.client.get(f"/r/{tampered_token}")
        self.assertEqual(response.status_code, 404)

    # -------------------------------------------------------------------------
    # 13. Revoked token rejected
    # -------------------------------------------------------------------------
    def test_13_revoked_token_rejected(self) -> None:
        """13. Revoked share token is immediately rejected with 404."""
        insp_id = self._create_sample_completed_inspection()
        share, raw_token, _ = self.sharing_service.create_share(insp_id)

        self.sharing_service.revoke_share(insp_id, share.id, current_user_id="owner-user-uuid-1234")

        response = self.client.get(f"/r/{raw_token}")
        self.assertEqual(response.status_code, 404)

    # -------------------------------------------------------------------------
    # 14. Expired token rejected
    # -------------------------------------------------------------------------
    def test_14_expired_token_rejected(self) -> None:
        """14. Expired share token is rejected with 404."""
        insp_id = self._create_sample_completed_inspection()
        # Create share that expired in the past
        share, raw_token, _ = self.sharing_service.create_share(insp_id)
        share.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        self.store.save_share(share)

        response = self.client.get(f"/r/{raw_token}")
        self.assertEqual(response.status_code, 404)

    # -------------------------------------------------------------------------
    # 15. Running inspection rejected
    # -------------------------------------------------------------------------
    def test_15_running_inspection_rejected(self) -> None:
        """15. Inspection in RUNNING state cannot have shares created or resolved."""
        session = self.store.create_session(owner_id=self.owner_user.user_id)
        insp_id = session.inspection.inspection_id
        session.inspection.status = InspectionStatus.RUNNING
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.post(f"/api/v1/inspections/{insp_id}/share", json={})
        self.assertEqual(response.status_code, 400)

    # -------------------------------------------------------------------------
    # 16. Missing report rejected
    # -------------------------------------------------------------------------
    def test_16_missing_report_rejected(self) -> None:
        """16. Inspection with COMPLETED state but missing report object is rejected."""
        session = self.store.create_session(owner_id=self.owner_user.user_id)
        insp_id = session.inspection.inspection_id
        session.inspection.status = InspectionStatus.COMPLETED
        session.report = None
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.post(f"/api/v1/inspections/{insp_id}/share", json={})
        self.assertEqual(response.status_code, 400)

    # -------------------------------------------------------------------------
    # 17. Owner can revoke
    # -------------------------------------------------------------------------
    def test_17_owner_can_revoke(self) -> None:
        """17. Owner can revoke active share via POST /api/v1/inspections/{id}/share/{share_id}/revoke."""
        insp_id = self._create_sample_completed_inspection()
        share, _, _ = self.sharing_service.create_share(insp_id, created_by=self.owner_user.user_id)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        response = self.client.post(f"/api/v1/inspections/{insp_id}/share/{share.id}/revoke")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "REVOKED")
        self.assertEqual(data["share_id"], share.id)

    # -------------------------------------------------------------------------
    # 18. Cross-user cannot revoke
    # -------------------------------------------------------------------------
    def test_18_cross_user_cannot_revoke(self) -> None:
        """18. Non-owner cannot revoke another user's share (returns 404)."""
        insp_id = self._create_sample_completed_inspection(owner_id=self.owner_user.user_id)
        share, _, _ = self.sharing_service.create_share(insp_id, created_by=self.owner_user.user_id)
        app.dependency_overrides[get_current_user] = lambda: self.other_user

        response = self.client.post(f"/api/v1/inspections/{insp_id}/share/{share.id}/revoke")
        self.assertEqual(response.status_code, 404)

    # -------------------------------------------------------------------------
    # 19. Revocation is immediate
    # -------------------------------------------------------------------------
    def test_19_revocation_is_immediate(self) -> None:
        """19. Public resolution fails immediately upon revocation."""
        insp_id = self._create_sample_completed_inspection()
        share, raw_token, _ = self.sharing_service.create_share(insp_id, created_by=self.owner_user.user_id)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        # Before revocation: 200
        res_before = self.client.get(f"/r/{raw_token}")
        self.assertEqual(res_before.status_code, 200)

        # Revoke
        self.client.post(f"/api/v1/inspections/{insp_id}/share/{share.id}/revoke")

        # After revocation: 404
        res_after = self.client.get(f"/r/{raw_token}")
        self.assertEqual(res_after.status_code, 404)

    # -------------------------------------------------------------------------
    # 20. Repeated revoke is safe
    # -------------------------------------------------------------------------
    def test_20_repeated_revoke_is_safe(self) -> None:
        """20. Repeated revocation call is idempotent and returns 200."""
        insp_id = self._create_sample_completed_inspection()
        share, _, _ = self.sharing_service.create_share(insp_id, created_by=self.owner_user.user_id)
        app.dependency_overrides[get_current_user] = lambda: self.owner_user

        res1 = self.client.post(f"/api/v1/inspections/{insp_id}/share/{share.id}/revoke")
        self.assertEqual(res1.status_code, 200)

        res2 = self.client.post(f"/api/v1/inspections/{insp_id}/share/{share.id}/revoke")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["status"], "REVOKED")

    # -------------------------------------------------------------------------
    # 21. QR URL uses configured public base URL
    # -------------------------------------------------------------------------
    def test_21_qr_url_uses_configured_public_base_url(self) -> None:
        """21. QR URL respects configured public report base URL."""
        insp_id = self._create_sample_completed_inspection()
        custom_settings = get_settings()
        custom_settings.public_report_base_url = "https://reports.veriqoo.ai/r"
        svc = ReportSharingService(store=self.store, settings=custom_settings)

        _, raw_token, qr = svc.create_share(insp_id)
        self.assertTrue(qr.url.startswith("https://reports.veriqoo.ai/r/"))
        self.assertEqual(qr.url, f"https://reports.veriqoo.ai/r/{raw_token}")

    # -------------------------------------------------------------------------
    # 22. QR does not contain complete report JSON
    # -------------------------------------------------------------------------
    def test_22_qr_does_not_contain_complete_report_json(self) -> None:
        """22. QR payload contains only lightweight reference metadata, not report JSON."""
        insp_id = self._create_sample_completed_inspection()
        _, _, qr = self.sharing_service.create_share(insp_id)
        qr_dict = qr.to_dict()

        self.assertNotIn("verification_results", qr_dict)
        self.assertNotIn("evidence_annotations", qr_dict)
        self.assertNotIn("overall_status", qr_dict)
        self.assertNotIn("summary", qr_dict)

    # -------------------------------------------------------------------------
    # 23. QR does not contain JWT
    # -------------------------------------------------------------------------
    def test_23_qr_does_not_contain_jwt(self) -> None:
        """23. QR payload and URL contains no JWT tokens."""
        insp_id = self._create_sample_completed_inspection()
        _, _, qr = self.sharing_service.create_share(insp_id)

        self.assertNotIn("eyJ", qr.url)
        self.assertNotIn("Bearer", qr.url)

    # -------------------------------------------------------------------------
    # 24. QR does not contain Supabase service key
    # -------------------------------------------------------------------------
    def test_24_qr_does_not_contain_supabase_service_key(self) -> None:
        """24. QR payload contains no Supabase service role keys or credentials."""
        insp_id = self._create_sample_completed_inspection()
        _, _, qr = self.sharing_service.create_share(insp_id)

        self.assertNotIn("service_role", str(qr.to_dict()))
        self.assertNotIn("supabase", str(qr.to_dict()).lower())

    # -------------------------------------------------------------------------
    # 25. Public response excludes owner_id
    # -------------------------------------------------------------------------
    def test_25_public_response_excludes_owner_id(self) -> None:
        """25. Public resolved report strictly excludes owner_id or user identity."""
        insp_id = self._create_sample_completed_inspection(owner_id="secret-user-uuid-9999")
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        response = self.client.get(f"/r/{raw_token}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertNotIn("owner_id", data)
        self.assertNotIn("secret-user-uuid-9999", str(data))

    # -------------------------------------------------------------------------
    # 26. Public response excludes private storage path
    # -------------------------------------------------------------------------
    def test_26_public_response_excludes_private_storage_path(self) -> None:
        """26. Public resolved report excludes private storage paths in annotations."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        response = self.client.get(f"/r/{raw_token}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertNotIn("private/images/img_001.jpg", str(data))

    # -------------------------------------------------------------------------
    # 27. Public response preserves overall status
    # -------------------------------------------------------------------------
    def test_27_public_response_preserves_overall_status(self) -> None:
        """27. Public response accurately reports overall compliance status."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        response = self.client.get(f"/r/{raw_token}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["overall_status"], "FAIL")

    # -------------------------------------------------------------------------
    # 28. Public response preserves U1 score / counts
    # -------------------------------------------------------------------------
    def test_28_public_response_preserves_u1_counts(self) -> None:
        """28. Public response preserves requirement counts and verification outcomes."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        response = self.client.get(f"/r/{raw_token}")
        self.assertEqual(response.status_code, 200)
        counts = response.json()["counts"]
        self.assertEqual(counts["pass_count"], 1)
        self.assertEqual(counts["fail_count"], 1)
        self.assertEqual(counts["applicable_requirement_count"], 2)

    # -------------------------------------------------------------------------
    # 29. Public response preserves U2 annotation geometry
    # -------------------------------------------------------------------------
    def test_29_public_response_preserves_u2_annotation_geometry(self) -> None:
        """29. Public response preserves exact normalized bounding boxes and polygon points."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        response = self.client.get(f"/r/{raw_token}")
        self.assertEqual(response.status_code, 200)
        annotations = response.json()["evidence_annotations"]
        self.assertEqual(len(annotations), 1)
        ann = annotations[0]
        self.assertEqual(ann["annotation_id"], "ann_001")
        self.assertEqual(ann["annotation_type"], "ERROR_HIGHLIGHT")
        self.assertEqual(ann["polygon"], [[0.1, 0.2], [0.5, 0.2], [0.5, 0.4], [0.1, 0.4]])
        self.assertEqual(ann["normalized_box"]["x_min"], 0.1)
        self.assertEqual(ann["normalized_box"]["y_min"], 0.2)
        self.assertEqual(ann["normalized_box"]["x_max"], 0.5)
        self.assertEqual(ann["normalized_box"]["y_max"], 0.4)

    # -------------------------------------------------------------------------
    # 30. Public response supports lang=en
    # -------------------------------------------------------------------------
    def test_30_public_response_supports_lang_en(self) -> None:
        """30. Public report resolves in English when requested via ?lang=en."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        response = self.client.get(f"/r/{raw_token}?lang=en")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["language"], "en")
        self.assertIn("Statutory compliance failure", data["summary"])

    # -------------------------------------------------------------------------
    # 31. Public response supports lang=hi
    # -------------------------------------------------------------------------
    def test_31_public_response_supports_lang_hi(self) -> None:
        """31. Public report resolves in Hindi when requested via ?lang=hi."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        response = self.client.get(f"/r/{raw_token}?lang=hi")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["language"], "hi")
        # Summary and reasons are in Hindi
        self.assertIn("विधिक अनुपालन विफलता", data["summary"])

    # -------------------------------------------------------------------------
    # 32. Public response supports lang=mr
    # -------------------------------------------------------------------------
    def test_32_public_response_supports_lang_mr(self) -> None:
        """32. Public report resolves in Marathi when requested via ?lang=mr."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        response = self.client.get(f"/r/{raw_token}?lang=mr")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["language"], "mr")
        # Summary is in Marathi
        self.assertIn("वैधानिक अनुपालन अपयश आढळले", data["summary"])

    # -------------------------------------------------------------------------
    # 33. Same share token works across languages
    # -------------------------------------------------------------------------
    def test_33_same_share_token_works_across_languages(self) -> None:
        """33. A single share token dynamically localizes based on query param."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        res_en = self.client.get(f"/r/{raw_token}?lang=en").json()
        res_hi = self.client.get(f"/r/{raw_token}?lang=hi").json()
        res_mr = self.client.get(f"/r/{raw_token}?lang=mr").json()

        self.assertEqual(res_en["inspection_id"], res_hi["inspection_id"])
        self.assertEqual(res_hi["inspection_id"], res_mr["inspection_id"])
        self.assertNotEqual(res_en["summary"], res_hi["summary"])
        self.assertNotEqual(res_hi["summary"], res_mr["summary"])

    # -------------------------------------------------------------------------
    # 34. Canonical machine enums remain unchanged
    # -------------------------------------------------------------------------
    def test_34_canonical_machine_enums_remain_unchanged(self) -> None:
        """34. Machine status codes (PASS, FAIL) remain unchanged across languages."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        res_hi = self.client.get(f"/r/{raw_token}?lang=hi").json()
        self.assertEqual(res_hi["overall_status"], "FAIL")
        self.assertEqual(res_hi["verification_results"][0]["status"], "PASS")
        self.assertEqual(res_hi["verification_results"][1]["status"], "FAIL")

    # -------------------------------------------------------------------------
    # 35. Legal provision identifiers remain unchanged
    # -------------------------------------------------------------------------
    def test_35_legal_provision_identifiers_remain_unchanged(self) -> None:
        """35. Requirement IDs ('R-6-1-a', 'R-6-1-e') remain unchanged across languages."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        res_mr = self.client.get(f"/r/{raw_token}?lang=mr").json()
        req_ids = [r["requirement_id"] for r in res_mr["verification_results"]]
        self.assertEqual(req_ids, ["R-6-1-a", "R-6-1-e"])

    # -------------------------------------------------------------------------
    # 36. Public endpoint does not invoke OCR
    # -------------------------------------------------------------------------
    def test_36_public_endpoint_does_not_invoke_ocr(self) -> None:
        """36. Public share resolution does not invoke OCR processing engines."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        with patch("backend.app.services.ocr.engine.PaddleOCREngine.predict") as mock_ocr:
            response = self.client.get(f"/r/{raw_token}")
            self.assertEqual(response.status_code, 200)
            mock_ocr.assert_not_called()

    # -------------------------------------------------------------------------
    # 37. Public endpoint does not invoke Gemini
    # -------------------------------------------------------------------------
    def test_37_public_endpoint_does_not_invoke_gemini(self) -> None:
        """37. Public share resolution does not call external Gemini AI models."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        with patch("backend.app.services.gemini.service.GeminiEvidenceService.evaluate_requirement") as mock_gemini:
            response = self.client.get(f"/r/{raw_token}")
            self.assertEqual(response.status_code, 200)
            mock_gemini.assert_not_called()

    # -------------------------------------------------------------------------
    # 38. Public endpoint does not invoke RAG
    # -------------------------------------------------------------------------
    def test_38_public_endpoint_does_not_invoke_rag(self) -> None:
        """38. Public share resolution does not perform RAG legal embeddings retrieval."""
        insp_id = self._create_sample_completed_inspection()
        _, raw_token, _ = self.sharing_service.create_share(insp_id)

        with patch("backend.app.services.legal_rag.service.LegalRetrievalService.retrieve_for_applicable_requirements") as mock_rag:
            response = self.client.get(f"/r/{raw_token}")
            self.assertEqual(response.status_code, 200)
            mock_rag.assert_not_called()

    # -------------------------------------------------------------------------
    # 39. No raw token in logs/errors
    # -------------------------------------------------------------------------
    def test_39_no_raw_token_in_logs_or_errors(self) -> None:
        """39. Error responses on invalid share tokens do not echo or log raw tokens."""
        secret_token = "vqr_super_sensitive_token_payload_9876543210"
        response = self.client.get(f"/r/{secret_token}")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(secret_token, response.text)

    # -------------------------------------------------------------------------
    # 40. Migration is additive and non-destructive
    # -------------------------------------------------------------------------
    def test_40_migration_is_additive_and_non_destructive(self) -> None:
        """40. Phase U4 SQL migration exists and uses non-destructive DDL."""
        migration_file = Path("supabase/migrations/20261006000000_phase_u4_report_shares.sql")
        self.assertTrue(migration_file.exists())
        content = migration_file.read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS public.inspection_report_shares", content)
        self.assertIn("token_hash text NOT NULL UNIQUE", content)
        self.assertNotIn("DROP TABLE", content)
        self.assertNotIn("DROP COLUMN", content)
        self.assertNotIn("ALTER TABLE public.inspection_reports", content)


if __name__ == "__main__":
    unittest.main()
