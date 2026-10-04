# U3 — Multilingual Backend Architecture

## 1. Core Architectural Principle

Veriqoo maintains a **language-independent compliance core**. The execution pipeline strictly separates statutory legal logic, geometric reasoning, and compliance verdicts from the downstream user presentation layer.

```
Official Legal Source (Gazette)
        ↓
Requirement ID (R-6-1-e)
        ↓
Applicability Evaluation
        ↓
Verification Engine & Gemini Gate
        ↓
Canonical Result (PASS / FAIL / REVIEW_REQUIRED)
        ↓
Localization & Presentation Service (U3)
        ↓
API / Flutter / Telegram UI
```

**Rule of Language Independence**:
Localization **never** feeds back into:
- Applicability rules
- Legal RAG retrieval
- Gemini compliance verification prompts
- Compliance score calculations
- Statutory requirement IDs or machine codes
- Evidence bounding box coordinates

---

## 2. Supported Languages & Negotiation Hierarchy

| Code | Language | Script | Status |
| :--- | :--- | :--- | :--- |
| `en` | **English** | Latin | **Canonical Default & Fallback** |
| `hi` | **Hindi (हिन्दी)** | Devanagari | First-Class Indian Official Language |
| `mr` | **Marathi (मराठी)** | Devanagari | First-Class Regional Language (Maharashtra jurisdiction) |

### Precedence Hierarchy for Language Negotiation
When processing API requests or generating reports, the active language is resolved deterministically:

1. **Explicit Request Parameter**: `?lang=mr` or `request.language` (highest priority)
2. **Inspection Session Metadata**: `inspection.metadata["preferred_language"]`
3. **Authenticated User Claims**: `current_user.claims["preferred_language"]`
4. **HTTP Header**: `Accept-Language: hi-IN,hi;q=0.9,en;q=0.8`
5. **Canonical Fallback**: `en` (English)

---

## 3. Localization Architecture

All translations are organized into static, version-controlled catalog modules:

```
backend/app/localization/
├── __init__.py                # Package exports (SupportedLanguage, Persona, LocalizationService)
├── service.py                 # LocalizationService, negotiation resolver, template interpolator
└── catalogs/
    ├── __init__.py            # Catalog registry
    ├── en.py                  # Canonical English catalog
    ├── hi.py                  # Hindi catalog (Statutory labels, reasons, errors, Telegram)
    └── mr.py                  # Marathi catalog (Statutory labels, reasons, errors, Telegram)
```

---

## 4. Canonical vs. Localized Data

- **Persistence Immutability**: `VerificationResult`, `InspectionReport`, and `EvidenceAnnotation` are persisted in their canonical representations in PostgreSQL / Supabase JSONB.
- **On-the-Fly Presentation**: Localization occurs during presentation (e.g. `report.to_dict(lang="mr")` or `format_inspection_report(report, lang="hi")`).
- **Machine Invariance**: `overall_status`, `status`, `requirement_id`, `error.code`, and numeric score percentages are never translated.

---

## 5. Telegram Multilingual Integration

The Telegram Bot (`backend/app/telegram/`) provides native language switching:
- `/lang en` — Switch active session to English
- `/lang hi` — Switch active session to हिन्दी
- `/lang mr` — Switch active session to मराठी

Language preference is persisted per-conversation in `TelegramConversation.metadata["preferred_language"]` without requiring database schema changes.

---

## 6. API Response Representation

`GET /api/v1/inspections/{id}/report?lang=mr` returns:

```json
{
  "inspection_id": "insp_01JXYZ...",
  "overall_status": "FAIL",
  "language": "mr",
  "summary": "आवश्यकतेमध्ये वैधानिक अनुपालन अपयश आढळले: R-6-1-e.",
  "counts": {
    "image_count": 1,
    "applicable_requirement_count": 1,
    "pass_count": 0,
    "fail_count": 1,
    "review_required_count": 0,
    "not_visible_count": 0,
    "not_applicable_count": 0
  },
  "verification_results": [
    {
      "requirement_id": "R-6-1-e",
      "status": "FAIL",
      "reason": "एमआरपी घोषणेमध्ये अनिवार्य भारतीय रुपयांचे चलन चिन्ह (₹ किंवा Rs.) नमूद केलेले नाही."
    }
  ],
  "evidence_annotations": [
    {
      "annotation_id": "ann_9c2df3a48e71b260",
      "image_id": "img_001",
      "requirement_id": "R-6-1-e",
      "evidence_id": "ev_001",
      "status": "FAIL",
      "annotation_type": "ERROR_HIGHLIGHT",
      "label": "कमाल किरकोळ किंमत (MRP)",
      "reason": "एमआरपी घोषणेमध्ये अनिवार्य भारतीय रुपयांचे चलन चिन्ह (₹ किंवा Rs.) नमूद केलेले नाही.",
      "polygon": [[10.0, 20.0], [50.0, 20.0], [50.0, 60.0], [10.0, 60.0]],
      "bounding_box": {"x_min": 10.0, "y_min": 20.0, "x_max": 50.0, "y_max": 60.0, "width": 40.0, "height": 40.0},
      "normalized_box": {"x_min": 0.1, "y_min": 0.2, "x_max": 0.5, "y_max": 0.6},
      "is_locatable": true
    }
  ],
  "errors": [],
  "created_at": "2026-10-04T19:00:00+00:00",
  "metadata": {}
}
```
