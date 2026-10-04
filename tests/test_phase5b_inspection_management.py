"""Comprehensive unit tests for Phase 5B Multi-Image Inspection Management.

Tests all 30 required verification conditions:
1. inspection creation
2. inspection has deterministic identity format/type
3. inspection starts in collecting state
4. empty inspection is valid
5. add one ImageArtifact
6. add multiple ImageArtifacts
7. image order is preserved
8. explicit sequence values are correct
9. same ImageArtifact can be referenced intentionally
10. duplicate membership is not silently discarded
11. ImageArtifact bytes remain unchanged
12. ImageArtifact hash remains unchanged
13. ImageArtifact metadata remains unchanged
14. invalid image reference rejected
15. retrieval returns correct inspection
16. unknown inspection rejected
17. collecting -> ready transition
18. invalid lifecycle transition rejected
19. ready inspection cannot be mutated unexpectedly
20. no semantic image roles are created
21. no OCR dependency
22. no Gemini dependency
23. no legal dependency
24. no Supabase/database mutation
25. deterministic serialization
26. timezone-aware timestamps
27. multiple inspections remain isolated
28. image membership is isolated between inspections
29. removing image preserves remaining ordering
30. empty inspection can become ready only according to explicit chosen contract
"""

from __future__ import annotations

import io
import unittest
import uuid
from datetime import datetime, timezone
from typing import Any

from PIL import Image

from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.evidence.models import ImageArtifact
from backend.app.services.inspection.errors import (
    ImageNotFoundInInspectionError,
    InspectionError,
    InspectionNotFoundError,
    InspectionStateError,
    InvalidInspectionError,
    InvalidInspectionImageReferenceError,
    InvalidLifecycleTransitionError,
)
from backend.app.services.inspection.manager import InspectionManager
from backend.app.services.inspection.models import (
    Inspection,
    InspectionImage,
    InspectionStatus,
)


