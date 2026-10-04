# Phase U10 — Consumer → Authority Action Bridge + Authority Case Integration

## 1. Overview & Purpose
Phase U10 closes the loop between consumer-facing inspections and regulatory enforcement workflows. When a consumer performs a package scan that reveals non-compliance or significant declaration defects, they can convert the verified scan findings into a structured, evidence-backed regulatory report package (`ConsumerReport`) that feeds directly into regulatory authority prioritisation (U9) and case management (T3).

```
CONSUMER
   │ (Mobile Scan)
   ▼
PRODUCT SCAN & VERIFICATION (U1-U6)
   │
   ▼
COMPLIANCE ISSUE (FAIL / REVIEW_REQUIRED)
   │
   ▼
PRESERVE EVIDENCE & ANNOTATIONS (U2)
   │
   ▼
REPORT ISSUE (POST /api/v1/inspections/{id}/consumer-reports)
   │
   ▼
AUTHORITY INTELLIGENCE & PRIORITIZATION (U9)
   │
   ▼
TYPED CASE INPUT CONTRACT (AuthorityCaseInput)
   │
   ▼
T3 AUTHORITY CASE / ENFORCEMENT WORKFLOW
```

---

## 2. Ownership Boundary

| Responsibility Area | Owner | Description |
| :--- | :--- | :--- |
| **Evidence & Intelligence Packaging** | **Developer 1 (Backend Intelligence)** | Aggregating U2 bounding boxes, U5 identity, U6 findings, and U9 priority scoring into an immutable snapshot package. |
| **Eligibility & Legal Provenance** | **Developer 1 (Backend Intelligence)** | Deterministic filtering (rejecting compliant PASS or incomplete scans), preventing user notes from mutating legal findings. |
| **API & Contract Surface** | **Developer 1 (Backend Intelligence)** | `POST /inspections/{id}/consumer-reports`, `GET /consumer-reports/{id}`, `GET /consumer-reports/{id}/case-input`. |
| **Case Operations & Workflow** | **T3 (Operations / Admin / Case Mgmt)** | Officer assignment, notice issuance, compounding fees, prosecution tracking, authority UI, notifications. |

---

## 3. Core Principles

### 3.1 Legal Safety & Immutability
- The consumer report **packages persisted verification results**; it does NOT run new OCR, Gemini, or RAG models.
- **Consumer Description as Context Only**: User-provided descriptions (e.g. *"MRP was scratched off"*) are saved under `consumer_description` as user context. They **never** override OCR evidence, statutory requirements, canonical statuses (`PASS`/`FAIL`/`REVIEW_REQUIRED`), or U9 risk scores.
- Legal authority strictly derives from:
  $$\text{Official Legal Corpus} \rightarrow \text{Applicability} \rightarrow \text{Requirement} \rightarrow \text{Verification Result}$$

### 3.2 Snapshot Stability
- When submitted, the `ConsumerReport` freezes the exact evidence, visual annotations (U2), product identity fields (U5), findings (U6), and risk signals (U9) at that instant.
- Subsequent changes to the consumer scan session do not mutate or taint the authority report package.

### 3.3 Strict Ownership & Privacy Obscuring
- Only the authenticated owner of the inspection session may submit a consumer report.
- Unauthenticated requests return `401 Unauthorized`.
- Cross-user inspection or report queries return safe `404 Not Found` (never `403 Forbidden`) to obscure existence from unauthorized callers.
- Regulatory authority callers (`role="authority"`) are authorized to inspect all submitted reports and fetch case input contracts.

### 3.4 Deterministic Eligibility Policy
Scans must meet strict criteria before being accepted as authority violation reports:
- **`FAIL`**: Fully eligible for reporting.
- **`REVIEW_REQUIRED`**: Eligible for reporting (human review recommended).
- **`NOT_VISIBLE`**: Eligible if associated with missing mandatory declarations.
- **`PASS`**: **Ineligible** (`400 Bad Request`, `INELIGIBLE_PASS`). Fully compliant scans cannot be submitted as violations.
- **`NOT_APPLICABLE`**: **Ineligible** (`400 Bad Request`, `INELIGIBLE_NOT_APPLICABLE`). Exempt packages cannot generate violation reports.
- **`INCOMPLETE` / `FAILED`**: **Ineligible** (`400 Bad Request`). Scans that did not complete analysis cannot be submitted.

