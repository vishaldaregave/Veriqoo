"""Core models and data contracts for Phase 5A (Ingestion) & Phase 5D (Evidence Normalization)."""

from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# =====================================================================
# Phase 5A Image Ingestion Models & Enums
# =====================================================================

class ImageFormat(str, Enum):
    """Supported image file formats."""
    JPEG = "JPEG"
    PNG = "PNG"
    WEBP = "WEBP"

    @classmethod
    def from_string(cls, format_str: str) -> ImageFormat | None:
        if not format_str:
            return None
        clean = format_str.strip().upper().replace(".", "")
        if clean in ("JPG", "JPEG"):
            return cls.JPEG
        elif clean == "PNG":
            return cls.PNG
        elif clean == "WEBP":
            return cls.WEBP
        return None


class ColorMode(str, Enum):
    """Normalized image color representation modes."""
    RGB = "RGB"
    RGBA = "RGBA"
    GRAYSCALE = "L"


@dataclasses.dataclass(frozen=True)
class IngestionConfig:
    """Configurable safety and normalization parameters for package photograph ingestion."""
    max_file_size_bytes: int = 25 * 1024 * 1024  # 25 MB
    max_width: int = 8192                        # Absolute rejection threshold
    max_height: int = 8192                       # Absolute rejection threshold
    max_pixels: int = 32_000_000                 # Absolute rejection threshold (32 MP)
    downscale_max_dimension: int = 2560          # Downscale dimension target for oversized images
    auto_downscale: bool = True                  # Downscale oversized images while preserving aspect ratio
    target_format: ImageFormat = ImageFormat.PNG # Default lossless normalized storage format
    jpeg_quality: int = 95                       # JPEG quality if target_format is JPEG
    allowed_formats: tuple[ImageFormat, ...] = (
        ImageFormat.JPEG,
        ImageFormat.PNG,
        ImageFormat.WEBP,
    )


@dataclasses.dataclass
class ImageArtifact:
    """Normalized, immutable evidence image artifact suitable for downstream OCR and analysis.

    Preserves full technical provenance and content-derived cryptographic identity.
    """
    image_id: str
    source_hash: str
    normalized_hash: str
    source_format: str
    normalized_format: str
    original_width: int
    original_height: int
    normalized_width: int
    normalized_height: int
    pixel_count: int
    aspect_ratio: float
    file_size_bytes: int
    source_file_size_bytes: int
    color_mode: str
    normalized_bytes: bytes
    was_resized: bool = False
    was_orientation_corrected: bool = False
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self, include_bytes: bool = False) -> dict[str, Any]:
        """Convert artifact metadata to a serializable dictionary."""
        data: dict[str, Any] = {
            "image_id": self.image_id,
            "source_hash": self.source_hash,
            "normalized_hash": self.normalized_hash,
            "source_format": self.source_format,
            "normalized_format": self.normalized_format,
            "original_width": self.original_width,
            "original_height": self.original_height,
            "normalized_width": self.normalized_width,
            "normalized_height": self.normalized_height,
            "pixel_count": self.pixel_count,
            "aspect_ratio": self.aspect_ratio,
            "file_size_bytes": self.file_size_bytes,
            "source_file_size_bytes": self.source_file_size_bytes,
            "color_mode": self.color_mode,
            "was_resized": self.was_resized,
            "was_orientation_corrected": self.was_orientation_corrected,
            "metadata": self.metadata,
        }
        if include_bytes:
            data["normalized_bytes_len"] = len(self.normalized_bytes)
        return data


@dataclasses.dataclass
class BatchItem:
    """Represents a single entry in an ImageBatch, tracking its duplicate relationships."""
    index: int
    artifact: ImageArtifact
    is_duplicate: bool = False
    duplicate_of_index: int | None = None
    duplicate_of_id: str | None = None


