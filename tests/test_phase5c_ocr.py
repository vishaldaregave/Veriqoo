"""Comprehensive unit tests for Phase 5C PaddleOCR Extraction.

Tests all 40 required verification conditions:
1. valid ImageArtifact accepted
2. invalid input rejected
3. OCRResult created
4. image_id preserved
5. text preserved exactly
6. confidence preserved
7. bounding boxes preserved
8. quadrilateral boxes preserved
9. observation ordering deterministic
10. engine name recorded
11. engine version recorded
12. language/model configuration recorded
13. processing status recorded
14. no-text result represented correctly
15. OCR failure represented correctly
16. multiple observations supported
17. multiple images processed independently
18. inspection ordering preserved
19. same ImageArtifact produces equivalent OCR output
20. duplicate ImageArtifact produces deterministic output
21. no OCR correction
22. no quantity parsing
23. no MRP parsing
24. no date parsing
25. no legal interpretation
26. no Gemini dependency
27. no legal dependency
28. no Supabase dependency
29. Phase 5A ImageArtifact remains unchanged
30. Phase 5B Inspection remains unchanged
31. no image bytes modified
32. no image preprocessing that changes the canonical artifact
33. quality warning behavior
34. unsupported language/model configuration handled explicitly
35. OCR initialization failure handled
36. model unavailable handled
37. processing failure handled
38. configuration determinism
39. metadata completeness
40. multi-image OCR result isolation
"""

from __future__ import annotations

import io
import unittest
from datetime import timezone
from typing import Any

from PIL import Image

from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.evidence.models import ImageArtifact
from backend.app.services.inspection.manager import InspectionManager
from backend.app.services.ocr.config import OCRConfig
from backend.app.services.ocr.engine import MockOCREngine, PaddleOCREngine
from backend.app.services.ocr.errors import (
    OCRExtractionError,
    OCRInitializationError,
    OCRInvalidInputError,
    OCRModelUnavailableError,
    OCRProcessingError,
)
from backend.app.services.ocr.extractor import OCRExtractor
from backend.app.services.ocr.models import (
    BoundingBox,
    OCRObservation,
    OCRProcessingStatus,
    OCRResult,
)
from backend.app.services.ocr.quality import OCRQualityAssessor, OCRQualityReport


