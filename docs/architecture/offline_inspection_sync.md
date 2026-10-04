# Offline Inspection & Sync Architecture (Phase U24-A)

## 1. Overview & Objective

Phase **U24-A** establishes the backend contract models and deterministic legal snapshot architecture for Veriqoo's offline inspection and device-to-server synchronization capabilities.

This contract ensures that:
- Offline inspections can be conducted locally on mobile devices using deterministic rules.
- Offline and online evaluation modes are explicitly identified via typed provenance metadata.
- Legal authority is represented as a deterministic cryptographic hash (`legal_snapshot_id`) derived from approved legal data (excluding drafts and unapproved rules).
- Synchronisation operations, receipts, conflicts, and manifests are strongly typed and idempotent.
- **Security boundary:** Client-supplied owner/user identities are strictly rejected from payload trust; the server establishes identity and authority exclusively through verified JWTs.

---

## 2. Core Architectural Invariants

### 2.1 Orthogonal Lifecycles

The inspection lifecycle and synchronization lifecycle are strictly separated:

1. **Inspection Processing Lifecycle (`InspectionStatus`)**:
   - `COLLECTING`
   - `READY`
   - `RUNNING`
   - `COMPLETED`
   - `FAILED`
   *(No offline states are introduced to `InspectionStatus`)*

2. **Synchronization Lifecycle (`SyncStatus`)**:
   - `DRAFT_LOCAL`: Created and stored locally on the device.
   - `SYNC_PENDING`: Enqueued in local outbox, ready for network transfer.
   - `SYNCING`: Upload/reconciliation in progress.
   - `SYNCED`: Authoritatively acknowledged and ingested by server.
   - `SYNC_FAILED`: Transmission or processing failed (retryable or rejected).
   - `REVALIDATION_REQUIRED`: Ingested, but requires server revalidation due to stale legal snapshot or probabilistic components.
   - `REVALIDATED`: Server revalidation has executed and confirmed/updated compliance report.

---

### 2.2 Canonical Compliance Statuses

Canonical legal metrology compliance statuses are strictly preserved:
- `PASS`
- `FAIL`
- `NOT_VISIBLE`
- `NOT_APPLICABLE`
- `REVIEW_REQUIRED`

**No pseudo-statuses** (e.g. `OFFLINE_PASS`, `PROVISIONAL_PASS`, `OFFLINE_FAIL`) exist. Instead, offline evaluation status is recorded in `EvaluationMetadata`.

---

## 3. Evaluation Metadata Contract

Every evaluation result records its execution mode and legal lineage:

```python
class EvaluationMode(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE_DETERMINISTIC = "OFFLINE_DETERMINISTIC"
    SERVER_REVALIDATED = "SERVER_REVALIDATED"
```

### Model Structure (`EvaluationMetadata`):
- `evaluation_mode`: `ONLINE`, `OFFLINE_DETERMINISTIC`, or `SERVER_REVALIDATED`.
- `revalidation_required`: Boolean flag indicating whether server-side revalidation is required.
- `evaluated_at`: Timezone-aware UTC ISO-8601 timestamp.
- `engine_version`: Semantic version of the evaluation engine.
- `model_version`: Optional AI model identifier (omitted for offline deterministic runs).
- `prompt_version`: Optional prompt version identifier (omitted for offline deterministic runs).
- `legal_snapshot_id`: SHA-256 identity of the legal ruleset used during evaluation.

---

## 4. Deterministic Legal Snapshot Identity

### 4.1 Derivation Principles
The `legal_snapshot_id` is **NOT** a manual timestamp string or semantic version. It is a deterministic **SHA-256 digest** computed from all approved legal data:
- Legal Documents
- Provisions
- Requirements
- Schedules & Schedule Entries
- Tables
- Amendments
- Approved Applicability Rule Versions (status `APPROVED` or `ACTIVE`)
- Condition Groups & Conditions associated with approved rules

