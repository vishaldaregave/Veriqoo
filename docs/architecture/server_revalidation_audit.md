# Veriqoo Architectural Audit: Phase U24-F Server Revalidation of Offline Inspections

**Author**: Veriqoo Backend Architecture Team  
**Phase**: U24-F (Offline Inspection & Sync — Server Revalidation)  
**Date**: October 2026  
**Status**: COMPLETE / AUTHORITATIVE  

---

## 1. Executive Summary & Purpose

Veriqoo's legal authority resides exclusively in the approved statutory legal corpus and its cryptographic snapshot. Mobile devices running offline deterministic evaluations (U24-D) operate in an untrusted execution environment with potentially stale snapshots, omitted statutory requirements, or incomplete applicability rules.

The objective of **Phase U24-F** is to implement the **authoritative server-side revalidation boundary**. The server must **never blindly trust** offline compliance conclusions, target requirement lists, or applicability decisions. It must independently derive complete statutory requirements, re-evaluate applicability against current server law, deterministically verify evidence, and record authoritative `SERVER_REVALIDATED` results with complete audit provenance.

---

## 2. Core Audit Findings (Questions A through R)

### A. What exactly does the server currently persist from an offline evaluation?
The server persists granular `DurableSyncOperationRecord`s in `inspection_sync_operations` (and in-memory `InspectionSession` containers). These records store:
- `INSPECTION`: Root session metadata, ownership, creation timestamps.
- `IMAGE`: Image identifiers, source SHA-256 hashes, normalized hashes, dimensions.
- `OCR_OBSERVATION`: Raw text observations, bounding boxes, detection confidences, sequence numbers.
- `EVIDENCE`: Typed candidate declarations (field, raw text, normalized text, parsed value/unit, status).
- `FACT`: Atomic inspection facts (`is_prepacked`, commodity type, volume, weight).
- `REPORT`: Client-computed summary, counts, offline evaluation metadata (`evaluation_mode = OFFLINE_DETERMINISTIC`, `legal_snapshot_id`, `revalidation_required`).

### B. Can the server reconstruct the complete inspection evidence from persisted data?
**Yes.** All raw observations and normalized candidate declarations are preserved in structured sync records with content-hash integrity.

### C. Can the server independently reconstruct inspection facts?
**Yes.** All inspection facts submitted via `FACT` sync operations are indexed and deduplicated by fact key.

### D. Can the server independently evaluate applicability?
**Yes.** The server re-runs the pure in-memory `ApplicabilityService.evaluate_run()` using reconstructed facts and approved server applicability rules/versions.

### E. Can the server independently derive the complete applicable requirement set?
**Yes.** The server resolves all statutory requirements directly from the authoritative server `LegalSnapshotContext.requirements`. It treats the client-submitted `target_requirements` strictly as an assertion or diagnostic reference, never as legal authority.

### F. Can the server independently validate the legal snapshot?
**Yes.** `LegalSnapshotValidator.validate_snapshot()` checks the client's snapshot ID against the server active snapshot and known historical snapshots, classifying it as `MATCHED`, `STALE`, or `UNKNOWN`.

### G. Can the server deterministically re-run compliance verification?
**Yes.** The server uses `DeterministicVerifier.verify()` and `EvidenceMatcher.match_candidates()`, computing exact canonical verification statuses (`PASS`, `FAIL`, `NOT_VISIBLE`, `NOT_APPLICABLE`, `REVIEW_REQUIRED`).

### H. Which components can be reused directly from U24-D?
- `LegalSnapshotContext` and `LegalSnapshotBuilder`.
- `LegalSnapshotValidator`.
- `ApplicabilityService` (pure in-memory rule engine).
- `DeterministicVerifier` and `EvidenceMatcher`.
- `EvidenceNormalizationService`.
- `compute_overall_status()`.
- `generate_evidence_annotations()`.

### I. Which data must be persisted to make revalidation possible?
Synced operation records in `inspection_sync_operations`, active server legal corpus snapshot, and the inspection session record.

