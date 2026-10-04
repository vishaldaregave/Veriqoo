# Veriqoo U24-G Architecture Audit: Authoritative Revalidation Result Persistence, History & Report Lifecycle

## Executive Summary
This document fulfills the Phase 1 audit requirement for **Veriqoo U24-G**. It evaluates how authoritative server revalidation results (from Phase U24-F) transition from transient computation into durable, traceable, idempotent persistence, and how they become visible to existing inspection and report APIs (`GET /api/v1/inspections/{id}` and `GET /api/v1/inspections/{id}/report`) while retaining historical offline evaluations and diagnostic comparisons.

---

## 1. Audit Questions & Definitive Answers

### A. Where is the offline result currently persisted?
- **Durable Sync Store**: In the `inspection_sync_operations` repository/table as durable sync operations with `entity_type = SyncEntityType.REPORT` and `SyncEntityType.REQUIREMENT_RESULT`, carrying `evaluation_mode = OFFLINE_DETERMINISTIC`, `legal_snapshot_id = <client_snapshot_id>`, and the client's offline verdict.
- **In-Memory Session Store**: If the client uploaded an offline report during sync ingestion, `InMemoryInspectionStore` holds an `InspectionSession` whose `session.report` was initially derived from or created for the offline inspection.

### B. Where is the server-revalidated result currently persisted?
- **Durable Sync Store**: In `inspection_sync_operations` under a deterministic authoritative key `reval-rep-{inspection_id}` with `entity_type = SyncEntityType.REPORT`, `operation_type = SyncOperationType.UPSERT`, containing the complete authoritative payload: `server_overall_status`, `server_legal_snapshot_id`, `verification_results`, `applicable_requirements`, `revalidation_comparison`, and `evaluation_metadata` (`evaluation_mode = SERVER_REVALIDATED`, `revalidation_required = False`).
- **Session / Inspection Store**: In `InMemoryInspectionStore` as `session.report` (an instance of `InspectionReport`) and `session.inspection.status = InspectionStatus.COMPLETED`.
- **Relational Persistence (`InspectionRepository`)**: When Supabase or persistent storage is active, in `inspection_reports` and `inspection_requirement_results` via atomic upsert.

### C. Can the current report endpoint distinguish offline vs server-revalidated evaluation?
- **Yes**: `InspectionReport.metadata` contains `evaluation_metadata` containing `evaluation_mode` (`SERVER_REVALIDATED` vs `OFFLINE_DETERMINISTIC`), `revalidation_required`, and `legal_snapshot_id`. In addition, `metadata["revalidation_comparison"]` contains the structured diff between offline and server evaluations.

### D. Can an existing report be safely replaced by a server-revalidated result?
- **Yes**: The authoritative report lifecycle requires that server revalidation supercedes the client's preliminary offline verdict. In `session_store.store_report(inspection_id, report)` or `session.report = server_revalidated_report`, the active report is updated in-place. The historical offline evaluation is preserved intact in `inspection_sync_operations` under its original sync operation ID and within `metadata["revalidation_comparison"]`.

### E. How are requirement results persisted?
- Requirement results are persisted as a list of canonical `VerificationResult` objects within `InspectionReport.verification_results`.
- In `inspection_sync_operations`, they are serialized in the `reval-rep-{inspection_id}` report payload.
- In `InspectionRepository`, they are written to `inspection_requirement_results` (or the in-memory equivalent).

### F. How are applicability decisions persisted?
- Evaluated independently by `ApplicabilityService.evaluate_run()` against the active server legal snapshot.
- Recorded on each `VerificationResult.applicability_decision_id` / `VerificationResult.status`, within `ServerRevalidationResult.applicable_requirements`, and in `RevalidationComparison.applicability_changed`.

### G. Where should `RevalidationComparison` be stored?
- Inside `InspectionReport.metadata["revalidation_comparison"]`.
- Inside `ServerRevalidationResult.comparison`.
- Inside the payload of `reval-rep-{inspection_id}` in `inspection_sync_operations`.
- Returned directly in the `ServerRevalidationResponse` schema.

### H. How can historical offline results be retained?
- The original client `SyncEntityType.REPORT` operation record uploaded during sync is **never deleted or overwritten**. It remains in `inspection_sync_operations` with its original payload, client timestamp, and content hash.
- `RevalidationComparison` captures `offline_overall_status`, `offline_legal_snapshot_id`, `offline_requirement_count`, and exact requirement-level status differences (`requirement_status_diffs`).

### I. How can repeated revalidation remain idempotent?
- `ServerRevalidationService` computes a deterministic SHA-256 `content_hash` over the canonical normalized verification results and metadata (excluding run-transient timestamps and UUIDs).
- Repeated calls execute deterministic revalidation and UPSERT into `reval-rep-{inspection_id}` and `session_store.report`, preventing duplicate records, duplicate session reports, or state degradation.

