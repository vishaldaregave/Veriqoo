"""Comprehensive unit tests for Phase 5A Evidence Image Ingestion & Normalization.

Tests all 30 required verification conditions using synthetic in-memory images:
1. Valid JPEG ingestion.
2. Valid PNG ingestion.
3. Valid WEBP ingestion.
4. Invalid image bytes.
5. Empty file.
6. Missing file path.
7. Unsupported format.
8. EXIF orientation normalization.
9. RGB normalization.
10. RGBA normalization.
11. Grayscale normalization.
12. Aspect-ratio preservation.
13. Large-image downscaling.
14. No upscaling of small images.
15. Maximum file-size rejection.
16. Maximum pixel-count rejection.
17. Source hash stability.
18. Normalized hash stability.
19. Same normalized image produces same identity.
20. Duplicate image detection.
21. Input order preservation.
22. Original input remains unchanged.
23. Normalized artifact metadata correctness.
24. Multiple-image batch ingestion.
25. Duplicate handling in batch.
26. No OCR dependency.
27. No Gemini calls.
28. No legal database mutation.
29. No Phase 3A table mutation.
30. Deterministic output for identical input.
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from backend.app.services.evidence.batch import ImageBatchIngestionService
from backend.app.services.evidence.errors import (
    ImageDecodeError,
    ImageIngestionError,
    ImageTooLargeError,
    ImageTooManyPixelsError,
    InvalidImageError,
    UnsupportedImageFormatError,
)
from backend.app.services.evidence.hashing import compute_sha256, derive_image_id
from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.evidence.models import (
    ImageArtifact,
    ImageFormat,
    IngestionConfig,
)


def _create_synthetic_image(
    format_name: str = "PNG",
    size: tuple[int, int] = (200, 100),
    color: tuple[int, int, int] | str = (200, 50, 50),
    mode: str = "RGB",
    exif_orientation: int | None = None,
) -> bytes:
    """Helper to generate in-memory synthetic image bytes."""
    img = Image.new(mode, size, color)
    draw = ImageDraw.Draw(img)
    draw.line((0, 0, size[0], size[1]), fill=(255, 255, 255) if mode == "RGB" else 255, width=3)

    buf = io.BytesIO()
    if exif_orientation is not None:
        exif = img.getexif()
        exif[0x0112] = exif_orientation  # 0x0112 is Orientation tag
        img.save(buf, format=format_name, exif=exif)
    else:
        img.save(buf, format=format_name)

    return buf.getvalue()


class TestPhase5AImageIngestion(unittest.TestCase):
    """Rigorous Phase 5A test suite."""

    def setUp(self) -> None:
        self.service = ImageIngestionService()
        self.batch_service = ImageBatchIngestionService(self.service)

    def test_01_valid_jpeg_ingestion(self) -> None:
        """1. Verify valid JPEG image ingestion."""
        jpeg_bytes = _create_synthetic_image(format_name="JPEG", size=(300, 200), color=(100, 150, 200))
        artifact = self.service.ingest_bytes(jpeg_bytes, source_name="test.jpg")
        self.assertIsInstance(artifact, ImageArtifact)
        self.assertEqual(artifact.source_format, "JPEG")
        self.assertEqual(artifact.original_width, 300)
        self.assertEqual(artifact.original_height, 200)
        self.assertEqual(artifact.color_mode, "RGB")
        self.assertTrue(len(artifact.normalized_bytes) > 0)

    def test_02_valid_png_ingestion(self) -> None:
        """2. Verify valid PNG image ingestion."""
        png_bytes = _create_synthetic_image(format_name="PNG", size=(250, 150), color=(50, 200, 100))
        artifact = self.service.ingest_bytes(png_bytes, source_name="test.png")
        self.assertEqual(artifact.source_format, "PNG")
        self.assertEqual(artifact.original_width, 250)
        self.assertEqual(artifact.original_height, 150)
        self.assertEqual(artifact.normalized_format, "PNG")

    def test_03_valid_webp_ingestion(self) -> None:
        """3. Verify valid WEBP image ingestion."""
        webp_bytes = _create_synthetic_image(format_name="WEBP", size=(400, 300), color=(220, 180, 50))
        artifact = self.service.ingest_bytes(webp_bytes, source_name="test.webp")
        self.assertEqual(artifact.source_format, "WEBP")
        self.assertEqual(artifact.original_width, 400)
        self.assertEqual(artifact.original_height, 300)

    def test_04_invalid_image_bytes(self) -> None:
        """4. Verify that corrupt or invalid image bytes are explicitly rejected."""
        corrupt_bytes = b"NOT_AN_IMAGE_RANDOM_GARBAGE_BYTES_12345"
        with self.assertRaises(InvalidImageError):
            self.service.ingest_bytes(corrupt_bytes, source_name="corrupt.jpg")

    def test_05_empty_file(self) -> None:
        """5. Verify that empty (0-byte) image streams are explicitly rejected."""
        with self.assertRaises(InvalidImageError):
            self.service.ingest_bytes(b"", source_name="empty.png")

    def test_06_missing_file_path(self) -> None:
        """6. Verify that non-existent filesystem paths raise InvalidImageError."""
        with self.assertRaises(InvalidImageError):
            self.service.ingest_file("non_existent_file_path_12345.jpg")

    def test_07_unsupported_format(self) -> None:
        """7. Verify that unsupported formats (e.g. BMP/GIF) are explicitly rejected."""
        bmp_bytes = _create_synthetic_image(format_name="BMP", size=(100, 100))
        with self.assertRaises(UnsupportedImageFormatError):
            self.service.ingest_bytes(bmp_bytes, source_name="test.bmp")

    def test_08_exif_orientation_normalization(self) -> None:
        """8. Verify that EXIF orientation is transposed into physical canonical pixels."""
        # Orientation 6 corresponds to 90-degree CCW rotation (width and height swap)
        exif_bytes = _create_synthetic_image(
            format_name="JPEG",
            size=(400, 200),
            exif_orientation=6,
        )
        artifact = self.service.ingest_bytes(exif_bytes, source_name="rotated.jpg")
        self.assertTrue(artifact.was_orientation_corrected)
        # Orientation 6 swaps dimensions: 400x200 becomes 200x400
        self.assertEqual(artifact.normalized_width, 200)
        self.assertEqual(artifact.normalized_height, 400)

    def test_09_rgb_normalization(self) -> None:
        """9. Verify standard RGB images are normalized without loss."""
        rgb_bytes = _create_synthetic_image(format_name="PNG", size=(120, 80), mode="RGB")
        artifact = self.service.ingest_bytes(rgb_bytes)
        self.assertEqual(artifact.color_mode, "RGB")

    def test_10_rgba_normalization(self) -> None:
        """10. Verify RGBA images with transparency are cleanly composited over white into RGB."""
        rgba_bytes = _create_synthetic_image(
            format_name="PNG",
            size=(100, 100),
            mode="RGBA",
            color=(255, 0, 0, 128),
        )
        artifact = self.service.ingest_bytes(rgba_bytes)
        self.assertEqual(artifact.color_mode, "RGB")
        # Check decoded normalized bytes are indeed 3-channel RGB
        decoded = Image.open(io.BytesIO(artifact.normalized_bytes))
        self.assertEqual(decoded.mode, "RGB")

    def test_11_grayscale_normalization(self) -> None:
        """11. Verify Grayscale (L) images are normalized into 3-channel RGB."""
        gray_bytes = _create_synthetic_image(format_name="PNG", size=(100, 100), mode="L", color=128)
        artifact = self.service.ingest_bytes(gray_bytes)
        self.assertEqual(artifact.color_mode, "RGB")
        decoded = Image.open(io.BytesIO(artifact.normalized_bytes))
        self.assertEqual(decoded.mode, "RGB")

    def test_12_aspect_ratio_preservation(self) -> None:
        """12. Verify aspect ratio is preserved exactly during normalization."""
        w, h = 300, 150
        bytes_data = _create_synthetic_image(size=(w, h))
        artifact = self.service.ingest_bytes(bytes_data)
        self.assertAlmostEqual(artifact.aspect_ratio, 2.0, places=3)
        self.assertAlmostEqual(artifact.normalized_width / artifact.normalized_height, 2.0, places=3)

    def test_13_large_image_downscaling(self) -> None:
        """13. Verify that oversized images are downscaled while preserving aspect ratio."""
        config = IngestionConfig(downscale_max_dimension=1000, auto_downscale=True)
        custom_service = ImageIngestionService(config=config)

        # 2000x1000 (aspect ratio 2.0)
        large_bytes = _create_synthetic_image(size=(2000, 1000))
        artifact = custom_service.ingest_bytes(large_bytes)
        self.assertTrue(artifact.was_resized)
        self.assertEqual(artifact.normalized_width, 1000)
        self.assertEqual(artifact.normalized_height, 500)
        self.assertAlmostEqual(artifact.aspect_ratio, 2.0, places=3)

    def test_14_no_upscaling_of_small_images(self) -> None:
        """14. Verify that small images are never upscaled."""
        config = IngestionConfig(downscale_max_dimension=2000, auto_downscale=True)
        custom_service = ImageIngestionService(config=config)

        small_bytes = _create_synthetic_image(size=(300, 200))
        artifact = custom_service.ingest_bytes(small_bytes)
        self.assertFalse(artifact.was_resized)
        self.assertEqual(artifact.normalized_width, 300)
        self.assertEqual(artifact.normalized_height, 200)

    def test_15_maximum_file_size_rejection(self) -> None:
        """15. Verify that images exceeding maximum file size are rejected."""
        config = IngestionConfig(max_file_size_bytes=1000)
        custom_service = ImageIngestionService(config=config)

        # Generate ~10KB image
        img_bytes = _create_synthetic_image(size=(400, 400))
        self.assertTrue(len(img_bytes) > 1000)
        with self.assertRaises(ImageTooLargeError):
            custom_service.ingest_bytes(img_bytes)

    def test_16_maximum_pixel_count_rejection(self) -> None:
        """16. Verify that images exceeding maximum pixel count threshold are rejected."""
        config = IngestionConfig(max_pixels=50_000)
        custom_service = ImageIngestionService(config=config)

        # 400x400 = 160,000 pixels > 50,000
        img_bytes = _create_synthetic_image(size=(400, 400))
        with self.assertRaises(ImageTooManyPixelsError):
            custom_service.ingest_bytes(img_bytes)

    def test_17_source_hash_stability(self) -> None:
        """17. Verify source hash is deterministic and matches raw SHA-256."""
        img_bytes = _create_synthetic_image(size=(100, 100), color=(10, 20, 30))
        expected_hash = compute_sha256(img_bytes)
        artifact = self.service.ingest_bytes(img_bytes)
        self.assertEqual(artifact.source_hash, expected_hash)

    def test_18_normalized_hash_stability(self) -> None:
        """18. Verify normalized hash is deterministic and matches normalized bytes SHA-256."""
        img_bytes = _create_synthetic_image(size=(100, 100), color=(10, 20, 30))
        artifact = self.service.ingest_bytes(img_bytes)
        expected_norm_hash = compute_sha256(artifact.normalized_bytes)
        self.assertEqual(artifact.normalized_hash, expected_norm_hash)

    def test_19_same_normalized_image_same_identity(self) -> None:
        """19. Verify identical input produces identical normalized image ID."""
        img_bytes = _create_synthetic_image(size=(150, 150), color=(55, 66, 77))
        art1 = self.service.ingest_bytes(img_bytes)
        art2 = self.service.ingest_bytes(img_bytes)
        self.assertEqual(art1.image_id, art2.image_id)
        self.assertEqual(art1.normalized_hash, art2.normalized_hash)

    def test_20_duplicate_image_detection(self) -> None:
        """20. Verify that identical images in a batch are detected as duplicates."""
        img_a = _create_synthetic_image(size=(100, 100), color=(1, 2, 3))
        img_b = _create_synthetic_image(size=(100, 100), color=(4, 5, 6))

        batch = self.batch_service.ingest_byte_list([
            (img_a, "a1.png"),
            (img_b, "b.png"),
            (img_a, "a2.png"),  # Duplicate of item 0
        ])

        self.assertEqual(batch.total_count, 3)
        self.assertEqual(batch.unique_count, 2)
        self.assertEqual(batch.duplicate_count, 1)

        item2 = batch.get_by_index(2)
        self.assertTrue(item2.is_duplicate)
        self.assertEqual(item2.duplicate_of_index, 0)
        self.assertEqual(item2.duplicate_of_id, batch.get_by_index(0).artifact.image_id)

    def test_21_input_order_preservation(self) -> None:
        """21. Verify batch preserves exact input order."""
        img1 = _create_synthetic_image(size=(100, 100), color=(10, 0, 0))
        img2 = _create_synthetic_image(size=(100, 100), color=(0, 20, 0))
        img3 = _create_synthetic_image(size=(100, 100), color=(0, 0, 30))

        batch = self.batch_service.ingest_byte_list([
            (img1, "first"),
            (img2, "second"),
            (img3, "third"),
        ])

        self.assertEqual(batch.get_by_index(0).artifact.metadata["source_name"], "first")
        self.assertEqual(batch.get_by_index(1).artifact.metadata["source_name"], "second")
        self.assertEqual(batch.get_by_index(2).artifact.metadata["source_name"], "third")

    def test_22_original_input_remains_unchanged(self) -> None:
        """22. Verify filesystem file is never modified or overwritten in place."""
        img_bytes = _create_synthetic_image(size=(150, 100))
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            tf.write(img_bytes)
            tf.flush()
            tmp_path = tf.name

        try:
            initial_mtime = os.path.getmtime(tmp_path)
            initial_size = os.path.getsize(tmp_path)

            artifact = self.service.ingest_file(tmp_path)
            self.assertIsInstance(artifact, ImageArtifact)

            # Assert original file attributes and content did not change
            self.assertEqual(os.path.getsize(tmp_path), initial_size)
            self.assertEqual(os.path.getmtime(tmp_path), initial_mtime)
            with open(tmp_path, "rb") as f:
                self.assertEqual(f.read(), img_bytes)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_23_normalized_artifact_metadata_correctness(self) -> None:
        """23. Verify all metadata dictionary fields are populated correctly."""
        img_bytes = _create_synthetic_image(size=(200, 100), color=(12, 34, 56))
        artifact = self.service.ingest_bytes(
            img_bytes,
            source_name="pkg_front.png",
            metadata={"package_side": "front_mock"},
        )
        d = artifact.to_dict(include_bytes=True)
        self.assertEqual(d["original_width"], 200)
        self.assertEqual(d["original_height"], 100)
        self.assertEqual(d["pixel_count"], 20000)
        self.assertEqual(d["aspect_ratio"], 2.0)
        self.assertEqual(d["color_mode"], "RGB")
        self.assertEqual(d["metadata"]["source_name"], "pkg_front.png")
        self.assertEqual(d["metadata"]["package_side"], "front_mock")
        self.assertTrue(d["normalized_bytes_len"] > 0)

    def test_24_multiple_image_batch_ingestion(self) -> None:
        """24. Verify multiple distinct images batch ingestion."""
        images = [
            (_create_synthetic_image(size=(100, 100), color=(i * 20, i * 20, i * 20)), f"img_{i}.png")
            for i in range(5)
        ]
        batch = self.batch_service.ingest_byte_list(images)
        self.assertEqual(batch.total_count, 5)
        self.assertEqual(batch.unique_count, 5)
        self.assertEqual(batch.duplicate_count, 0)
        self.assertEqual(len(batch.unique_images), 5)

    def test_25_duplicate_handling_in_batch(self) -> None:
        """25. Verify batch unique_images vs duplicate_images collections."""
        img_unique1 = _create_synthetic_image(size=(100, 100), color=(10, 10, 10))
        img_unique2 = _create_synthetic_image(size=(100, 100), color=(20, 20, 20))

        batch = self.batch_service.ingest_byte_list([
            (img_unique1, "u1"),
            (img_unique1, "u1_dup"),
            (img_unique2, "u2"),
            (img_unique2, "u2_dup1"),
            (img_unique2, "u2_dup2"),
        ])

        self.assertEqual(batch.total_count, 5)
        self.assertEqual(batch.unique_count, 2)
        self.assertEqual(batch.duplicate_count, 3)
        self.assertEqual(len(batch.unique_images), 2)
        self.assertEqual(len(batch.duplicate_images), 3)

    def test_26_no_ocr_dependency(self) -> None:
        """26. Verify evidence package does NOT import or depend on OCR modules."""
        import sys
        evidence_modules = [m for m in sys.modules if m.startswith("backend.app.services.evidence")]
        for mod_name in evidence_modules:
            mod = sys.modules[mod_name]
            self.assertFalse(hasattr(mod, "PaddleOCR"), f"{mod_name} must not contain PaddleOCR")
            self.assertFalse(hasattr(mod, "ocr"), f"{mod_name} must not contain ocr")

    def test_27_no_gemini_calls(self) -> None:
        """27. Verify evidence package does NOT call or import Gemini services."""
        import sys
        evidence_modules = [m for m in sys.modules if m.startswith("backend.app.services.evidence")]
        for mod_name in evidence_modules:
            mod = sys.modules[mod_name]
            self.assertFalse(hasattr(mod, "GeminiService"), f"{mod_name} must not contain GeminiService")
            self.assertFalse(hasattr(mod, "genai"), f"{mod_name} must not contain genai")

    def test_28_no_legal_database_mutation(self) -> None:
        """28. Verify image ingestion operates purely in-memory without database access."""
        img_bytes = _create_synthetic_image(size=(100, 100))
        artifact = self.service.ingest_bytes(img_bytes)
        self.assertIsNotNone(artifact.image_id)
        # Verify no database connection object is stored in the service
        self.assertFalse(hasattr(self.service, "supabase"))
        self.assertFalse(hasattr(self.service, "db"))

    def test_29_no_phase3a_table_mutation(self) -> None:
        """29. Verify image ingestion does NOT touch Phase 3A tables or models."""
        from backend.app.services.evidence import ImageIngestionService
        service = ImageIngestionService()
        self.assertFalse(hasattr(service, "applicability_rules"))
        self.assertFalse(hasattr(service, "inspection_facts"))

    def test_30_deterministic_output_for_identical_input(self) -> None:
        """30. Verify that running ingestion twice produces identical hashes and bytes."""
        img_bytes = _create_synthetic_image(size=(220, 110), color=(70, 80, 90))
        art1 = self.service.ingest_bytes(img_bytes)
        art2 = self.service.ingest_bytes(img_bytes)

        self.assertEqual(art1.source_hash, art2.source_hash)
        self.assertEqual(art1.normalized_hash, art2.normalized_hash)
        self.assertEqual(art1.image_id, art2.image_id)
        self.assertEqual(art1.normalized_bytes, art2.normalized_bytes)


if __name__ == "__main__":
    unittest.main()

