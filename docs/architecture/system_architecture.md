# Veriqoo System Architecture

Veriqoo is an automated regulatory compliance inspection platform for packaged commodities under the Indian **Legal Metrology Act, 2009** and the **Legal Metrology (Packaged Commodities) Rules, 2011** (with all amendments).

---

## 1. High-Level Architecture Overview

Veriqoo adopts a decoupled, microservice-ready modular architecture:

```
┌────────────────────────────────────────────────────────────────────────┐
│                             CLIENT LAYER                               │
│  ┌──────────────────────────────┐     ┌─────────────────────────────┐  │
│  │   Flutter Cross-Platform     │     │     Telegram Bot Client     │  │
│  │   (Mobile, Web, Desktop)     │     │  (Album Ingestion, Reports) │  │
│  └──────────────┬───────────────┘     └──────────────┬──────────────┘  │
└─────────────────┼────────────────────────────────────┼─────────────────┘
                  │ HTTPS (Bearer JWT)                 │ HTTP / Webhook
                  ▼                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND SERVICE                         │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ API & Auth Router (/api/v1)                                      │  │
│  │ • Cryptographic JWT Verification (Supabase Auth)                 │  │
│  │ • Strict IDOR Isolation & Ownership Validation                   │  │
│  └──────────────────────────────┬───────────────────────────────────┘  │
│                                 ▼                                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Inspection Orchestration Pipeline                                │  │
│  │                                                                  │  │
│  │  1. Evidence Ingestion: SHA-256 Hashing, EXIF/Format Validation  │  │
│  │  2. Local OCR Engine: PaddleOCR (PP-OCRv6 + UVDoc Unwarping)     │  │
│  │  3. Applicability Gating: Rule applicability evaluation          │  │
│  │  4. Legal RAG Retrieval: pgvector + Rule Graph Expansion         │  │
│  │  5. Gemini Multimodal Reasoning: Constrained evidence analysis   │  │
│  │  6. Verification Engine: Deterministic compliance evaluation     │  │
│  │  7. Synthesis & Reporting: Structured PASS/FAIL audit report     │  │
│  └──────────────┬───────────────────────────────────┬───────────────┘  │
└─────────────────┼───────────────────────────────────┼──────────────────┘
                  ▼                                   ▼
┌───────────────────────────────────┐ ┌──────────────────────────────────┐
│         SUPABASE CLOUD            │ │       GOOGLE GEMINI AI           │
│ • PostgreSQL 17 + pgvector        │ │ • text-embedding-004 (768-dim)   │
│ • Row Level Security (RLS)        │ │ • gemini-2.5-flash Reasoning     │
│ • Durable Image Storage Buckets   │ │ • Structured JSON Schema Outputs │
│ • Account Link Token Store        │ └──────────────────────────────────┘
└───────────────────────────────────┘
```

---

## 2. Core Subsystems

### 2.1 Evidence Ingestion & Normalization (`backend/app/services/evidence/`)
- Multi-image package capture: supports front, back, bottom, and side panels.
- Content hashing: calculates SHA-256 checksums per image to prevent redundant reprocessing.
- Image integrity validation: rejects corrupt files, validates MIME types (`image/jpeg`, `image/png`, `image/webp`), and enforces dimensional and size constraints.
- EXIF orientation correction: standardizes input orientation for downstream computer vision models.

### 2.2 OCR & Document Intelligence (`backend/app/services/ocr/`)
- Powered by PaddleOCR (PP-OCRv6 detection and recognition) paired with UVDoc textline unwarping.
- Document orientation correction (PP-LCNet doc orientation).
- Structured output: bounding boxes, character-level confidence scores, and paragraph text reconstruction.
- Fallback resilience: deterministic fallbacks when local neural models are warming up or under resource constraints.

