"""Localization Service and Language Negotiation Engine for LegalMetrologyAI (U3)."""

from __future__ import annotations

from enum import Enum
import re
from typing import Any

from backend.app.localization.catalogs.en import CATALOG_EN
from backend.app.localization.catalogs.hi import CATALOG_HI
from backend.app.localization.catalogs.mr import CATALOG_MR


class SupportedLanguage(str, Enum):
    """Strongly typed ISO 639-1 language identifiers for LegalMetrologyAI."""
    EN = "en"
    HI = "hi"
    MR = "mr"

    @classmethod
    def from_str(cls, val: Any) -> SupportedLanguage:
        """Parse raw language string safely with canonical English fallback."""
        if not val or not isinstance(val, str):
            return cls.EN

        clean = val.strip().lower()
        # Handle compound tags like 'hi-IN', 'mr_IN', 'en-US'
        primary = re.split(r"[-_;,]", clean)[0].strip()

        for lang in cls:
            if lang.value == primary:
                return lang

        return cls.EN

    @property
    def display_name(self) -> str:
        """Human-readable display title in native script."""
        names = {
            SupportedLanguage.EN: "English",
            SupportedLanguage.HI: "हिन्दी",
            SupportedLanguage.MR: "मराठी",
        }
        return names.get(self, "English")


class Persona(str, Enum):
    """Target user persona for tailored presentation layers."""
    CONSUMER = "consumer"
    INSPECTOR = "inspector"
    AUTHORITY = "authority"

    @classmethod
    def from_str(cls, val: Any) -> Persona:
        if not val or not isinstance(val, str):
            return cls.CONSUMER
        clean = val.strip().lower()
        for p in cls:
            if p.value == clean:
                return p
        return cls.CONSUMER


class _SafeFormatDict(dict):
    """Safe dictionary helper that leaves unresolved format placeholders intact."""
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