### J. What happens if revalidation succeeds computationally but persistence fails?
- If persistence to `sync_repo` or `session_store` fails with an unhandled exception, the service does **NOT** swallow the fatal error or falsely return a 200 OK. The error propagates, resulting in an HTTP 500 error, ensuring no phantom success is reported to the client.
- The inspection remains in its pre-revalidation state, ready for safe retry.

### K. What happens if persistence succeeds but the response is lost?
- When the client retries `POST /revalidate`, the idempotent revalidation handler re-executes deterministically, recognizes/upserts the authoritative state in `sync_repo` and `session_store`, and returns the identical authoritative `ServerRevalidationResponse`.

### L. What happens if two revalidation requests execute concurrently?
- In `ServerRevalidationService`, the critical revalidation and persistence block is guarded by `threading.RLock()` across threads.
- In the database layer, `inspection_sync_operations` enforces a `UNIQUE (operation_id)` constraint, and `inspection_reports` enforces a `UNIQUE (inspection_id)` constraint with `ON CONFLICT DO UPDATE` (UPSERT). No duplicate or corrupted state can be produced.

### M. Can current report generation safely consume `SERVER_REVALIDATED` results?
- **Yes**: `GET /api/v1/inspections/{inspection_id}/report` queries `store.get_report(inspection_id)` and returns `report.to_dict()`. Because `report.overall_status` is updated to the server status and `report.metadata` contains the revalidation metadata, the existing endpoint naturally exposes the authoritative result without requiring changes to report consumers.

### N. What fields are actually necessary to persist?
1. `inspection_id`
2. `overall_status` (canonical `PASS`, `FAIL`, `REVIEW_REQUIRED`)
3. `verification_results` (canonical statutory requirement verifications)
4. `applicable_requirements` (list of derived statutory requirement IDs)
5. `server_legal_snapshot_id` (cryptographic snapshot ID)
6. `offline_legal_snapshot_id` (client snapshot ID if available)
7. `evaluation_metadata` (`evaluation_mode = SERVER_REVALIDATED`, `revalidation_required = False`)
8. `revalidation_comparison` (status diffs, missing/extra requirements, snapshot validation status)
9. `evidence_annotations` (bounding boxes and visual anchors)
10. `revalidated_at` (ISO-8601 UTC timestamp)
11. `content_hash` (deterministic SHA-256 content hash)

### O. Can this be done without modifying existing legal/compliance semantics?
- **Yes**: The canonical compliance statuses remain strictly:
  - `PASS`
  - `FAIL`
  - `NOT_VISIBLE`
  - `NOT_APPLICABLE`
  - `REVIEW_REQUIRED`
- No new compliance statuses (e.g. `OFFLINE_PASS`, `SERVER_CONFLICT`) are created. `SERVER_REVALIDATED` is evaluation metadata, not a compliance status.

---

## 2. Trusted Result Model & Architecture

```
+-------------------------------------------------------------+
|                      OFFLINE RESULT                         |
|  (evaluation_mode: OFFLINE_DETERMINISTIC, Snapshot: client) |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                         SYNC API                            |
|       (persisted in inspection_sync_operations as op)       |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                    SERVER REVALIDATION                      |
|  - Independent applicability evaluation                     |
|  - Complete statutory requirement coverage                  |
|  - Deterministic verifier execution                         |
|  - Structured comparison with offline claims                |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                    AUTHORITATIVE RESULT                     |
|  (evaluation_mode: SERVER_REVALIDATED, Snapshot: server)    |
|                                                             |
|  +--> inspection_sync_operations (reval-rep-{id})           |
|  +--> session_store / inspection_reports (InspectionReport) |
|  +--> historical offline sync operation retained            |
|  +--> RevalidationComparison retained in metadata           |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|               EXISTING INSPECTION & REPORT APIS             |
|  - GET /api/v1/inspections/{id} (status: COMPLETED)         |
|  - GET /api/v1/inspections/{id}/report (authoritative)      |
+-------------------------------------------------------------+
```

---

## 3. Conclusion & Implementation Plan
1. Update `ServerRevalidationService` in `backend/app/services/offline_sync/revalidation.py`:
   - Inject `session_store: InMemoryInspectionStore | None = None`.
   - Update `session.report` and `session.inspection.status = InspectionStatus.COMPLETED` with full revalidation metadata and comparison.
   - If session was not initialized in memory, create it with completed status, image artifacts, and authoritative report.
   - Durably write to `sync_repo` and `inspection_repo`.
2. Update `backend/app/api/dependencies.py`:
   - Pass `session_store = Depends(get_session_store)` to `get_server_revalidation_service`.
3. Create exhaustive test suite `tests/test_phase24g_revalidation_persistence.py`.
4. Validate zero regressions across all U24 suites and full project test suite.
