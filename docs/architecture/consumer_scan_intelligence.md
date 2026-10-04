# Veriqoo — Phase U5: Consumer Scan Intelligence

## Overview

Phase U5 introduces the backend intelligence layer for the "Scan Before You Buy" consumer workflow. Consumer Scan Intelligence derives structured product identity, scan-quality diagnostics, deterministic risk classification, and guidance actions from completed inspection sessions.

```
Consumer Scan Lifecycle
=======================
Package Capture (Consumer App / Telegram)
      │
      ▼
Canonical Inspection Pipeline (OCR, Extraction, Applicability, Verification, Scoring)
      │
      ▼
Persisted Session (InspectionReport + EvidenceCandidates)
      │
      ▼
Consumer Scan Intelligence Engine (U5)
  ├─ Product Identity (Zero Hallucination, Provenance Tracking)
  ├─ Identity Confidence (HIGH / MEDIUM / LOW / UNKNOWN)
  ├─ Scan Quality Diagnostics (Lighting, Coverage, Completeness)
  ├─ Risk Signal Derivation (Product Risk, NOT Legal Verdict)
  ├─ Guidance Actions (Deterministic suggestions for consumers)
  └─ U3 Multilingual Localization (en, hi, mr)
      │
      ▼
Consumer Experience / U6 Consumer Presentation
```

---

## 1. Ownership & Architectural Boundaries

### U5 Scope vs. T3 Ownership
- **U5 Ownership**: Purely the *intelligence generated FROM a scan* (product identity extraction, scan quality signals, consumer risk classification, guidance actions).
- **T3 Ownership**: Product-level user profiles, consumer scan history persistence, saved products, consumer issue reporting, consumer-to-authority bridge, user management, and notifications.
- **Rule**: U5 does not create or duplicate user product databases or scan history storage.

### Single Canonical Pipeline
- Consumer scans use the exact same canonical Veriqoo inspection pipeline as inspector inspections.
- Scan context is distinguished via session metadata (`scan_context = "CONSUMER" | "INSPECTOR"`).
- Legal compliance remains determined exclusively by the canonical Legal Metrology applicability and verification engine (`PASS`, `FAIL`, `REVIEW_REQUIRED`, `NOT_VISIBLE`, `NOT_APPLICABLE`).
- Consumer risk signals are advisory product signals, not legal determinations.

---

## 2. Core Data Models

### 2.1 Enums
- `ScanContext`: `CONSUMER`, `INSPECTOR`
- `IdentityConfidence`: `HIGH`, `MEDIUM`, `LOW`, `UNKNOWN`
- `RiskSignal`:
  - `HIGH_RISK_NON_COMPLIANCE`: Detected compliance violations (`FAIL`).
  - `POTENTIAL_COMPLIANCE_ISSUE`: Ambiguous or review-required declarations (`REVIEW_REQUIRED`).
  - `INSUFFICIENT_EVIDENCE`: Missing declarations or occluded panels (`NOT_VISIBLE`).
  - `PRODUCT_IDENTITY_UNCERTAIN`: Identity cannot be reliably corroborated.
  - `NO_MAJOR_ISSUES_DETECTED`: All applicable declarations pass verification.
- `ConsumerAction`:
  - `REVIEW_LABEL`, `CHECK_MRP`, `CHECK_NET_QUANTITY`, `CHECK_MANUFACTURER_DETAILS`, `CHECK_CONSUMER_CARE_DETAILS`, `CAPTURE_BACK_PANEL`, `CAPTURE_FRONT_PANEL`, `RESCAN_PACKAGE`, `REVIEW_REPORT`
- `ScanQualityIssue`:
  - `INSUFFICIENT_IMAGES`, `LOW_OCR_CONFIDENCE`, `INCOMPLETE_PACKAGE_VIEW`, `CONFLICTING_OBSERVATIONS`, `INSUFFICIENT_REQUIRED_DECLARATIONS`, `PRODUCT_IDENTITY_UNCERTAIN`

### 2.2 Product Identity & Provenance
- `FieldProvenance`: Tracks `evidence_id`, `observation_id`, `image_id`, and `confidence` for every extracted field.
- `ExtractedProductField`: Holds `value`, `unit`, `provenance`, `is_conflicting`, and `conflicting_values`.
- `ProductIdentity`: Encapsulates extracted fields (brand, generic_name, commodity, net_quantity, declared_mrp, manufacturer_name, manufacturer_address, country_of_origin, batch_number, barcode, manufacturing_date, expiry_date, consumer_care) alongside separate caller-supplied `user_entered_selling_price`.

---

## 3. Product Identity & Confidence Rules

### 3.1 Zero Hallucination Policy
- Product fields are populated **strictly** from normalized `EvidenceCandidate`s produced by the extraction engine.
- Missing fields remain `None` and are systematically cataloged in `missing_information`.
- Barcode values without explicit OCR/barcode evidence default to `UNKNOWN`. External barcode lookups are prohibited in U5.

### 3.2 Price Separation
- `declared_mrp` is derived from package label evidence.
- `user_entered_selling_price` is accepted as an optional query parameter supplied by the consumer app.
- The backend never infers or equates selling price to MRP.

