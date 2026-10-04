"""Comprehensive Test Suite for Phase U3 — Multilingual Backend."""

from datetime import datetime, timezone
import unittest

from fastapi.testclient import TestClient

from backend.app.api.errors import ErrorCode
from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.localization.service import (
    Persona,
    SupportedLanguage,
    get_localization_service,
)
from backend.app.main import app
from backend.app.services.evidence.models import (
    EvidenceCandidate,
    EvidenceField,
    EvidenceStatus,
    ImageArtifact,
)
from backend.app.services.inspection.models import Inspection, InspectionStatus
from backend.app.services.inspection_pipeline.annotations import (
    EvidenceAnnotation,
    NormalizedBox,
    build_deterministic_annotation_id,
    generate_evidence_annotations,
)
from backend.app.services.inspection_pipeline.models import OverallInspectionStatus
from backend.app.services.inspection_pipeline.report import (
    InspectionReport,
    compute_overall_status,
)
from backend.app.services.ocr.models import BoundingBox
from backend.app.services.verification.models import VerificationResult, VerificationStatus
from backend.app.telegram.adapter import TelegramBotAdapter
from backend.app.telegram.formatter import (
    format_help_message,
    format_inspection_report,
    format_inspection_status,
    format_safe_error,
    format_welcome_message,
)
from backend.app.telegram.models import TelegramUserIdentity