### 3.5 Duplicate Handling (Idempotency)
- Submitting multiple report requests for the same `(inspection_id, user_id)` returns the existing `ConsumerReport` record without creating duplicate case entries.

---

## 4. API Endpoints

### 4.1 Submit Consumer Report
- **Endpoint**: `POST /api/v1/inspections/{inspection_id}/consumer-reports`
- **Auth**: Supabase Bearer JWT (Session Owner)
- **Request Body**:
  ```json
  {
    "consumer_description": "The MRP appears scratched and net quantity is missing.",
    "preferred_language": "en"
  }
  ```
- **Response**: `201 Created` with full `ConsumerReport` payload.

### 4.2 Get Consumer Report
- **Endpoint**: `GET /api/v1/consumer-reports/{report_id}`
- **Auth**: Report Owner or Authority Role
- **Query Params**: `lang` (`en`, `hi`, `mr`)
- **Response**: `200 OK` with `ConsumerReport`.

### 4.3 List Consumer Reports
- **Endpoint**: `GET /api/v1/consumer-reports`
- **Auth**: Authenticated User
- **Response**: List of reports submitted by caller (or all reports if authority).

### 4.4 Get Authority Case Input Contract (T3 Integration)
- **Endpoint**: `GET /api/v1/consumer-reports/{report_id}/case-input`
- **Auth**: Report Owner or Authority Role
- **Response**: Typed `AuthorityCaseInput` data package.

---

## 5. T3 Integration Contract (`AuthorityCaseInput`)
```json
{
  "source_report_id": "8f03c035-7fa9-4ee7-9f15-77983ea928b3",
  "inspection_id": "b1828859-994c-474d-965d-3d440adbb8f0",
  "consumer_user_id": "00000000-0000-0000-0000-000000000001",
  "case_type": "CONSUMER_GRIEVANCE",
  "priority": "HIGH",
  "priority_score": 85,
  "canonical_status": "FAIL",
  "product_identity": {
    "brand": "Acme Brand",
    "commodity": "Packaged Snack",
    "manufacturer": "Acme Foods Pvt Ltd",
    "declared_mrp": "Rs. 100.00"
  },
  "manufacturer_name": "Acme Foods Pvt Ltd",
  "commodity": "Packaged Snack",
  "brand": "Acme Brand",
  "barcode": "8901234567890",
  "findings_count": 2,
  "findings": [
    {
      "finding_id": "fnd_001",
      "requirement_id": "req_mrp",
      "canonical_status": "FAIL",
      "severity": "CRITICAL",
      "rule_number": "Rule 6(1)(e)",
      "statutory_label": "Maximum Retail Price (MRP)",
      "section_reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
      "evidence_ids": ["ev_01"],
      "annotation_ids": ["ann_01"],
      "image_ids": ["img_01"],
      "annotations": [
        {
          "annotation_id": "ann_01",
          "box_2d": [100, 200, 300, 400],
          "label": "MRP Not Legible",
          "color": "#E53935"
        }
      ]
    }
  ],
  "consumer_notes": "The MRP appears scratched and net quantity is missing.",
  "location": {
    "state_code": "MH",
    "state_name": "Maharashtra",
    "district_code": "MH-PUN",
    "district_name": "Pune"
  },
  "risk_signals": [
    {
      "signal_type": "REPEAT_OFFENDER_MANUFACTURER",
      "severity": "HIGH",
      "score_contribution": 30
    }
  ],
  "submitted_at": "2026-10-04T16:35:00Z"
}
```

---

## 6. Security, Privacy & Token Sanitization
- **No Secret Leakage**: The report payload never includes JWTs, Supabase API keys, database connection strings, or cloud storage bucket keys.
- **Public Share Separation**: Consumer authority reports are distinct from U4 public share QR links. Authority packages require authenticated access.
- **Safe 404 Masking**: Access attempts by unauthorized consumers return standard 404 resource not found errors to prevent user enumeration.