### 2.3 Legal Corpus & Knowledge Graph (`backend/app/services/legal_rag/`)
- Complete parsing of the Legal Metrology (Packaged Commodities) Rules, 2011.
- Hierarchical structure: Document $\to$ Provision $\to$ Rule $\to$ Sub-Rule $\to$ Clause $\to$ Schedule $\to$ Amendment.
- Temporal resolution: tracks amendments by `effective_from` and `effective_to` dates, distinguishing CURRENT, SUPERSEDED, and FUTURE provisions.
- Relationship graph: bidirectional expansion connecting provisions with First through Tenth Schedules and Gazette notifications.

### 2.4 Applicability Gating Engine (`backend/app/services/applicability/`)
- Deterministic rules engine that filters out non-applicable requirements before LLM reasoning.
- Attributes evaluated:
  - Commodity type (food, cosmetic, industrial, general)
  - Net content quantity and unit (weight, volume, count, length)
  - Packaging nature (pre-packaged, retail, wholesale)
  - Distribution channel (e-commerce, physical retail)
  - Import vs. domestic manufacturing
- Built-in rule authoring linter to enforce syntactic validity and prevent orphaned rules.

### 2.5 Hybrid Retrieval-Augmented Generation (Legal RAG)
- Vector Search: Google `text-embedding-004` (768-dimension embeddings) stored in PostgreSQL with pgvector cosine similarity indexing.
- Direct Rule Lookup: exact key-based indexing (`Rule 6(1)(a)`, `Rule 6(1)(d)`, `First Schedule`).
- Graph Expansion: pulls associated tables, penalty provisions, and historical amendments for each candidate rule.
- Deduplication: merges exact-match and semantic candidate sets, ranking by relevance and temporal priority.

### 2.6 Constrained Gemini Evidence Reasoning (`backend/app/services/gemini/`)
- Gemini 2.5 Flash constrained by strict Pydantic JSON schemas.
- Hallucination prevention: the model is explicitly forbidden from making up declarations not present in OCR text or image observations.
- Contradiction resolution: identifies and flags discrepancies across multiple package panels.
- Structured classification: returns status (`PASS`, `FAIL`, `NOT_VISIBLE`, `REVIEW_REQUIRED`) along with verbatim evidence quotes and bounding coordinates.

### 2.7 Inspection Orchestrator & Lifecycle (`backend/app/services/inspection_pipeline/`)
- State Machine: `CREATED` $\to$ `UPLOADING` $\to$ `PROCESSING` $\to$ `COMPLETED` / `FAILED`.
- Asynchronous task processing via FastAPI background execution.
- Persistence: atomic transactions into Supabase PostgreSQL tables (`inspections`, `inspection_items`, `verification_results`).
- Durable storage: images archived in Supabase Storage (`inspection-images` bucket) with hashed hierarchical paths.

### 2.8 Security, Authentication & IDOR Isolation (`backend/app/auth/`)
- Supabase Auth JWT validation: cryptographically verifies signatures (HS256/RS256/ES256), expiration (`exp`), and audience (`aud`).
- User Isolation: all inspection queries are scoped strictly to `user_id == caller.user_id`.
- Secret masking: error handling layers scrub bearer tokens, database passwords, and API keys before responses leave the backend.

### 2.9 Telegram Bot Integration (`backend/app/telegram/` & `telegram_bot/`)
- Ingestion of package photo albums via Telegram Media Group handlers.
- Conversational state management with commands: `/start`, `/new`, `/run`, `/status`, `/report`, `/link`.
- Secure Telegram Account Linking: generates one-time cryptographically secure verification codes valid for 10 minutes to link Telegram chat IDs with Supabase Auth user profiles.

