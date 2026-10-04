# Veriqoo — Phase U6: Consumer Compliance Result & Explanation

## Overview

Phase U6 implements the presentation and plain-language explanation layer for the consumer-facing "Scan Before You Buy" experience. While Phase U5 establishes structured scan intelligence ("What did Veriqoo infer from this scan?"), Phase U6 translates canonical Legal Metrology compliance results into accessible, actionable explanations for ordinary consumers ("What does this result mean to a consumer?").

```
Canonical Compliance & Verification Flow
========================================
Canonical Legal/Compliance Result (InspectionReport + VerificationResults)
       │
       ▼
U1 Compliance Score Projection (score, percentage, rating)
       │
       ▼
U2 Evidence Annotations (bounding boxes, polygons, evidence coordinates)
       │
       ▼
U5 Consumer Scan Intelligence (product identity, scan quality, risk signal)
       │
       ▼
U6 Consumer Compliance Result & Explanation Engine
  ├─ Overall Result Classification (Consumer-safe categories)
  ├─ Plain-Language Summaries & "What This Means"
  ├─ Structured Findings (Severity, Canonical Reasons, Evidence Provenance)
  ├─ Statutory Citations (Rule numbers preserved without fabrication)
  ├─ Actionable Guidance (Deterministic consumer suggestions)
  ├─ Evidence Limitations (Capture quality, occluded panels)
  └─ U3 Multilingual Localization (en, hi, mr deterministic catalogs)
       │
       ▼
Consumer REST API (/api/v1/inspections/{id}/consumer-result) / Flutter Consumer App
```

---

## 1. Core Safety Principles & Architectural Boundaries