### 4.2 Filtering & Canonicalization
- **Exclusion of Non-Approved Data**: Any applicability rule version with status `DRAFT`, `REJECTED`, `IN_REVIEW`, or `RETIRED` is excluded from the snapshot computation.
- **Canonical Serialization**:
  - Keys sorted alphabetically (`sort_keys=True`).
  - Strict JSON formatting with compact separators `(',', ':')`.
  - UTF-8 encoding (`ensure_ascii=False`).
  - Entities sorted deterministically by primary keys before serialization.
  - Ephemeral timestamps (e.g. `generated_at`, runtime memory pointers) are excluded from the hashed payload.

---

## 5. Offline Inspection Metadata & Trust Boundaries

### 5.1 Payload Metadata (`OfflineInspectionMetadata`)
- `inspection_id`: Unique inspection identifier.
- `client_created_at`: Client creation timestamp.
- `device_id`: Client hardware/app installation identifier.
- `legal_snapshot_id`: Legal snapshot active on client during capture.
- `evaluation_mode`: Mode under which local evaluation took place.
- `revalidation_required`: Boolean flag.
- `client_engine_version`: Client runtime engine version.
- `metadata_schema_version`: Schema version.

### 5.2 Server vs Client Trust Boundary

| Field / Concept | Client Authority | Server Responsibility |
| :--- | :--- | :--- |
| `inspection_id` | May propose/provide | Verifies format & uniqueness |
| `device_id` | May provide | Ingests as telemetry |
| `image_hash` / `content_hash` | May provide | Re-verifies SHA-256 against actual bytes |
| `legal_snapshot_id` | Declares active version | Compares against active server snapshot (`MATCHED` / `STALE` / `UNKNOWN`) |
| `user_id` / `owner_id` | **NEVER TRUSTED** | Derived strictly from validated Supabase JWT |
| `role` / `permissions` | **NEVER TRUSTED** | Derived strictly from database/JWT authorization context |
| `final compliance report` | May propose offline result | Validates and issues authoritative report |

---

## 6. Sync Operations, Acknowledgements, Conflicts & Manifests

### 6.1 `SyncOperation`
Represents an atomic, ordered change pending synchronization:
- `operation_id`: UUID of the operation.
- `inspection_id`: Target inspection.
- `entity_type`: `INSPECTION`, `IMAGE`, `OCR_OBSERVATION`, `EVIDENCE`, `FACT`, `APPLICABILITY`, `REQUIREMENT_RESULT`, `REPORT`.
- `entity_id`: ID of the target entity.
- `operation_type`: `CREATE` or `UPSERT`.
- `content_hash`: SHA-256 of the payload.
- `sequence`: Integer sequence for causal ordering.
- `dependency_ids`: List of operations that must be acknowledged before this operation.

### 6.2 `SyncAcknowledgement`
Server receipt returned to client:
- `operation_id`
- `entity_id`
- `status`: `ACKNOWLEDGED`, `ALREADY_APPLIED`, `REJECTED`, `RETRYABLE_FAILURE`
- `server_timestamp`
- `error_code` / `error_message`

### 6.3 `SyncConflict`
Classification of synchronization discrepancies:
- `SAFE_TO_REPLAY`: Idempotent re-submission safe to accept.
- `MUST_REJECT`: Invalid mutation or security violation.
- `MUST_REVALIDATE`: Entity accepted but requires server revalidation.
- `HUMAN_REVIEW_REQUIRED`: Unresolvable conflict requiring officer inspection.

### 6.4 `SyncManifest`
Answers *“What is the synchronization and evaluation state of this inspection?”*:
- `inspection_id`
- `lifecycle_status`: `InspectionStatus` (`COLLECTING`, `READY`, `RUNNING`, `COMPLETED`, `FAILED`)
- `sync_status`: `SyncStatus`
- `entity_acknowledgements`: List of acknowledgements.
- `image_hashes`: Mapping of image IDs to SHA-256 hashes.
- `legal_snapshot_id`: Snapshot ID attached to the sync record.
- `evaluation_metadata`: Evaluation provenance metadata.
- `last_synced_at`: Server timestamp of last synchronization event.

---

## 7. Legal Snapshot Validation Contract

