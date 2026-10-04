# Veriqoo Phase U24-D — Offline Execution Audit

## 1. Executive Summary
This audit analyzes the existing Veriqoo backend architecture to determine the exact boundaries, contracts, and services required to execute deterministic offline compliance evaluations. 

The core legal compliance engine in Veriqoo was architected with a strict separation between legal authority (statutory corpus & applicability rules), evidence ingestion (OCR & normalization), interpretation (deterministic verification & optional Gemini interpretation), and reporting. 

Because the core applicability and deterministic verification logic is already implemented as pure in-memory algorithms without hidden database or network side-effects, an offline execution engine can reuse 100% of the canonical compliance semantics without duplicating or diverging from the online engine.

---

## 2. Component-by-Component Offline Capability Analysis

| Component | Offline-Capable? | Reason / Cloud Dependencies | Reusable As-Is? | Required Adaptation | Ownership |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Image Ingestion & Storage** (`ImageArtifact`, Supabase Storage) | **PARTIAL** | Online uses Supabase Storage URLs. Offline operates on local byte arrays / file paths and SHA-256 hashes. | **YES (Contract)** | Use SHA-256 image hashes and local client identifiers instead of remote storage URLs. | Backend contract, T2 local capture |
| **OCR Extraction** (`OCRExtractor`, PaddleOCR) | **PARTIAL** | Backend OCR runs PaddleOCR locally/server-side. Mobile runs on-device OCR (ML Kit / Flutter T2). | **NO (Engine) / YES (Model)** | Backend defines `OCRObservation` and `OCRResult` schemas; T2 provides local observations on mobile. | T2 local OCR, Backend ingestion contract |
| **Evidence Normalization** (`EvidenceNormalizationService`, `parsers.py`) | **YES** | 100% pure regex, date parsing, unit normalization, and geometry preservation in memory. | **YES** | Reusable directly in Python offline bundle / test harness and mirrored in portable contract for T2. | Backend engine & contract |
| **Inspection Facts Collection** (`InspectionFact`) | **YES** | Pure dataclass representing declared attributes (commodity category, package type, weight, date). | **YES** | Pass directly as structured facts dictionary / list. | Backend & T2 |
| **Applicability Engine** (`ApplicabilityService`, `evaluator.py`, `gating.py`) | **YES** | `ApplicabilityService.evaluate_run()` is a pure in-memory function operating over facts and rule structures. | **YES** | Feed approved rule structures directly from the verified local `LegalSnapshotContext`. | Backend engine & contract |
| **Legal Corpus & RAG** (`LegalRetrievalService`, pgvector) | **NO (Online RAG) / YES (Snapshot)** | Online RAG performs remote vector embedding search against Supabase pgvector. Offline uses deterministic `LegalSnapshot`. | **PARTIAL** | In offline mode, requirements and rules are supplied directly by the active, verified `LegalSnapshot` (no vector embeddings required). | Backend contract |
| **Evidence Verification** (`DeterministicVerifier`, `EvidenceMatcher`) | **YES** | Pure in-memory matching of required declarations against evidence candidates, detecting contradictions and missing fields. | **YES** | Reused directly as the core evaluation engine. Returns canonical `PASS`, `FAIL`, `NOT_VISIBLE`, `NOT_APPLICABLE`, `REVIEW_REQUIRED`. | Backend engine & contract |
| **Gemini Reasoning** (`GeminiEvidenceService`) | **NO** | Requires remote HTTPS calls to Google Gemini API. | **NO (Excluded)** | **NEVER invoked offline.** Ambiguous, unparsed, or contradictory evidence defaults deterministically to `REVIEW_REQUIRED` with `revalidation_required=True`. | Backend gating |
| **Status Aggregation & Reporting** (`compute_overall_status`, `InspectionReport`) | **YES** | Pure mathematical/logical reduction over `VerificationResult` list to derive overall status. | **YES** | Reused directly to produce offline evaluation reports. | Backend engine |
| **U24-A Offline Contracts** (`EvaluationMode`, `LegalSnapshotBuilder`, `EvaluationMetadata`) | **YES** | Pure dataclasses and deterministic SHA-256 canonical hashing. | **YES** | Forms the foundation for the `OfflineInspectionBundle` and `OfflineEvaluationResult`. | Backend contract |
| **U24-B/C Sync Foundation & API** (`SyncOperation`, `SyncIngestionService`) | **YES** | Durable sync operations and batch sync endpoints. | **YES** | Ingests offline evaluation bundles and sync operations when connectivity is restored. | Backend API |