class LocalizationService:
    """Core localization service managing catalog resolution, templates, and negotiation."""

    def __init__(self) -> None:
        self._catalogs: dict[SupportedLanguage, dict[str, Any]] = {
            SupportedLanguage.EN: CATALOG_EN,
            SupportedLanguage.HI: CATALOG_HI,
            SupportedLanguage.MR: CATALOG_MR,
        }

    def get_catalog(self, lang: SupportedLanguage | str) -> dict[str, Any]:
        """Retrieve catalog dictionary for requested language."""
        lang_enum = lang if isinstance(lang, SupportedLanguage) else SupportedLanguage.from_str(lang)
        return self._catalogs.get(lang_enum, CATALOG_EN)

    def get_string(
        self,
        section: str,
        key: str,
        lang: SupportedLanguage | str = SupportedLanguage.EN,
        params: dict[str, Any] | None = None,
        default: str | None = None,
    ) -> str:
        """Retrieve and format a localized string with graceful English and default fallbacks."""
        lang_enum = lang if isinstance(lang, SupportedLanguage) else SupportedLanguage.from_str(lang)
        catalog = self.get_catalog(lang_enum)
        en_catalog = CATALOG_EN

        raw_template = None
        # Try target language catalog
        if section in catalog and isinstance(catalog[section], dict):
            raw_template = catalog[section].get(key)

        # Fallback to English catalog
        if raw_template is None and section in en_catalog and isinstance(en_catalog[section], dict):
            raw_template = en_catalog[section].get(key)

        # Fallback to provided default
        if raw_template is None:
            raw_template = default or key

        # Interpolate params safely
        if params and isinstance(raw_template, str) and "{" in raw_template:
            try:
                # Stringify all parameters to prevent format errors
                safe_params = {k: str(v) if v is not None else "" for k, v in params.items()}
                return raw_template.format_map(_SafeFormatDict(safe_params))
            except Exception:
                return raw_template

        return str(raw_template)

    def get_statutory_label(
        self,
        requirement_id: str,
        lang: SupportedLanguage | str = SupportedLanguage.EN,
    ) -> str:
        """Resolve localized title for statutory requirement ID."""
        return self.get_string(
            section="statutory_labels",
            key=requirement_id,
            lang=lang,
            default=f"Requirement {requirement_id}",
        )

    def get_field_label(
        self,
        field_name: str,
        lang: SupportedLanguage | str = SupportedLanguage.EN,
    ) -> str:
        """Resolve localized title for package declaration field name."""
        clean_name = field_name.value if hasattr(field_name, "value") else str(field_name)
        fallback_default = clean_name.replace("_", " ").title() if clean_name else "Declaration"
        return self.get_string(
            section="field_labels",
            key=clean_name,
            lang=lang,
            default=fallback_default,
        )

    def get_status_label(
        self,
        status: str,
        lang: SupportedLanguage | str = SupportedLanguage.EN,
    ) -> str:
        """Resolve localized label for compliance verification status."""
        status_str = status.value if hasattr(status, "value") else str(status)
        return self.get_string(
            section="status_labels",
            key=status_str,
            lang=lang,
            default=status_str,
        )

    def get_rating_label(
        self,
        rating: str,
        lang: SupportedLanguage | str = SupportedLanguage.EN,
    ) -> str:
        """Resolve localized label for compliance score rating."""
        rating_str = rating.value if hasattr(rating, "value") else str(rating)
        return self.get_string(
            section="ratings",
            key=rating_str,
            lang=lang,
            default=rating_str.replace("_", " ").title(),
        )

    def localize_verification_reason(
        self,
        canonical_reason: str,
        status: str,
        requirement_id: str,
        lang: SupportedLanguage | str = SupportedLanguage.EN,
        reason_key: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Produce localized human-readable reason while preserving canonical reasoning semantics."""
        lang_enum = lang if isinstance(lang, SupportedLanguage) else SupportedLanguage.from_str(lang)
        if lang_enum == SupportedLanguage.EN and not reason_key:
            return canonical_reason

        # If explicit reason key provided, use catalog
        if reason_key:
            return self.get_string("reasons", reason_key, lang=lang_enum, params=params, default=canonical_reason)

        # Match known canonical deterministic patterns to keys
        r_text = canonical_reason or ""
        if "not applicable under current inspection facts" in r_text.lower():
            return self.get_string("reasons", "requirement_not_applicable", lang=lang_enum)
        if "applicability of requirement is unknown" in r_text.lower():
            return self.get_string("reasons", "applicability_unknown", lang=lang_enum)
        if "required declaration was not visible" in r_text.lower():
            return self.get_string("reasons", "declaration_not_visible", lang=lang_enum)
        if "missing currency symbol" in r_text.lower() or "currency symbol prefix" in r_text.lower():
            return self.get_string("reasons", "mrp_missing_currency", lang=lang_enum)
        if "missing mandatory city, state, or pin" in r_text.lower() or "address declaration is missing" in r_text.lower():
            return self.get_string("reasons", "mfg_address_incomplete", lang=lang_enum)
        if "missing standard metric unit" in r_text.lower() or "unclear unit" in r_text.lower():
            return self.get_string("reasons", "net_qty_unspecified_unit", lang=lang_enum)
        if "country of origin" in r_text.lower() and "mandatory" in r_text.lower():
            return self.get_string("reasons", "country_of_origin_missing", lang=lang_enum)
        if "requirement satisfied by" in r_text.lower():
            count_match = re.search(r"(\d+)\s+valid declaration", r_text)
            cnt = count_match.group(1) if count_match else "1"
            return self.get_string("reasons", "requirement_satisfied", lang=lang_enum, params={"count": cnt})

        # For unknown / Gemini custom reasoning without an exact template match:
        # Fall back to canonical English to guarantee statutory accuracy without hallucination
        return canonical_reason

    def localize_report_summary(
        self,
        overall_status: str,
        failed_ids: list[str] | None = None,
        review_ids: list[str] | None = None,
        not_vis_ids: list[str] | None = None,
        pass_count: int = 0,
        na_count: int = 0,
        lang: SupportedLanguage | str = SupportedLanguage.EN,
    ) -> str:
        """Format localized overall report summary statement."""
        lang_enum = lang if isinstance(lang, SupportedLanguage) else SupportedLanguage.from_str(lang)
        status_str = overall_status.value if hasattr(overall_status, "value") else str(overall_status)

        if status_str == "FAIL" and failed_ids:
            return self.get_string(
                "report_summaries",
                "fail",
                lang=lang_enum,
                params={"failed_ids": ", ".join(failed_ids)},
            )
        if status_str == "REVIEW_REQUIRED":
            if failed_ids:
                return self.get_string(
                    "report_summaries",
                    "fail",
                    lang=lang_enum,
                    params={"failed_ids": ", ".join(failed_ids)},
                )
            if review_ids:
                return self.get_string(
                    "report_summaries",
                    "review_required",
                    lang=lang_enum,
                    params={"review_ids": ", ".join(review_ids)},
                )
            if not_vis_ids:
                return self.get_string(
                    "report_summaries",
                    "not_visible",
                    lang=lang_enum,
                    params={"not_vis_ids": ", ".join(not_vis_ids)},
                )
            if pass_count == 0 and na_count == 0:
                return self.get_string("report_summaries", "no_requirements", lang=lang_enum)
            return self.get_string("report_summaries", "unable_to_establish", lang=lang_enum)
        if status_str == "PASS":
            return self.get_string(
                "report_summaries",
                "pass",
                lang=lang_enum,
                params={"pass_count": pass_count, "na_count": na_count},
            )

        return self.get_string("report_summaries", "unable_to_establish", lang=lang_enum)

    def localize_error(
        self,
        error_code: str,
        fallback_message: str | None = None,
        lang: SupportedLanguage | str = SupportedLanguage.EN,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Retrieve localized human-readable error description while preserving error.code."""
        code_str = error_code.value if hasattr(error_code, "value") else str(error_code)
        return self.get_string(
            section="errors",
            key=code_str,
            lang=lang,
            params=params,
            default=fallback_message or "An error occurred.",
        )

    def localize_persona_explanation(
        self,
        requirement_id: str,
        status: str,
        persona: Persona | str = Persona.CONSUMER,
        lang: SupportedLanguage | str = SupportedLanguage.EN,
        details: dict[str, Any] | None = None,
    ) -> str:
        """Format persona-tailored compliance guidance (Consumer vs Inspector vs Authority)."""
        persona_enum = persona if isinstance(persona, Persona) else Persona.from_str(persona)
        status_str = status.value.lower() if hasattr(status, "value") else str(status).lower()

        section = "personas"
        persona_cat = self.get_catalog(lang).get(section, {}).get(persona_enum.value, {})
        en_persona_cat = CATALOG_EN.get(section, {}).get(persona_enum.value, {})

        key = "pass" if "pass" in status_str else ("fail" if "fail" in status_str else "review")
        raw_tmpl = persona_cat.get(key) or en_persona_cat.get(key) or ""

        params = dict(details or {})
        params["requirement_id"] = requirement_id
        return raw_tmpl.format_map(_SafeFormatDict(params))

    def resolve_language(
        self,
        explicit_lang: str | None = None,
        inspection_meta: dict[str, Any] | None = None,
        user_claims: dict[str, Any] | None = None,
        accept_language_header: str | None = None,
    ) -> SupportedLanguage:
        """Negotiate request language via strict cascading precedence.

        Precedence:
        1. Explicit request query parameter (?lang=mr) or argument
        2. Inspection session metadata ("preferred_language" or "language")
        3. Authenticated user claims ("preferred_language")
        4. HTTP Accept-Language header
        5. Canonical fallback to English (SupportedLanguage.EN)
        """
        # 1. Explicit request language
        if explicit_lang and isinstance(explicit_lang, str) and explicit_lang.strip():
            lang = SupportedLanguage.from_str(explicit_lang)
            if explicit_lang.strip().lower().startswith(lang.value):
                return lang

        # 2. Inspection metadata preference
        if inspection_meta and isinstance(inspection_meta, dict):
            meta_lang = inspection_meta.get("preferred_language") or inspection_meta.get("language")
            if meta_lang and isinstance(meta_lang, str) and meta_lang.strip():
                return SupportedLanguage.from_str(meta_lang)

        # 3. Authenticated user claims
        if user_claims and isinstance(user_claims, dict):
            claim_lang = user_claims.get("preferred_language") or user_claims.get("language")
            if claim_lang and isinstance(claim_lang, str) and claim_lang.strip():
                return SupportedLanguage.from_str(claim_lang)

        # 4. Accept-Language header
        if accept_language_header and isinstance(accept_language_header, str):
            # Parse comma-separated weighted tags, e.g. "hi-IN,hi;q=0.9,en;q=0.8"
            for part in accept_language_header.split(","):
                tag = part.split(";")[0].strip()
                if tag:
                    parsed = SupportedLanguage.from_str(tag)
                    if tag.lower().startswith(parsed.value):
                        return parsed

        # 5. Default fallback
        return SupportedLanguage.EN


# Global singleton instance
_GLOBAL_LOCALIZATION_SERVICE = LocalizationService()


def get_localization_service() -> LocalizationService:
    """Dependency / accessor for LocalizationService singleton."""
    return _GLOBAL_LOCALIZATION_SERVICE
