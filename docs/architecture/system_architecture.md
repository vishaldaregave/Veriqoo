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