---

## 3. Key Findings

### A. Zero Compliance Duplication
The existing `DeterministicVerifier`, `EvidenceMatcher`, `ApplicabilityService`, and `compute_overall_status` functions are completely pure (deterministic, zero side-effects, zero network calls, zero database queries). The backend offline executor (`OfflineInspectionExecutor`) can directly compose these existing components without creating a parallel rule engine.

### B. Gemini Exclusion & Uncertainty Preservation
When evaluating offline:
- If a declaration candidate is clearly valid and matches the requirement: status is `PASS`.
- If a required declaration is missing from all evidence candidates: status is `NOT_VISIBLE`.
- If a requirement is not applicable based on facts: status is `NOT_APPLICABLE`.
- If a candidate is ambiguous, unparsed, or conflicting: status is `REVIEW_REQUIRED` (and `revalidation_required` is flagged `True`).
- **Under no circumstances is Gemini emulated or called over the network.**

### C. Approved Legal Snapshot Binding
- Offline evaluation requires an approved `LegalSnapshotContext` whose `legal_snapshot_id` matches the SHA-256 hash computed by `LegalSnapshotBuilder`.
- If the snapshot is missing, corrupted, or tampered, the evaluation fails safely with explicit validation errors and flags `revalidation_required=True`.

### D. Portable Offline Bundle Contract
To allow T2 (Flutter) to serialize inspection state on the mobile device and enable the backend to execute deterministic offline evaluation, a dedicated, strongly typed `OfflineInspectionBundle` is needed.
The bundle must encapsulate:
- `bundle_id` and `inspection_id`
- `schema_version`
- `legal_snapshot_id`
- `inspection_facts`
- `image_artifacts` (metadata and content hashes)
- `ocr_results` / `ocr_observations`
- `evidence_candidates`
- `target_requirements`
- `evaluation_metadata`
- `content_hash` (deterministic SHA-256 over canonical bundle payload)

---

## 4. Architectural Boundaries

```
+-------------------------------------------------------------------------+
| MOBILE (T2 Owned - Flutter)                                             |
| 1. Capture Images -> Local SQLite / Filesystem                          |
| 2. Local OCR -> OCRObservation list                                     |
| 3. Assemble OfflineInspectionBundle (with active LegalSnapshotId)       |
| 4. (Optional) Run local Dart deterministic verifier matching contract   |
| 5. Queue SyncOperations in local outbox                                 |
+-------------------------------------------------------------------------+
                                    |
                                    v (Network Restore)
+-------------------------------------------------------------------------+
| BACKEND (Phase U24-D Offline Execution Service & U24-C Sync API)        |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  | OfflineInspectionExecutor                                         |  |
|  | - Verifies LegalSnapshotContext SHA-256                          |  |
|  | - Reuses ApplicabilityService (Pure in-memory)                   |  |
|  | - Reuses DeterministicVerifier (Pure in-memory)                  |  |
|  | - Sets EvaluationMode = OFFLINE_DETERMINISTIC                     |  |
|  | - Sets revalidation_required = True if review required           |  |
|  | - Aggregates canonical statuses (PASS/FAIL/NOT_VIS/NA/REVIEW)    |  |
|  +-------------------------------------------------------------------+  |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  | U24-C Sync Ingestion Service & Endpoints                          |  |
|  | - Ingests batch operations idempotently                          |  |
|  | - Verifies JWT ownership & inspection state                      |  |
|  +-------------------------------------------------------------------+  |
+-------------------------------------------------------------------------+
                                    |
                                    v (Future Phase U24-F)
+-------------------------------------------------------------------------+
| SERVER REVALIDATION WORKER (Gemini & Legal Corpus Revalidation)         |
+-------------------------------------------------------------------------+
```
