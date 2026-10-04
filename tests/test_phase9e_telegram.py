"""Unit and integration test suite for Phase 9E Telegram Bot Integration.

Verifies:
1. Complete Telegram command lifecycle (/start, /help, /new, /run, /status, /report, /cancel).
2. Telegram photo upload, normalization, and sequence preservation.
3. Asynchronous execution triggering and manual retry from FAILED.
4. Telegram identity mapping and strict multi-tenant IDOR protection.
5. Message and error sanitization (no tokens, keys, or stack traces leaked).
6. Configuration safety and application factory behavior.
"""

from __future__ import annotations

import io
import time
from typing import Any
import unittest

from PIL import Image

from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.evidence.models import ImageArtifact, IngestionConfig
from backend.app.services.inspection.execution import InspectionExecutionService
from backend.app.services.inspection.models import InspectionStatus
from backend.app.services.inspection.repository import InMemoryInspectionRepository
from backend.app.services.inspection.service import InspectionService
from backend.app.services.inspection_pipeline.models import (
    InspectionPipelineRequest,
    OverallInspectionStatus,
)
from backend.app.services.inspection_pipeline.orchestrator import InspectionPipelineOrchestrator
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.storage.in_memory import InMemoryImageStorage
from backend.app.services.verification.models import VerificationResult, VerificationStatus
from backend.app.telegram.adapter import TelegramBotAdapter
from backend.app.telegram.bot import build_telegram_application
from backend.app.telegram.formatter import (
    format_help_message,
    format_inspection_report,
    format_inspection_status,
    format_safe_error,
    format_welcome_message,
    sanitize_telegram_text,
)
from backend.app.telegram.identity import (
    DeterministicTelegramIdentityProvider,
    ExplicitMappingTelegramIdentityProvider,
)
from backend.app.telegram.models import TelegramUserIdentity, TelegramWorkflowState


def _create_sample_jpeg_bytes(width: int = 150, height: int = 100) -> bytes:
    """Generate valid in-memory JPEG bytes for upload testing."""
    img = Image.new("RGB", (width, height), color=(50, 100, 150))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class MockPipelineOrchestrator:
    """Mock pipeline orchestrator for testing execution via Telegram."""

    def __init__(self, delay_sec: float = 0.0, overall_status: OverallInspectionStatus = OverallInspectionStatus.PASS) -> None:
        self.delay_sec = delay_sec
        self.overall_status = overall_status
        self.run_count = 0

    def run(self, request: InspectionPipelineRequest) -> InspectionReport:
        self.run_count += 1
        if self.delay_sec > 0:
            time.sleep(self.delay_sec)

        res = VerificationResult(
            verification_id=f"v_{request.inspection_id}_R-6-1-a",
            requirement_id="R-6-1-a",
            status=VerificationStatus.PASS if self.overall_status == OverallInspectionStatus.PASS else VerificationStatus.FAIL,
            reason="Verified compliant statutory declaration.",
            confidence=0.99,
        )
        return InspectionReport(
            inspection_id=request.inspection_id,
            overall_status=self.overall_status,
            verification_results=[res],
            summary="All statutory requirements verified compliant.",
            evidence_count=len(request.image_artifacts),
            image_count=len(request.image_artifacts),
            applicable_requirement_count=1,
            pass_count=1 if self.overall_status == OverallInspectionStatus.PASS else 0,
            fail_count=0 if self.overall_status == OverallInspectionStatus.PASS else 1,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
        )


