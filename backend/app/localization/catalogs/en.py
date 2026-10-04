"""Canonical English Translation Catalog for LegalMetrologyAI (Phase U3)."""

from typing import Any

CATALOG_EN: dict[str, Any] = {
    # -----------------------------------------------------------------
    # Statutory Rule and Declaration Field Labels
    # -----------------------------------------------------------------
    "statutory_labels": {
        "R-6-1-a": "Manufacturer / Packer / Importer Identity & Address",
        "R-6-1-b": "Generic Name of Commodity",
        "R-6-1-c": "Net Quantity Declaration",
        "R-6-1-d": "Date of Manufacture / Packing / Import",
        "R-6-1-e": "Maximum Retail Price (MRP)",
        "R-6-1-f": "Consumer Care Contact Details",
        "R-6-1-g": "Country of Origin",
        "R-6-1-h": "Unit Sale Price (USP)",
    },
    "field_labels": {
        "manufacturer_name": "Manufacturer Name",
        "manufacturer_address": "Manufacturer Address",
        "packer_name": "Packer Name",
        "packer_address": "Packer Address",
        "importer_name": "Importer Name",
        "importer_address": "Importer Address",
        "commodity_name": "Commodity Name",
        "net_quantity": "Net Quantity Declaration",
        "net_quantity_unit": "Net Quantity Unit",
        "mrp": "Maximum Retail Price (MRP)",
        "mrp_currency": "MRP Currency Symbol",
        "batch_number": "Batch Number",
        "lot_number": "Lot Number",
        "manufacture_date": "Date of Manufacture",
        "packing_date": "Date of Packing",
        "import_date": "Date of Import",
        "consumer_care": "Consumer Care Details",
        "consumer_care_phone": "Consumer Care Phone",
        "consumer_care_email": "Consumer Care Email",
        "country_of_origin": "Country of Origin",
        "generic_declaration": "Mandatory Declaration",
        "unparsed": "Unparsed Evidence",
    },

    # -----------------------------------------------------------------
    # Verification Status Display Names
    # -----------------------------------------------------------------
    "status_labels": {
        "PASS": "Compliant",
        "FAIL": "Non-Compliant",
        "REVIEW_REQUIRED": "Review Required",
        "NOT_VISIBLE": "Not Visible",
        "NOT_APPLICABLE": "Not Applicable",
    },

    # -----------------------------------------------------------------
    # Compliance Score Ratings (U1)
    # -----------------------------------------------------------------
    "ratings": {
        "FULLY_COMPLIANT": "Fully Compliant",
        "SUBSTANTIALLY_COMPLIANT": "Substantially Compliant",
        "PARTIALLY_COMPLIANT": "Partially Compliant",
        "NON_COMPLIANT": "Non-Compliant",
    },

    # -----------------------------------------------------------------
    # Deterministic Verification Reason Templates
    # -----------------------------------------------------------------
    "reasons": {
        "requirement_not_applicable": "Requirement is not applicable under current inspection facts.",
        "applicability_unknown": "Applicability of requirement is UNKNOWN. Human review required before compliance evaluation.",
        "declaration_not_visible": "Requirement applies, but required declaration was not visible in provided evidence.",
        "contradictory_declarations": "Contradictory declarations detected for requirement {requirement_id}: candidate {c1_id} ('{c1_text}') vs candidate {c2_id} ('{c2_text}').",
        "evidence_ambiguous": "Evidence for requirement is ambiguous or unparsed ({details}). Requires manual review.",
        "requirement_satisfied": "Requirement satisfied by {count} valid declaration candidate(s).",
        "statutory_defect_generic": "Statutory non-compliance detected for requirement {requirement_id}: {details}",
        "mrp_missing_currency": "MRP declaration is missing mandatory Indian Rupee currency symbol prefix (₹ or Rs.).",
        "mfg_address_incomplete": "Manufacturer address declaration is missing mandatory city, state, or PIN code details.",
        "net_qty_unspecified_unit": "Net quantity declaration is missing standard metric unit of measurement.",
        "date_incomplete_format": "Date of manufacture/packing must specify month and year of packing.",
        "country_of_origin_missing": "Country of origin declaration is mandatory for imported and pre-packaged goods.",
    },

    # -----------------------------------------------------------------
    # Report Overall Summary Templates
    # -----------------------------------------------------------------
    "report_summaries": {
        "fail": "Statutory compliance failure in requirement(s): {failed_ids}.",
        "review_required": "Manual review required for requirement(s): {review_ids}.",
        "not_visible": "Required declaration(s) not visible in evidence for requirement(s): {not_vis_ids}.",
        "pass": "All applicable requirements satisfied ({pass_count} passed, {na_count} not applicable).",
        "no_requirements": "No legal requirements were evaluated in this inspection.",
        "unable_to_establish": "Unable to establish conclusive compliance state.",
    },

    # -----------------------------------------------------------------
    # API Error Messages (Mapped by ErrorCode)
    # -----------------------------------------------------------------
    "errors": {
        "INVALID_REQUEST": "Invalid request parameters or payload format.",
        "INSPECTION_NOT_FOUND": "Inspection session with ID '{inspection_id}' not found.",
        "INVALID_INSPECTION_STATE": "Operation not permitted in current inspection lifecycle state.",
        "INVALID_IMAGE": "Provided file is not a valid or decodable image.",
        "IMAGE_EMPTY": "Uploaded image file is empty (0 bytes).",
        "IMAGE_TOO_LARGE": "Uploaded image exceeds maximum permissible dimensions or file size.",
        "IMAGE_UNSUPPORTED": "Unsupported image format. Please supply a valid JPEG, PNG, or WEBP photograph.",
        "AUTHENTICATION_REQUIRED": "Authentication required to access this resource.",
        "AUTHENTICATION_INVALID": "Provided authentication credentials or token are invalid.",
        "AUTHENTICATION_EXPIRED": "Authentication token has expired.",
        "INSPECTION_ACCESS_DENIED": "You do not have permission to access this inspection session.",
        "REPORT_NOT_AVAILABLE": "Inspection report has not been generated for this inspection.",
        "PIPELINE_ERROR": "Inspection verification pipeline execution encountered an internal error.",
        "INTERNAL_ERROR": "An unexpected internal server error occurred.",
        "ACCOUNT_UNLINKED": "Your Telegram account is not linked to a Veriqoo account. Please link your account first using /link.",
    },

    # -----------------------------------------------------------------
    # Telegram Bot Messages
    # -----------------------------------------------------------------
    "telegram": {
        "welcome": (
            "👋 Welcome to Veriqoo, {display_name}!\n\n"
            "Veriqoo is an AI-powered legal-compliance inspection system for packaged commodities.\n\n"
            "📋 *Commands:*\n"
            "• /link — Connect your Veriqoo account\n"
            "• /unlink — Disconnect your account\n"
            "• /lang — Switch language (en, hi, mr)\n"
            "• /new — Start a new inspection session\n"
            "• Send Photos — Upload package photographs\n"
            "• /run — Trigger compliance verification\n"
            "• /status — Check current inspection status\n"
            "• /report — View detailed compliance results\n"
            "• /cancel — Cancel the active session\n"
            "• /help — Show assistance & command guide"
        ),
        "help": (
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
            "• /lang — Switch language (en, hi, mr)\n"
            "• /new — Initialize new session\n"
            "• /run — Execute verification pipeline\n"
            "• /status — Check current progress\n"
            "• /report — Retrieve final report\n"
            "• /cancel — Reset active session\n"
            "• /help — Show this help message"
        ),
        "status_header": "📊 *Inspection Status*",
        "status_collecting": "📥 Collecting Photos",
        "status_ready": "📦 Ready for Verification",
        "status_running": "⏳ Analysis in Progress",
        "status_completed": "✅ Completed",
        "status_failed": "❌ Processing Failed",
        "tip_collecting": "\n💡 Send more photos or send /run to begin compliance verification.",
        "tip_running": "\n💡 Verification is running in the background. Send /status or /report in a few moments.",
        "tip_completed": "\n💡 Verification complete! Send /report to view findings.",
        "tip_failed": "\n💡 Inspection failed. You can send /run to manually retry.",
        "report_header_pass": "✅ *COMPLIANCE STATUS: PASS*",
        "report_header_fail": "❌ *COMPLIANCE STATUS: NON-COMPLIANT (FAIL)*",
        "report_header_review": "⚠️ *COMPLIANCE STATUS: REVIEW REQUIRED*",
        "counts_breakdown": "📈 *Counts Breakdown:*",
        "total_evaluated": "Total Requirements Evaluated",
        "passed": "Passed",
        "failed": "Failed",
        "review_required": "Review Required",
        "not_visible": "Not Visible",
        "key_findings": "🔍 *Key Findings & Observations:*",
        "lang_changed": "🌐 Language set to *English*.",
        "lang_invalid": "⚠️ Unsupported language '{lang}'. Supported languages: `en` (English), `hi` (हिन्दी), `mr` (मराठी).",
    },

    # -----------------------------------------------------------------
    # Telegram Safe Error Messages
    # -----------------------------------------------------------------
    "telegram_errors": {
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
    },

    # -----------------------------------------------------------------
    # Persona Tailored Presentations
    # -----------------------------------------------------------------
    "personas": {
        "consumer": {
            "pass": "The package displays all required legal declarations properly.",
            "fail": "This package appears to have an issue with mandatory declarations (e.g. MRP, quantity, or date).",
            "review": "Some declarations on this package require further clarification or verification.",
        },
        "inspector": {
            "pass": "Statutory declarations verified and conformant with Legal Metrology (Packaged Commodities) Rules, 2011.",
            "fail": "Non-compliance observed under Legal Metrology Rules for requirement(s): {requirement_id}.",
            "review": "Ambiguity or contradiction detected in mandatory declarations. Field inspection review recommended.",
        },
        "authority": {
            "pass": "Pre-packaged commodity complies with the Legal Metrology Act, 2009 and Rules framed thereunder.",
            "fail": "Noticeable contravention of Legal Metrology (Packaged Commodities) Rules, 2011 documented for {requirement_id}.",
            "review": "Inconclusive evidence requiring statutory verification under Rule 6 of Packaged Commodities Rules.",
        },
    },

    # -----------------------------------------------------------------
    # Consumer Scan Intelligence (Phase U5)
    # -----------------------------------------------------------------
    "consumer_risk_signals": {
        "HIGH_RISK_NON_COMPLIANCE": "Potential serious compliance issue detected.",
        "POTENTIAL_COMPLIANCE_ISSUE": "Potential declaration issue requiring attention.",
        "INSUFFICIENT_EVIDENCE": "Required package declarations not fully visible.",
        "PRODUCT_IDENTITY_UNCERTAIN": "Product identity could not be verified with confidence.",
        "NO_MAJOR_ISSUES_DETECTED": "No major legal metrology issues detected.",
    },
    "consumer_actions": {
        "REVIEW_LABEL": "Review package labels carefully before purchase.",
        "CHECK_MRP": "Verify that the selling price does not exceed the Maximum Retail Price (MRP).",
        "CHECK_NET_QUANTITY": "Check net quantity declaration on the packaging.",
        "CHECK_MANUFACTURER_DETAILS": "Verify manufacturer, packer, or importer name and address.",
        "CHECK_CONSUMER_CARE_DETAILS": "Verify consumer care phone number and email contact.",
        "CAPTURE_BACK_PANEL": "Capture the back panel of the package for complete verification.",
        "CAPTURE_FRONT_PANEL": "Capture the front panel showing brand and commodity name.",
        "RESCAN_PACKAGE": "Rescan the package with clear lighting and focused text.",
        "REVIEW_REPORT": "Review the full detailed verification report.",
    },
    "scan_quality_issues": {
        "INSUFFICIENT_IMAGES": "Insufficient number of images captured.",
        "LOW_OCR_CONFIDENCE": "OCR text readability is low due to lighting or blur.",
        "INCOMPLETE_PACKAGE_VIEW": "Some sides of the packaging were not captured.",
        "CONFLICTING_OBSERVATIONS": "Conflicting text detected across multiple photographs.",
        "INSUFFICIENT_REQUIRED_DECLARATIONS": "Key mandatory declarations were not found.",
        "PRODUCT_IDENTITY_UNCERTAIN": "Product name or brand could not be clearly identified.",
    },

    # -----------------------------------------------------------------
    # Consumer Compliance Result & Explanation (Phase U6)
    # -----------------------------------------------------------------
    "consumer_results": {
        "NO_MAJOR_ISSUES_DETECTED": "No Major Compliance Issues Detected",
        "COMPLIANCE_ISSUE_DETECTED": "Compliance Issue Detected",
        "REVIEW_RECOMMENDED": "Review Recommended",
        "INSUFFICIENT_EVIDENCE": "Insufficient Visible Evidence",
    },
    "consumer_summaries": {
        "NO_MAJOR_ISSUES_DETECTED": "The scanned package did not show any major compliance issues in the requirements that could be verified from the submitted images.",
        "COMPLIANCE_ISSUE_DETECTED": "One or more compliance requirements were not satisfied based on the evidence captured during this scan.",
        "REVIEW_RECOMMENDED": "Some requirements could not be confidently verified. A closer review or additional package images may be needed.",
        "INSUFFICIENT_EVIDENCE": "There was not enough visible information to complete the verification.",
    },
    "consumer_what_this_means": {
        "NO_MAJOR_ISSUES_DETECTED": "Based on the photos provided, the visible declarations conform to standard packaging requirements.",
        "COMPLIANCE_ISSUE_DETECTED": "The package appears to have missing, incomplete, or non-compliant mandatory declarations.",
        "REVIEW_RECOMMENDED": "The package information captured was partially unclear or requires human verification before making a purchase.",
        "INSUFFICIENT_EVIDENCE": "Important panels of the packaging were not visible in your photos, so full compliance could not be verified.",
    },
    "consumer_finding_templates": {
        "pass": "Verified from the submitted package images.",
        "review_required": "Declaration for {title} could not be confidently verified from the images.",
        "not_visible": "Declaration for {title} was not visible on the captured package panels.",
    },
    "consumer_limitations": {
        "VERIFICATION_LIMITED_TO_CAPTURED_IMAGES": "Compliance verification is limited strictly to the declarations visible in the provided package images.",
        "SOME_DECLARATIONS_NOT_VISIBLE": "Some mandatory declarations were not visible on the submitted package sides.",
        "PRODUCT_IDENTITY_UNCERTAIN": "Product identification was uncertain because available package evidence was incomplete.",
        "NON_APPLICABLE_EXCLUDED": "Exempt or non-applicable legal requirements were excluded from this evaluation.",
        "INCOMPLETE_PACKAGE_VIEW": "Not all package sides were captured in the photos.",
        "LOW_OCR_CONFIDENCE": "Text readability was reduced due to lighting, glare, or blur.",
    },
    "consumer_severities": {
        "HIGH": "Issue",
        "MEDIUM": "Review Needed",
        "LOW": "Not Visible",
        "INFO": "Verified",
    },
}