class TestPhase12Multilingual(unittest.TestCase):
    """32+ exhaustive tests covering U3 Multilingual Backend requirements."""

    def setUp(self) -> None:
        self.loc = get_localization_service()

    # -----------------------------------------------------------------
    # 1-7: Language Negotiation & Precedence
    # -----------------------------------------------------------------
    def test_01_english_default_resolution(self) -> None:
        """1. Default language resolves to English."""
        lang = self.loc.resolve_language()
        self.assertEqual(lang, SupportedLanguage.EN)

    def test_02_hindi_resolution(self) -> None:
        """2. Explicit Hindi resolves to SupportedLanguage.HI."""
        lang = self.loc.resolve_language(explicit_lang="hi")
        self.assertEqual(lang, SupportedLanguage.HI)

    def test_03_marathi_resolution(self) -> None:
        """3. Explicit Marathi resolves to SupportedLanguage.MR."""
        lang = self.loc.resolve_language(explicit_lang="mr")
        self.assertEqual(lang, SupportedLanguage.MR)

    def test_04_unsupported_language_fallback(self) -> None:
        """4. Unsupported language codes safely fall back to English."""
        self.assertEqual(self.loc.resolve_language(explicit_lang="fr"), SupportedLanguage.EN)
        self.assertEqual(self.loc.resolve_language(explicit_lang="xyz"), SupportedLanguage.EN)
        self.assertEqual(self.loc.resolve_language(explicit_lang=""), SupportedLanguage.EN)
        self.assertEqual(self.loc.resolve_language(explicit_lang=None), SupportedLanguage.EN)

    def test_05_explicit_lang_precedence_over_headers_and_meta(self) -> None:
        """5. Explicit request parameter overrides metadata and Accept-Language header."""
        lang = self.loc.resolve_language(
            explicit_lang="mr",
            inspection_meta={"preferred_language": "hi"},
            user_claims={"preferred_language": "en"},
            accept_language_header="hi-IN,hi;q=0.9",
        )
        self.assertEqual(lang, SupportedLanguage.MR)

    def test_06_accept_language_header_parsing(self) -> None:
        """6. Accept-Language header correctly parsed with compound dialect tags."""
        self.assertEqual(
            self.loc.resolve_language(accept_language_header="hi-IN,hi;q=0.9,en;q=0.8"),
            SupportedLanguage.HI,
        )
        self.assertEqual(
            self.loc.resolve_language(accept_language_header="mr-IN,mr;q=0.9"),
            SupportedLanguage.MR,
        )
        self.assertEqual(
            self.loc.resolve_language(accept_language_header="de-DE,fr;q=0.8"),
            SupportedLanguage.EN,
        )

    def test_07_stored_preference_precedence(self) -> None:
        """7. Inspection session and user profile stored preference precedence."""
        # Inspection meta overrides header
        lang1 = self.loc.resolve_language(
            inspection_meta={"preferred_language": "hi"},
            accept_language_header="en-US",
        )
        self.assertEqual(lang1, SupportedLanguage.HI)

        # User claim overrides header when inspection meta is absent
        lang2 = self.loc.resolve_language(
            user_claims={"preferred_language": "mr"},
            accept_language_header="en-US",
        )
        self.assertEqual(lang2, SupportedLanguage.MR)

    # -----------------------------------------------------------------
    # 8-10: Catalogs & Template Interpolation
    # -----------------------------------------------------------------
    def test_08_catalog_lookup(self) -> None:
        """8. Catalog lookup retrieves correct regional statutory labels."""
        mrp_en = self.loc.get_statutory_label("R-6-1-e", lang="en")
        mrp_hi = self.loc.get_statutory_label("R-6-1-e", lang="hi")
        mrp_mr = self.loc.get_statutory_label("R-6-1-e", lang="mr")

        self.assertEqual(mrp_en, "Maximum Retail Price (MRP)")
        self.assertIn("अधिकतम खुदरा मूल्य", mrp_hi)
        self.assertIn("कमाल किरकोळ किंमत", mrp_mr)

    def test_09_missing_catalog_key_fallback(self) -> None:
        """9. Missing catalog key falls back gracefully to English without error."""
        res = self.loc.get_string("statutory_labels", "UNKNOWN_KEY_999", lang="mr", default="Fallback Label")
        self.assertEqual(res, "Fallback Label")

    def test_10_parameterized_template_interpolation(self) -> None:
        """10. Parameterized templates interpolate dynamic variables safely."""
        res_hi = self.loc.get_string(
            section="report_summaries",
            key="fail",
            lang=SupportedLanguage.HI,
            params={"failed_ids": "R-6-1-e, R-6-1-a"},
        )
        self.assertIn("R-6-1-e, R-6-1-a", res_hi)
        self.assertIn("विधिक अनुपालन विफलता", res_hi)

    # -----------------------------------------------------------------
    # 11-15: Result Status & Reason Localization
    # -----------------------------------------------------------------
    def test_11_pass_localization(self) -> None:
        """11. PASS status label localization."""
        self.assertEqual(self.loc.get_status_label("PASS", lang="en"), "Compliant")
        self.assertIn("सुसंगत", self.loc.get_status_label("PASS", lang="hi"))
        self.assertIn("सुसंगत", self.loc.get_status_label("PASS", lang="mr"))

    def test_12_fail_localization(self) -> None:
        """12. FAIL status label localization."""
        self.assertEqual(self.loc.get_status_label("FAIL", lang="en"), "Non-Compliant")
        self.assertIn("असुसंगत", self.loc.get_status_label("FAIL", lang="hi"))
        self.assertIn("असुसंगत", self.loc.get_status_label("FAIL", lang="mr"))

    def test_13_review_required_localization(self) -> None:
        """13. REVIEW_REQUIRED status label localization."""
        self.assertEqual(self.loc.get_status_label("REVIEW_REQUIRED", lang="en"), "Review Required")
        self.assertIn("समीक्षा", self.loc.get_status_label("REVIEW_REQUIRED", lang="hi"))
        self.assertIn("पुनरावलोकन", self.loc.get_status_label("REVIEW_REQUIRED", lang="mr"))

    def test_14_not_visible_localization(self) -> None:
        """14. NOT_VISIBLE status label localization."""
        self.assertIn("अनुपस्थित", self.loc.get_status_label("NOT_VISIBLE", lang="hi"))
        self.assertIn("अनुपस्थित", self.loc.get_status_label("NOT_VISIBLE", lang="mr"))

    def test_15_not_applicable_localization(self) -> None:
        """15. NOT_APPLICABLE status label localization."""
        self.assertEqual(self.loc.get_status_label("NOT_APPLICABLE", lang="hi"), "लागू नहीं (NOT APPLICABLE)")
        self.assertEqual(self.loc.get_status_label("NOT_APPLICABLE", lang="mr"), "लागू नाही (NOT APPLICABLE)")

    # -----------------------------------------------------------------
    # 16-20: Report Summary, Annotations & Invariance
    # -----------------------------------------------------------------
    def test_16_report_summary_localization(self) -> None:
        """16. Report summary is localized according to requested language."""
        summary_hi = self.loc.localize_report_summary(
            overall_status="PASS",
            pass_count=5,
            na_count=1,
            lang=SupportedLanguage.HI,
        )
        self.assertIn("5 उत्तीर्ण", summary_hi)

        summary_mr = self.loc.localize_report_summary(
            overall_status="FAIL",
            failed_ids=["R-6-1-e"],
            lang=SupportedLanguage.MR,
        )
        self.assertIn("R-6-1-e", summary_mr)
        self.assertIn("अनुपालन अपयश", summary_mr)

    def test_17_annotation_label_localization(self) -> None:
        """17. EvidenceAnnotation labels are localized when presenting report."""
        norm_box = NormalizedBox(x_min=0.1, y_min=0.2, x_max=0.5, y_max=0.6)
        ann = EvidenceAnnotation(
            annotation_id="ann_test_001",
            image_id="img_001",
            requirement_id="R-6-1-e",
            evidence_id="ev_001",
            status="FAIL",
            annotation_type="ERROR_HIGHLIGHT",
            polygon=[[10.0, 20.0], [50.0, 20.0], [50.0, 60.0], [10.0, 60.0]],
            bounding_box={"x_min": 10.0, "y_min": 20.0, "x_max": 50.0, "y_max": 60.0, "width": 40.0, "height": 40.0},
            normalized_box=norm_box,
            label="Maximum Retail Price (MRP)",
            reason="MRP declaration is missing currency symbol prefix.",
        )
        report = InspectionReport(
            inspection_id="insp_ann_loc",
            overall_status=OverallInspectionStatus.FAIL,
            verification_results=[],
            summary="Canonical summary",
            evidence_count=1,
            image_count=1,
            applicable_requirement_count=1,
            pass_count=0,
            fail_count=1,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
            evidence_annotations=[ann],
        )

        d_mr = report.to_dict(lang="mr")
        self.assertIn("कमाल किरकोळ किंमत", d_mr["evidence_annotations"][0]["label"])

    def test_18_annotation_reason_localization(self) -> None:
        """18. EvidenceAnnotation reason is localized to target language."""
        norm_box = NormalizedBox(x_min=0.1, y_min=0.2, x_max=0.5, y_max=0.6)
        ann = EvidenceAnnotation(
            annotation_id="ann_test_002",
            image_id="img_001",
            requirement_id="R-6-1-e",
            evidence_id="ev_001",
            status="FAIL",
            annotation_type="ERROR_HIGHLIGHT",
            polygon=[[10.0, 20.0], [50.0, 20.0], [50.0, 60.0], [10.0, 60.0]],
            bounding_box={"x_min": 10.0, "y_min": 20.0, "x_max": 50.0, "y_max": 60.0, "width": 40.0, "height": 40.0},
            normalized_box=norm_box,
            label="Maximum Retail Price (MRP)",
            reason="MRP declaration is missing currency symbol prefix.",
        )
        report = InspectionReport(
            inspection_id="insp_ann_loc2",
            overall_status=OverallInspectionStatus.FAIL,
            verification_results=[],
            summary="Canonical summary",
            evidence_count=1,
            image_count=1,
            applicable_requirement_count=1,
            pass_count=0,
            fail_count=1,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
            evidence_annotations=[ann],
        )

        d_hi = report.to_dict(lang="hi")
        self.assertIn("मुद्रा प्रतीक", d_hi["evidence_annotations"][0]["reason"])

    def test_19_annotation_geometry_unchanged_between_languages(self) -> None:
        """19. Annotation geometry remains 100% identical regardless of requested language."""
        norm_box = NormalizedBox(x_min=0.1234, y_min=0.2345, x_max=0.5678, y_max=0.6789)
        ann = EvidenceAnnotation(
            annotation_id="ann_geom",
            image_id="img_001",
            requirement_id="R-6-1-e",
            evidence_id="ev_001",
            status="FAIL",
            annotation_type="ERROR_HIGHLIGHT",
            polygon=[[12.3, 23.4], [56.7, 23.4], [56.7, 67.8], [12.3, 67.8]],
            bounding_box={"x_min": 12.3, "y_min": 23.4, "x_max": 56.7, "y_max": 67.8, "width": 44.4, "height": 44.4},
            normalized_box=norm_box,
            label="MRP",
            reason="Error",
        )
        report = InspectionReport(
            inspection_id="insp_geom",
            overall_status=OverallInspectionStatus.FAIL,
            verification_results=[],
            summary="Report",
            evidence_count=1,
            image_count=1,
            applicable_requirement_count=1,
            pass_count=0,
            fail_count=1,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
            evidence_annotations=[ann],
        )

        d_en = report.to_dict(lang="en")
        d_hi = report.to_dict(lang="hi")
        d_mr = report.to_dict(lang="mr")

        self.assertEqual(d_en["evidence_annotations"][0]["polygon"], d_hi["evidence_annotations"][0]["polygon"])
        self.assertEqual(d_en["evidence_annotations"][0]["bounding_box"], d_mr["evidence_annotations"][0]["bounding_box"])
        self.assertEqual(d_en["evidence_annotations"][0]["normalized_box"], d_hi["evidence_annotations"][0]["normalized_box"])

    def test_20_annotation_id_unchanged_between_languages(self) -> None:
        """20. Annotation IDs remain deterministic and identical across all languages."""
        id_en = build_deterministic_annotation_id("insp_1", "img_1", "R-6-1-e", "ev_1", "ERROR_HIGHLIGHT")
        id_hi = build_deterministic_annotation_id("insp_1", "img_1", "R-6-1-e", "ev_1", "ERROR_HIGHLIGHT")
        self.assertEqual(id_en, id_hi)

    # -----------------------------------------------------------------
    # 21-27: Invariance, Error Localization & Legal Safety
    # -----------------------------------------------------------------
    def test_21_compliance_score_unchanged_between_languages(self) -> None:
        """21. Compliance score rating labels localize correctly while maintaining semantic categories."""
        rating_en = self.loc.get_rating_label("FULLY_COMPLIANT", lang="en")
        rating_hi = self.loc.get_rating_label("FULLY_COMPLIANT", lang="hi")
        rating_mr = self.loc.get_rating_label("FULLY_COMPLIANT", lang="mr")

        self.assertEqual(rating_en, "Fully Compliant")
        self.assertEqual(rating_hi, "पूर्णतः सुसंगत")
        self.assertEqual(rating_mr, "पूर्णतः सुसंगत")

    def test_22_overall_status_unchanged_between_languages(self) -> None:
        """22. Overall status enum remains strictly machine-readable ('FAIL', 'PASS')."""
        report = InspectionReport(
            inspection_id="insp_status_test",
            overall_status=OverallInspectionStatus.FAIL,
            verification_results=[],
            summary="Report",
            evidence_count=1,
            image_count=1,
            applicable_requirement_count=1,
            pass_count=0,
            fail_count=1,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
        )
        self.assertEqual(report.to_dict(lang="hi")["overall_status"], "FAIL")
        self.assertEqual(report.to_dict(lang="mr")["overall_status"], "FAIL")

    def test_23_machine_readable_enums_remain_unchanged(self) -> None:
        """23. Status enums, requirement IDs, and codes never change."""
        v_res = VerificationResult(
            requirement_id="R-6-1-c",
            status=VerificationStatus.REVIEW_REQUIRED,
            reason="Unclear unit",
        )
        report = InspectionReport(
            inspection_id="insp_enums",
            overall_status=OverallInspectionStatus.REVIEW_REQUIRED,
            verification_results=[v_res],
            summary="Summary",
            evidence_count=1,
            image_count=1,
            applicable_requirement_count=1,
            pass_count=0,
            fail_count=0,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=1,
        )
        d_mr = report.to_dict(lang="mr")
        self.assertEqual(d_mr["verification_results"][0]["status"], "REVIEW_REQUIRED")
        self.assertEqual(d_mr["verification_results"][0]["requirement_id"], "R-6-1-c")

    def test_24_api_error_code_unchanged_while_message_localizes(self) -> None:
        """24. API error code remains unchanged while message localizes."""
        msg_hi = self.loc.localize_error("INSPECTION_NOT_FOUND", lang="hi", params={"inspection_id": "123"})
        self.assertIn("123", msg_hi)
        self.assertIn("तपासणी" if "तपासणी" in msg_hi else "निरीक्षण", msg_hi)

    def test_25_gemini_canonical_reason_preserved_for_custom_prose(self) -> None:
        """25. Arbitrary custom Gemini reasoning without a fixed template falls back to canonical English."""
        custom_gemini_reason = "Gemini observed specific irregular ink distortion on the back label causing ambiguous batch ID."
        localized = self.loc.localize_verification_reason(
            canonical_reason=custom_gemini_reason,
            status="REVIEW_REQUIRED",
            requirement_id="R-6-1-d",
            lang="hi",
        )
        self.assertEqual(localized, custom_gemini_reason)

    def test_26_legal_reference_remains_canonical(self) -> None:
        """26. Official statutory references remain canonical."""
        v_res = VerificationResult(
            requirement_id="R-6-1-e",
            status=VerificationStatus.FAIL,
            reason="MRP missing currency symbol",
            metadata={"rule_source": "Rule 6(1)(e), Legal Metrology (Packaged Commodities) Rules, 2011"},
        )
        self.assertEqual(
            v_res.metadata["rule_source"],
            "Rule 6(1)(e), Legal Metrology (Packaged Commodities) Rules, 2011",
        )

    def test_27_ocr_raw_text_remains_unchanged(self) -> None:
        """27. Raw package OCR observations are never altered or translated."""
        cand = EvidenceCandidate(
            evidence_id="ev_raw",
            observation_id="obs_001",
            image_id="img_001",
            field=EvidenceField.MRP,
            raw_text="MRP Rs. 250.00 INCL OF ALL TAXES",
            status=EvidenceStatus.VALID,
        )
        self.assertEqual(cand.raw_text, "MRP Rs. 250.00 INCL OF ALL TAXES")

    # -----------------------------------------------------------------
    # 28-32: Telegram, Personas, Security & API Integration
    # -----------------------------------------------------------------
    def test_28_telegram_localization(self) -> None:
        """28. Telegram bot messages format correctly in Hindi and Marathi."""
        msg_hi = format_welcome_message("राम", lang="hi")
        self.assertIn("राम", msg_hi)
        self.assertIn("वेरिकू", msg_hi)

        msg_mr = format_help_message(lang="mr")
        self.assertIn("मार्गदर्शिका", msg_mr)

        err_mr = format_safe_error("IMAGE_EMPTY", lang="mr")
        self.assertIn("रिकामी", err_mr)

    def test_29_consumer_inspector_authority_persona_presentation(self) -> None:
        """29. Persona-based guidance generates tailored wording."""
        guidance_consumer_hi = self.loc.localize_persona_explanation(
            requirement_id="R-6-1-e",
            status="FAIL",
            persona=Persona.CONSUMER,
            lang="hi",
        )
        self.assertIn("पैकेज", guidance_consumer_hi)

        guidance_inspector_mr = self.loc.localize_persona_explanation(
            requirement_id="R-6-1-e",
            status="FAIL",
            persona=Persona.INSPECTOR,
            lang="mr",
        )
        self.assertIn("R-6-1-e", guidance_inspector_mr)
        self.assertIn("भंग", guidance_inspector_mr)

    def test_30_security_no_arbitrary_module_injection(self) -> None:
        """30. Language resolver safely handles malicious strings without code execution."""
        malicious_input = "__import__('os').system('ls')"
        resolved = self.loc.resolve_language(explicit_lang=malicious_input)
        self.assertEqual(resolved, SupportedLanguage.EN)

    def test_31_fastapi_report_endpoint_language_negotiation(self) -> None:
        """31. GET /inspections/{id}/report returns localized response with ?lang= parameter."""
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id="user_lang_test", email="user@test.com", role="authenticated"
        )
        try:
            # Create inspection
            res_create = client.post("/api/v1/inspections", json={})
            self.assertEqual(res_create.status_code, 201)
            insp_id = res_create.json()["inspection_id"]

            # Store report
            from backend.app.api.dependencies import get_session_store
            store = app.dependency_overrides.get(get_session_store, get_session_store)()
            v_fail = VerificationResult(
                requirement_id="R-6-1-e",
                status=VerificationStatus.FAIL,
                reason="MRP declaration is missing currency symbol prefix.",
            )
            report = InspectionReport(
                inspection_id=insp_id,
                overall_status=OverallInspectionStatus.FAIL,
                verification_results=[v_fail],
                summary="Canonical fail summary",
                evidence_count=1,
                image_count=1,
                applicable_requirement_count=1,
                pass_count=0,
                fail_count=1,
                not_visible_count=0,
                not_applicable_count=0,
                review_required_count=0,
            )
            store.store_report(insp_id, report)

            # 1. Fetch with ?lang=mr
            res_mr = client.get(f"/api/v1/inspections/{insp_id}/report?lang=mr")
            self.assertEqual(res_mr.status_code, 200)
            data_mr = res_mr.json()
            self.assertEqual(data_mr["language"], "mr")
            self.assertIn("अनुपालन अपयश", data_mr["summary"])

            # 2. Fetch with Accept-Language: hi
            res_hi = client.get(
                f"/api/v1/inspections/{insp_id}/report",
                headers={"Accept-Language": "hi-IN,hi;q=0.9"},
            )
            self.assertEqual(res_hi.status_code, 200)
            data_hi = res_hi.json()
            self.assertEqual(data_hi["language"], "hi")
            self.assertIn("विधिक अनुपालन विफलता", data_hi["summary"])

            # 3. Fetch default (English)
            res_en = client.get(f"/api/v1/inspections/{insp_id}/report")
            self.assertEqual(res_en.status_code, 200)
            data_en = res_en.json()
            self.assertEqual(data_en["language"], "en")
        finally:
            app.dependency_overrides.clear()

    def test_32_legacy_api_report_behavior_remains_compatible(self) -> None:
        """32. Existing report consumers receiving response without lang param parse normally."""
        norm_box = NormalizedBox(x_min=0.1, y_min=0.2, x_max=0.5, y_max=0.6)
        ann = EvidenceAnnotation(
            annotation_id="ann_legacy",
            image_id="img_001",
            requirement_id="R-6-1-e",
            evidence_id="ev_001",
            status="FAIL",
            annotation_type="ERROR_HIGHLIGHT",
            polygon=[[100.0, 200.0], [500.0, 200.0], [500.0, 600.0], [100.0, 600.0]],
            bounding_box={"x_min": 100.0, "y_min": 200.0, "x_max": 500.0, "y_max": 600.0, "width": 400.0, "height": 400.0},
            normalized_box=norm_box,
            label="Maximum Retail Price (MRP)",
            reason="Missing currency symbol",
        )
        report = InspectionReport(
            inspection_id="insp_compat",
            overall_status=OverallInspectionStatus.FAIL,
            verification_results=[],
            summary="Legacy report",
            evidence_count=1,
            image_count=1,
            applicable_requirement_count=1,
            pass_count=0,
            fail_count=1,
            not_visible_count=0,
            not_applicable_count=0,
            review_required_count=0,
            evidence_annotations=[ann],
        )
        d = report.to_dict()
        self.assertIn("language", d)
        self.assertEqual(d["language"], "en")
        self.assertIn("evidence_annotations", d)
        self.assertEqual(d["overall_status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