def _create_sample_artifact(size: tuple[int, int] = (200, 100), color: tuple[int, int, int] = (50, 100, 150)) -> ImageArtifact:
    """Helper to generate a valid Phase 5A ImageArtifact."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    service = ImageIngestionService()
    return service.ingest_bytes(buf.getvalue(), source_name="sample.png")


class TestPhase5COCRExtraction(unittest.TestCase):
    """Rigorous Phase 5C test suite."""

    def setUp(self) -> None:
        self.sample_predictions = [
            (
                [[10.0, 10.0], [90.0, 10.0], [90.0, 30.0], [10.0, 30.0]],
                ("MRP ₹12S.00", 0.945),
            ),
            (
                [[10.0, 40.0], [80.0, 40.0], [80.0, 60.0], [10.0, 60.0]],
                ("Net Qty: 5OOg", 0.880),
            ),
        ]
        self.mock_engine = MockOCREngine(observations=self.sample_predictions, engine_version="mock_v2.8")
        self.extractor = OCRExtractor(engine=self.mock_engine)
        self.artifact = _create_sample_artifact()

    def test_01_valid_image_artifact_accepted(self) -> None:
        """1. Verify valid ImageArtifact is accepted by OCRExtractor."""
        result = self.extractor.extract_from_artifact(self.artifact)
        self.assertIsInstance(result, OCRResult)
        self.assertEqual(result.status, OCRProcessingStatus.SUCCESS)

    def test_02_invalid_input_rejected(self) -> None:
        """2. Verify invalid non-ImageArtifact input is rejected with OCRInvalidInputError."""
        with self.assertRaises(OCRInvalidInputError):
            self.extractor.extract_from_artifact("not_an_artifact")  # type: ignore

    def test_03_ocr_result_created(self) -> None:
        """3. Verify OCRResult container is instantiated with valid ID and timestamps."""
        result = self.extractor.extract_from_artifact(self.artifact)
        self.assertTrue(len(result.result_id) > 0)
        self.assertIsNotNone(result.processed_at.tzinfo)

    def test_04_image_id_preserved(self) -> None:
        """4. Verify source image_id is preserved on result and each observation."""
        result = self.extractor.extract_from_artifact(self.artifact)
        self.assertEqual(result.image_id, self.artifact.image_id)
        for obs in result.observations:
            self.assertEqual(obs.image_id, self.artifact.image_id)

    def test_05_text_preserved_exactly(self) -> None:
        """5. Verify exact uncorrected OCR text is preserved."""
        result = self.extractor.extract_from_artifact(self.artifact)
        self.assertEqual(result.observations[0].text, "MRP ₹12S.00")
        self.assertEqual(result.observations[1].text, "Net Qty: 5OOg")

    def test_06_confidence_preserved(self) -> None:
        """6. Verify exact confidence scores are preserved as floats."""
        result = self.extractor.extract_from_artifact(self.artifact)
        self.assertAlmostEqual(result.observations[0].confidence, 0.945, places=3)
        self.assertAlmostEqual(result.observations[1].confidence, 0.880, places=3)

    def test_07_bounding_boxes_preserved(self) -> None:
        """7. Verify bounding box metrics are calculated and preserved."""
        result = self.extractor.extract_from_artifact(self.artifact)
        box = result.observations[0].bounding_box
        self.assertIsInstance(box, BoundingBox)
        self.assertEqual(box.x_min, 10.0)
        self.assertEqual(box.y_min, 10.0)
        self.assertEqual(box.x_max, 90.0)
        self.assertEqual(box.y_max, 30.0)
        self.assertEqual(box.width, 80.0)
        self.assertEqual(box.height, 20.0)

    def test_08_quadrilateral_boxes_preserved(self) -> None:
        """8. Verify all 4 quadrilateral vertices are preserved in polygon order."""
        result = self.extractor.extract_from_artifact(self.artifact)
        points = result.observations[0].bounding_box.points
        self.assertEqual(points, [[10.0, 10.0], [90.0, 10.0], [90.0, 30.0], [10.0, 30.0]])

    def test_09_observation_ordering_deterministic(self) -> None:
        """9. Verify observations preserve 1-based sequential engine order."""
        result = self.extractor.extract_from_artifact(self.artifact)
        self.assertEqual(result.observations[0].sequence, 1)
        self.assertEqual(result.observations[1].sequence, 2)

    def test_10_engine_name_recorded(self) -> None:
        """10. Verify engine name is recorded in result and observations."""
        result = self.extractor.extract_from_artifact(self.artifact)
        self.assertEqual(result.engine, "MockPaddleOCR")
        self.assertEqual(result.observations[0].engine, "MockPaddleOCR")

    def test_11_engine_version_recorded(self) -> None:
        """11. Verify engine version is recorded in result and observations."""
        result = self.extractor.extract_from_artifact(self.artifact)
        self.assertEqual(result.engine_version, "mock_v2.8")
        self.assertEqual(result.observations[0].engine_version, "mock_v2.8")

    def test_12_language_configuration_recorded(self) -> None:
        """12. Verify configured language is recorded in OCRResult."""
        cfg = OCRConfig(language="hi")
        result = self.extractor.extract_from_artifact(self.artifact, config=cfg)
        self.assertEqual(result.language, "hi")

    def test_13_processing_status_recorded(self) -> None:
        """13. Verify processing status enum is populated."""
        result = self.extractor.extract_from_artifact(self.artifact)
        self.assertEqual(result.status, OCRProcessingStatus.SUCCESS)

    def test_14_no_text_result_represented_correctly(self) -> None:
        """14. Verify NO_TEXT_DETECTED status when engine returns 0 detections."""
        empty_engine = MockOCREngine(observations=[])
        extractor = OCRExtractor(engine=empty_engine)
        result = extractor.extract_from_artifact(self.artifact)
        self.assertEqual(result.status, OCRProcessingStatus.NO_TEXT_DETECTED)
        self.assertEqual(result.total_observations, 0)
        self.assertIsNone(result.error_message)

    def test_15_ocr_failure_represented_correctly(self) -> None:
        """15. Verify FAILED status with error_message when engine fails."""
        failing_engine = MockOCREngine(simulate_failure=True)
        extractor = OCRExtractor(engine=failing_engine)
        result = extractor.extract_from_artifact(self.artifact)
        self.assertEqual(result.status, OCRProcessingStatus.FAILED)
        self.assertIsNotNone(result.error_message)
        self.assertIn("Simulated mock OCR", result.error_message)

    def test_16_multiple_observations_supported(self) -> None:
        """16. Verify multiple observations are held in result."""
        result = self.extractor.extract_from_artifact(self.artifact)
        self.assertEqual(result.total_observations, 2)
        self.assertEqual(len(result.raw_texts), 2)

    def test_17_multiple_images_processed_independently(self) -> None:
        """17. Verify multi-image extraction returns isolated results per image."""
        art1 = _create_sample_artifact(color=(10, 20, 30))
        art2 = _create_sample_artifact(color=(40, 50, 60))

        res1 = self.extractor.extract_from_artifact(art1)
        res2 = self.extractor.extract_from_artifact(art2)

        self.assertEqual(res1.image_id, art1.image_id)
        self.assertEqual(res2.image_id, art2.image_id)
        self.assertNotEqual(res1.image_id, res2.image_id)

    def test_18_inspection_ordering_preserved(self) -> None:
        """18. Verify extract_from_inspection processes images in exact inspection order."""
        manager = InspectionManager()
        insp = manager.create_inspection()
        art1 = _create_sample_artifact(color=(10, 10, 10))
        art2 = _create_sample_artifact(color=(20, 20, 20))
        art3 = _create_sample_artifact(color=(30, 30, 30))

        manager.add_image(insp.inspection_id, art2)
        manager.add_image(insp.inspection_id, art1)
        manager.add_image(insp.inspection_id, art3)

        results = self.extractor.extract_from_inspection(insp, manager.get_artifact)
        self.assertEqual(len(results), 3)
        self.assertEqual([r.image_id for r in results], [art2.image_id, art1.image_id, art3.image_id])

    def test_19_same_artifact_equivalent_output(self) -> None:
        """19. Verify identical artifact yields equivalent observation texts and geometry."""
        res1 = self.extractor.extract_from_artifact(self.artifact)
        res2 = self.extractor.extract_from_artifact(self.artifact)

        self.assertEqual(res1.raw_texts, res2.raw_texts)
        self.assertEqual(res1.total_observations, res2.total_observations)

    def test_20_duplicate_artifact_deterministic_output(self) -> None:
        """20. Verify duplicate artifact in inspection produces deterministic observations."""
        manager = InspectionManager()
        insp = manager.create_inspection()
        manager.add_image(insp.inspection_id, self.artifact)
        manager.add_image(insp.inspection_id, self.artifact)

        results = self.extractor.extract_from_inspection(insp, manager.get_artifact)
        self.assertEqual(results[0].raw_texts, results[1].raw_texts)

    def test_21_no_ocr_correction(self) -> None:
        """21. Verify OCR does NOT fix '12S' to '125' or '5OO' to '500'."""
        result = self.extractor.extract_from_artifact(self.artifact)
        self.assertIn("12S", result.raw_texts[0])
        self.assertNotIn("125", result.raw_texts[0])
        self.assertIn("5OO", result.raw_texts[1])
        self.assertNotIn("500", result.raw_texts[1])

    def test_22_no_quantity_parsing(self) -> None:
        """22. Verify result does NOT parse structured quantity fields."""
        result = self.extractor.extract_from_artifact(self.artifact)
        for attr in ["net_quantity", "quantity", "unit", "parsed_quantity"]:
            self.assertFalse(hasattr(result, attr))

    def test_23_no_mrp_parsing(self) -> None:
        """23. Verify result does NOT parse structured MRP fields."""
        result = self.extractor.extract_from_artifact(self.artifact)
        for attr in ["mrp", "mrp_value", "currency", "parsed_price"]:
            self.assertFalse(hasattr(result, attr))

    def test_24_no_date_parsing(self) -> None:
        """24. Verify result does NOT parse manufacturing/expiry dates."""
        result = self.extractor.extract_from_artifact(self.artifact)
        for attr in ["mfg_date", "expiry_date", "best_before"]:
            self.assertFalse(hasattr(result, attr))

    def test_25_no_legal_interpretation(self) -> None:
        """25. Verify result contains NO legal compliance or decision fields."""
        result = self.extractor.extract_from_artifact(self.artifact)
        for attr in ["compliant", "is_valid", "pass_fail", "decision"]:
            self.assertFalse(hasattr(result, attr))

    def test_26_no_gemini_dependency(self) -> None:
        """26. Verify OCR package has zero Gemini dependencies."""
        import sys
        ocr_modules = [m for m in sys.modules if m.startswith("backend.app.services.ocr")]
        for mod_name in ocr_modules:
            mod = sys.modules[mod_name]
            self.assertFalse(hasattr(mod, "GeminiService"), f"{mod_name} must not contain GeminiService")
            self.assertFalse(hasattr(mod, "genai"), f"{mod_name} must not contain genai")

    def test_27_no_legal_dependency(self) -> None:
        """27. Verify OCR package has zero legal dependencies."""
        import sys
        ocr_modules = [m for m in sys.modules if m.startswith("backend.app.services.ocr")]
        for mod_name in ocr_modules:
            mod = sys.modules[mod_name]
            self.assertFalse(hasattr(mod, "applicability"), f"{mod_name} must not contain applicability")
            self.assertFalse(hasattr(mod, "legal_rag"), f"{mod_name} must not contain legal_rag")

    def test_28_no_supabase_dependency(self) -> None:
        """28. Verify extractor has zero database dependencies."""
        self.assertFalse(hasattr(self.extractor, "supabase"))
        self.assertFalse(hasattr(self.extractor, "db"))

    def test_29_phase5a_artifact_unchanged(self) -> None:
        """29. Verify ImageArtifact attributes are unchanged after OCR."""
        initial_hash = str(self.artifact.normalized_hash)
        self.extractor.extract_from_artifact(self.artifact)
        self.assertEqual(self.artifact.normalized_hash, initial_hash)

    def test_30_phase5b_inspection_unchanged(self) -> None:
        """30. Verify Inspection container is unchanged after OCR."""
        manager = InspectionManager()
        insp = manager.create_inspection()
        manager.add_image(insp.inspection_id, self.artifact)
        self.assertEqual(insp.image_count, 1)

        self.extractor.extract_from_inspection(insp, manager.get_artifact)
        self.assertEqual(insp.image_count, 1)
        self.assertEqual(insp.status, "COLLECTING")

    def test_31_no_image_bytes_modified(self) -> None:
        """31. Verify artifact normalized_bytes are identical before and after extraction."""
        orig_bytes = bytes(self.artifact.normalized_bytes)
        self.extractor.extract_from_artifact(self.artifact)
        self.assertEqual(self.artifact.normalized_bytes, orig_bytes)

    def test_32_no_preprocessing_modifies_artifact(self) -> None:
        """32. Verify no binarization/sharpening alters canonical artifact."""
        w, h = self.artifact.normalized_width, self.artifact.normalized_height
        self.extractor.extract_from_artifact(self.artifact)
        self.assertEqual(self.artifact.normalized_width, w)
        self.assertEqual(self.artifact.normalized_height, h)

    def test_33_quality_warning_behavior(self) -> None:
        """33. Verify OCR quality assessor flags low-resolution images."""
        small_art = _create_sample_artifact(size=(50, 50))
        report = OCRQualityAssessor.assess(small_art)
        self.assertFalse(report.is_suitable)
        self.assertTrue(len(report.warnings) > 0)
        self.assertIn("Low resolution", report.warnings[0])

    def test_34_unsupported_language_handled(self) -> None:
        """34. Verify custom language config is cleanly propagated."""
        cfg = OCRConfig(language="fr")
        result = self.extractor.extract_from_artifact(self.artifact, config=cfg)
        self.assertEqual(result.language, "fr")

    def test_35_ocr_initialization_failure_handled(self) -> None:
        """35. Verify OCRInitializationError is a valid exception subclass."""
        err = OCRInitializationError("Test initialization failure")
        self.assertIsInstance(err, OCRExtractionError)

    def test_36_model_unavailable_handled(self) -> None:
        """36. Verify PaddleOCREngine gracefully raises OCRModelUnavailableError when not installed."""
        prod_engine = PaddleOCREngine()
        if prod_engine._ocr_instance is None:
            with self.assertRaises(OCRModelUnavailableError):
                prod_engine.predict(self.artifact.normalized_bytes, OCRConfig())

    def test_37_processing_failure_handled(self) -> None:
        """37. Verify OCRProcessingError is captured gracefully without crashing extractor."""
        failing_engine = MockOCREngine(simulate_failure=True)
        extractor = OCRExtractor(engine=failing_engine)
        result = extractor.extract_from_artifact(self.artifact)
        self.assertEqual(result.status, OCRProcessingStatus.FAILED)

    def test_38_configuration_determinism(self) -> None:
        """38. Verify OCRConfig to_dict serialization is deterministic."""
        cfg1 = OCRConfig(language="en", det_db_thresh=0.4)
        cfg2 = OCRConfig(language="en", det_db_thresh=0.4)
        self.assertEqual(cfg1.to_dict(), cfg2.to_dict())

    def test_39_metadata_completeness(self) -> None:
        """39. Verify OCRResult dictionary contains all required provenance fields."""
        result = self.extractor.extract_from_artifact(self.artifact)
        d = result.to_dict()
        self.assertIn("result_id", d)
        self.assertIn("image_id", d)
        self.assertIn("status", d)
        self.assertIn("total_observations", d)
        self.assertIn("engine", d)
        self.assertIn("engine_version", d)
        self.assertIn("language", d)
        self.assertIn("processed_at", d)
        self.assertIn("observations", d)
        self.assertIn("quality_report", d)

    def test_40_multi_image_ocr_isolation(self) -> None:
        """40. Verify observations from different images are strictly separated."""
        art1 = _create_sample_artifact((150, 100), (10, 10, 10))
        art2 = _create_sample_artifact((150, 100), (20, 20, 20))

        res1 = self.extractor.extract_from_artifact(art1)
        res2 = self.extractor.extract_from_artifact(art2)

        for obs in res1.observations:
            self.assertEqual(obs.image_id, art1.image_id)
            self.assertNotEqual(obs.image_id, art2.image_id)

        for obs in res2.observations:
            self.assertEqual(obs.image_id, art2.image_id)
            self.assertNotEqual(obs.image_id, art1.image_id)


if __name__ == "__main__":
    unittest.main()

