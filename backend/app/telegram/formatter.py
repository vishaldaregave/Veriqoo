"""Message formatting utilities for Telegram bot responses."""

from __future__ import annotations

import re
from typing import Any

from backend.app.localization.service import (
    SupportedLanguage,
    get_localization_service,
)
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


def format_welcome_message(
    display_name: str,
    lang: SupportedLanguage | str = SupportedLanguage.EN,
) -> str:
    """Format /start welcome response in requested language."""
    loc = get_localization_service()
    return loc.get_string("telegram", "welcome", lang=lang, params={"display_name": display_name})


def format_help_message(
    lang: SupportedLanguage | str = SupportedLanguage.EN,
) -> str:
    """Format /help command guide in requested language."""
    loc = get_localization_service()
    return loc.get_string("telegram", "help", lang=lang)


def format_lang_changed_message(
    lang: SupportedLanguage | str,
) -> str:
    """Format confirmation message after switching language."""
    loc = get_localization_service()
    return loc.get_string("telegram", "lang_changed", lang=lang)


def format_lang_invalid_message(
    invalid_lang: str,
    lang: SupportedLanguage | str = SupportedLanguage.EN,
) -> str:
    """Format error message for unsupported language code."""
    loc = get_localization_service()
    return loc.get_string("telegram", "lang_invalid", lang=lang, params={"lang": invalid_lang})


def format_inspection_status(
    inspection: Inspection,
    lang: SupportedLanguage | str = SupportedLanguage.EN,
) -> str:
    """Format current inspection container status in requested language."""
    loc = get_localization_service()
    lang_enum = lang if isinstance(lang, SupportedLanguage) else SupportedLanguage.from_str(lang)

    status_keys = {
        InspectionStatus.COLLECTING: "status_collecting",
        InspectionStatus.READY: "status_ready",
        InspectionStatus.RUNNING: "status_running",
        InspectionStatus.COMPLETED: "status_completed",
        InspectionStatus.FAILED: "status_failed",
    }
    key = status_keys.get(inspection.status, "status_collecting")
    status_label = loc.get_string("telegram", key, lang=lang_enum)
    img_count = inspection.image_count

    msg = (
        f"{loc.get_string('telegram', 'status_header', lang=lang_enum)}\n\n"
        f"• *Inspection ID:* `{inspection.inspection_id}`\n"
        f"• *Status:* {status_label}\n"
        f"• *Images Uploaded:* {img_count}\n"
    )

    if inspection.status == InspectionStatus.COLLECTING:
        msg += loc.get_string("telegram", "tip_collecting", lang=lang_enum)
    elif inspection.status == InspectionStatus.RUNNING:
        msg += loc.get_string("telegram", "tip_running", lang=lang_enum)
    elif inspection.status == InspectionStatus.COMPLETED:
        msg += loc.get_string("telegram", "tip_completed", lang=lang_enum)
    elif inspection.status == InspectionStatus.FAILED:
        msg += loc.get_string("telegram", "tip_failed", lang=lang_enum)

    return msg


def format_inspection_report(
    report: InspectionReport,
    lang: SupportedLanguage | str = SupportedLanguage.EN,
) -> str:
    """Format final InspectionReport into a structured Telegram message in requested language."""
    loc = get_localization_service()
    lang_enum = lang if isinstance(lang, SupportedLanguage) else SupportedLanguage.from_str(lang)

    header_keys = {
        OverallInspectionStatus.PASS: "report_header_pass",
        OverallInspectionStatus.FAIL: "report_header_fail",
        OverallInspectionStatus.REVIEW_REQUIRED: "report_header_review",
    }
    header_key = header_keys.get(report.overall_status, "report_header_review")
    header = loc.get_string("telegram", header_key, lang=lang_enum)

    failed_ids = [r.requirement_id for r in report.verification_results if r.status == VerificationStatus.FAIL]
    review_ids = [r.requirement_id for r in report.verification_results if r.status == VerificationStatus.REVIEW_REQUIRED]
    not_vis_ids = [r.requirement_id for r in report.verification_results if r.status == VerificationStatus.NOT_VISIBLE]

    summary_text = loc.localize_report_summary(
        overall_status=report.overall_status.value,
        failed_ids=failed_ids,
        review_ids=review_ids,
        not_vis_ids=not_vis_ids,
        pass_count=report.pass_count,
        na_count=report.not_applicable_count,
        lang=lang_enum,
    ) if lang_enum != SupportedLanguage.EN else report.summary

    counts_title = loc.get_string("telegram", "counts_breakdown", lang=lang_enum)
    lbl_total = loc.get_string("telegram", "total_evaluated", lang=lang_enum)
    lbl_passed = loc.get_string("telegram", "passed", lang=lang_enum)
    lbl_failed = loc.get_string("telegram", "failed", lang=lang_enum)
    lbl_review = loc.get_string("telegram", "review_required", lang=lang_enum)
    lbl_notvis = loc.get_string("telegram", "not_visible", lang=lang_enum)

    lines = [
        header,
        f"\n• *Inspection ID:* `{report.inspection_id}`",
        f"• *Summary:* {summary_text}",
        f"\n{counts_title}",
        f"• {lbl_total}: {report.applicable_requirement_count}",
        f"• ✅ {lbl_passed}: {report.pass_count}",
        f"• ❌ {lbl_failed}: {report.fail_count}",
        f"• ⚠️ {lbl_review}: {report.review_required_count}",
        f"• 👁️ {lbl_notvis}: {report.not_visible_count}",
    ]

    # Include specific findings for FAIL or REVIEW_REQUIRED results
    issues: list[VerificationResult] = [
        r for r in report.verification_results
        if r.status in (VerificationStatus.FAIL, VerificationStatus.REVIEW_REQUIRED)
    ]

    if issues:
        lines.append(f"\n{loc.get_string('telegram', 'key_findings', lang=lang_enum)}")
        for idx, issue in enumerate(issues[:5], start=1):
            status_icon = "❌" if issue.status == VerificationStatus.FAIL else "⚠️"
            req_id = issue.requirement_id
            rule_src = (issue.metadata or {}).get("rule_source", "")
            src_text = f" ({rule_src})" if rule_src else ""
            reason_text = loc.localize_verification_reason(
                canonical_reason=issue.reason,
                status=issue.status.value if hasattr(issue.status, "value") else str(issue.status),
                requirement_id=issue.requirement_id,
                lang=lang_enum,
            ) if lang_enum != SupportedLanguage.EN else issue.reason
            lines.append(f"{idx}. {status_icon} *{req_id}*{src_text}: {reason_text}")

    return "\n".join(lines)


def format_safe_error(
    error_code: str,
    message: str | None = None,
    lang: SupportedLanguage | str = SupportedLanguage.EN,
) -> str:
    """Map standardized API error codes into user-friendly Telegram error messages in requested language."""
    loc = get_localization_service()
    code_str = error_code.value if hasattr(error_code, "value") else str(error_code)
    # Check telegram specific errors section first
    lang_cat = loc.get_catalog(lang)
    en_cat = loc.get_catalog("en")
    user_msg = lang_cat.get("telegram_errors", {}).get(code_str) or en_cat.get("telegram_errors", {}).get(code_str)
    if user_msg:
        return user_msg
    clean_msg = sanitize_telegram_text(message or "An unexpected error occurred.")
    return f"⚠️ {clean_msg}"

