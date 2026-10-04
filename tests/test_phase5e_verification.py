"""Unit and Contract Tests for Phase 5E — Evidence-to-Requirement Verification."""

from __future__ import annotations

import unittest
from uuid import uuid4

from backend.app.services.applicability.models import ApplicabilityDecision, TriState
from backend.app.services.evidence.models import (
    EvidenceCandidate,
    EvidenceField,
    EvidenceStatus,
)
from backend.app.services.verification.deterministic import DeterministicVerifier
from backend.app.services.verification.errors import (
    MissingRequirementError,
    VerificationError,
)
from backend.app.services.verification.evidence_matcher import EvidenceMatcher
from backend.app.services.verification.models import (
    RequirementReference,
    VerificationResult,
    VerificationStatus,
)
from backend.app.services.verification.service import VerificationService


class TestPhase5EVerification(unittest.TestCase):
    """Test suite verifying the deterministic contract for Phase 5E."""

    def setUp(self) -> None:
        self.service = VerificationService()

    def _make_candidate(
        self,
        field: EvidenceField = EvidenceField.MRP,
        raw_text: str = "MRP Rs. 150.00",
        parsed_value: any = 150.0,
        parsed_unit: str | None = None,
        status: EvidenceStatus = EvidenceStatus.VALID,
        image_id: str = "img_hash_123",
        observation_id: str = "obs_456",
        evidence_id: str | None = None,
        confidence: float = 0.95,
    ) -> EvidenceCandidate:
        return EvidenceCandidate(
            evidence_id=evidence_id or f"ev_{uuid4().hex[:8]}",
            observation_id=observation_id,
            image_id=image_id,
            field=field,
            raw_text=raw_text,
            normalized_text=raw_text.strip(),
            parsed_value=parsed_value,
            parsed_unit=parsed_unit,
            status=status,
            confidence=confidence,
            ocr_confidence=confidence,
        )

    # 1. applicable + valid MRP -> PASS
    def test_01_applicable_valid_mrp_passes(self) -> None:
        req = RequirementReference(requirement_id="REQ_MRP_001", target_field=EvidenceField.MRP)
        cand = self._make_candidate(field=EvidenceField.MRP, raw_text="MRP ₹125.00", parsed_value=125.0)
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertEqual(res.status, VerificationStatus.PASS)
        self.assertFalse(res.review_required)
        self.assertIn(cand.evidence_id, res.evidence_ids)

    # 2. applicable + missing MRP -> NOT_VISIBLE
    def test_02_applicable_missing_mrp_is_not_visible(self) -> None:
        req = RequirementReference(requirement_id="REQ_MRP_001", target_field=EvidenceField.MRP)
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[])
        self.assertEqual(res.status, VerificationStatus.NOT_VISIBLE)
        self.assertNotEqual(res.status, VerificationStatus.FAIL)
        self.assertFalse(res.review_required)

    # 3. not applicable -> NOT_APPLICABLE
    def test_03_not_applicable_yields_not_applicable(self) -> None:
        req = RequirementReference(requirement_id="REQ_IMPORT_001", target_field=EvidenceField.IMPORTER_NAME)
        cand = self._make_candidate(field=EvidenceField.IMPORTER_NAME, raw_text="Imported by ABC", parsed_value="ABC")
        res = self.service.verify_requirement(req, applicability=TriState.FALSE, candidates=[cand])
        self.assertEqual(res.status, VerificationStatus.NOT_APPLICABLE)
        self.assertFalse(res.review_required)
        self.assertEqual(res.evidence_ids, [])

    # 4. unknown applicability -> REVIEW_REQUIRED
    def test_04_unknown_applicability_yields_review_required(self) -> None:
        req = RequirementReference(requirement_id="REQ_EXPIRY_001", target_field=EvidenceField.MANUFACTURE_DATE)
        cand = self._make_candidate(field=EvidenceField.MANUFACTURE_DATE, raw_text="Mfg 01/2025")
        res = self.service.verify_requirement(req, applicability=TriState.UNKNOWN, candidates=[cand])
        self.assertEqual(res.status, VerificationStatus.REVIEW_REQUIRED)
        self.assertTrue(res.review_required)
        self.assertNotEqual(res.status, VerificationStatus.FAIL)

    # 5. ambiguous MRP -> REVIEW_REQUIRED
    def test_05_ambiguous_mrp_yields_review_required(self) -> None:
        req = RequirementReference(requirement_id="REQ_MRP_001", target_field=EvidenceField.MRP)
        cand = self._make_candidate(
            field=EvidenceField.MRP,
            raw_text="125",
            status=EvidenceStatus.AMBIGUOUS,
        )
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertEqual(res.status, VerificationStatus.REVIEW_REQUIRED)
        self.assertTrue(res.review_required)
        self.assertIn(cand.evidence_id, res.evidence_ids)

    # 6. malformed / unparsed MRP -> REVIEW_REQUIRED
    def test_06_unparsed_mrp_yields_review_required(self) -> None:
        req = RequirementReference(requirement_id="REQ_MRP_001", target_field=EvidenceField.MRP)
        cand = self._make_candidate(
            field=EvidenceField.MRP,
            raw_text="MRP $$--",
            parsed_value=None,
            status=EvidenceStatus.UNPARSED,
        )
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertEqual(res.status, VerificationStatus.REVIEW_REQUIRED)
        self.assertTrue(res.review_required)

    # 7. contradictory MRP -> REVIEW_REQUIRED
    def test_07_contradictory_mrp_yields_review_required(self) -> None:
        req = RequirementReference(requirement_id="REQ_MRP_001", target_field=EvidenceField.MRP)
        c1 = self._make_candidate(field=EvidenceField.MRP, raw_text="MRP ₹125", parsed_value=125.0, image_id="img_1")
        c2 = self._make_candidate(field=EvidenceField.MRP, raw_text="MRP ₹150", parsed_value=150.0, image_id="img_2")
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[c1, c2])
        self.assertEqual(res.status, VerificationStatus.REVIEW_REQUIRED)
        self.assertTrue(res.review_required)
        self.assertIn(c1.evidence_id, res.evidence_ids)
        self.assertIn(c2.evidence_id, res.evidence_ids)
        self.assertIn("img_1", res.image_ids)
        self.assertIn("img_2", res.image_ids)

    # 8. valid quantity -> PASS
    def test_08_valid_quantity_passes(self) -> None:
        req = RequirementReference(requirement_id="REQ_QTY_001", target_field=EvidenceField.NET_QUANTITY)
        cand = self._make_candidate(
            field=EvidenceField.NET_QUANTITY,
            raw_text="Net Qty: 500 g",
            parsed_value="500",
            parsed_unit="g",
        )
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertEqual(res.status, VerificationStatus.PASS)
        self.assertFalse(res.review_required)

    # 9. missing quantity -> NOT_VISIBLE
    def test_09_missing_quantity_is_not_visible(self) -> None:
        req = RequirementReference(requirement_id="REQ_QTY_001", target_field=EvidenceField.NET_QUANTITY)
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[])
        self.assertEqual(res.status, VerificationStatus.NOT_VISIBLE)

    # 10. valid manufacturer name -> PASS
    def test_10_valid_manufacturer_name_passes(self) -> None:
        req = RequirementReference(requirement_id="REQ_MFG_001", target_field=EvidenceField.MANUFACTURER_NAME)
        cand = self._make_candidate(
            field=EvidenceField.MANUFACTURER_NAME,
            raw_text="Manufactured by: ABC Foods Ltd",
            parsed_value="ABC Foods Ltd",
        )
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertEqual(res.status, VerificationStatus.PASS)

    # 11. missing manufacturer name -> NOT_VISIBLE
    def test_11_missing_manufacturer_name_is_not_visible(self) -> None:
        req = RequirementReference(requirement_id="REQ_MFG_001", target_field=EvidenceField.MANUFACTURER_NAME)
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[])
        self.assertEqual(res.status, VerificationStatus.NOT_VISIBLE)

    # 12. valid importer information -> PASS
    def test_12_valid_importer_passes(self) -> None:
        req = RequirementReference(requirement_id="REQ_IMP_001", target_field=EvidenceField.IMPORTER_NAME)
        cand = self._make_candidate(
            field=EvidenceField.IMPORTER_NAME,
            raw_text="Imported by: XYZ Global Pvt Ltd",
            parsed_value="XYZ Global Pvt Ltd",
        )
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertEqual(res.status, VerificationStatus.PASS)

    # 13. missing importer information -> NOT_VISIBLE
    def test_13_missing_importer_is_not_visible(self) -> None:
        req = RequirementReference(requirement_id="REQ_IMP_001", target_field=EvidenceField.IMPORTER_NAME)
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[])
        self.assertEqual(res.status, VerificationStatus.NOT_VISIBLE)

    # 14. valid consumer care -> PASS
    def test_14_valid_consumer_care_passes(self) -> None:
        req = RequirementReference(requirement_id="REQ_CARE_001", target_field="consumer_care_phone")
        cand = self._make_candidate(
            field=EvidenceField.CONSUMER_CARE_PHONE,
            raw_text="Customer Care: 1800-111-222",
            parsed_value="1800111222",
        )
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertEqual(res.status, VerificationStatus.PASS)

    # 15. ambiguous consumer care -> REVIEW_REQUIRED
    def test_15_ambiguous_consumer_care_yields_review_required(self) -> None:
        req = RequirementReference(requirement_id="REQ_CARE_001", target_field="consumer_care_email")
        cand = self._make_candidate(
            field=EvidenceField.CONSUMER_CARE_EMAIL,
            raw_text="care at domain",
            status=EvidenceStatus.AMBIGUOUS,
        )
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertEqual(res.status, VerificationStatus.REVIEW_REQUIRED)

    # 16. duplicate evidence preserved
    def test_16_duplicate_evidence_preserved_in_provenance(self) -> None:
        req = RequirementReference(requirement_id="REQ_MRP_001", target_field=EvidenceField.MRP)
        c1 = self._make_candidate(evidence_id="ev_1", raw_text="MRP ₹100", parsed_value=100.0)
        c2 = self._make_candidate(evidence_id="ev_2", raw_text="MRP ₹100", parsed_value=100.0)
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[c1, c2])
        self.assertEqual(res.status, VerificationStatus.PASS)
        self.assertIn("ev_1", res.evidence_ids)
        self.assertIn("ev_2", res.evidence_ids)

    # 17. multi-image evidence preserved
    def test_17_multi_image_evidence_preserved(self) -> None:
        req = RequirementReference(requirement_id="REQ_MFG_001", target_fields=[EvidenceField.MANUFACTURER_NAME, EvidenceField.MANUFACTURER_ADDRESS])
        c1 = self._make_candidate(field=EvidenceField.MANUFACTURER_NAME, image_id="img_front", raw_text="Mfg by ABC")
        c2 = self._make_candidate(field=EvidenceField.MANUFACTURER_ADDRESS, image_id="img_back", raw_text="Industrial Area, Delhi")
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[c1, c2])
        self.assertIn("img_front", res.image_ids)
        self.assertIn("img_back", res.image_ids)

    # 18. image IDs preserved
    def test_18_image_ids_preserved(self) -> None:
        req = RequirementReference(requirement_id="REQ_BATCH_001", target_field=EvidenceField.BATCH_NUMBER)
        cand = self._make_candidate(field=EvidenceField.BATCH_NUMBER, image_id="img_top_99", raw_text="Batch: B123")
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertEqual(res.image_ids, ["img_top_99"])

    # 19. evidence IDs preserved
    def test_19_evidence_ids_preserved(self) -> None:
        req = RequirementReference(requirement_id="REQ_BATCH_001", target_field=EvidenceField.BATCH_NUMBER)
        cand = self._make_candidate(evidence_id="ev_custom_id_007", field=EvidenceField.BATCH_NUMBER, raw_text="Batch: B123")
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertEqual(res.evidence_ids, ["ev_custom_id_007"])

    # 20. observation IDs preserved
    def test_20_observation_ids_preserved(self) -> None:
        req = RequirementReference(requirement_id="REQ_ORIGIN_001", target_field=EvidenceField.COUNTRY_OF_ORIGIN)
        cand = self._make_candidate(observation_id="obs_box_42", field=EvidenceField.COUNTRY_OF_ORIGIN, raw_text="Country of Origin: India", parsed_value="India")
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertEqual(res.source_observation_ids, ["obs_box_42"])

    # 21. requirement ID mandatory
    def test_21_requirement_id_mandatory(self) -> None:
        with self.assertRaises(MissingRequirementError):
            RequirementReference(requirement_id="")
        with self.assertRaises(MissingRequirementError):
            VerificationResult(requirement_id="", status=VerificationStatus.PASS, reason="test")

    # 22. no fabricated requirement ID
    def test_22_no_fabricated_requirement_id(self) -> None:
        with self.assertRaises(MissingRequirementError):
            self.service.verify_requirement(requirement="   ", applicability=TriState.TRUE)

    # 23. no fabricated legal text in result
    def test_23_authoritative_reference_retained(self) -> None:
        req = RequirementReference(requirement_id="REQ_SEC_18", rule_number="Rule 6(1)(e)", target_field=EvidenceField.MRP)
        cand = self._make_candidate(field=EvidenceField.MRP, raw_text="MRP 100", parsed_value=100.0)
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertEqual(res.requirement_id, "REQ_SEC_18")

    # 24. no Gemini import in verification module
    def test_24_no_gemini_import_in_verification(self) -> None:
        import backend.app.services.verification.deterministic as det
        import backend.app.services.verification.service as srv
        import backend.app.services.verification.models as mdl
        import backend.app.services.verification.evidence_matcher as em

        for module in (det, srv, mdl, em):
            with open(module.__file__, "r", encoding="utf-8") as f:
                module_src = f.read()
            self.assertNotIn("google.generativeai", module_src)
            self.assertNotIn("gemini", module_src.lower())

    # 25. no legal database access in verification module
    def test_25_no_database_access_in_verification(self) -> None:
        import backend.app.services.verification.deterministic as det
        import backend.app.services.verification.service as srv

        for module in (det, srv):
            with open(module.__file__, "r", encoding="utf-8") as f:
                module_src = f.read()
            self.assertNotIn("create_client", module_src)
            self.assertNotIn("supabase", module_src.lower())
            self.assertNotIn("psycopg", module_src.lower())

    # 26. deterministic repeated execution
    def test_26_deterministic_repeated_execution(self) -> None:
        req = RequirementReference(requirement_id="REQ_QTY_001", target_field=EvidenceField.NET_QUANTITY)
        cand = self._make_candidate(field=EvidenceField.NET_QUANTITY, raw_text="Net Qty: 1 kg", parsed_value="1", parsed_unit="kg")
        
        res1 = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        res2 = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        
        self.assertEqual(res1.status, res2.status)
        self.assertEqual(res1.reason, res2.reason)
        self.assertEqual(res1.evidence_ids, res2.evidence_ids)

    # 27. UNKNOWN applicability never becomes FAIL
    def test_27_unknown_applicability_never_becomes_fail(self) -> None:
        req = RequirementReference(requirement_id="REQ_X", target_field=EvidenceField.MRP)
        res = self.service.verify_requirement(req, applicability=TriState.UNKNOWN, candidates=[])
        self.assertNotEqual(res.status, VerificationStatus.FAIL)
        self.assertEqual(res.status, VerificationStatus.REVIEW_REQUIRED)

    # 28. UNKNOWN applicability never becomes PASS
    def test_28_unknown_applicability_never_becomes_pass(self) -> None:
        req = RequirementReference(requirement_id="REQ_X", target_field=EvidenceField.MRP)
        cand = self._make_candidate(field=EvidenceField.MRP, raw_text="MRP 100", parsed_value=100.0)
        res = self.service.verify_requirement(req, applicability=TriState.UNKNOWN, candidates=[cand])
        self.assertNotEqual(res.status, VerificationStatus.PASS)
        self.assertEqual(res.status, VerificationStatus.REVIEW_REQUIRED)

    # 29. ambiguous evidence never silently becomes PASS
    def test_29_ambiguous_evidence_never_silently_becomes_pass(self) -> None:
        req = RequirementReference(requirement_id="REQ_DATE_001", target_field=EvidenceField.MANUFACTURE_DATE)
        cand = self._make_candidate(field=EvidenceField.MANUFACTURE_DATE, raw_text="2024", status=EvidenceStatus.AMBIGUOUS)
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertNotEqual(res.status, VerificationStatus.PASS)
        self.assertEqual(res.status, VerificationStatus.REVIEW_REQUIRED)

    # 30. conflicting evidence never silently selects one
    def test_30_conflicting_evidence_never_silently_selects_one(self) -> None:
        req = RequirementReference(requirement_id="REQ_ORIGIN_001", target_field=EvidenceField.COUNTRY_OF_ORIGIN)
        c1 = self._make_candidate(field=EvidenceField.COUNTRY_OF_ORIGIN, raw_text="Made in India", parsed_value="India")
        c2 = self._make_candidate(field=EvidenceField.COUNTRY_OF_ORIGIN, raw_text="Made in China", parsed_value="China")
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[c1, c2])
        self.assertEqual(res.status, VerificationStatus.REVIEW_REQUIRED)
        self.assertTrue(res.review_required)
        self.assertEqual(len(res.evidence_ids), 2)

    # 31. NOT_VISIBLE distinct from FAIL
    def test_31_not_visible_distinct_from_fail(self) -> None:
        req = RequirementReference(requirement_id="REQ_GENERIC_001", target_field=EvidenceField.COMMODITY_NAME)
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[])
        self.assertEqual(res.status, VerificationStatus.NOT_VISIBLE)
        self.assertNotEqual(res.status, VerificationStatus.FAIL)

    # 32. NOT_APPLICABLE distinct from NOT_VISIBLE
    def test_32_not_applicable_distinct_from_not_visible(self) -> None:
        req = RequirementReference(requirement_id="REQ_IMP_001", target_field=EvidenceField.IMPORTER_NAME)
        res_na = self.service.verify_requirement(req, applicability=TriState.FALSE, candidates=[])
        res_nv = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[])
        self.assertEqual(res_na.status, VerificationStatus.NOT_APPLICABLE)
        self.assertEqual(res_nv.status, VerificationStatus.NOT_VISIBLE)
        self.assertNotEqual(res_na.status, res_nv.status)

    # 33. PASS requires sufficient evidence
    def test_33_pass_requires_sufficient_evidence(self) -> None:
        req = RequirementReference(requirement_id="REQ_MRP_001", target_field=EvidenceField.MRP)
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[])
        self.assertNotEqual(res.status, VerificationStatus.PASS)

    # 34. FAIL distinct from NOT_VISIBLE and requires evidence
    def test_34_fail_distinct_from_not_visible(self) -> None:
        status_nv = VerificationStatus.NOT_VISIBLE
        status_fail = VerificationStatus.FAIL
        self.assertNotEqual(status_nv, status_fail)

    # 35. review flag preserved on REVIEW_REQUIRED
    def test_35_review_flag_preserved(self) -> None:
        req = RequirementReference(requirement_id="REQ_DATE_001", target_field=EvidenceField.MANUFACTURE_DATE)
        cand = self._make_candidate(field=EvidenceField.MANUFACTURE_DATE, status=EvidenceStatus.AMBIGUOUS)
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertTrue(res.review_required)
        self.assertTrue(res.to_dict()["review_required"])

    # 36. evidence order deterministic
    def test_36_evidence_order_deterministic(self) -> None:
        req = RequirementReference(requirement_id="REQ_MFG_001", target_fields=[EvidenceField.MANUFACTURER_NAME])
        c1 = self._make_candidate(evidence_id="ev_alpha", field=EvidenceField.MANUFACTURER_NAME, raw_text="Mfg A")
        c2 = self._make_candidate(evidence_id="ev_beta", field=EvidenceField.MANUFACTURER_NAME, raw_text="Mfg A")
        res1 = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[c1, c2])
        res2 = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[c1, c2])
        self.assertEqual(res1.evidence_ids, res2.evidence_ids)

    # 37. empty evidence set handled safely
    def test_37_empty_evidence_set_handled_safely(self) -> None:
        req = RequirementReference(requirement_id="REQ_SAFE_001", target_field=EvidenceField.MRP)
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=None)
        self.assertEqual(res.status, VerificationStatus.NOT_VISIBLE)

    # 38. multiple evidence candidates handled in batch inspection
    def test_38_multiple_evidence_candidates_in_inspection(self) -> None:
        req1 = RequirementReference(requirement_id="REQ_1", target_field=EvidenceField.MRP)
        req2 = RequirementReference(requirement_id="REQ_2", target_field=EvidenceField.NET_QUANTITY)
        
        c1 = self._make_candidate(field=EvidenceField.MRP, raw_text="MRP 50", parsed_value=50.0)
        c2 = self._make_candidate(field=EvidenceField.NET_QUANTITY, raw_text="100 g", parsed_value="100", parsed_unit="g")

        results = self.service.verify_inspection(
            requirements=[req1, req2],
            applicability_decisions={"REQ_1": TriState.TRUE, "REQ_2": TriState.TRUE},
            candidates=[c1, c2],
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].status, VerificationStatus.PASS)
        self.assertEqual(results[1].status, VerificationStatus.PASS)

    # 39. unrelated evidence ignored
    def test_39_unrelated_evidence_ignored(self) -> None:
        req = RequirementReference(requirement_id="REQ_MRP_001", target_field=EvidenceField.MRP)
        unrelated = self._make_candidate(field=EvidenceField.COMMODITY_NAME, raw_text="Biscuits")
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[unrelated])
        self.assertEqual(res.status, VerificationStatus.NOT_VISIBLE)
        self.assertEqual(res.evidence_ids, [])

    # 40. raw OCR provenance remains reachable
    def test_40_raw_ocr_provenance_reachable(self) -> None:
        req = RequirementReference(requirement_id="REQ_MRP_001", target_field=EvidenceField.MRP)
        cand = self._make_candidate(
            evidence_id="ev_prov_123",
            observation_id="obs_ocr_999",
            image_id="img_hash_aaa",
            field=EvidenceField.MRP,
            raw_text="MRP Rs. 200.00",
            parsed_value=200.0,
        )
        res = self.service.verify_requirement(req, applicability=TriState.TRUE, candidates=[cand])
        self.assertIn("ev_prov_123", res.evidence_ids)
        self.assertIn("obs_ocr_999", res.source_observation_ids)
        self.assertIn("img_hash_aaa", res.image_ids)


if __name__ == "__main__":
    unittest.main()