@dataclasses.dataclass
class ImageBatch:
    """Collection of ingested images preserving input order, identity, and duplicate tracking."""
    items: list[BatchItem] = dataclasses.field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def unique_images(self) -> list[ImageArtifact]:
        """Return list of distinct unique image artifacts in their first-encountered order."""
        return [item.artifact for item in self.items if not item.is_duplicate]

    @property
    def duplicate_images(self) -> list[BatchItem]:
        """Return list of items that are content duplicates of an earlier item in the batch."""
        return [item for item in self.items if item.is_duplicate]

    @property
    def unique_count(self) -> int:
        return len(self.unique_images)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicate_images)

    def get_by_index(self, index: int) -> BatchItem:
        if index < 0 or index >= len(self.items):
            raise IndexError(f"Batch item index {index} out of range [0, {len(self.items) - 1}]")
        return self.items[index]

    def get_by_id(self, image_id: str) -> ImageArtifact | None:
        for item in self.items:
            if item.artifact.image_id == image_id:
                return item.artifact
        return None


# =====================================================================
# Phase 5D Evidence Normalization Models & Controlled Vocabularies
# =====================================================================

class EvidenceField(str, Enum):
    """Controlled vocabulary of standardized evidence fields for packaged commodity declarations."""
    MANUFACTURER_NAME = "manufacturer_name"
    MANUFACTURER_ADDRESS = "manufacturer_address"
    PACKER_NAME = "packer_name"
    PACKER_ADDRESS = "packer_address"
    IMPORTER_NAME = "importer_name"
    IMPORTER_ADDRESS = "importer_address"
    COMMODITY_NAME = "commodity_name"
    NET_QUANTITY = "net_quantity"
    NET_QUANTITY_UNIT = "net_quantity_unit"
    MRP = "mrp"
    MRP_CURRENCY = "mrp_currency"
    BATCH_NUMBER = "batch_number"
    LOT_NUMBER = "lot_number"
    MANUFACTURE_DATE = "manufacture_date"
    PACKING_DATE = "packing_date"
    IMPORT_DATE = "import_date"
    CONSUMER_CARE = "consumer_care"
    CONSUMER_CARE_PHONE = "consumer_care_phone"
    CONSUMER_CARE_EMAIL = "consumer_care_email"
    COUNTRY_OF_ORIGIN = "country_of_origin"
    GENERIC_DECLARATION = "generic_declaration"
    UNPARSED = "unparsed"


class EvidenceStatus(str, Enum):
    """Lifecycle and certainty status of an extracted evidence candidate."""
    VALID = "VALID"
    AMBIGUOUS = "AMBIGUOUS"
    UNPARSED = "UNPARSED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclasses.dataclass
class EvidenceCandidate:
    """Strongly typed normalized evidence candidate derived deterministically from an OCR observation.

    Strictly preserves raw OCR text, geometry, confidence, and observation provenance.
    Does NOT contain legal compliance judgments or PASS/FAIL evaluations.
    """
    evidence_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    observation_id: str = ""
    image_id: str = ""
    field: EvidenceField = EvidenceField.UNPARSED
    raw_text: str = ""
    normalized_text: str = ""
    parsed_value: Any = None
    parsed_unit: str | None = None
    ocr_confidence: float | None = None
    parser_confidence: float = 1.0
    confidence: float = 1.0
    bounding_box: Any = None
    sequence: int = 0
    parser: str = "GenericParser"
    parser_version: str = "1.0.0"
    status: EvidenceStatus = EvidenceStatus.UNPARSED
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)
    created_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        # If composite confidence was not explicitly altered, compute conservative product
        if self.confidence == 1.0 and self.ocr_confidence is not None:
            self.confidence = float(self.ocr_confidence * self.parser_confidence)

    def to_dict(self) -> dict[str, Any]:
        """Serialize evidence candidate to clean dictionary for downstream consumers."""
        bbox_dict = None
        if hasattr(self.bounding_box, "to_dict"):
            bbox_dict = self.bounding_box.to_dict()
        elif isinstance(self.bounding_box, dict):
            bbox_dict = self.bounding_box

        return {
            "evidence_id": self.evidence_id,
            "observation_id": self.observation_id,
            "image_id": self.image_id,
            "field": self.field.value if isinstance(self.field, EvidenceField) else str(self.field),
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "parsed_value": self.parsed_value,
            "parsed_unit": self.parsed_unit,
            "ocr_confidence": self.ocr_confidence,
            "parser_confidence": self.parser_confidence,
            "confidence": self.confidence,
            "bounding_box": bbox_dict,
            "sequence": self.sequence,
            "parser": self.parser,
            "parser_version": self.parser_version,
            "status": self.status.value if isinstance(self.status, EvidenceStatus) else str(self.status),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }
