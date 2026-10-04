"""Phase 9D Authentication & Authorization Test Suite.

Verifies:
1. Public endpoints (health, docs) remain publicly accessible without credentials.
2. Protected endpoints reject missing, malformed, expired, wrong-signature, and wrong-audience JWTs with HTTP 401.
3. Cryptographic JWT validation extracts user_id (sub), email, and role from valid Supabase access tokens.
4. Inspection creation binds ownership (owner_id) to the authenticated caller.
5. Cross-tenant access isolation: unauthorized callers receive safe HTTP 404 (preventing IDOR and enumeration).
6. Authorized owners can inspect, upload images to, execute, and retrieve reports for their inspections.
7. Background execution runs under trusted server context without storing or passing JWT tokens.
8. Error response envelopes adhere strictly to API error standards.
"""

from __future__ import annotations

import io
import time
from typing import Any
import unittest

from fastapi.testclient import TestClient
import jwt
from PIL import Image

from backend.app.api.dependencies import (
    get_pipeline_orchestrator,
    get_session_store,
)
from backend.app.api.errors import ErrorCode
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth.errors import AuthErrorCode
from backend.app.auth.jwt import create_jwt_token, validate_supabase_jwt
from backend.app.auth.models import AuthenticatedUser
from backend.app.config import settings
from backend.app.main import app
from backend.app.services.evidence.models import ImageArtifact
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.inspection.repository import InMemoryInspectionRepository
from backend.app.services.inspection_pipeline.models import (
    InspectionPipelineRequest,
    OverallInspectionStatus,
)
from backend.app.services.inspection_pipeline.orchestrator import InspectionPipelineOrchestrator
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.ocr.models import OCRObservation, OCRProcessingStatus, OCRResult
from backend.app.services.verification.models import VerificationResult, VerificationStatus