Validation of client snapshot against server repository yields:
- `MATCHED`: Client snapshot exactly matches current server authoritative snapshot.
- `STALE`: Client snapshot was valid in the past but newer approved legal rules exist on server. Evidence accepted, but compliance requires server revalidation.
- `UNKNOWN`: Client snapshot is unrecognized. Evidence accepted, but full revalidation is required.

---

## 8. Durable Sync Ingestion & Idempotency Foundation (Phase U24-B)

### 8.1 Durable Operation State Model
The server tracks each sync operation individually via `OperationStatus`:
- `PENDING`: Enqueued / received, awaiting processing.
- `PROCESSING`: Currently executing within transaction.
- `ACKNOWLEDGED`: Ingested and applied to server state.
- `ALREADY_APPLIED`: Idempotently recognized replay of an identical prior operation.
- `RETRYABLE_FAILURE`: Operation blocked on pending dependencies or transient state.
- `REJECTED`: Permanently invalid mutation (integrity hash mismatch, unauthorized access, cyclic dependency, invalid schema).

> **Architectural Distinction:**
> - `InspectionStatus` (`COLLECTING`, `READY`, `RUNNING`, `COMPLETED`, `FAILED`): Domain lifecycle of the inspection.
> - `SyncStatus` (`DRAFT_LOCAL`, `SYNC_PENDING`, `SYNCING`, `SYNCED`, `SYNC_FAILED`, `REVALIDATION_REQUIRED`, `REVALIDATED`): Aggregate synchronization state.
> - `OperationStatus` (`PENDING`, `PROCESSING`, `ACKNOWLEDGED`, `ALREADY_APPLIED`, `RETRYABLE_FAILURE`, `REJECTED`): Processing state of an individual atomic mutation.

---

### 8.2 Database Schema & Persistence
Durable synchronization state is persisted in `public.inspection_sync_operations`:
- `operation_id`: Unique identifier with database uniqueness constraint `UNIQUE (operation_id)`.
- `inspection_id`: Target inspection container.
- `entity_type`: `SyncEntityType`.
- `entity_id`: Target entity identifier.
- `operation_type`: `CREATE` or `UPSERT`.
- `content_hash`: Cryptographic SHA-256 digest of the canonical JSON payload.
- `dependency_ids`: JSONB array of prerequisite operation IDs.
- `status`: `OperationStatus`.
- `attempt_count`: Ingestion retry counter.
- `payload`: JSONB payload.
- `created_at`, `received_at`, `acknowledged_at`: Timezone-aware audit timestamps.
- **Row Level Security (RLS)**: Enforced with backend service-role execution policy.

---

### 8.3 Idempotency & Replay Strategy
1. **First Submission**: Operation validated, applied, and marked `ACKNOWLEDGED`.
2. **Identical Replay** (same `operation_id` + identical `content_hash`): Returns `ALREADY_APPLIED` without re-executing mutations.
3. **Conflicting Replay** (same `operation_id` + different `content_hash`): Detected immediately as a hash collision/conflict, permanently `REJECTED` with error code `SYNC_DUPLICATE_PAYLOAD_MISMATCH`.

---

### 8.4 Content Integrity Verification
Before applying any mutation, the server serializes `payload` canonically (`sort_keys=True`, `separators=(',', ':')`, UTF-8) and computes `hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()`.
- If `computed_hash != operation.content_hash`, the operation is rejected with `SYNC_CONTENT_HASH_MISMATCH`.

---

### 8.5 Dependency Management & Cycle Detection
- **Dependency State Check**:
  - All `dependency_ids` must be present and in `ACKNOWLEDGED` or `ALREADY_APPLIED` state.
  - If any dependency is pending or missing: returned as `RETRYABLE_FAILURE` (`SYNC_DEPENDENCY_PENDING`).
  - If any dependency was rejected: returned as `REJECTED` (`SYNC_DEPENDENCY_REJECTED`).
- **Circular Dependency Detection**:
  - Multi-operation batches are scanned via topological depth-first search for cycles.
  - Any operation in a cycle is immediately rejected with `SYNC_CIRCULAR_DEPENDENCY`.

---