### 2.10 Authority Access Control & Jurisdiction Architecture (`backend/app/services/authority/`)
- **AuthorityPrincipal Contract:** Verified identity injected via `require_authority_user` containing authenticated `user_id`, authoritative `app_role` (`authority` or `admin`), assigned `department`, `designation`, badge number, and explicit `JurisdictionScope`.
- **Role Authorization vs. Jurisdiction Authorization:**
  - *Role Authorization:* Verifies caller's `app_role` in `user_profiles` is `authority` or `admin` (rejects consumers and inspectors with HTTP 403 `FORBIDDEN`).
  - *Jurisdiction Authorization:* Evaluated via `AuthorityAccessPolicy.can_access_case()`. Enforces strict default-deny matching of department, state, and explicitly authorized district codes.
  - *Admin Scope Constraint:* An `admin` role does **not** grant automatic or unrestricted case access; admins must possess an explicitly provisioned authority profile and jurisdiction scope.
- **Provisioning & Elevation Protection:** Authority accounts cannot self-provision or self-elevate. Ordinary consumer profile update paths (`PATCH /api/v1/users/me`) strictly ignore role modifications. Authority profiles can only be provisioned or modified through trusted administrative operations.
- **Authority Persistence Contract (`public.authority_profiles`):**
  - Database schema: `id` (UUID PK), `user_id` (UUID UNIQUE NOT NULL), `department` (text check constraint), `designation` (text), `badge_number` (text nullable), `state_code` (text), `jurisdiction_level` (DISTRICT or STATE), `authorized_district_codes` (`text[]` non-empty array of Local Government Directory codes), `is_active` (boolean default true), and `created_at`/`updated_at` timestamptz.
  - Handled by `SupabaseAuthorityRepository`, which validates rows on retrieval and fails closed with HTTP 403 / ValueError if stored jurisdiction data is malformed or corrupted.
- **Complaint Jurisdiction & Verification (`public.consumer_issues`):**
  - Extended schema: `department`, `state_code`, `district_code`, `jurisdiction_verified` (boolean default false), `assigned_officer_id`, `assigned_at`, and `assigned_by`.
  - Unresolved complaints (`jurisdiction_verified = false` or null district/state codes) fail closed under RLS and `AuthorityAccessPolicy`, preventing arbitrary district officers from viewing unverified complaints.
  - Jurisdiction must originate from verified retail/inspection records, not unverified GPS or user-submitted metadata.
- **Audit Retention Policy (`public.consumer_issue_audit_events`):**
  - Schema: `id`, `issue_id` (UUID nullable, `REFERENCES consumer_issues(id) ON DELETE SET NULL`), `actor_id`, `actor_role`, `event_type`, `previous_state`, `new_state`, `metadata` (JSONB object), `created_at`.
  - Non-cascading retention: When a consumer withdraws or deletes a complaint, foreign-key constraint `ON DELETE SET NULL` decouples the complaint ID while preserving the statutory audit history intact.
- **Confidential Investigation Notes (`public.consumer_issue_notes`):**
  - Schema: `id`, `issue_id` (UUID `REFERENCES consumer_issues(id) ON DELETE CASCADE`), `author_id`, `note_text`, `is_internal` (boolean default true), timestamps.
  - Private notes are restricted to active authority officers whose provisioned jurisdiction scope covers the complaint.
- **Migration Deployment Status:**
  - Migration scripts:
    1. `supabase/migrations/20261009000000_t3_4_authority_workflow.sql`
    2. `supabase/migrations/20261010000000_t3_4_atomic_authority_rpc.sql`
    3. `supabase/migrations/20261010000001_t3_4_phase5_2_hardening.sql`
  - Status: Authored locally, verified via static review, mocked RPC tests, and regression tests. **Not applied to any live database.**