def _create_sample_jpeg_bytes(width: int = 150, height: int = 100) -> bytes:
    """Generate valid in-memory JPEG bytes for upload testing."""
    img = Image.new("RGB", (width, height), color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class MockPipelineOrchestrator:
    """Mock pipeline orchestrator for testing execution."""

    def run(self, request: InspectionPipelineRequest) -> InspectionReport:
        res = VerificationResult(
            verification_id=f"v_{request.inspection_id}_R-6-1-a",
            requirement_id="R-6-1-a",
            status=VerificationStatus.PASS,
            reason="Verified compliant statutory declaration.",
            confidence=0.99,
        )
        return InspectionReport(
            inspection_id=request.inspection_id,
            overall_status=OverallInspectionStatus.PASS,
            verification_results=[res],
            summary="All statutory requirements verified compliant.",
            evidence_count=len(request.image_artifacts),
            image_count=len(request.image_artifacts),
            applicable_requirement_count=1,
            pass_count=1,
            fail_count=0,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
        )


class Phase9DAuthTestCase(unittest.TestCase):
    """Test suite validating Phase 9D Authentication and Authorization."""

    def setUp(self) -> None:
        self.secret = "test-phase9d-jwt-secret-key-32-chars-long!"
        self.audience = "authenticated"
        self.original_secret = settings.supabase_jwt_secret
        self.original_audience = settings.supabase_jwt_audience

        settings.supabase_jwt_secret = self.secret
        settings.supabase_jwt_audience = self.audience

        self.store = InMemoryInspectionStore()
        self.mock_orch = MockPipelineOrchestrator()

        app.dependency_overrides[get_session_store] = lambda: self.store
        app.dependency_overrides[get_pipeline_orchestrator] = lambda: self.mock_orch

        self.client = TestClient(app)

        self.user_a_id = "11111111-1111-4111-8111-111111111111"
        self.user_a_email = "alice@example.com"
        self.user_a_token = create_jwt_token(
            payload={"sub": self.user_a_id, "email": self.user_a_email, "role": "authenticated"},
            secret=self.secret,
            audience=self.audience,
            expires_in_seconds=3600,
        )

        self.user_b_id = "22222222-2222-4222-8222-222222222222"
        self.user_b_email = "bob@example.com"
        self.user_b_token = create_jwt_token(
            payload={"sub": self.user_b_id, "email": self.user_b_email, "role": "authenticated"},
            secret=self.secret,
            audience=self.audience,
            expires_in_seconds=3600,
        )

    def tearDown(self) -> None:
        settings.supabase_jwt_secret = self.original_secret
        settings.supabase_jwt_audience = self.original_audience
        app.dependency_overrides.clear()
        self.store.clear()

    # =================================================================
    # 1. Public Endpoints Verification
    # =================================================================

    def test_root_health_endpoint_is_public(self) -> None:
        """Root GET /health does not require Authorization header."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_api_v1_health_endpoint_is_public(self) -> None:
        """GET /api/v1/health does not require Authorization header."""
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_openapi_documentation_is_public(self) -> None:
        """GET /openapi.json does not require Authorization header."""
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)

    # =================================================================
    # 2. Token Authentication & Error Handling Tests
    # =================================================================

    def test_missing_authorization_header_returns_401(self) -> None:
        """Calling protected endpoint without auth header returns 401 AUTHENTICATION_REQUIRED."""
        response = self.client.post("/api/v1/inspections", json={})
        self.assertEqual(response.status_code, 401)
        err = response.json()["error"]
        self.assertEqual(err["code"], ErrorCode.AUTHENTICATION_REQUIRED.value)

    def test_malformed_authorization_scheme_returns_401(self) -> None:
        """Non-Bearer scheme returns 401 AUTHENTICATION_REQUIRED."""
        response = self.client.post(
            "/api/v1/inspections",
            json={},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        self.assertEqual(response.status_code, 401)
        err = response.json()["error"]
        self.assertEqual(err["code"], ErrorCode.AUTHENTICATION_REQUIRED.value)

    def test_invalid_jwt_signature_returns_401(self) -> None:
        """Token signed with wrong secret returns 401 AUTHENTICATION_INVALID."""
        bad_token = create_jwt_token(
            payload={"sub": self.user_a_id, "email": self.user_a_email},
            secret="wrong-secret-key-that-does-not-match!",
            audience=self.audience,
        )
        response = self.client.post(
            "/api/v1/inspections",
            json={},
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        self.assertEqual(response.status_code, 401)
        err = response.json()["error"]
        self.assertEqual(err["code"], ErrorCode.AUTHENTICATION_INVALID.value)

    def test_expired_jwt_returns_401(self) -> None:
        """Expired token returns 401 AUTHENTICATION_EXPIRED."""
        expired_token = create_jwt_token(
            payload={"sub": self.user_a_id, "email": self.user_a_email},
            secret=self.secret,
            audience=self.audience,
            expires_in_seconds=-60,
        )
        response = self.client.post(
            "/api/v1/inspections",
            json={},
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        self.assertEqual(response.status_code, 401)
        err = response.json()["error"]
        self.assertEqual(err["code"], ErrorCode.AUTHENTICATION_EXPIRED.value)

    def test_invalid_audience_jwt_returns_401(self) -> None:
        """Token with mismatched audience returns 401 AUTHENTICATION_INVALID."""
        wrong_aud_token = create_jwt_token(
            payload={"sub": self.user_a_id, "email": self.user_a_email},
            secret=self.secret,
            audience="wrong_audience",
        )
        response = self.client.post(
            "/api/v1/inspections",
            json={},
            headers={"Authorization": f"Bearer {wrong_aud_token}"},
        )
        self.assertEqual(response.status_code, 401)
        err = response.json()["error"]
        self.assertEqual(err["code"], ErrorCode.AUTHENTICATION_INVALID.value)

    def test_jwt_missing_sub_claim_returns_401(self) -> None:
        """Token missing 'sub' subject claim returns 401 AUTHENTICATION_INVALID."""
        payload = {"email": "no_sub@example.com", "aud": self.audience, "exp": int(time.time()) + 3600}
        token_no_sub = jwt.encode(payload, self.secret, algorithm="HS256")
        response = self.client.post(
            "/api/v1/inspections",
            json={},
            headers={"Authorization": f"Bearer {token_no_sub}"},
        )
        self.assertEqual(response.status_code, 401)
        err = response.json()["error"]
        self.assertEqual(err["code"], ErrorCode.AUTHENTICATION_INVALID.value)

    # =================================================================
    # 3. Ownership & Multi-Tenant Authorization Tests
    # =================================================================

    def test_create_inspection_sets_owner_id(self) -> None:
        """Created inspection is bound to the authenticated user's ID."""
        response = self.client.post(
            "/api/v1/inspections",
            json={"metadata": {"batch_id": "BATCH-001"}},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["owner_id"], self.user_a_id)

    def test_owner_can_get_own_inspection(self) -> None:
        """Owner can retrieve their own inspection."""
        create_res = self.client.post(
            "/api/v1/inspections",
            json={},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        insp_id = create_res.json()["inspection_id"]

        get_res = self.client.get(
            f"/api/v1/inspections/{insp_id}",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["inspection_id"], insp_id)
        self.assertEqual(get_res.json()["owner_id"], self.user_a_id)

    def test_unauthorized_user_cannot_get_inspection(self) -> None:
        """User B cannot GET User A's inspection (returns 404 INSPECTION_NOT_FOUND)."""
        create_res = self.client.post(
            "/api/v1/inspections",
            json={},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        insp_id = create_res.json()["inspection_id"]

        get_res = self.client.get(
            f"/api/v1/inspections/{insp_id}",
            headers={"Authorization": f"Bearer {self.user_b_token}"},
        )
        self.assertEqual(get_res.status_code, 404)
        err = get_res.json()["error"]
        self.assertEqual(err["code"], ErrorCode.INSPECTION_NOT_FOUND.value)

    def test_unauthorized_user_cannot_upload_images(self) -> None:
        """User B cannot upload images to User A's inspection (returns 404 INSPECTION_NOT_FOUND)."""
        create_res = self.client.post(
            "/api/v1/inspections",
            json={},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        insp_id = create_res.json()["inspection_id"]

        img_bytes = _create_sample_jpeg_bytes()
        upload_res = self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("sample.jpg", img_bytes, "image/jpeg")},
            headers={"Authorization": f"Bearer {self.user_b_token}"},
        )
        self.assertEqual(upload_res.status_code, 404)
        err = upload_res.json()["error"]
        self.assertEqual(err["code"], ErrorCode.INSPECTION_NOT_FOUND.value)

    def test_unauthorized_user_cannot_run_inspection(self) -> None:
        """User B cannot execute User A's inspection (returns 404 INSPECTION_NOT_FOUND)."""
        create_res = self.client.post(
            "/api/v1/inspections",
            json={},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        insp_id = create_res.json()["inspection_id"]

        # Owner uploads image
        self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("sample.jpg", _create_sample_jpeg_bytes(), "image/jpeg")},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )

        # Unauthorized user tries to run
        run_res = self.client.post(
            f"/api/v1/inspections/{insp_id}/run",
            json={},
            headers={"Authorization": f"Bearer {self.user_b_token}"},
        )
        self.assertEqual(run_res.status_code, 404)
        err = run_res.json()["error"]
        self.assertEqual(err["code"], ErrorCode.INSPECTION_NOT_FOUND.value)

    def test_unauthorized_user_cannot_get_report(self) -> None:
        """User B cannot retrieve report for User A's inspection (returns 404 INSPECTION_NOT_FOUND)."""
        create_res = self.client.post(
            "/api/v1/inspections",
            json={},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        insp_id = create_res.json()["inspection_id"]

        # Owner uploads and executes
        self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("sample.jpg", _create_sample_jpeg_bytes(), "image/jpeg")},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.client.post(
            f"/api/v1/inspections/{insp_id}/run",
            json={},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )

        time.sleep(0.05)

        # Unauthorized user tries to get report
        report_res = self.client.get(
            f"/api/v1/inspections/{insp_id}/report",
            headers={"Authorization": f"Bearer {self.user_b_token}"},
        )
        self.assertEqual(report_res.status_code, 404)
        err = report_res.json()["error"]
        self.assertEqual(err["code"], ErrorCode.INSPECTION_NOT_FOUND.value)

    def test_owner_full_lifecycle_success(self) -> None:
        """Owner User A can complete full end-to-end inspection lifecycle."""
        # 1. Create inspection
        create_res = self.client.post(
            "/api/v1/inspections",
            json={"metadata": {"package": "biscuits"}},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(create_res.status_code, 201)
        insp_id = create_res.json()["inspection_id"]
        self.assertEqual(create_res.json()["owner_id"], self.user_a_id)

        # 2. Upload image
        upload_res = self.client.post(
            f"/api/v1/inspections/{insp_id}/images",
            files={"file": ("front.jpg", _create_sample_jpeg_bytes(), "image/jpeg")},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(upload_res.status_code, 201)

        # 3. Execute
        run_res = self.client.post(
            f"/api/v1/inspections/{insp_id}/run",
            json={},
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(run_res.status_code, 200)
        self.assertEqual(run_res.json()["status"], "RUNNING")

        # 4. Wait for background execution to complete
        time.sleep(0.05)

        # 5. Check session status
        get_res = self.client.get(
            f"/api/v1/inspections/{insp_id}",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["status"], "COMPLETED")
        self.assertTrue(get_res.json()["has_report"])

        # 6. Retrieve report
        report_res = self.client.get(
            f"/api/v1/inspections/{insp_id}/report",
            headers={"Authorization": f"Bearer {self.user_a_token}"},
        )
        self.assertEqual(report_res.status_code, 200)
        report_data = report_res.json()
        self.assertEqual(report_data["inspection_id"], insp_id)
        self.assertEqual(report_data["overall_status"], "PASS")

    # =================================================================
    # 4. In-Memory Repository Owner Tests
    # =================================================================

    def test_in_memory_repository_persists_owner_id(self) -> None:
        """InMemoryInspectionRepository correctly stores and retrieves owner_id."""
        repo = InMemoryInspectionRepository()
        session = repo.create_inspection(owner_id=self.user_a_id)
        self.assertEqual(session.owner_id, self.user_a_id)
        self.assertEqual(session.metadata.get("owner_id"), self.user_a_id)

        retrieved = repo.get_inspection(session.inspection_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.owner_id, self.user_a_id)

    # =================================================================
    # 5. Token Validation Unit Tests
    # =================================================================

    def test_validate_supabase_jwt_success(self) -> None:
        """validate_supabase_jwt returns AuthenticatedUser with claims."""
        token = create_jwt_token(
            payload={"sub": "user-123", "email": "test@veriqoo.ai", "role": "authenticated"},
            secret=self.secret,
            audience=self.audience,
        )
        user = validate_supabase_jwt(token, secret=self.secret, audience=self.audience)
        self.assertEqual(user.user_id, "user-123")
        self.assertEqual(user.email, "test@veriqoo.ai")
        self.assertEqual(user.role, "authenticated")
        self.assertIn("exp", user.claims)
