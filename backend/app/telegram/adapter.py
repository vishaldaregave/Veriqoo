"""Telegram Bot Adapter bridging Telegram user interactions with Veriqoo Inspection Services."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from backend.app.auth.models import AuthenticatedUser
from backend.app.services.evidence.errors import (
    ImageDecodeError,
    ImageIngestionError,
    ImageTooLargeError,
    InvalidImageError,
    UnsupportedImageFormatError,
)
from backend.app.services.inspection.errors import (
    InspectionNotFoundError,
    InspectionStateError,
)
from backend.app.services.inspection.execution import InspectionExecutionService
from backend.app.services.inspection.models import Inspection, InspectionStatus
from backend.app.services.inspection.service import InspectionService
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
    TelegramIdentityProvider,
)
from backend.app.telegram.models import (
    TelegramConversation,
    TelegramUserIdentity,
    TelegramWorkflowState,
)

logger = logging.getLogger(__name__)


class TelegramBotAdapter:
    """Core adapter bridging Telegram messenger requests to Veriqoo inspection domain."""

    def __init__(
        self,
        inspection_service: InspectionService,
        execution_service: InspectionExecutionService | None = None,
        identity_provider: TelegramIdentityProvider | None = None,
    ) -> None:
        self.inspection_service = inspection_service
        self.execution_service = execution_service or InspectionExecutionService(inspection_service=inspection_service)
        self.identity_provider = identity_provider or DeterministicTelegramIdentityProvider()
        self._conversations: dict[int, TelegramConversation] = {}
        self._lock = threading.RLock()

    def _get_conversation(self, identity: TelegramUserIdentity) -> TelegramConversation:
        """Get or initialize conversation state for a chat."""
        with self._lock:
            if identity.chat_id not in self._conversations:
                self._conversations[identity.chat_id] = TelegramConversation(
                    chat_id=identity.chat_id,
                    telegram_user_id=identity.telegram_user_id,
                )
            conv = self._conversations[identity.chat_id]
            conv.last_interaction = datetime.now(timezone.utc)
            return conv

    def _verify_ownership(self, inspection: Inspection, user: AuthenticatedUser) -> bool:
        """Verify the authenticated user owns the inspection."""
        if inspection.owner_id and inspection.owner_id != user.user_id:
            return False
        return True

    def handle_start(self, identity: TelegramUserIdentity) -> str:
        """Handle /start command."""
        self._get_conversation(identity)
        return format_welcome_message(identity.display_name)

    def handle_help(self, identity: TelegramUserIdentity) -> str:
        """Handle /help command."""
        self._get_conversation(identity)
        return format_help_message()

    def handle_new(
        self,
        identity: TelegramUserIdentity,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Handle /new command: create a new inspection session."""
        conv = self._get_conversation(identity)
        user = self.identity_provider.get_authenticated_user(identity)

        with self._lock:
            # Check if active inspection is already in COLLECTING state
            if conv.active_inspection_id:
                try:
                    active_insp = self.inspection_service.repository.get_inspection(conv.active_inspection_id)
                    if active_insp.status == InspectionStatus.COLLECTING:
                        return (
                            f"⚠️ You already have an active inspection (`{active_insp.inspection_id}`) with "
                            f"{active_insp.image_count} image(s).\n\n"
                            "• Send photos to add images\n"
                            "• Send /run to analyze\n"
                            "• Send /cancel to discard and start fresh"
                        )
                except Exception:
                    # Stale active ID, reset cleanly
                    conv.active_inspection_id = None

            # Prepare metadata with Telegram context
            meta = dict(metadata or {})
            meta["created_via"] = "telegram"
            meta["telegram_chat_id"] = identity.chat_id
            meta["telegram_user_id"] = identity.telegram_user_id
            if identity.username:
                meta["telegram_username"] = identity.username

            inspection = self.inspection_service.create_inspection(
                metadata=meta,
                owner_id=user.user_id,
            )
            conv.active_inspection_id = inspection.inspection_id
            conv.state = TelegramWorkflowState.COLLECTING

            return (
                f"🆕 *New Inspection Initialized!*\n\n"
                f"• *Inspection ID:* `{inspection.inspection_id}`\n"
                f"• *Status:* 📥 Collecting Photos\n\n"
                "📸 Please send photographs of the package (front, back, sides, declarations).\n"
                "When you are done uploading, send /run to begin compliance verification."
            )

    def handle_photo(
        self,
        identity: TelegramUserIdentity,
        photo_bytes: bytes,
        filename: str | None = None,
    ) -> str:
        """Handle receiving a photo from a Telegram user."""
        conv = self._get_conversation(identity)
        user = self.identity_provider.get_authenticated_user(identity)

        if not conv.active_inspection_id:
            return "🔍 No active inspection session. Send /new to start one."

        inspection_id = conv.active_inspection_id

        try:
            insp = self.inspection_service.repository.get_inspection(inspection_id)
        except InspectionNotFoundError:
            conv.active_inspection_id = None
            return format_safe_error("INSPECTION_NOT_FOUND")

        # Authorization check
        if not self._verify_ownership(insp, user):
            conv.active_inspection_id = None
            return format_safe_error("INSPECTION_NOT_FOUND")

        # Lifecycle check
        if insp.status != InspectionStatus.COLLECTING:
            return (
                f"⚠️ This inspection is currently *{insp.status.value}* and cannot accept new photos.\n"
                "Send /new to start a new inspection."
            )

        # Upload and normalize image
        try:
            artifact, ref = self.inspection_service.upload_image(
                inspection_id=inspection_id,
                contents=photo_bytes,
                filename=filename or "telegram_photo.jpg",
            )
            # Fetch updated inspection
            updated_insp = self.inspection_service.repository.get_inspection(inspection_id)
            count = updated_insp.image_count
            return (
                f"📸 *Photo {ref.sequence} added!* (Total: {count})\n\n"
                "• Send another photo\n"
                "• Or send /run to start compliance verification"
            )
        except ImageTooLargeError:
            return format_safe_error("IMAGE_TOO_LARGE")
        except UnsupportedImageFormatError:
            return format_safe_error("IMAGE_UNSUPPORTED")
        except (InvalidImageError, ImageDecodeError, ImageIngestionError):
            return format_safe_error("INVALID_IMAGE")
        except InspectionStateError:
            return format_safe_error("INVALID_INSPECTION_STATE")
        except Exception as exc:
            logger.exception("Unexpected error uploading Telegram image: %s", exc)
            return format_safe_error("INTERNAL_ERROR", str(exc))

    def handle_run(self, identity: TelegramUserIdentity) -> str:
        """Handle /run command: schedule background verification."""
        conv = self._get_conversation(identity)
        user = self.identity_provider.get_authenticated_user(identity)

        if not conv.active_inspection_id:
            return "🔍 No active inspection session. Send /new to start one."

        inspection_id = conv.active_inspection_id

        try:
            insp = self.inspection_service.repository.get_inspection(inspection_id)
        except InspectionNotFoundError:
            conv.active_inspection_id = None
            return format_safe_error("INSPECTION_NOT_FOUND")

        # Authorization check
        if not self._verify_ownership(insp, user):
            conv.active_inspection_id = None
            return format_safe_error("INSPECTION_NOT_FOUND")

        if insp.image_count == 0:
            return "⚠️ Please upload at least one package photo before running verification."

        if insp.status == InspectionStatus.COMPLETED:
            return "✅ This inspection is already completed. Send /report to view the compliance findings."

        if insp.status == InspectionStatus.RUNNING:
            return "⏳ Verification is currently running. Send /status or /report to check progress."

        # Schedule execution (also handles manual retry from FAILED)
        try:
            status, msg = self.execution_service.schedule_execution(inspection_id)
            conv.state = TelegramWorkflowState.RUNNING
            return (
                "🚀 *Verification Started!*\n\n"
                f"• *Inspection ID:* `{inspection_id}`\n"
                f"• *Status:* ⏳ Analysis in Progress\n\n"
                "The AI engine is currently performing OCR extraction and statutory legal rule verification.\n"
                "💡 Send /status or /report in a few moments to view your findings."
            )
        except Exception as exc:
            logger.exception("Failed to schedule execution via Telegram: %s", exc)
            return format_safe_error("PIPELINE_ERROR", str(exc))

    def handle_status(self, identity: TelegramUserIdentity) -> str:
        """Handle /status command: query current persistent inspection status."""
        conv = self._get_conversation(identity)
        user = self.identity_provider.get_authenticated_user(identity)

        if not conv.active_inspection_id:
            return "🔍 No active inspection session. Send /new to start one."

        inspection_id = conv.active_inspection_id

        try:
            insp = self.inspection_service.repository.get_inspection(inspection_id)
        except InspectionNotFoundError:
            conv.active_inspection_id = None
            return format_safe_error("INSPECTION_NOT_FOUND")

        if not self._verify_ownership(insp, user):
            conv.active_inspection_id = None
            return format_safe_error("INSPECTION_NOT_FOUND")

        return format_inspection_status(insp)

    def handle_report(self, identity: TelegramUserIdentity) -> str:
        """Handle /report command: retrieve final verification report."""
        conv = self._get_conversation(identity)
        user = self.identity_provider.get_authenticated_user(identity)

        if not conv.active_inspection_id:
            return "🔍 No active inspection session. Send /new to start one."

        inspection_id = conv.active_inspection_id

        try:
            insp = self.inspection_service.repository.get_inspection(inspection_id)
        except InspectionNotFoundError:
            conv.active_inspection_id = None
            return format_safe_error("INSPECTION_NOT_FOUND")

        if not self._verify_ownership(insp, user):
            conv.active_inspection_id = None
            return format_safe_error("INSPECTION_NOT_FOUND")

        if insp.status == InspectionStatus.COLLECTING:
            return (
                f"📥 Photos are still being collected (Total: {insp.image_count}).\n"
                "Send /run to execute verification before viewing the report."
            )

        if insp.status == InspectionStatus.RUNNING:
            return "⏳ Verification is still running in the background. Please check /report again shortly."

        if insp.status == InspectionStatus.FAILED:
            error_details = insp.metadata.get("execution_error", "Verification pipeline failed.")
            clean_err = sanitize_telegram_text(str(error_details))
            return (
                f"❌ *Verification Failed:*\n{clean_err}\n\n"
                "💡 Send /run to manually retry this inspection."
            )

        # COMPLETED: Fetch report
        report = self.inspection_service.repository.get_report(inspection_id)
        if not report:
            return format_safe_error("REPORT_NOT_AVAILABLE")

        conv.state = TelegramWorkflowState.COMPLETED
        return format_inspection_report(report)

    def handle_cancel(self, identity: TelegramUserIdentity) -> str:
        """Handle /cancel command: clear Telegram conversation state."""
        conv = self._get_conversation(identity)
        with self._lock:
            old_id = conv.active_inspection_id
            conv.active_inspection_id = None
            conv.state = TelegramWorkflowState.IDLE

        if old_id:
            return f"🛑 Session for inspection `{old_id}` has been cleared.\nSend /new to start a new inspection."
        return "🛑 No active inspection session. Send /new to start one."