### J. What happens when the offline legal snapshot is stale?
The server detects `LegalSnapshotValidationStatus.STALE`. It validates that evidence is structurally intact, but executes revalidation against the **current approved server snapshot**, noting the snapshot migration in diagnostic comparison metadata.

### K. What happens when the legal snapshot ID is unknown?
The server detects `LegalSnapshotValidationStatus.UNKNOWN`. It gives zero weight to offline compliance conclusions and performs full statutory re-evaluation against the active server snapshot.

### L. What happens when the offline result differs from the server result?
The **server result is authoritative**. The discrepancy is captured in a structured `RevalidationComparison` object (detailing status changes, requirement diffs, and reasons) and stored in evaluation metadata without overriding the server's verdict.

### M. What happens when evidence differs?
Revalidation evaluates strictly against the server's persisted evidence. Missing evidence for applicable requirements yields `NOT_VISIBLE` $\to$ `REVIEW_REQUIRED`.

### N. What happens when applicability differs?
Server-side applicability evaluation governs. If a rule is determined to be applicable under server law, it must be verified; if inapplicable, it receives `NOT_APPLICABLE`.

### O. What happens when requirement coverage differs?
The server derives the complete statutory set. Any requirement omitted by the mobile client is evaluated (preventing manufactured PASS results); any extra client requirement not recognized by the legal corpus is rejected.

### P. What happens when the inspection has changed since offline evaluation?
The server revalidates against the current persisted state of the inspection.

### Q. Can revalidation be performed without Gemini?
**Yes.** The server revalidation engine is 100% deterministic, in-memory, and rule-based. It does not invoke Gemini, LLMs, or external cloud networks.

### R. If Gemini is required for the final online interpretation, what exact boundary remains?
If online interpretation is invoked, Gemini is strictly constrained by Phase 6: it only interprets ambiguous OCR text within pre-defined candidate bounds. It cannot alter legal requirements, determine statutory applicability, or override deterministic status aggregation.

---

## 3. Trust Boundary Model

```
┌────────────────────────────────────────────────────────┐
│               UNTRUSTED OFFLINE DATA                   │
│  - overall_status                                      │
│  - per-requirement compliance status                   │
│  - target_requirements list                            │
│  - applicability decisions                             │
│  - legal interpretations / conclusions                 │
└──────────────────────────┬─────────────────────────────┘
                           │ Validation & Recomputation
                           ▼
┌────────────────────────────────────────────────────────┐
│             TRUSTED EVIDENCE & INPUTS                  │
│  - Image artifacts & hashes                            │
│  - OCR observations & bounding boxes                   │
│  - Extracted evidence candidates                       │
│  - Declared inspection facts                           │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│             AUTHORITATIVE SERVER PIPELINE              │
│  1. Server Active Legal Snapshot Context               │
│  2. ApplicabilityService.evaluate_run()                │
│  3. Complete Statutory Requirements Derivation         │
│  4. DeterministicVerifier.verify()                     │
│  5. compute_overall_status()                           │
│  6. Diagnostic RevalidationComparison                  │
│  7. EvaluationMode = SERVER_REVALIDATED                │
└────────────────────────────────────────────────────────┘
```

---

## 4. Implementation Specification

1. **`ServerRevalidationService`**:
   - `revalidate(inspection_id: str, authenticated_user_id: str, server_snapshot_context: LegalSnapshotContext | None = None, force: bool = False) -> ServerRevalidationResult`
   - Retrieves synced operations from `SyncOperationRepository`.
   - Reconstructs bundle & evidence candidates.
   - Validates client snapshot vs active server snapshot.
   - Derives complete authoritative requirements and recomputes applicability deterministically.
   - Computes canonical verification results and overall inspection status.
   - Computes structured `RevalidationComparison` (comparing offline vs server results).
   - Generates `EvaluationMetadata(evaluation_mode=EvaluationMode.SERVER_REVALIDATED, revalidation_required=False)`.
   - Persists updated session & report in `InMemoryInspectionStore` / repositories.
2. **API Endpoint**:
   - `POST /api/v1/inspections/{inspection_id}/revalidate`
   - Authenticated via JWT, ownership enforced.
   - Idempotent and safe for concurrent invocations.