def _create_sample_artifact(color: tuple[int, int, int] = (100, 150, 200), name: str = "test.png") -> ImageArtifact:
    """Helper to generate a real Phase 5A ImageArtifact using the Phase 5A service."""
    img = Image.new("RGB", (100, 100), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    service = ImageIngestionService()
    return service.ingest_bytes(buf.getvalue(), source_name=name)


class TestPhase5BInspectionManagement(unittest.TestCase):
    """Rigorous Phase 5B test suite."""

    def setUp(self) -> None:
        self.manager = InspectionManager()
        self.art_a = _create_sample_artifact((10, 20, 30), "art_a.png")
        self.art_b = _create_sample_artifact((40, 50, 60), "art_b.png")
        self.art_c = _create_sample_artifact((70, 80, 90), "art_c.png")

    def test_01_inspection_creation(self) -> None:
        """1. Verify inspection creation."""
        insp = self.manager.create_inspection()
        self.assertIsInstance(insp, Inspection)
        self.assertTrue(len(insp.inspection_id) > 0)
        self.assertEqual(insp.status, InspectionStatus.COLLECTING)

    def test_02_inspection_identity_format(self) -> None:
        """2. Verify inspection has valid UUID-formatted identity."""
        insp = self.manager.create_inspection()
        # Verify valid UUID string
        parsed = uuid.UUID(insp.inspection_id)
        self.assertEqual(str(parsed), insp.inspection_id)

    def test_03_inspection_starts_in_collecting_state(self) -> None:
        """3. Verify inspection starts in COLLECTING state."""
        insp = self.manager.create_inspection()
        self.assertEqual(insp.status, InspectionStatus.COLLECTING)
        self.assertTrue(insp.is_collecting)
        self.assertFalse(insp.is_ready)

    def test_04_empty_inspection_is_valid(self) -> None:
        """4. Verify empty inspection is valid and contains 0 images."""
        insp = self.manager.create_inspection()
        self.assertEqual(insp.image_count, 0)
        self.assertEqual(len(insp.images), 0)
        self.assertEqual(insp.image_ids, [])

    def test_05_add_one_image_artifact(self) -> None:
        """5. Verify adding one ImageArtifact to an inspection."""
        insp = self.manager.create_inspection()
        ref = self.manager.add_image(insp.inspection_id, self.art_a)

        self.assertIsInstance(ref, InspectionImage)
        self.assertEqual(ref.image_id, self.art_a.image_id)
        self.assertEqual(ref.sequence, 1)
        self.assertEqual(insp.image_count, 1)
        self.assertEqual(insp.image_ids, [self.art_a.image_id])

    def test_06_add_multiple_image_artifacts(self) -> None:
        """6. Verify adding multiple ImageArtifacts."""
        insp = self.manager.create_inspection()
        refs = self.manager.add_images(insp.inspection_id, [self.art_a, self.art_b, self.art_c])

        self.assertEqual(len(refs), 3)
        self.assertEqual(insp.image_count, 3)
        self.assertEqual(insp.image_ids, [self.art_a.image_id, self.art_b.image_id, self.art_c.image_id])

    def test_07_image_order_is_preserved(self) -> None:
        """7. Verify image order is strictly preserved."""
        insp = self.manager.create_inspection()
        self.manager.add_image(insp.inspection_id, self.art_b)
        self.manager.add_image(insp.inspection_id, self.art_a)
        self.manager.add_image(insp.inspection_id, self.art_c)

        ordered = self.manager.get_ordered_image_references(insp.inspection_id)
        self.assertEqual([r.image_id for r in ordered], [self.art_b.image_id, self.art_a.image_id, self.art_c.image_id])

    def test_08_explicit_sequence_values(self) -> None:
        """8. Verify sequence values are sequential integers starting at 1."""
        insp = self.manager.create_inspection()
        r1 = self.manager.add_image(insp.inspection_id, self.art_a)
        r2 = self.manager.add_image(insp.inspection_id, self.art_b)
        r3 = self.manager.add_image(insp.inspection_id, self.art_c)

        self.assertEqual(r1.sequence, 1)
        self.assertEqual(r2.sequence, 2)
        self.assertEqual(r3.sequence, 3)

    def test_09_same_artifact_referenced_intentionally(self) -> None:
        """9. Verify the same ImageArtifact can be referenced multiple times."""
        insp = self.manager.create_inspection()
        r1 = self.manager.add_image(insp.inspection_id, self.art_a)
        r2 = self.manager.add_image(insp.inspection_id, self.art_b)
        r3 = self.manager.add_image(insp.inspection_id, self.art_a)  # Intentionally added again

        self.assertEqual(insp.image_count, 3)
        self.assertEqual(r1.image_id, self.art_a.image_id)
        self.assertEqual(r3.image_id, self.art_a.image_id)
        self.assertEqual(r1.sequence, 1)
        self.assertEqual(r3.sequence, 3)

    def test_10_duplicate_membership_not_silently_discarded(self) -> None:
        """10. Verify duplicate membership is tracked explicitly."""
        insp = self.manager.create_inspection()
        self.manager.add_image(insp.inspection_id, self.art_a)
        self.manager.add_image(insp.inspection_id, self.art_a)

        matches = insp.get_images_by_id(self.art_a.image_id)
        self.assertEqual(len(matches), 2)
        self.assertEqual([m.sequence for m in matches], [1, 2])

    def test_11_artifact_bytes_remain_unchanged(self) -> None:
        """11. Verify ImageArtifact normalized_bytes are never mutated."""
        orig_bytes = bytes(self.art_a.normalized_bytes)
        insp = self.manager.create_inspection()
        self.manager.add_image(insp.inspection_id, self.art_a)

        self.assertEqual(self.art_a.normalized_bytes, orig_bytes)

    def test_12_artifact_hash_remains_unchanged(self) -> None:
        """12. Verify ImageArtifact source_hash and normalized_hash are untouched."""
        orig_norm_hash = str(self.art_a.normalized_hash)
        orig_src_hash = str(self.art_a.source_hash)

        insp = self.manager.create_inspection()
        self.manager.add_image(insp.inspection_id, self.art_a)

        self.assertEqual(self.art_a.normalized_hash, orig_norm_hash)
        self.assertEqual(self.art_a.source_hash, orig_src_hash)

    def test_13_artifact_metadata_remains_unchanged(self) -> None:
        """13. Verify ImageArtifact metadata dictionary is unchanged."""
        meta_copy = dict(self.art_a.metadata)
        insp = self.manager.create_inspection()
        self.manager.add_image(insp.inspection_id, self.art_a)

        self.assertEqual(self.art_a.metadata, meta_copy)

    def test_14_invalid_image_reference_rejected(self) -> None:
        """14. Verify non-ImageArtifact objects are rejected with explicit error."""
        insp = self.manager.create_inspection()
        with self.assertRaises(InvalidInspectionImageReferenceError):
            self.manager.add_image(insp.inspection_id, "invalid_string_not_an_artifact")  # type: ignore

    def test_15_retrieval_returns_correct_inspection(self) -> None:
        """15. Verify get_inspection returns the exact inspection."""
        insp = self.manager.create_inspection(metadata={"batch_label": "sample_1"})
        retrieved = self.manager.get_inspection(insp.inspection_id)
        self.assertEqual(retrieved.inspection_id, insp.inspection_id)
        self.assertEqual(retrieved.metadata["batch_label"], "sample_1")

    def test_16_unknown_inspection_rejected(self) -> None:
        """16. Verify requesting an unknown inspection ID raises InspectionNotFoundError."""
        with self.assertRaises(InspectionNotFoundError):
            self.manager.get_inspection("non_existent_inspection_uuid_12345")

    def test_17_collecting_to_ready_transition(self) -> None:
        """17. Verify explicit COLLECTING -> READY state transition."""
        insp = self.manager.create_inspection()
        self.manager.add_image(insp.inspection_id, self.art_a)
        self.assertEqual(insp.status, InspectionStatus.COLLECTING)

        updated = self.manager.mark_ready(insp.inspection_id)
        self.assertEqual(updated.status, InspectionStatus.READY)
        self.assertTrue(updated.is_ready)
        self.assertFalse(updated.is_collecting)

    def test_18_invalid_lifecycle_transition_rejected(self) -> None:
        """18. Verify illegal lifecycle transitions raise InvalidLifecycleTransitionError."""
        from backend.app.services.inspection.lifecycle import InspectionLifecycleValidator
        # Trying to transition to a non-existent state or illegal state
        with self.assertRaises(InvalidLifecycleTransitionError):
            InspectionLifecycleValidator.validate_transition(
                InspectionStatus.READY,
                "COMPLIANT",  # type: ignore
            )

    def test_19_ready_inspection_cannot_be_mutated(self) -> None:
        """19. Verify mutating an inspection in READY state is rejected."""
        insp = self.manager.create_inspection()
        self.manager.add_image(insp.inspection_id, self.art_a)
        self.manager.mark_ready(insp.inspection_id)

        # Adding images to a READY inspection should raise InspectionStateError
        with self.assertRaises(InspectionStateError):
            self.manager.add_image(insp.inspection_id, self.art_b)

        # Removing images from a READY inspection should raise InspectionStateError
        with self.assertRaises(InspectionStateError):
            self.manager.remove_image_by_sequence(insp.inspection_id, 1)

    def test_20_no_semantic_roles_created(self) -> None:
        """20. Verify Inspection and InspectionImage have NO semantic role fields."""
        insp = self.manager.create_inspection()
        ref = self.manager.add_image(insp.inspection_id, self.art_a)

        for attr in ["role", "surface", "side", "is_front", "is_back", "label_type"]:
            self.assertFalse(hasattr(insp, attr), f"Inspection must not have {attr}")
            self.assertFalse(hasattr(ref, attr), f"InspectionImage must not have {attr}")

    def test_21_no_ocr_dependency(self) -> None:
        """21. Verify inspection package has zero OCR imports or dependencies."""
        import sys
        inspection_modules = [m for m in sys.modules if m.startswith("backend.app.services.inspection")]
        for mod_name in inspection_modules:
            mod = sys.modules[mod_name]
            self.assertFalse(hasattr(mod, "PaddleOCR"), f"{mod_name} must not contain PaddleOCR")
            self.assertFalse(hasattr(mod, "ocr"), f"{mod_name} must not contain ocr")

    def test_22_no_gemini_dependency(self) -> None:
        """22. Verify inspection package has zero Gemini imports or dependencies."""
        import sys
        inspection_modules = [m for m in sys.modules if m.startswith("backend.app.services.inspection")]
        for mod_name in inspection_modules:
            mod = sys.modules[mod_name]
            self.assertFalse(hasattr(mod, "GeminiService"), f"{mod_name} must not contain GeminiService")
            self.assertFalse(hasattr(mod, "genai"), f"{mod_name} must not contain genai")

    def test_23_no_legal_dependency(self) -> None:
        """23. Verify inspection package has zero legal or applicability dependencies."""
        import sys
        inspection_modules = [m for m in sys.modules if m.startswith("backend.app.services.inspection")]
        for mod_name in inspection_modules:
            mod = sys.modules[mod_name]
            self.assertFalse(hasattr(mod, "applicability"), f"{mod_name} must not contain applicability")
            self.assertFalse(hasattr(mod, "legal_rag"), f"{mod_name} must not contain legal_rag")

    def test_24_no_supabase_database_mutation(self) -> None:
        """24. Verify manager is completely in-memory with zero database attributes."""
        self.assertFalse(hasattr(self.manager, "supabase"))
        self.assertFalse(hasattr(self.manager, "db"))
        self.assertFalse(hasattr(self.manager, "table"))

    def test_25_deterministic_serialization(self) -> None:
        """25. Verify inspection serialization dictionary produces expected structure."""
        insp = self.manager.create_inspection(metadata={"case": "pkg_123"})
        self.manager.add_image(insp.inspection_id, self.art_a)

        d = insp.to_dict()
        self.assertEqual(d["inspection_id"], insp.inspection_id)
        self.assertEqual(d["status"], "COLLECTING")
        self.assertEqual(d["image_count"], 1)
        self.assertEqual(d["metadata"]["case"], "pkg_123")
        self.assertEqual(len(d["images"]), 1)
        self.assertEqual(d["images"][0]["image_id"], self.art_a.image_id)
        self.assertEqual(d["images"][0]["sequence"], 1)

    def test_26_timezone_aware_timestamps(self) -> None:
        """26. Verify created_at and added_at timestamps are timezone-aware UTC."""
        insp = self.manager.create_inspection()
        ref = self.manager.add_image(insp.inspection_id, self.art_a)

        self.assertIsNotNone(insp.created_at.tzinfo)
        self.assertIsNotNone(ref.added_at.tzinfo)
        self.assertEqual(insp.created_at.tzinfo, timezone.utc)
        self.assertEqual(ref.added_at.tzinfo, timezone.utc)

    def test_27_multiple_inspections_remain_isolated(self) -> None:
        """27. Verify independent inspections do not interfere with each other."""
        insp1 = self.manager.create_inspection()
        insp2 = self.manager.create_inspection()

        self.manager.add_image(insp1.inspection_id, self.art_a)
        self.assertEqual(insp1.image_count, 1)
        self.assertEqual(insp2.image_count, 0)

    def test_28_image_membership_isolated_between_inspections(self) -> None:
        """28. Verify same artifact can belong to multiple inspections independently."""
        insp1 = self.manager.create_inspection()
        insp2 = self.manager.create_inspection()

        r1 = self.manager.add_image(insp1.inspection_id, self.art_a)
        r2 = self.manager.add_image(insp2.inspection_id, self.art_a)

        self.assertEqual(r1.sequence, 1)
        self.assertEqual(r2.sequence, 1)
        self.assertEqual(insp1.image_count, 1)
        self.assertEqual(insp2.image_count, 1)

    def test_29_removing_image_preserves_remaining_ordering(self) -> None:
        """29. Verify removing an image preserves order of remaining images."""
        insp = self.manager.create_inspection()
        r1 = self.manager.add_image(insp.inspection_id, self.art_a)  # seq 1
        r2 = self.manager.add_image(insp.inspection_id, self.art_b)  # seq 2
        r3 = self.manager.add_image(insp.inspection_id, self.art_c)  # seq 3

        removed = self.manager.remove_image_by_sequence(insp.inspection_id, sequence=2)
        self.assertEqual(removed.image_id, self.art_b.image_id)
        self.assertEqual(insp.image_count, 2)
        self.assertEqual([r.image_id for r in insp.images], [self.art_a.image_id, self.art_c.image_id])
        self.assertEqual([r.sequence for r in insp.images], [1, 3])

    def test_30_empty_inspection_mark_ready_contract(self) -> None:
        """30. Verify empty inspection can become ready according to allow_empty contract."""
        insp = self.manager.create_inspection()

        # With allow_empty=False, marking empty inspection as ready raises InvalidInspectionError
        with self.assertRaises(InvalidInspectionError):
            self.manager.mark_ready(insp.inspection_id, allow_empty=False)

        # With allow_empty=True, marking empty inspection as ready succeeds
        ready_insp = self.manager.mark_ready(insp.inspection_id, allow_empty=True)
        self.assertEqual(ready_insp.status, InspectionStatus.READY)


if __name__ == "__main__":
    unittest.main()

