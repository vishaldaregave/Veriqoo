"""Structured Evidence Image Error Highlighting & Visual Annotations for U2."""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Mapping, Sequence

from backend.app.services.evidence.models import EvidenceCandidate, ImageArtifact
from backend.app.services.verification.models import VerificationResult, VerificationStatus


# Canonical statutory declaration label mappings
STATUTORY_LABELS: dict[str, str] = {
    "R-6-1-a": "Manufacturer / Packer / Importer Identity & Address",
    "R-6-1-b": "Generic Name of Commodity",
    "R-6-1-c": "Net Quantity Declaration",
    "R-6-1-d": "Date of Manufacture / Packing / Import",
    "R-6-1-e": "Maximum Retail Price (MRP)",
    "R-6-1-f": "Consumer Care Contact Details",
    "R-6-1-g": "Country of Origin",
    "R-6-1-h": "Unit Sale Price (USP)",
}

FIELD_LABELS: dict[str, str] = {
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
}


@dataclasses.dataclass(frozen=True)
class NormalizedBox:
    """Relative coordinates (clamped strictly to 0.0 - 1.0) for responsive UI rendering."""
    x_min: float = 0.0
    y_min: float = 0.0
    x_max: float = 0.0
    y_max: float = 0.0

    def __post_init__(self) -> None:
        # Clamp strictly between 0.0 and 1.0
        object.__setattr__(self, "x_min", max(0.0, min(1.0, float(self.x_min))))
        object.__setattr__(self, "y_min", max(0.0, min(1.0, float(self.y_min))))
        object.__setattr__(self, "x_max", max(0.0, min(1.0, float(self.x_max))))
        object.__setattr__(self, "y_max", max(0.0, min(1.0, float(self.y_max))))

    def to_dict(self) -> dict[str, float]:
        return {
            "x_min": round(self.x_min, 6),
            "y_min": round(self.y_min, 6),
            "x_max": round(self.x_max, 6),
            "y_max": round(self.y_max, 6),
        }


