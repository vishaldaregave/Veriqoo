"""Message formatting utilities for Telegram bot responses."""

from __future__ import annotations

import re
from typing import Any

from backend.app.services.inspection.models import Inspection, InspectionStatus
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.inspection_pipeline.report import InspectionReport
from backend.app.services.verification.models import VerificationResult, VerificationStatus


def sanitize_telegram_text(text: str) -> str:
    """Strip any accidental internal paths, tokens, or sensitive patterns from message text."""
    if not text:
        return ""
    # Redact JWTs
    sanitized = re.sub(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9._-]{10,}", "[REDACTED_TOKEN]", text)
    # Redact bearer headers
    sanitized = re.sub(r"(?i)bearer\s+[A-Za-z0-9._-]+", "Bearer [REDACTED]", sanitized)
    # Redact secret keys
    sanitized = re.sub(r"(?i)(?:key|secret|token|password)[=:]\s*[\'\"]?([^\s\'\"]{6,})[\'\"]?", r"key=[REDACTED]", sanitized)
    return sanitized


def format_welcome_message(display_name: str) -> str:
    """Format /start welcome response."""
    return (
        f"👋 Welcome to Veriqoo, {display_name}!\n\n"
        "Veriqoo is an AI-powered legal-compliance inspection system for packaged commodities.\n\n"
        "📋 *Commands:*\n"
        "• /link — Connect your Veriqoo account\n"
        "• /unlink — Disconnect your account\n"
        "• /new — Start a new inspection session\n"
        "• Send Photos — Upload package photographs\n"
        "• /run — Trigger compliance verification\n"
        "• /status — Check current inspection status\n"
        "• /report — View detailed compliance results\n"
        "• /cancel — Cancel the active session\n"
        "• /help — Show assistance & command guide"
    )


def format_help_message() -> str:
    """Format /help command guide."""
    return (
        "📖 *Veriqoo Telegram Inspection Guide*\n\n"
        "*Step-by-Step Workflow:*\n"
        "0️⃣ Send /link to connect your Veriqoo user account (one-time setup).\n"
        "1️⃣ Send /new to begin a fresh package inspection.\n"
        "2️⃣ Send photos of the package (front, back, sides, declarations).\n"
        "3️⃣ Send /run to start AI OCR & legal verification.\n"
        "4️⃣ Check /status or /report to see your compliance findings.\n\n"
        "*Available Commands:*\n"
        "• /link — Connect your Veriqoo account\n"
        "• /unlink — Disconnect your account\n"
        "• /new — Initialize new session\n"
        "• /run — Execute verification pipeline\n"
        "• /status — Check current progress\n"
        "• /report — Retrieve final report\n"
        "• /cancel — Reset active session\n"
        "• /help — Show this help message"
    )


def format_inspection_status(inspection: Inspection) -> str:
    """Format current inspection container status."""
    status_emojis = {
        InspectionStatus.COLLECTING: "📥 Collecting Photos",
        InspectionStatus.READY: "📦 Ready for Verification",
        InspectionStatus.RUNNING: "⏳ Analysis in Progress",
        InspectionStatus.COMPLETED: "✅ Completed",
        InspectionStatus.FAILED: "❌ Processing Failed",
    }
    status_label = status_emojis.get(inspection.status, inspection.status.value)
    img_count = inspection.image_count

    msg = (
        f"📊 *Inspection Status*\n\n"
        f"• *Inspection ID:* `{inspection.inspection_id}`\n"
        f"• *Status:* {status_label}\n"
        f"• *Images Uploaded:* {img_count}\n"
    )

    if inspection.status == InspectionStatus.COLLECTING:
        msg += "\n💡 Send more photos or send /run to begin compliance verification."
    elif inspection.status == InspectionStatus.RUNNING:
        msg += "\n💡 Verification is running in the background. Send /status or /report in a few moments."
    elif inspection.status == InspectionStatus.COMPLETED:
        msg += "\n💡 Verification complete! Send /report to view findings."
    elif inspection.status == InspectionStatus.FAILED:
        msg += "\n💡 Inspection failed. You can send /run to manually retry."

    return msg