### 3.3 Conflict Resolution Across Multi-Image Scans
- If multiple images provide identical normalized values for a field, provenances are merged.
- If distinct non-matching values are detected for the same field (e.g. conflicting net quantities), `is_conflicting = True`, all unique values are listed in `conflicting_values`, and scan quality flags `CONFLICTING_OBSERVATIONS`. The engine never silently chooses an arbitrary value.

### 3.4 Deterministic Identity Confidence Calculation
1. **HIGH**: Core identifiers (`commodity`, `manufacturer_name`, `net_quantity`, `declared_mrp`) present, average OCR confidence $\ge 0.85$, and zero conflicts.
2. **MEDIUM**: Core identifiers present with average OCR $\ge 0.65$ (or at least 2 core identifiers with OCR $\ge 0.75$), zero conflicts.
3. **LOW**: Minimal fields present ($< 2$ core fields) or conflicting values detected.
4. **UNKNOWN**: Zero product identity fields extracted.

---

## 4. Scan Quality Diagnostics vs. Legal Compliance

Scan quality diagnostics assess the physical and visual adequacy of the scan:
- Quality issues (e.g. `LOW_OCR_CONFIDENCE`, `INCOMPLETE_PACKAGE_VIEW`) do **NOT** convert an otherwise compliant product into a legal `FAIL`.
- Insufficient visual evidence maps canonically to `NOT_VISIBLE` or `REVIEW_REQUIRED`.

---

## 5. Risk Signal & Consumer Action Derivation

### Deterministic Risk Signal Precedence:
```
IF report.fail_count > 0 OR report.overall_status == FAIL:
    risk_signal = HIGH_RISK_NON_COMPLIANCE
ELSE IF report.review_required_count > 0:
    risk_signal = POTENTIAL_COMPLIANCE_ISSUE
ELSE IF report.not_visible_count > 0:
    risk_signal = INSUFFICIENT_EVIDENCE
ELSE IF report.overall_status == REVIEW_REQUIRED:
    risk_signal = POTENTIAL_COMPLIANCE_ISSUE
ELSE IF identity_confidence in (LOW, UNKNOWN):
    risk_signal = PRODUCT_IDENTITY_UNCERTAIN
ELSE:
    risk_signal = NO_MAJOR_ISSUES_DETECTED
```

### Action Suggestions:
- Guided suggestions mapped deterministically to failed requirement IDs and scan quality flags without asserting unsupported legal conclusions.

---

## 6. U3 Localization & Presentation

- Machine enum codes (`risk_signal`, `consumer_actions`, `issues`) remain invariant across all languages.
- Localized presentation strings are deterministically resolved via U3 catalogs (`en`, `hi`, `mr`) for:
  - `risk_signal_label`
  - `consumer_action_labels`
- No LLM execution is performed during localization.

---

## 7. API Contract

### Endpoint:
`GET /api/v1/inspections/{inspection_id}/consumer-intelligence`

- **Authentication**: Bearer JWT required (Phase 9D).
- **Authorization**: Owner-only access enforced (`_verify_inspection_ownership`).
- **Preconditions**: Inspection must be in `COMPLETED` state with an existing `InspectionReport`.
- **Query Parameters**:
  - `lang`: `en` | `hi` | `mr` (optional)
  - `selling_price`: float (optional)
- **Response**:
```json
{
  "schema_version": "1.0.0",
  "scan_context": "CONSUMER",
  "product_identity": {
    "brand": { "value": "Veriqoo Foods", "unit": null, "provenance": [...] },
    "commodity": { "value": "Green Tea", "unit": null, "provenance": [...] },
    "net_quantity": { "value": 250.0, "unit": "g", "provenance": [...] },
    "declared_mrp": { "value": 350.0, "unit": "INR", "provenance": [...] },
    "user_entered_selling_price": 320.0
  },
  "identity_confidence": "HIGH",
  "scan_quality": {
    "is_acceptable": true,
    "quality_score": 0.95,
    "issues": []
  },
  "compliance_summary": {
    "overall_status": "PASS",
    "score": 100.0,
    "pass_count": 4,
    "fail_count": 0,
    "review_count": 0,
    "not_visible_count": 0,
    "not_applicable_count": 0
  },
  "risk_signal": "NO_MAJOR_ISSUES_DETECTED",
  "risk_signal_label": "No Major Compliance Issues Detected",
  "consumer_actions": ["REVIEW_REPORT"],
  "consumer_action_labels": ["View Full Compliance Report"],
  "missing_information": ["batch_number", "manufacturing_date", "expiry_date"],
  "generated_at": "2026-10-04T19:30:00Z"
}
```

---

## 8. Security & Authorization (Phase 9D)

- **Authentication**: Bearer JWT token required. Unauthenticated requests return `401 AUTHENTICATION_REQUIRED`.
- **Ownership Obscuring**: In accordance with Phase 9D security policy, requests for inspections owned by another user return `404 INSPECTION_NOT_FOUND` (identical to nonexistent inspections) to prevent resource enumeration / IDOR existence leakage.
- **Privacy**: No private storage paths, JWT claims, Telegram identifiers, or internal database metadata are exposed in intelligence responses.