### 2.11 Atomic Authority Workflow & Database RPC Hardening (Phase 5, 5.1 & 5.2)
- **Atomic Operations (`public.authority_assign_case`, `public.authority_transition_status`, `public.authority_create_case_note`):**
  - Database-side PostgreSQL stored procedures execute with `SECURITY DEFINER` and pinned `search_path = public, pg_temp`.
  - Concurrency safety: Applies row-level locking (`SELECT ... FOR UPDATE`) on target complaint records to prevent lost updates and race conditions.
  - Transaction boundary: Case mutation / note insertion and audit event insertion occur within a single database transaction; failure during audit insertion rolls back the mutation.
  - Mandatory Assignment Concurrency: Concurrency is mandatory by default. Callers must provide an explicit representation of expected current state: `expect_unassigned=true` (or `"expected_assigned_officer_id": "UNASSIGNED"`) for unassigned cases, or the expected assigned officer UUID. Missing preconditions return HTTP 422. Stale preconditions return HTTP 409 Conflict (`INVALID_INSPECTION_STATE`).
  - Mandatory Status Concurrency: `authority_transition_status` enforces mandatory non-empty `expected_status` (`CONCURRENCY_TOKEN_REQUIRED`).
- **Least-Privilege Reassignment (Phase 5.2):**
  - Cross-officer assignment is disabled until a formal verified supervisor hierarchy is approved.
  - Officers may only self-assign cases within their provisioned jurisdiction.
  - The restriction is enforced in database RPC (`CROSS_OFFICER_ASSIGNMENT_DENIED`, ERRCODE `42501`) and in the FastAPI service layer (HTTP 403 Forbidden).
  - An administrator role does NOT grant global reassignment access.
- **Atomic Investigation Notes (`public.authority_create_case_note`):**
  - Inserts confidential internal note into `consumer_issue_notes` and writes `NOTE_ADDED` audit event into `consumer_issue_audit_events` in a single transaction.
  - Note length is validated at database level (`length(trim(p_note_text)) BETWEEN 1 AND 5000`).
  - Confidentiality protection: Audit event metadata stores only `note_id`, `author_id`, and `note_length`, without replicating the confidential investigation note text into public audit streams.
- **Security Boundary & Role Grants:**
  - Execution privileges are revoked from `PUBLIC` and `authenticated`; granted **exclusively to `service_role`**.
  - Direct PostgREST RPC invocation by clients or consumers is blocked. All authority workflows are mediated by the authenticated FastAPI backend.
  - Actor spoofing is guarded via `p_actor_id != auth.uid()`.
  - Actor role is verified against `user_profiles.app_role IN ('authority', 'admin')` and `authority_profiles.is_active = true`.
  - Administrators do NOT receive global case access; all actors must strictly match the complaint's department, state, and authorized district codes.
- **Audit Immutability & Privileges:**
  - Audit events are insert-only via database RPC or trusted backend service-role paths.
  - Default-deny RLS prevents ordinary clients from inserting, modifying, or truncating audit logs.

### 2.12 Authority Dashboard Integration (Phase 6)
- **Frontend Architecture (`lib/screens/dashboard/authority_cases_screen.dart`, `lib/services/authority_api_service.dart`):**
  - Dedicated cross-platform Flutter dashboard interface for regulatory authority officers.
  - Consumes `/api/v1/authority/...` REST endpoints with JWT authorization header retrieved from the authenticated Supabase session.
  - Reuses existing Material 3 styling tokens (`#183B32` primary seed, `#F7F7F3` background), navigation layout, and TopBar controls (`/dashboard`, `/authority/cases`, `/products`, `/inspections`).
- **Enforced Security & Authority Scoping:**
  - Zero client-side jurisdiction filtering: displays only records returned by the authorized backend query.
  - Access denial states: Displays clear, safe "Access Denied" screens on HTTP 401 / 403 without leaking case numbers, evidence, or complaint details.
  - Cross-officer assignment blocked: Enforces self-assignment in the UI (`expect_unassigned=true` or current officer ID); cross-officer assignments return HTTP 403.
  - Concurrency conflict handling: On HTTP 409, informs the user with an actionable banner and refreshes the case state without blind auto-retries.
- **Confidentiality & Audit Integrity:**
  - Investigation notes are explicitly labeled `INTERNAL ONLY` and validated (1–5000 characters).
  - Rapid double-click protection disables submit buttons while requests are in flight.
  - Audit timeline renders statutory audit events chronologically without leaking internal note bodies.