def format_inspection_report(report: InspectionReport) -> str:
    """Format final InspectionReport into a structured Telegram message."""
    status_headers = {
        OverallInspectionStatus.PASS: "✅ *COMPLIANCE STATUS: PASS*",
        OverallInspectionStatus.FAIL: "❌ *COMPLIANCE STATUS: NON-COMPLIANT (FAIL)*",
        OverallInspectionStatus.REVIEW_REQUIRED: "⚠️ *COMPLIANCE STATUS: REVIEW REQUIRED*",
    }

    header = status_headers.get(report.overall_status, f"📋 *COMPLIANCE STATUS: {report.overall_status.value}*")

    lines = [
        header,
        f"\n• *Inspection ID:* `{report.inspection_id}`",
        f"• *Summary:* {report.summary}",
        f"\n📈 *Counts Breakdown:*",
        f"• Total Requirements Evaluated: {report.applicable_requirement_count}",
        f"• ✅ Passed: {report.pass_count}",
        f"• ❌ Failed: {report.fail_count}",
        f"• ⚠️ Review Required: {report.review_required_count}",
        f"• 👁️ Not Visible: {report.not_visible_count}",
    ]

    # Include specific findings for FAIL or REVIEW_REQUIRED results
    issues: list[VerificationResult] = [
        r for r in report.verification_results
        if r.status in (VerificationStatus.FAIL, VerificationStatus.REVIEW_REQUIRED)
    ]

    if issues:
        lines.append("\n🔍 *Key Findings & Observations:*")
        for idx, issue in enumerate(issues[:5], start=1):  # Limit to top 5 findings
            status_icon = "❌" if issue.status == VerificationStatus.FAIL else "⚠️"
            req_id = issue.requirement_id
            rule_src = (issue.metadata or {}).get("rule_source", "")
            src_text = f" ({rule_src})" if rule_src else ""
            lines.append(f"{idx}. {status_icon} *{req_id}*{src_text}: {issue.reason}")

    return "\n".join(lines)


def format_safe_error(error_code: str, message: str | None = None) -> str:
    """Map standardized API error codes into user-friendly Telegram error messages."""
    error_mappings = {
        "ACCOUNT_UNLINKED": "🔒 Your Telegram account is not linked to a Veriqoo account. Please link your account first using /link.",
        "INSPECTION_NOT_FOUND": "🔍 Inspection session not found or you are not authorized to access it.",
        "INVALID_INSPECTION_STATE": "⚠️ Action not permitted in the current inspection state. Send /status to check.",
        "IMAGE_EMPTY": "❌ The uploaded photograph appears to be empty (0 bytes). Please send a valid photo.",
        "IMAGE_TOO_LARGE": "❌ The image is too large (max 25 MB / 32 MP). Please send a compressed photo.",
        "IMAGE_UNSUPPORTED": "❌ Unsupported image format. Please send a standard JPEG, PNG, or WEBP photo.",
        "INVALID_IMAGE": "❌ The image could not be processed. Please take a clear, well-lit photo of the package.",
        "REPORT_NOT_AVAILABLE": "⏳ The inspection report is not yet available. Verification is either running or pending.",
        "PIPELINE_ERROR": "⚠️ Verification processing encountered an issue. Send /run to retry.",
        "AUTHENTICATION_REQUIRED": "🔒 Authentication error. Please restart the session.",
        "INTERNAL_ERROR": "⚠️ A server error occurred. Please try again shortly.",
    }
    user_msg = error_mappings.get(error_code)
    if user_msg:
        return user_msg
    clean_msg = sanitize_telegram_text(message or "An unexpected error occurred.")
    return f"⚠️ {clean_msg}"

