"""Unit tests for Phase 5D — Evidence Normalization and Structured Extraction.

Tests verify:
- Deterministic extraction across all statutory declaration fields
- Absolute preservation of raw OCR observations, confidences, bounding boxes, and image IDs
- Strict ambiguity classification without over-inference or silent OCR correction
- Zero legal compliance reasoning, zero PASS/FAIL output, zero database dependency
- Multi-image isolation and duplicate observation tracking
"""

from __future__ import annotations

import unittest
import uuid

from backend.app.services.evidence.errors import (
    EvidenceNormalizationError,
    InvalidEvidenceInputError,
)
from backend.app.services.evidence.models import (
    EvidenceCandidate,
    EvidenceField,
    EvidenceStatus,
)
from backend.app.services.evidence.normalization import normalize_evidence_text
from backend.app.services.evidence.parsers import (
    BatchParser,
    ContactParser,
    DateParser,
    GenericParser,
    IdentityParser,
    MRPParser,
    QuantityParser,
)
from backend.app.services.evidence.service import EvidenceNormalizationService
from backend.app.services.ocr.models import (
    BoundingBox,
    OCRObservation,
    OCRProcessingStatus,
    OCRResult,
)


class TestPhase5DEvidenceNormalization(unittest.TestCase):
    """Test suite for Phase 5D Evidence Normalization layer."""

    def setUp(self) -> None:
        self.service = EvidenceNormalizationService()
        self.dummy_box = BoundingBox(
            points=[
                [10.0, 10.0],
                [100.0, 10.0],
                [100.0, 30.0],
                [10.0, 30.0],
            ]
        )

    def _make_observation(
        self,
        text: str,
        confidence: float = 0.98,
        image_id: str = "img_test_123",
        sequence: int = 1,
    ) -> OCRObservation:
        return OCRObservation(
            observation_id=f"obs_{uuid.uuid4().hex[:8]}",
            image_id=image_id,
            text=text,
            confidence=confidence,
            bounding_box=self.dummy_box,
            sequence=sequence,
            engine="PaddleOCR",
            engine_version="3.7.0",
        )

    # 1. MRP Parsing
    def test_01_mrp_parsing(self) -> None:
        obs = self._make_observation("MRP ₹125.00")
        candidates = self.service.normalize_observation(obs)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.MRP)
        self.assertEqual(c.parsed_value, 125.00)
        self.assertEqual(c.parsed_unit, "INR")
        self.assertEqual(c.status, EvidenceStatus.VALID)

    # 2. MRP Currency Parsing
    def test_02_mrp_currency_parsing(self) -> None:
        for text, expected_curr in [
            ("MRP Rs. 250", "INR"),
            ("MRP INR 99.50", "INR"),
            ("MRP $ 15.00", "USD"),
            ("MRP € 10.50", "EUR"),
        ]:
            obs = self._make_observation(text)
            c = self.service.normalize_observation(obs)[0]
            self.assertEqual(c.field, EvidenceField.MRP)
            self.assertEqual(c.parsed_unit, expected_curr)
            self.assertEqual(c.status, EvidenceStatus.VALID)

    # 3. Quantity Parsing
    def test_03_quantity_parsing(self) -> None:
        obs = self._make_observation("Net Qty 500 g")
        candidates = self.service.normalize_observation(obs)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.NET_QUANTITY)
        self.assertEqual(c.parsed_value, 500.0)
        self.assertEqual(c.parsed_unit, "g")
        self.assertEqual(c.status, EvidenceStatus.VALID)

    # 4. Quantity Units
    def test_04_quantity_units(self) -> None:
        units_to_test = [
            ("Net Quantity 1.5 kg", 1.5, "kg"),
            ("Net Volume 750 ml", 750.0, "ml"),
            ("Net Qty 2 ltr", 2.0, "l"),
            ("Net Content 100 mg", 100.0, "mg"),
            ("Net Quantity 10 pieces", 10.0, "pieces"),
            ("Net Qty 5 N", 5.0, "N"),
        ]
        for text, expected_val, expected_unit in units_to_test:
            obs = self._make_observation(text)
            c = self.service.normalize_observation(obs)[0]
            self.assertEqual(c.field, EvidenceField.NET_QUANTITY)
            self.assertEqual(c.parsed_value, expected_val)
            self.assertEqual(c.parsed_unit, expected_unit)
            self.assertEqual(c.status, EvidenceStatus.VALID)

    # 5. Date Parsing
    def test_05_date_parsing(self) -> None:
        obs = self._make_observation("PKD 01/2026")
        candidates = self.service.normalize_observation(obs)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.PACKING_DATE)
        self.assertEqual(c.parsed_value, "01/2026")
        self.assertEqual(c.status, EvidenceStatus.VALID)

    # 6. Phone Parsing
    def test_06_phone_parsing(self) -> None:
        obs = self._make_observation("Consumer Care 1800-111-222")
        candidates = self.service.normalize_observation(obs)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.CONSUMER_CARE_PHONE)
        self.assertEqual(c.parsed_value, "1800-111-222")
        self.assertEqual(c.status, EvidenceStatus.VALID)

    # 7. Email Parsing
    def test_07_email_parsing(self) -> None:
        obs = self._make_observation("Customer Care: feedback@packagedfood.com")
        candidates = self.service.normalize_observation(obs)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.CONSUMER_CARE_EMAIL)
        self.assertEqual(c.parsed_value, "feedback@packagedfood.com")
        self.assertEqual(c.status, EvidenceStatus.VALID)

    # 8. Explicit Manufacturer Text
    def test_08_explicit_manufacturer_text(self) -> None:
        obs = self._make_observation("Manufactured by ABC Foods Pvt Ltd, Industrial Area, Mumbai")
        candidates = self.service.normalize_observation(obs)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.MANUFACTURER_NAME)
        self.assertIn("ABC Foods Pvt Ltd", str(c.parsed_value))
        self.assertEqual(c.status, EvidenceStatus.VALID)

    # 9. Explicit Importer Text
    def test_09_explicit_importer_text(self) -> None:
        obs = self._make_observation("Imported by Global Trade Solutions India Ltd")
        candidates = self.service.normalize_observation(obs)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.IMPORTER_NAME)
        self.assertIn("Global Trade Solutions", str(c.parsed_value))
        self.assertEqual(c.status, EvidenceStatus.VALID)

    # 10. Explicit Packer Text
    def test_10_explicit_packer_text(self) -> None:
        obs = self._make_observation("Packed by QuickPackers Facility #4, Bengaluru")
        candidates = self.service.normalize_observation(obs)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.PACKER_NAME)
        self.assertIn("QuickPackers", str(c.parsed_value))
        self.assertEqual(c.status, EvidenceStatus.VALID)

    # 11. Ambiguity Handling
    def test_11_ambiguity(self) -> None:
        # OCR corrupted number following MRP
        obs1 = self._make_observation("MRP 12S.00")
        c1 = self.service.normalize_observation(obs1)[0]
        self.assertEqual(c1.field, EvidenceField.MRP)
        self.assertEqual(c1.status, EvidenceStatus.AMBIGUOUS)

        # Standalone date without label
        obs2 = self._make_observation("01/2026")
        c2 = self.service.normalize_observation(obs2)[0]
        self.assertEqual(c2.status, EvidenceStatus.AMBIGUOUS)

    # 12. Malformed Numeric Value
    def test_12_malformed_numeric_value(self) -> None:
        obs = self._make_observation("Net Qty 5OO g")
        candidates = self.service.normalize_observation(obs)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.NET_QUANTITY)
        self.assertEqual(c.status, EvidenceStatus.AMBIGUOUS)

    # 13. Malformed Date
    def test_13_malformed_date(self) -> None:
        obs = self._make_observation("DOM 99/99/9999")
        candidates = self.service.normalize_observation(obs)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.MANUFACTURE_DATE)
        self.assertEqual(c.status, EvidenceStatus.AMBIGUOUS)

    # 14. OCR Text Preservation
    def test_14_ocr_text_preservation(self) -> None:
        raw = "  MRP   ₹125.00  "
        obs = self._make_observation(raw)
        c = self.service.normalize_observation(obs)[0]
        self.assertEqual(c.raw_text, raw)
        self.assertEqual(c.normalized_text, "MRP ₹125.00")

    # 15. Confidence Preservation
    def test_15_confidence_preservation(self) -> None:
        obs = self._make_observation("MRP ₹125.00", confidence=0.887)
        c = self.service.normalize_observation(obs)[0]
        self.assertEqual(c.ocr_confidence, 0.887)
        self.assertAlmostEqual(c.confidence, 0.887, places=4)

    # 16. Bounding Box Preservation
    def test_16_bounding_box_preservation(self) -> None:
        obs = self._make_observation("MRP ₹125.00")
        c = self.service.normalize_observation(obs)[0]
        self.assertEqual(c.bounding_box, self.dummy_box)

    # 17. Image ID Preservation
    def test_17_image_id_preservation(self) -> None:
        obs = self._make_observation("Net Qty 500 g", image_id="img_panel_north_42")
        c = self.service.normalize_observation(obs)[0]
        self.assertEqual(c.image_id, "img_panel_north_42")

    # 18. Observation ID Preservation
    def test_18_observation_id_preservation(self) -> None:
        obs = self._make_observation("Batch No: B123")
        c = self.service.normalize_observation(obs)[0]
        self.assertEqual(c.observation_id, obs.observation_id)

    # 19. Sequence Preservation
    def test_19_sequence_preservation(self) -> None:
        obs = self._make_observation("Batch No: B123", sequence=4)
        c = self.service.normalize_observation(obs)[0]
        self.assertEqual(c.sequence, 4)

    # 20. Multi-Image Isolation
    def test_20_multi_image_isolation(self) -> None:
        res1 = OCRResult(
            image_id="img_A",
            observations=[self._make_observation("MRP ₹125.00", image_id="img_A")],
        )
        res2 = OCRResult(
            image_id="img_B",
            observations=[self._make_observation("Net Qty 500 g", image_id="img_B")],
        )
        grouped = self.service.normalize_inspection_observations({"img_A": res1, "img_B": res2})
        self.assertEqual(len(grouped["img_A"]), 1)
        self.assertEqual(len(grouped["img_B"]), 1)
        self.assertEqual(grouped["img_A"][0].field, EvidenceField.MRP)
        self.assertEqual(grouped["img_B"][0].field, EvidenceField.NET_QUANTITY)
        self.assertEqual(grouped["img_A"][0].image_id, "img_A")
        self.assertEqual(grouped["img_B"][0].image_id, "img_B")

    # 21. Duplicate Observations
    def test_21_duplicate_observations(self) -> None:
        res1 = OCRResult(
            image_id="img_A",
            observations=[self._make_observation("MRP 125", image_id="img_A")],
        )
        res2 = OCRResult(
            image_id="img_B",
            observations=[self._make_observation("MRP 125", image_id="img_B")],
        )
        all_candidates = self.service.normalize_ocr_results([res1, res2])
        self.assertEqual(len(all_candidates), 2)
        self.assertNotEqual(all_candidates[0].evidence_id, all_candidates[1].evidence_id)
        self.assertNotEqual(all_candidates[0].image_id, all_candidates[1].image_id)

    # 22. No Legal Interpretation
    def test_22_no_legal_interpretation(self) -> None:
        obs = self._make_observation("MRP ₹125.00")
        c = self.service.normalize_observation(obs)[0]
        d = c.to_dict()
        self.assertNotIn("is_compliant", d)
        self.assertNotIn("rule_id", d)
        self.assertNotIn("decision", d)

    # 23. No PASS/FAIL Output
    def test_23_no_pass_fail_output(self) -> None:
        obs = self._make_observation("MRP ₹125.00")
        c = self.service.normalize_observation(obs)[0]
        self.assertIn(c.status, [EvidenceStatus.VALID, EvidenceStatus.AMBIGUOUS, EvidenceStatus.UNPARSED, EvidenceStatus.INSUFFICIENT_EVIDENCE])
        self.assertNotIn(c.status.value, ["PASS", "FAIL", "COMPLIANT", "NON_COMPLIANT"])

    # 24. Deterministic Output
    def test_24_deterministic_output(self) -> None:
        obs = self._make_observation("Net Qty 500 g")
        c1 = self.service.normalize_observation(obs)[0]
        c2 = self.service.normalize_observation(obs)[0]
        self.assertEqual(c1.field, c2.field)
        self.assertEqual(c1.parsed_value, c2.parsed_value)
        self.assertEqual(c1.parsed_unit, c2.parsed_unit)
        self.assertEqual(c1.status, c2.status)
        self.assertEqual(c1.confidence, c2.confidence)

    # 25. Unicode Handling
    def test_25_unicode_handling(self) -> None:
        raw_unicode = "MRP ₹ 150.00"
        obs = self._make_observation(raw_unicode)
        c = self.service.normalize_observation(obs)[0]
        self.assertEqual(c.field, EvidenceField.MRP)
        self.assertEqual(c.parsed_value, 150.0)

    # 26. Whitespace Normalization
    def test_26_whitespace_normalization(self) -> None:
        self.assertEqual(normalize_evidence_text("  Net   Qty\t\t500   g  "), "Net Qty 500 g")
        self.assertEqual(normalize_evidence_text(""), "")

    # 27. No Silent OCR Correction
    def test_27_no_silent_ocr_correction(self) -> None:
        obs = self._make_observation("tQty 500 g")
        c = self.service.normalize_observation(obs)[0]
        self.assertEqual(c.raw_text, "tQty 500 g")
        self.assertNotEqual(c.normalized_text, "Net Qty 500 g")

    # 28. Empty OCR Result
    def test_28_empty_ocr_result(self) -> None:
        empty_res = OCRResult(image_id="img_empty", status=OCRProcessingStatus.NO_TEXT_DETECTED, observations=[])
        candidates = self.service.normalize_ocr_result(empty_res)
        self.assertEqual(candidates, [])

    # 29. Unreadable OCR Observation
    def test_29_unreadable_ocr_observation(self) -> None:
        obs = self._make_observation("XYZ###@@@!!!")
        candidates = self.service.normalize_observation(obs)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.GENERIC_DECLARATION)
        self.assertEqual(c.status, EvidenceStatus.UNPARSED)

    # 30. Multiple Candidates from One Observation
    def test_30_multiple_candidates_from_one_observation(self) -> None:
        obs = self._make_observation("Consumer Care: 1800-111-222 or care@brand.in")
        candidates = self.service.normalize_observation(obs)
        fields = [c.field for c in candidates]
        self.assertIn(EvidenceField.CONSUMER_CARE_PHONE, fields)
        self.assertIn(EvidenceField.CONSUMER_CARE_EMAIL, fields)

    # 31. Country of Origin Parsing
    def test_31_country_of_origin(self) -> None:
        obs = self._make_observation("Country of Origin: India")
        candidates = self.service.normalize_observation(obs)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.COUNTRY_OF_ORIGIN)
        self.assertIn("India", str(c.parsed_value))
        self.assertEqual(c.status, EvidenceStatus.VALID)

    # 32. Batch Number Parsing
    def test_32_batch_number_parsing(self) -> None:
        obs = self._make_observation("Batch No: B12345")
        candidates = self.service.normalize_observation(obs)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.BATCH_NUMBER)
        self.assertIn("B12345", str(c.parsed_value))
        self.assertEqual(c.status, EvidenceStatus.VALID)

    # 33. Lot Number Parsing
    def test_33_lot_number_parsing(self) -> None:
        obs = self._make_observation("Lot No: L9876")
        candidates = self.service.normalize_observation(obs)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.LOT_NUMBER)
        self.assertIn("L9876", str(c.parsed_value))
        self.assertEqual(c.status, EvidenceStatus.VALID)

    # 34. Standalone Alphanumeric Code Marked Ambiguous
    def test_34_standalone_code_generic(self) -> None:
        obs = self._make_observation("ABC123")
        candidates = self.service.normalize_observation(obs)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.GENERIC_DECLARATION)
        self.assertEqual(c.status, EvidenceStatus.UNPARSED)

    # 35. Quantity Without Net Prefix Marked Ambiguous
    def test_35_quantity_without_net_prefix(self) -> None:
        obs = self._make_observation("500 g")
        candidates = self.service.normalize_observation(obs)
        c = candidates[0]
        self.assertEqual(c.field, EvidenceField.NET_QUANTITY)
        self.assertEqual(c.parsed_value, 500.0)
        self.assertEqual(c.parsed_unit, "g")
        self.assertEqual(c.status, EvidenceStatus.AMBIGUOUS)

    # 36. Manufacturing vs Packing vs Import Date
    def test_36_date_type_separation(self) -> None:
        mfg_obs = self._make_observation("Mfg Date: 10/2025")
        pkd_obs = self._make_observation("Pkg Date: 11/2025")
        imp_obs = self._make_observation("Import Date: 12/2025")

        self.assertEqual(self.service.normalize_observation(mfg_obs)[0].field, EvidenceField.MANUFACTURE_DATE)
        self.assertEqual(self.service.normalize_observation(pkd_obs)[0].field, EvidenceField.PACKING_DATE)
        self.assertEqual(self.service.normalize_observation(imp_obs)[0].field, EvidenceField.IMPORT_DATE)

    # 37. No Unit Conversion
    def test_37_no_unit_conversion(self) -> None:
        obs = self._make_observation("Net Qty 500 g")
        c = self.service.normalize_observation(obs)[0]
        self.assertEqual(c.parsed_value, 500.0)
        self.assertEqual(c.parsed_unit, "g")
        self.assertNotEqual(c.parsed_value, 0.5)
        self.assertNotEqual(c.parsed_unit, "kg")

    # 38. Invalid Input Error Handling
    def test_38_invalid_input_error_handling(self) -> None:
        with self.assertRaises(InvalidEvidenceInputError):
            self.service.normalize_observation("Not an observation")  # type: ignore

        with self.assertRaises(InvalidEvidenceInputError):
            self.service.normalize_ocr_result("Not an OCR result")  # type: ignore

    # 39. Serialization to Dictionary
    def test_39_serialization_to_dict(self) -> None:
        obs = self._make_observation("MRP ₹125.00")
        c = self.service.normalize_observation(obs)[0]
        d = c.to_dict()
        self.assertEqual(d["field"], "mrp")
        self.assertEqual(d["parsed_value"], 125.00)
        self.assertEqual(d["status"], "VALID")
        self.assertEqual(d["raw_text"], "MRP ₹125.00")
        self.assertEqual(d["image_id"], "img_test_123")

    # 40. Parser vs OCR Confidence Distinct Tracking
    def test_40_parser_vs_ocr_confidence_tracking(self) -> None:
        obs = self._make_observation("MRP ₹125.00", confidence=0.90)
        c = self.service.normalize_observation(obs)[0]
        self.assertEqual(c.ocr_confidence, 0.90)
        self.assertEqual(c.parser_confidence, 1.0)
        self.assertAlmostEqual(c.confidence, 0.90, places=4)


if __name__ == "__main__":
    unittest.main()