### 8.6 Server-Side Ownership & Authorization
- Client-asserted `owner_id`, `user_id`, or `role` fields in payloads are strictly ignored.
- The server identifies the owner exclusively via validated Supabase JWT claims (`authenticated_user_id`).
- When operating on an existing inspection, ownership is checked:
  - If the inspection owner differs from the authenticated user, the operation is rejected with `SYNC_NOT_OWNER`.

---

### 8.7 Acknowledgement & Manifest Generation
- **`SyncIngestionService`** produces typed `SyncAcknowledgement` objects with stable, machine-readable `SyncErrorCode` values (`SYNC_DUPLICATE`, `SYNC_CONTENT_HASH_MISMATCH`, `SYNC_DEPENDENCY_PENDING`, `SYNC_DEPENDENCY_REJECTED`, `SYNC_CIRCULAR_DEPENDENCY`, `SYNC_INSPECTION_NOT_FOUND`, `SYNC_NOT_OWNER`, `SYNC_INVALID_ENTITY`, `SYNC_INVALID_STATE`).
- **`SyncManifest`** provides a complete reconciliation manifest for any inspection without leaking raw JWTs, secret keys, or private storage bucket URLs.

---

## 9. Sync API Endpoints & Transport Layer (Phase U24-C)

### 9.1 Endpoint Summary

| Method | Path | Summary | Auth | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/inspections/sync/batch` | Idempotently ingests a batch of offline operations | Bearer JWT | `200`, `400`, `401`, `404`, `413` |
| `GET` | `/api/v1/inspections/{inspection_id}/sync-status` | Retrieves authoritative `SyncManifest` for inspection | Bearer JWT | `200`, `401`, `404` |

---

### 9.2 Batch Ingestion Semantics (`POST /sync/batch`)
- **Request Envelope (`SyncBatchRequest`)**:
  - `inspection_id`: Target inspection session identifier.
  - `batch_id`: Optional client batch UUID.
  - `client_metadata`: Telemetry and device identifiers.
  - `operations`: Array of 1 to 100 `SyncOperationRequest` items.
- **Batch Limits**:
  - Maximum operations per batch: `100`. Exceeding returns `413 (SYNC_BATCH_TOO_LARGE)`.
  - Empty batch returns `400 (INVALID_REQUEST)`.
  - Maximum dependencies per operation: `50`.
- **Partial Batch Processing**:
  - Operations are topologically ordered and evaluated individually.
  - Successful independent operations are marked `ACKNOWLEDGED`.
  - Unmet dependencies yield `RETRYABLE_FAILURE`.
  - Malformed or conflicting operations are marked `REJECTED`.
  - The HTTP response is `200 OK` containing per-operation `results` array with individual receipts.

---

### 9.3 Manifest Retrieval Semantics (`GET /{inspection_id}/sync-status`)
- Returns the complete `SyncManifestResponse`:
  - `inspection_id`, `lifecycle_status`, `sync_status`
  - `entity_acknowledgements`: List of all acknowledged receipts
  - `image_hashes`: Mapping of synchronized images
  - `legal_snapshot_id`: Active/declared snapshot identity
  - `evaluation_metadata`: Evaluation mode and revalidation indicators
  - `last_synced_at`: Latest server synchronization timestamp
- **Cross-User Protection**: Nonexistent inspections and cross-user requests return a uniform `404 INSPECTION_NOT_FOUND` to prevent ID enumeration.

---

## 10. Implementation Status & Phase Isolation

- **Phase U24-A**: Contracts, models, canonical snapshot builder, validator, and tests (**LOCKED**).
- **Phase U24-B**: Durable sync operation persistence, idempotency, dependency engine, ingestion service, and unit tests (**LOCKED**).
- **Phase U24-C**: FastAPI sync endpoints, schemas, authentication boundary, batching limits, and API unit tests (**LOCKED**).
- **Future Phases**:
  - `U24-D`: Server Revalidation worker & pipeline.
  - `U24-E`: End-to-end sync integration tests.
  - `T2 Frontend`: Flutter offline database (Isar/SQLite), local outbox, and background sync queue.


