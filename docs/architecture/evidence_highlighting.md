# U2 — Structured Evidence Image Error Highlighting & Visual Annotations

## 1. Purpose & Overview

The U2 Evidence Image Error Highlighting system provides structured visual coordinate overlays for compliance findings identified during inspection verification. Rather than modifying raw package photographs or burning pixel boxes into stored files, the backend calculates deterministic geometric coordinate metadata that frontends (such as Flutter) render as vector overlays over canonical normalized package images.

```
VerificationResult (FAIL / REVIEW_REQUIRED)
        ↓
evidence_ids linkage
        ↓
EvidenceCandidate (bounding_box + image_id)
        ↓
EvidenceAnnotation (polygon, pixel box, normalized_box)
        ↓
InspectionReport (evidence_annotations)
        ↓
GET /api/v1/inspections/{id}/report
```

---

## 2. Supported Statuses & Highlighting Policy

| Requirement Status | Visual Highlight Type | Generated Overlay Behavior |
| :--- | :--- | :--- |
| **`FAIL`** | `ERROR_HIGHLIGHT` | Red border/highlight overlay indicating non-compliant or defective declaration |
| **`REVIEW_REQUIRED`** | `REVIEW_HIGHLIGHT` | Amber border/highlight overlay indicating declaration requiring human inspector review |
| **`PASS`** | *None* | Omitted by default; fully compliant declarations require no visual correction callout |
| **`NOT_VISIBLE`** | *None* | **Strictly non-locatable.** Coordinates are **never fabricated** when evidence was absent |
| **`NOT_APPLICABLE`** | *None* | Omitted; exempt requirements have no applicable spatial bounding box |

---

## 3. Coordinate System & Geometry

Annotations operate strictly in the canonical **normalized image coordinate space** produced by Phase 5A image ingestion:
- **Origin**: Top-Left `(0, 0)`.
- **`polygon`**: 4-point OCR quadrilateral `[[x1, y1], [x2, y2], [x3, y3], [x4, y4]]` in normalized pixel space.
- **`bounding_box`**: Pixel-space rectangle `{"x_min", "y_min", "x_max", "y_max", "width", "height"}`.
- **`normalized_box`**: Responsive relative coordinates clamped strictly to `0.0 <= coordinate <= 1.0` calculated via `x / normalized_width` and `y / normalized_height`.

PaddleOCR coordinates already operate directly on the normalized image bytes; therefore, no inverse transforms or artificial scaling factors are applied.

---

## 4. Evidence Traceability & Deterministic Identity

1. **Resolution**: Verification outcomes resolve `VerificationResult.evidence_ids` directly to in-memory `EvidenceCandidate` and `ImageArtifact` structures without redundant database round-trips or OCR re-runs.
2. **Deterministic IDs**: `build_deterministic_annotation_id(inspection_id, image_id, requirement_id, evidence_id, annotation_type)` derives a stable `ann_{sha256[:16]}` hash ensuring idempotent report replays without timestamp jitter.
3. **Multi-Item Support**: Requirements referencing multiple distinct evidence candidates produce separate, discrete annotations per evidence item and image.
4. **Deduplication**: Duplicate candidate references on the same requirement, image, and annotation type are deduplicated.

---

## 5. Persistence & Storage Strategy

- **Zero DB Migration**: Annotations serialize directly into the existing `report_payload` JSONB column in `inspection_reports`.
- **Backward Compatibility**: Legacy reports lacking `evidence_annotations` automatically load with default `evidence_annotations = []`.
- **Image Byte Immutability**: Authoritative stored images (bytes, SHA-256 hashes, storage paths) remain 100% immutable. Annotations reside purely in the metadata and visualization layer.

---

## 6. API Representation

In `GET /api/v1/inspections/{inspection_id}/report`, `InspectionReportResponse` exposes:

```json
{
  "inspection_id": "insp_01JXYZ...",
  "overall_status": "FAIL",
  "summary": "Statutory compliance failure...",
  "counts": { ... },
  "verification_results": [ ... ],
  "evidence_annotations": [
    {
      "annotation_id": "ann_9c2df3a48e71b260",
      "image_id": "img_01JXYZ...",
      "requirement_id": "R-6-1-e",
      "evidence_id": "ev_01JXYZ...",
      "status": "FAIL",
      "annotation_type": "ERROR_HIGHLIGHT",
      "polygon": [[120.0, 340.0], [350.0, 340.0], [350.0, 385.0], [120.0, 385.0]],
      "bounding_box": {
        "x_min": 120.0,
        "y_min": 340.0,
        "x_max": 350.0,
        "y_max": 385.0,
        "width": 230.0,
        "height": 45.0
      },
      "normalized_box": {
        "x_min": 0.12,
        "y_min": 0.34,
        "x_max": 0.35,
        "y_max": 0.385
      },
      "label": "Maximum Retail Price (MRP)",
      "reason": "MRP declaration missing currency symbol prefix.",
      "confidence": 0.965,
      "is_locatable": true,
      "metadata": {
        "observation_id": "obs_01JXYZ...",
        "raw_text": "MRP 150.00",
        "field": "mrp"
      }
    }
  ],
  "errors": [],
  "created_at": "2026-10-04T18:45:00+00:00",
  "metadata": {}
}
```