### 1.1 Pure Presentation Layer
- **No Independent Compliance Engine**: U6 explains existing verification results and never recomputes legal determinations, evaluates applicability, overrides Gemini verifiers, or creates new legal requirements.
- **Authoritative Source of Truth**: The canonical [InspectionReport](file:///d:/Development/flutter/LegalMetrologyAI/backend/app/services/inspection_pipeline/report.py) remains authoritative.
- **Zero Hallucination / Zero Fabrication**: Statutory rule citations and evidence IDs are strictly preserved from verified records. Unknown rule numbers remain `None`.
- **Non-Judgmental Guidance for Inconclusive Scans**: Declarations with `REVIEW_REQUIRED` or `NOT_VISIBLE` statuses are presented as visual or evidence limitations, never as manufacturer violations.

### 1.2 T3 Ownership Boundaries Respected
- U6 does **NOT** implement or duplicate user profile management, consumer scan history tables, saved products, consumer issue reporting, notifications, or authority bridges.
- Consumer results are generated dynamically on-demand from the completed inspection session.

---

## 2. Core Data Models

### 2.1 Enums & Classifications
- `ConsumerOverallResult`:
  - `NO_MAJOR_ISSUES_DETECTED`: When canonical inspection status is `PASS`.
  - `COMPLIANCE_ISSUE_DETECTED`: When canonical inspection status is `FAIL` (or fail count > 0).
  - `REVIEW_RECOMMENDED`: When canonical status is `REVIEW_REQUIRED` (with review-required declarations).
  - `INSUFFICIENT_EVIDENCE`: When mandatory declarations were `NOT_VISIBLE` or missing package panels.
- `FindingSeverity`:
  - `HIGH`: Applicable to `FAIL` findings.
  - `MEDIUM`: Applicable to `REVIEW_REQUIRED` findings.
  - `LOW`: Applicable to `NOT_VISIBLE` findings.
  - `INFO`: Applicable to `PASS` findings.

### 2.2 Domain Entities
- `LegalReference`: `requirement_id`, `rule_number`, `statutory_label`, `section_reference`.
- `ConsumerScore`: `score`, `percentage`, `rating`, `rating_label`, `evaluated_requirements`, `pass_count`, `fail_count`, `review_count`, `not_visible_count`.
- `ConsumerFinding`: `finding_id`, `requirement_id`, `status`, `consumer_title`, `consumer_explanation`, `evidence_ids`, `annotation_ids`, `legal_reference`, `corrective_action`, `severity`, `severity_label`.
- `ConsumerReportReference`: Safe metadata reference (`inspection_id`, `image_count`, `evidence_count`, `applicable_requirement_count`, `has_report`, `created_at`).
- `ConsumerComplianceResult`: Complete envelope aggregating result category, summary, persona explanation, score, risk signal, findings, recommended actions, limitations, and safe report reference.

---

## 3. Canonical Result Mapping & Policies

### 3.1 Status Mapping
```
Canonical Status               Consumer Overall Result
────────────────────────────────────────────────────────────────
PASS                       ──> NO_MAJOR_ISSUES_DETECTED
FAIL                       ──> COMPLIANCE_ISSUE_DETECTED
REVIEW_REQUIRED (review>0) ──> REVIEW_RECOMMENDED
REVIEW_REQUIRED (not_vis>0)──> INSUFFICIENT_EVIDENCE
NOT_APPLICABLE             ──> Excluded from violation determination
```
*Note*: The canonical machine status (e.g. `canonical_status = "FAIL"`) is always preserved in the response alongside the consumer result category.

### 3.2 Finding Explanations
1. **FAIL Findings**:
   - What was checked: Localized statutory declaration title (e.g. "Maximum Retail Price (MRP)").
   - What was observed: Canonical verification failure reason (e.g. missing currency symbol).
   - Provenance: Linked source `evidence_ids` and matching U2 `annotation_ids`.
   - Action: Directed guidance (e.g. "Review package declaration").
2. **REVIEW_REQUIRED Findings**:
   - Clarifies that package information was ambiguous or unparsed without asserting non-compliance.
3. **NOT_VISIBLE Findings**:
   - Clarifies that required declarations were occluded or not captured on visible package surfaces.
4. **PASS Findings**:
   - Concise verification confirmation ("Verified from the submitted package images.").

---

## 4. Limitations & Disclaimers

Every consumer result includes a deterministic list of limitations:
- `VERIFICATION_LIMITED_TO_CAPTURED_IMAGES`: Always included to prevent false guarantees of absolute legality.
- `SOME_DECLARATIONS_NOT_VISIBLE`: Added when `not_visible_count > 0`.
- `PRODUCT_IDENTITY_UNCERTAIN`: Added when U5 identity confidence is `LOW` or `UNKNOWN`.
- `INCOMPLETE_PACKAGE_VIEW` / `LOW_OCR_CONFIDENCE`: Added when U5 scan quality flags capture issues.
- `NON_APPLICABLE_EXCLUDED`: Added when exempt requirements were not evaluated.

---

## 5. Multilingual Localization (Phase U3 Integration)

- **Language Negotiation**: Supports `?lang=en`, `?lang=hi`, `?lang=mr` with cascading fallback.
- **Deterministic Catalogs**: Extended `en.py`, `hi.py`, and `mr.py` with `consumer_results`, `consumer_summaries`, `consumer_what_this_means`, `consumer_finding_templates`, `consumer_limitations`, and `consumer_severities`.
- **Zero LLM Translation**: All text transformations use strict catalog lookups and templated substitutions.
- **Machine Invariance**: Machine enum codes (`overall_result`, `canonical_status`, `severity`, `requirement_id`) remain invariant across all languages.

---

## 6. Security & API Contract (Phase 9D)

### Endpoint:
`GET /api/v1/inspections/{inspection_id}/consumer-result`

- **Authentication**: Bearer JWT required (Phase 9D).
- **Authorization**: Session owner only (`_verify_inspection_ownership`).
- **Ownership Obscuring**: Requests for inspections owned by other users return `404 INSPECTION_NOT_FOUND` (no `403` or existence leakage).
- **Preconditions**: Inspection session must be in `COMPLETED` status with an existing `InspectionReport`.
- **Execution**: Pure in-memory projection — zero OCR, Gemini verifier, Legal RAG, or pipeline execution.

### Response Payload:
```json
{
  "schema_version": "1.0.0",
  "inspection_id": "insp_1234",
  "overall_result": "NO_MAJOR_ISSUES_DETECTED",
  "canonical_status": "PASS",
  "result_label": "No Major Compliance Issues Detected",
  "summary": "The scanned package did not show any major compliance issues in the requirements that could be verified from the submitted images.",
  "what_this_means": "Based on the photos provided, the visible declarations conform to standard packaging requirements.",
  "score": {
    "score": 100.0,
    "percentage": "100.0%",
    "rating": "FULLY_COMPLIANT",
    "rating_label": "Fully Compliant",
    "evaluated_requirements": 4,
    "pass_count": 4,
    "fail_count": 0,
    "review_count": 0,
    "not_visible_count": 0,
    "not_applicable_count": 0
  },
  "risk_signal": "NO_MAJOR_ISSUES_DETECTED",
  "risk_signal_label": "No Major Issues Detected",
  "key_findings": [
    {
      "finding_id": "find_R-6-1-a",
      "requirement_id": "R-6-1-a",
      "status": "PASS",
      "consumer_title": "Manufacturer / Packer / Importer Identity & Address",
      "consumer_explanation": "Verified from the submitted package images.",
      "evidence_ids": ["ev_001"],
      "annotation_ids": ["ann_001"],
      "legal_reference": {
        "requirement_id": "R-6-1-a",
        "rule_number": "Rule 6(1)(a)",
        "statutory_label": "Manufacturer / Packer / Importer Identity & Address",
        "section_reference": "Legal Metrology (Packaged Commodities) Rules, 2011"
      },
      "corrective_action": null,
      "severity": "INFO",
      "severity_label": "Verified"
    }
  ],
  "recommended_actions": ["REVIEW_REPORT"],
  "recommended_action_labels": ["Review the full detailed verification report."],
  "limitations": ["VERIFICATION_LIMITED_TO_CAPTURED_IMAGES"],
  "limitation_labels": ["Compliance verification is limited strictly to the declarations visible in the provided package images."],
  "report_reference": {
    "inspection_id": "insp_1234",
    "image_count": 2,
    "evidence_count": 4,
    "applicable_requirement_count": 4,
    "has_report": true,
    "created_at": "2026-10-04T19:30:00Z"
  },
  "generated_at": "2026-10-04T19:35:00Z"
}
```