@dataclasses.dataclass(frozen=True)
class EvidenceAnnotation:
    """Immutable structured visual annotation highlighting compliance findings on an image."""
    annotation_id: str
    image_id: str
    requirement_id: str
    evidence_id: str
    status: str
    annotation_type: str
    polygon: list[list[float]]
    bounding_box: dict[str, float]
    normalized_box: NormalizedBox
    label: str
    reason: str
    confidence: float | None = None
    is_locatable: bool = True
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert annotation to serializable dictionary."""
        return {
            "annotation_id": self.annotation_id,
            "image_id": self.image_id,
            "requirement_id": self.requirement_id,
            "evidence_id": self.evidence_id,
            "status": self.status,
            "annotation_type": self.annotation_type,
            "polygon": [[round(float(c), 2) for c in pt] for pt in self.polygon],
            "bounding_box": {k: round(float(v), 2) for k, v in self.bounding_box.items()},
            "normalized_box": self.normalized_box.to_dict(),
            "label": self.label,
            "reason": self.reason,
            "confidence": round(float(self.confidence), 4) if self.confidence is not None else None,
            "is_locatable": self.is_locatable,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceAnnotation:
        """Construct an EvidenceAnnotation from a dictionary representation."""
        norm_raw = data.get("normalized_box") or {}
        norm_box = NormalizedBox(
            x_min=float(norm_raw.get("x_min", 0.0)),
            y_min=float(norm_raw.get("y_min", 0.0)),
            x_max=float(norm_raw.get("x_max", 0.0)),
            y_max=float(norm_raw.get("y_max", 0.0)),
        )
        conf = data.get("confidence")
        return cls(
            annotation_id=str(data.get("annotation_id", "")),
            image_id=str(data.get("image_id", "")),
            requirement_id=str(data.get("requirement_id", "")),
            evidence_id=str(data.get("evidence_id", "")),
            status=str(data.get("status", "")),
            annotation_type=str(data.get("annotation_type", "")),
            polygon=list(data.get("polygon") or []),
            bounding_box=dict(data.get("bounding_box") or {}),
            normalized_box=norm_box,
            label=str(data.get("label", "")),
            reason=str(data.get("reason", "")),
            confidence=float(conf) if conf is not None else None,
            is_locatable=bool(data.get("is_locatable", True)),
            metadata=dict(data.get("metadata") or {}),
        )


def build_deterministic_annotation_id(
    inspection_id: str,
    image_id: str,
    requirement_id: str,
    evidence_id: str,
    annotation_type: str,
) -> str:
    """Generate a stable, deterministic annotation identifier."""
    seed = f"{inspection_id}:{image_id}:{requirement_id}:{evidence_id}:{annotation_type}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"ann_{digest}"


def resolve_annotation_label(requirement_id: str, candidate: EvidenceCandidate | None) -> str:
    """Resolve a human-readable statutory declaration label from requirement and evidence context."""
    if requirement_id in STATUTORY_LABELS:
        return STATUTORY_LABELS[requirement_id]

    if candidate is not None:
        field_name = candidate.field.value if hasattr(candidate.field, "value") else str(candidate.field)
        if field_name in FIELD_LABELS:
            return FIELD_LABELS[field_name]
        if field_name and field_name != "unparsed":
            return field_name.replace("_", " ").title()

    return f"Requirement {requirement_id}"


def _extract_bounding_geometry(
    bbox_obj: Any,
    image_width: int | None,
    image_height: int | None,
) -> tuple[list[list[float]], dict[str, float], NormalizedBox] | None:
    """Extract polygon, bounding box, and normalized box from a candidate geometry object."""
    if bbox_obj is None:
        return None

    points: list[list[float]] = []
    x_min: float = 0.0
    y_min: float = 0.0
    x_max: float = 0.0
    y_max: float = 0.0

    if hasattr(bbox_obj, "points"):
        raw_pts = bbox_obj.points
        if isinstance(raw_pts, (list, tuple)) and len(raw_pts) == 4:
            points = [[float(pt[0]), float(pt[1])] for pt in raw_pts]
            x_min = float(getattr(bbox_obj, "x_min", min(p[0] for p in points)))
            y_min = float(getattr(bbox_obj, "y_min", min(p[1] for p in points)))
            x_max = float(getattr(bbox_obj, "x_max", max(p[0] for p in points)))
            y_max = float(getattr(bbox_obj, "y_max", max(p[1] for p in points)))
    elif isinstance(bbox_obj, dict):
        raw_pts = bbox_obj.get("points")
        if isinstance(raw_pts, (list, tuple)) and len(raw_pts) == 4:
            points = [[float(pt[0]), float(pt[1])] for pt in raw_pts]
            x_min = float(bbox_obj.get("x_min", min(p[0] for p in points)))
            y_min = float(bbox_obj.get("y_min", min(p[1] for p in points)))
            x_max = float(bbox_obj.get("x_max", max(p[0] for p in points)))
            y_max = float(bbox_obj.get("y_max", max(p[1] for p in points)))
        elif "x_min" in bbox_obj and "y_min" in bbox_obj and "x_max" in bbox_obj and "y_max" in bbox_obj:
            x_min = float(bbox_obj["x_min"])
            y_min = float(bbox_obj["y_min"])
            x_max = float(bbox_obj["x_max"])
            y_max = float(bbox_obj["y_max"])
            points = [
                [x_min, y_min],
                [x_max, y_min],
                [x_max, y_max],
                [x_min, y_max],
            ]

    if not points or len(points) != 4:
        return None

    # Guarantee x_min <= x_max and y_min <= y_max
    if x_min > x_max:
        x_min, x_max = x_max, x_min
    if y_min > y_max:
        y_min, y_max = y_max, y_min

    width = max(0.0, x_max - x_min)
    height = max(0.0, y_max - y_min)

    bbox_dict = {
        "x_min": x_min,
        "y_min": y_min,
        "x_max": x_max,
        "y_max": y_max,
        "width": width,
        "height": height,
    }

    # Calculate normalized relative box (0.0 to 1.0)
    w_dim = float(image_width) if image_width and image_width > 0 else 1.0
    h_dim = float(image_height) if image_height and image_height > 0 else 1.0

    norm_box = NormalizedBox(
        x_min=x_min / w_dim if image_width else 0.0,
        y_min=y_min / h_dim if image_height else 0.0,
        x_max=x_max / w_dim if image_width else 0.0,
        y_max=y_max / h_dim if image_height else 0.0,
    )

    return points, bbox_dict, norm_box


def generate_evidence_annotations(
    verification_results: Sequence[VerificationResult],
    evidence_candidates: Sequence[EvidenceCandidate],
    images: Sequence[ImageArtifact] | None = None,
    inspection_id: str = "",
) -> list[EvidenceAnnotation]:
    """Generate structured visual evidence annotations for non-compliant and review findings.

    Policy:
    1. FAIL -> ERROR_HIGHLIGHT (Red)
    2. REVIEW_REQUIRED -> REVIEW_HIGHLIGHT (Amber)
    3. PASS -> Omitted by default (compliant findings do not require visual error highlighting)
    4. NOT_VISIBLE -> No fabricated coordinates, strictly omitted / non-locatable
    5. NOT_APPLICABLE -> No annotation
    """
    candidate_map: dict[str, EvidenceCandidate] = {}
    for cand in evidence_candidates:
        if cand.evidence_id:
            candidate_map[str(cand.evidence_id)] = cand

    image_dim_map: dict[str, tuple[int, int]] = {}
    if images:
        for img in images:
            image_dim_map[str(img.image_id)] = (img.normalized_width, img.normalized_height)

    annotations: list[EvidenceAnnotation] = []
    seen_keys: set[tuple[str, str, str, str]] = set()

    for result in verification_results:
        status_val = result.status.value if hasattr(result.status, "value") else str(result.status)

        # Only generate highlight annotations for actionable findings (FAIL and REVIEW_REQUIRED)
        if status_val == VerificationStatus.FAIL.value:
            ann_type = "ERROR_HIGHLIGHT"
        elif status_val == VerificationStatus.REVIEW_REQUIRED.value:
            ann_type = "REVIEW_HIGHLIGHT"
        else:
            # PASS, NOT_VISIBLE, and NOT_APPLICABLE produce no error highlights
            continue

        # If result has no evidence IDs (e.g. unobserved or missing text), do NOT fabricate coordinates
        if not result.evidence_ids:
            continue

        for ev_id in result.evidence_ids:
            cand = candidate_map.get(str(ev_id))
            if cand is None:
                continue

            target_img_id = str(cand.image_id or "")
            dims = image_dim_map.get(target_img_id)
            img_w = dims[0] if dims else None
            img_h = dims[1] if dims else None

            geom = _extract_bounding_geometry(cand.bounding_box, img_w, img_h)
            if geom is None:
                # Candidate has no valid bounding geometry; do not fabricate fake coordinates
                continue

            polygon, bbox_dict, norm_box = geom
            dedup_key = (target_img_id, str(result.requirement_id), str(ev_id), ann_type)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            ann_id = build_deterministic_annotation_id(
                inspection_id=inspection_id,
                image_id=target_img_id,
                requirement_id=str(result.requirement_id),
                evidence_id=str(ev_id),
                annotation_type=ann_type,
            )

            label = resolve_annotation_label(str(result.requirement_id), cand)
            conf = cand.confidence if cand.confidence is not None else cand.ocr_confidence

            annotations.append(
                EvidenceAnnotation(
                    annotation_id=ann_id,
                    image_id=target_img_id,
                    requirement_id=str(result.requirement_id),
                    evidence_id=str(ev_id),
                    status=status_val,
                    annotation_type=ann_type,
                    polygon=polygon,
                    bounding_box=bbox_dict,
                    normalized_box=norm_box,
                    label=label,
                    reason=result.reason,
                    confidence=float(conf) if conf is not None else None,
                    is_locatable=True,
                    metadata={
                        "observation_id": cand.observation_id,
                        "raw_text": cand.raw_text,
                        "field": cand.field.value if hasattr(cand.field, "value") else str(cand.field),
                    },
                )
            )

    return annotations
