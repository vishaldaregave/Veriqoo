# Phase U25: Evidence Trust and Chain of Custody Specification & Audit

## Executive Summary
This document provides the canonical architectural specification and audit for **Phase U25: Evidence Trust / Chain of Custody** in the Veriqoo Legal Metrology AI system.

The evidence custody subsystem establishes an append-oriented, tamper-evident cryptographic chain of custody for all physical package photographs and derived artifacts. It guarantees verifiable traceability from raw ingested pixels through OCR text extraction, candidate normalization, facts, statutory requirement verification, reports, and offline synchronization.

---

## 1. Trust Principles & Scope of Cryptographic Proof

> [!IMPORTANT]
> **Strict Trust Boundary**:
> - Evidence SHA-256 digests establish **byte-level cryptographic integrity** relative to a recorded hash.
> - Hashing proves that the exact stored byte stream has not been mutated, corrupted, or replaced since initial receipt.
> - Hashing **DOES NOT** prove that a photograph is truthful, genuine, physically unaltered in the physical world, or legally admissible in a court of law.
> - Hashing does not prove who physically held the camera or that the package physically existed.
> - Provenance chains prove event sequence integrity, not absolute legal authority.

---

## 2. Canonical Evidence Identity Model

The canonical identity of evidence is encapsulated in [`EvidenceRecord`](file:///d:/Development/flutter/LegalMetrologyAI/backend/app/services/evidence_chain/models.py):

| Field | Type | Description |
| :--- | :--- | :--- |
| `evidence_id` | `str` (UUID) | Unique canonical evidence identifier (`ev-...`) |
| `inspection_id` | `str` | Associated inspection identifier |
| `image_id` | `str \| None` | Key in image storage subsystem |
| `source_id` | `str \| None` | Mobile client or external entity ID |
| `content_hash` | `str` (64 hex) | Immutable SHA-256 digest of exact original bytes |
| `hash_algorithm` | `str` | Cryptographic digest algorithm (`SHA-256`) |
| `byte_size` | `int` | Exact byte count of original raw file |
| `media_type` | `str` | MIME type (`image/png`, `image/jpeg`, `image/webp`) |
| `original_filename` | `str \| None` | Original filename at capture/upload time |
| `storage_reference` | `str \| None` | Storage path in object storage |
| `captured_at` | `str \| None` | Client-reported capture timestamp (ISO-8601) |
| `received_at` | `str` | Server-recorded receipt timestamp (ISO-8601) |
| `created_at` | `str` | Database record creation timestamp (ISO-8601) |
| `submitted_by` | `str \| None` | Authenticated user ID (`sub` claim) |
| `source_type` | `str` | Ingestion mode (`UPLOAD`, `SYNC`, `CAMERA`, `CONSUMER`) |
| `integrity_status` | [`EvidenceIntegrityStatus`](file:///d:/Development/flutter/LegalMetrologyAI/backend/app/services/evidence_chain/models.py) | Controlled integrity state |
| `metadata` | `dict` | Immutable canonical metadata |

### Hash Algorithm Specification
- **Algorithm**: `SHA-256` (FIPS 180-4 compliant, 256-bit digest, lowercase hex representation).
- **Subject**: Computed strictly over the **raw, unaltered byte stream** as received at the API boundary.
- **Exclusions**: Resized variants, normalized images, OCR text strings, thumbnails, and JSON metadata are never hashed into `content_hash`.

---

## 3. Evidence Integrity States vs. Statutory Compliance

Evidence integrity status and legal compliance status are distinct domain concepts:

### Controlled Evidence Integrity Vocabulary ([`EvidenceIntegrityStatus`](file:///d:/Development/flutter/LegalMetrologyAI/backend/app/services/evidence_chain/models.py))
- `VERIFIED`: Stored bytes match recorded SHA-256 and event chain is continuous and valid.
- `UNVERIFIED`: Registered artifact pending byte audit or chain completion.
- `MISSING`: Stored object binary is not present in storage backend.
- `HASH_MISMATCH`: Retrieved bytes do not match recorded content hash (tamper detected).
- `CORRUPTED`: Broken cryptographic chain, invalid event hash, or missing genesis link.
- `REVIEW_REQUIRED`: Integrity verification requires human manual inspection.

### Statutory Compliance Vocabulary ([`VerificationStatus`](file:///d:/Development/flutter/LegalMetrologyAI/backend/app/services/verification/models.py))
- `PASS`: Compliant with statutory requirements.
- `FAIL`: Non-compliant with statutory requirements.
- `NOT_VISIBLE`: Mandatory declaration not visible in photographs.
- `NOT_APPLICABLE`: Requirement not applicable under current commodity rules.
- `REVIEW_REQUIRED`: Ambiguity requires statutory authority human determination.

Integrity failures **never silently mutate compliance verdicts into FAIL**. They surface explicitly in report metadata and trigger `REVIEW_REQUIRED` only where manual validation is required.

---

## 4. Tamper-Evident Provenance Chain Event Model

Every lifecycle event is recorded as an immutable [`EvidenceChainEvent`](file:///d:/Development/flutter/LegalMetrologyAI/backend/app/services/evidence_chain/models.py):

| Field | Description |
| :--- | :--- |
| `event_id` | Unique UUID event identifier (`evt-...`) |
| `evidence_id` | Associated evidence identifier |
| `inspection_id` | Associated inspection identifier |
| `event_type` | Controlled event type ([`ChainEventType`](file:///d:/Development/flutter/LegalMetrologyAI/backend/app/services/evidence_chain/models.py)) |
| `actor_type` | Subsystem actor (`USER`, `SYSTEM`, `OCR_ENGINE`, `REVALIDATION`) |
| `actor_id` | Authenticated user ID or engine version identifier |
| `timestamp` | Immutable ISO-8601 UTC timestamp |
| `previous_event_hash` | SHA-256 digest of preceding event (`null` for genesis `RECEIVED` event) |
| `event_hash` | Deterministic SHA-256 of canonical event JSON payload |
| `metadata` | Structured event-specific payload |
| `operation_id` | Idempotent operation tracking key |

### Event Types
- `CAPTURED`, `RECEIVED`, `STORED`, `HASHED`
- `OCR_STARTED`, `OCR_COMPLETED`
- `EVIDENCE_EXTRACTED`
- `FACT_DERIVED`
- `REQUIREMENT_EVALUATED`
- `REPORT_GENERATED`
- `REVALIDATED`
- `INTEGRITY_CHECKED`, `HASH_MISMATCH_DETECTED`

### Deterministic Event Hashing
`event_hash` is derived by serializing a canonical JSON dict of `(event_id, evidence_id, inspection_id, event_type, actor_type, actor_id, timestamp, previous_event_hash, metadata, operation_id)` with sorted keys, zero whitespace separators, and hashing with SHA-256.

---

## 5. Chain Verification Architecture

The [`EvidenceChainVerifier`](file:///d:/Development/flutter/LegalMetrologyAI/backend/app/services/evidence_chain/verifier.py) executes 8-point verification:
1. **Raw Byte Digest**: Computes SHA-256 over raw binary and asserts equality with `content_hash`.
2. **Event Signature**: Recomputes `event_hash` for each event node and asserts match.
3. **Genesis Integrity**: Asserts that first event has `previous_event_hash = None`.
4. **Parent Linkage**: Asserts that for all `i > 0`, `events[i].previous_event_hash == events[i-1].event_hash`.
5. **Evidence Isolation**: Rejects any event with mismatched `evidence_id`.
6. **Inspection Isolation**: Rejects any event with mismatched `inspection_id`.
7. **Chain Non-Emptiness**: Detects missing custody events.
8. **Broken Link Localization**: Identifies and reports the exact `broken_event_id` and error codes.

---

## 6. End-to-End Explicit Traceability Matrix

Every provenance link across the verification pipeline is explicitly linked through persistent IDs and durable repositories, with zero reliance on text similarity, timestamps, or array ordering:

```
[Raw Bytes] (SHA-256 content_hash)
    │
    ▼ [1] EvidenceRecord (`evidence_id`, `content_hash`, `image_id`)
[EvidenceChainEvent: RECEIVED / HASHED / STORED]
    │
    ▼ [2] OCRObservation (`observation_id`, `image_id`, `source_content_hash`)
[EvidenceChainEvent: OCR_COMPLETED]
    │
    ▼ [3] EvidenceCandidate (`candidate_id`, `observation_id`, `image_id`, `field_type`)
[EvidenceChainEvent: EVIDENCE_EXTRACTED]
    │
    ▼ [4] InspectionFact (`id`, `evidence_reference: {evidence_id, observation_id, image_id}`)
[EvidenceChainEvent: FACT_DERIVED]
    │
    ▼ [5] VerificationResult (`requirement_id`, `evidence_ids: [candidate_ids]`, `source_observation_ids`, `image_ids`, `metadata["fact_ids"]`)
[EvidenceChainEvent: REQUIREMENT_EVALUATED]
    │
    ▼ [6] InspectionReport (`inspection_id`, `verification_results: [VerificationResult]`)
[EvidenceChainEvent: REPORT_GENERATED]
```

### Traceability Audit Table

| Provenance Link | Source Model & Field | Target Model & Field | Persistence Mechanism | Survives Restart & Revalidation |
| :--- | :--- | :--- | :--- | :--- |
| **1. Evidence → OCR Observation** | `EvidenceRecord.content_hash` & `image_id` | `OCRObservation.image_id` + `source_content_hash` in `EvidenceChainEvent(OCR_COMPLETED)` | `inspection_evidence_records` table & `InspectionRepository.save_ocr_observations` | Yes (Explicit Foreign ID + SHA-256 byte digest matching) |
| **2. OCR Observation → Evidence Candidate** | `OCRObservation.observation_id` & `image_id` | `EvidenceCandidate.observation_id` & `EvidenceCandidate.image_id` | `InspectionRepository.save_candidates` & `EvidenceChainEvent(EVIDENCE_EXTRACTED)` | Yes (Explicit `observation_id` key) |
| **3. Evidence Candidate → Fact** | `EvidenceCandidate.candidate_id` | `InspectionFact.evidence_reference = {"evidence_id", "observation_id", "image_id"}` | `InspectionRepository.save_applicability_facts` & `EvidenceChainEvent(FACT_DERIVED)` | Yes (Structured dict reference holding explicit IDs) |
| **4. Fact → Requirement Result** | `InspectionFact.id` + `EvidenceCandidate.candidate_id` | `VerificationResult.evidence_ids` (candidate IDs), `source_observation_ids`, `image_ids`, and `metadata["fact_ids"]` | `InspectionRepository.save_requirement_results` & `EvidenceChainEvent(REQUIREMENT_EVALUATED)` | Yes (List of explicit candidate IDs, observation IDs, and fact IDs) |
| **5. Requirement Result → Report** | `VerificationResult.requirement_id` & list of results | `InspectionReport.verification_results` list (holding individual `VerificationResult` instances) | `InspectionRepository.save_report` / `inspection_reports` table & `EvidenceChainEvent(REPORT_GENERATED)` | Yes (Direct structured serialization in durable repository) |

---

## 7. Storage, Offline & Sync Integration

- **Storage Verification**: When evidence images are fetched, byte digests can be verified on-demand against recorded hashes, detecting missing or tampered files.
- **Offline Integrity**: Mobile sync bundles submit `evidence_id`, `inspection_id`, `content_hash`, and `byte_size`. Sync operations carry explicit `evidence_reference` payloads (`evidence_id`, `observation_id`, `image_id`).
- **Revalidation Integration**: Authoritative server revalidation operates directly on verified evidence records, logging `REVALIDATED` chain events without modifying historical evidence identity or overwriting historical provenance events.

---

## 8. Database Schema & Migration

Database migration: [`supabase/migrations/20261009000000_phase_u25_evidence_chain.sql`](file:///d:/Development/flutter/LegalMetrologyAI/supabase/migrations/20261009000000_phase_u25_evidence_chain.sql)

- Tables created:
  - `inspection_evidence_records`: Canonical evidence metadata with unique `evidence_id`, immutable `content_hash`, and indexes on `inspection_id` and `content_hash`.
  - `evidence_chain_events`: Append-oriented event chain with unique `event_id`, `previous_event_hash`, `event_hash`, and indexes on `evidence_id`, `inspection_id`, and `operation_id`.
  - Immutability trigger `trg_prevent_evidence_chain_event_mutation` preventing UPDATE and DELETE statements on historical chain events.

---

## 9. API Specifications

Mounted under `/api/v1/inspections`:

1. `GET /{inspection_id}/evidence`: Returns [`InspectionEvidenceSummaryResponse`](file:///d:/Development/flutter/LegalMetrologyAI/backend/app/api/schemas.py) with all evidence records, verified counts, and aggregate chain verification verdict.
2. `GET /{inspection_id}/evidence/{evidence_id}`: Returns single canonical [`EvidenceRecordResponse`](file:///d:/Development/flutter/LegalMetrologyAI/backend/app/api/schemas.py).
3. `GET /{inspection_id}/evidence/{evidence_id}/chain`: Returns complete chronological list of [`EvidenceChainEventResponse`](file:///d:/Development/flutter/LegalMetrologyAI/backend/app/api/schemas.py).
4. `GET /{inspection_id}/evidence/{evidence_id}/integrity`: Executes on-demand cryptographic verification and returns [`EvidenceIntegrityResponse`](file:///d:/Development/flutter/LegalMetrologyAI/backend/app/api/schemas.py).

---

## 10. Test Results & Validation Summary

### Test Suite Execution
- **Phase U25 Focused Tests**: `tests/test_phase25_evidence_chain_of_custody.py` (43 test cases) -> **43/43 PASSED (100%)**.
- **Phase U24 + U25 Regression**: `tests/test_phase24*.py` + `tests/test_phase25*.py` (202 test cases) -> **202/202 PASSED (100%)**.
- **Full Pytest Suite**: 1,203 test items -> **1,201 PASSED**, with strictly the **2 accepted Phase 9D baseline auth failures** (`test_malformed_authorization_scheme_returns_401` and `test_validate_supabase_jwt_success`).