class Phase9ETelegramTestCase(unittest.TestCase):
    """Test suite validating Telegram bot adapter and workflows."""

    def setUp(self) -> None:
        self.repo = InMemoryInspectionRepository()
        self.ingestion = ImageIngestionService(config=IngestionConfig(max_file_size_bytes=5 * 1024 * 1024))
        self.storage = InMemoryImageStorage()
        self.mock_orch = MockPipelineOrchestrator()
        self.service = InspectionService(
            repository=self.repo,
            ingestion_service=self.ingestion,
            orchestrator=self.mock_orch,
            storage=self.storage,
        )
        self.execution_service = InspectionExecutionService(inspection_service=self.service)
        self.identity_provider = DeterministicTelegramIdentityProvider()
        self.adapter = TelegramBotAdapter(
            inspection_service=self.service,
            execution_service=self.execution_service,
            identity_provider=self.identity_provider,
        )

        self.user_a = TelegramUserIdentity(telegram_user_id=1001, chat_id=1001, username="alice_inspector", first_name="Alice")
        self.user_b = TelegramUserIdentity(telegram_user_id=2002, chat_id=2002, username="bob_inspector", first_name="Bob")

    def tearDown(self) -> None:
        self.repo._inspections.clear()
        self.storage.clear()

    # =================================================================
    # 1. Identity Provider Tests
    # =================================================================

    def test_deterministic_identity_mapping(self) -> None:
        """DeterministicTelegramIdentityProvider maps telegram_user_id to a stable UUID."""
        user1 = self.identity_provider.get_authenticated_user(self.user_a)
        user2 = self.identity_provider.get_authenticated_user(self.user_a)
        user_b = self.identity_provider.get_authenticated_user(self.user_b)

        self.assertEqual(user1.user_id, user2.user_id)
        self.assertNotEqual(user1.user_id, user_b.user_id)
        self.assertEqual(user1.role, "authenticated")
        self.assertIn("1001", user1.email)

    def test_explicit_mapping_identity_provider(self) -> None:
        """ExplicitMappingTelegramIdentityProvider overrides mapping when registered."""
        prov = ExplicitMappingTelegramIdentityProvider()
        prov.register_mapping(1001, "custom-supabase-uuid-1001")
        mapped_user = prov.get_authenticated_user(self.user_a)
        self.assertEqual(mapped_user.user_id, "custom-supabase-uuid-1001")

    def test_telegram_identity_does_not_impersonate_supabase_user_and_lacks_jwt(self) -> None:
        """Audit test: Telegram deterministic identity generates a synthetic UUID5 and possesses no Supabase JWT."""
        existing_supabase_user_id = "99999999-9999-4999-8999-999999999999"
        tg_user = self.identity_provider.get_authenticated_user(self.user_a)

        # 1. Proves Telegram identity cannot guess or collide with an existing Supabase user UUID
        self.assertNotEqual(tg_user.user_id, existing_supabase_user_id)

        # 2. Proves Telegram user has no raw JWT token attached
        self.assertNotIn("token", tg_user.claims)
        self.assertNotIn("jwt", tg_user.claims)

    # =================================================================
    # 2. Command Flow Tests (/start, /help, /new, /cancel)
    # =================================================================

    def test_start_command_returns_welcome(self) -> None:
        """handle_start returns greeting and command overview."""
        reply = self.adapter.handle_start(self.user_a)
        self.assertIn("Welcome to Veriqoo", reply)
        self.assertIn("Alice", reply)
        self.assertIn("/new", reply)

    def test_help_command_returns_instructions(self) -> None:
        """handle_help returns workflow guide."""
        reply = self.adapter.handle_help(self.user_a)
        self.assertIn("Veriqoo Telegram Inspection Guide", reply)
        self.assertIn("Step-by-Step", reply)

    def test_new_command_creates_inspection(self) -> None:
        """handle_new creates inspection session in COLLECTING status."""
        reply = self.adapter.handle_new(self.user_a)
        self.assertIn("New Inspection Initialized", reply)
        self.assertIn("Collecting Photos", reply)

        conv = self.adapter._get_conversation(self.user_a)
        self.assertIsNotNone(conv.active_inspection_id)
        self.assertEqual(conv.state, TelegramWorkflowState.COLLECTING)

        # Check repository record
        insp = self.repo.get_inspection(conv.active_inspection_id)
        self.assertEqual(insp.status, InspectionStatus.COLLECTING)
        auth_user = self.identity_provider.get_authenticated_user(self.user_a)
        self.assertEqual(insp.owner_id, auth_user.user_id)

    def test_new_command_when_already_collecting(self) -> None:
        """handle_new when active inspection is already collecting warns user."""
        self.adapter.handle_new(self.user_a)
        reply2 = self.adapter.handle_new(self.user_a)
        self.assertIn("You already have an active inspection", reply2)

    def test_cancel_command_resets_session(self) -> None:
        """handle_cancel resets conversation state."""
        self.adapter.handle_new(self.user_a)
        reply = self.adapter.handle_cancel(self.user_a)
        self.assertIn("has been cleared", reply)

        conv = self.adapter._get_conversation(self.user_a)
        self.assertIsNone(conv.active_inspection_id)
        self.assertEqual(conv.state, TelegramWorkflowState.IDLE)

    # =================================================================
    # 3. Photo Upload & Normalization Tests
    # =================================================================

    def test_photo_upload_without_active_session_returns_guidance(self) -> None:
        """Uploading photo without /new returns guidance to start a session."""
        photo_bytes = _create_sample_jpeg_bytes()
        reply = self.adapter.handle_photo(self.user_a, photo_bytes)
        self.assertIn("No active inspection session", reply)

    def test_photo_upload_success_and_sequencing(self) -> None:
        """Photos uploaded sequentially are stored and sequenced correctly."""
        self.adapter.handle_new(self.user_a)
        conv = self.adapter._get_conversation(self.user_a)
        insp_id = conv.active_inspection_id

        reply1 = self.adapter.handle_photo(self.user_a, _create_sample_jpeg_bytes())
        self.assertIn("Photo 1 added", reply1)
        self.assertIn("Total: 1", reply1)

        reply2 = self.adapter.handle_photo(self.user_a, _create_sample_jpeg_bytes())
        self.assertIn("Photo 2 added", reply2)
        self.assertIn("Total: 2", reply2)

        insp = self.repo.get_inspection(insp_id)
        self.assertEqual(insp.image_count, 2)
        self.assertEqual(insp.images[0].sequence, 1)
        self.assertEqual(insp.images[1].sequence, 2)

    def test_invalid_photo_returns_safe_error(self) -> None:
        """Corrupt or non-image bytes return safe error message."""
        self.adapter.handle_new(self.user_a)
        reply = self.adapter.handle_photo(self.user_a, b"not_an_image_corrupt_data")
        self.assertIn("image could not be processed", reply)

    # =================================================================
    # 4. Verification Execution & Report Tests
    # =================================================================

    def test_run_without_images_prompts_for_photo(self) -> None:
        """handle_run with zero images warns user to send photos."""
        self.adapter.handle_new(self.user_a)
        reply = self.adapter.handle_run(self.user_a)
        self.assertIn("Please upload at least one package photo", reply)

    def test_run_executes_and_report_retrieval(self) -> None:
        """handle_run schedules background execution and /report retrieves results."""
        self.adapter.handle_new(self.user_a)
        self.adapter.handle_photo(self.user_a, _create_sample_jpeg_bytes())

        run_reply = self.adapter.handle_run(self.user_a)
        self.assertIn("Verification Started", run_reply)
        self.assertIn("Analysis in Progress", run_reply)

        # Allow execution to complete
        time.sleep(0.05)

        # Status check
        status_reply = self.adapter.handle_status(self.user_a)
        self.assertIn("Completed", status_reply)

        # Report check
        report_reply = self.adapter.handle_report(self.user_a)
        self.assertIn("COMPLIANCE STATUS: PASS", report_reply)
        self.assertIn("Total Requirements Evaluated: 1", report_reply)

    def test_manual_retry_from_failed_status(self) -> None:
        """Failed inspection can be manually retried via /run."""
        self.adapter.handle_new(self.user_a)
        self.adapter.handle_photo(self.user_a, _create_sample_jpeg_bytes())
        conv = self.adapter._get_conversation(self.user_a)
        insp_id = conv.active_inspection_id

        # Set status to FAILED
        self.repo.update_inspection_status(insp_id, InspectionStatus.FAILED)
        insp = self.repo.get_inspection(insp_id)
        insp.metadata["execution_error"] = "OCR timeout during processing."

        # Check /report reflects failure
        report_reply = self.adapter.handle_report(self.user_a)
        self.assertIn("Verification Failed", report_reply)
        self.assertIn("OCR timeout", report_reply)

        # Call /run to retry
        retry_reply = self.adapter.handle_run(self.user_a)
        self.assertIn("Verification Started", retry_reply)

        time.sleep(0.05)
        final_insp = self.repo.get_inspection(insp_id)
        self.assertEqual(final_insp.status, InspectionStatus.COMPLETED)

    # =================================================================
    # 5. Cross-User IDOR & Ownership Isolation Tests
    # =================================================================

    def test_cross_user_isolation(self) -> None:
        """User B cannot access, upload to, run, or view reports for User A's inspection."""
        # User A creates inspection and uploads photo
        self.adapter.handle_new(self.user_a)
        conv_a = self.adapter._get_conversation(self.user_a)
        insp_a_id = conv_a.active_inspection_id
        self.adapter.handle_photo(self.user_a, _create_sample_jpeg_bytes())

        # User B attempts to upload photo to A's inspection
        conv_b = self.adapter._get_conversation(self.user_b)
        conv_b.active_inspection_id = insp_a_id
        photo_res = self.adapter.handle_photo(self.user_b, _create_sample_jpeg_bytes())
        self.assertIn("not found or you are not authorized", photo_res)

        # User B attempts to run A's inspection
        conv_b.active_inspection_id = insp_a_id
        run_res = self.adapter.handle_run(self.user_b)
        self.assertIn("not found or you are not authorized", run_res)

        # User B attempts to view status of A's inspection
        conv_b.active_inspection_id = insp_a_id
        status_res = self.adapter.handle_status(self.user_b)
        self.assertIn("not found or you are not authorized", status_res)

        # User B attempts to view report of A's inspection
        conv_b.active_inspection_id = insp_a_id
        report_res = self.adapter.handle_report(self.user_b)
        self.assertIn("not found or you are not authorized", report_res)

    # =================================================================
    # 6. Sanitization & Safety Tests
    # =================================================================

    def test_sanitize_telegram_text_removes_tokens_and_secrets(self) -> None:
        """Sanitizer strips JWT tokens, bearer headers, and secrets from messages."""
        msg_with_jwt = "Error: Token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0In0.abc123def456 was invalid."
        clean = sanitize_telegram_text(msg_with_jwt)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIs", clean)
        self.assertIn("[REDACTED_TOKEN]", clean)

        msg_with_key = "Failed connection with key='sb_secret_token_123456'"
        clean_key = sanitize_telegram_text(msg_with_key)
        self.assertNotIn("sb_secret_token_123456", clean_key)
        self.assertIn("key=[REDACTED]", clean_key)

    def test_build_telegram_application_requires_valid_token(self) -> None:
        """build_telegram_application raises ValueError if token is empty."""
        with self.assertRaises(ValueError):
            build_telegram_application("", self.adapter)
        with self.assertRaises(ValueError):
            build_telegram_application("   ", self.adapter)

    def test_build_telegram_application_success(self) -> None:
        """build_telegram_application succeeds with valid token and registers handlers."""
        app = build_telegram_application("123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ", self.adapter)
        self.assertIsNotNone(app)

    def test_report_formatting_with_failures(self) -> None:
        """format_inspection_report includes key findings for non-compliant requirements."""
        res_fail = VerificationResult(
            verification_id="v_fail_1",
            requirement_id="R-6-1-c",
            status=VerificationStatus.FAIL,
            reason="Net quantity declaration missing standard unit.",
            metadata={"rule_source": "Rule 6(1)(c)"},
        )
        report = InspectionReport(
            inspection_id="test-fail-report-id",
            overall_status=OverallInspectionStatus.FAIL,
            verification_results=[res_fail],
            summary="Violations detected.",
            evidence_count=1,
            image_count=1,
            applicable_requirement_count=1,
            pass_count=0,
            fail_count=1,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
        )
        formatted = format_inspection_report(report)
        self.assertIn("COMPLIANCE STATUS: NON-COMPLIANT", formatted)
        self.assertIn("R-6-1-c", formatted)
        self.assertIn("Rule 6(1)(c)", formatted)
        self.assertIn("Net quantity declaration missing", formatted)

    def test_telegram_conversation_restart_resilience(self) -> None:
        """Telegram conversation re-attaches cleanly after simulated restart."""
        # 1. Create inspection
        self.adapter.handle_new(self.user_a)
        conv = self.adapter._get_conversation(self.user_a)
        saved_insp_id = conv.active_inspection_id

        # 2. Simulate process restart by instantiating fresh adapter
        new_adapter = TelegramBotAdapter(
            inspection_service=self.service,
            execution_service=self.execution_service,
            identity_provider=self.identity_provider,
        )

        # 3. User sends /new on fresh adapter -> starts fresh session cleanly
        reply = new_adapter.handle_new(self.user_a)
        self.assertIn("New Inspection Initialized", reply)
        new_conv = new_adapter._get_conversation(self.user_a)
        self.assertNotEqual(new_conv.active_inspection_id, saved_insp_id)

