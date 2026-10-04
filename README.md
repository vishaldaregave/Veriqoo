# Veriqoo — Legal Metrology Inspection AI

> **Automated packaged-commodity compliance inspection platform powered by multi-image OCR, legal RAG, and multimodal AI.**

[![Python Tests](https://img.shields.io/badge/Python_Tests-670%2F670_Passing-brightgreen.svg)](tests/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI_0.115-blue.svg)](backend/)
[![Flutter](https://img.shields.io/badge/Frontend-Flutter_3.x-02569B.svg)](lib/)
[![Supabase](https://img.shields.io/badge/Database-Supabase_%2B_pgvector-3ECF8E.svg)](supabase/)
[![AI Model](https://img.shields.io/badge/AI-Gemini_2.5_Flash-orange.svg)](backend/app/services/gemini/)

---

## 1. What Veriqoo Is

**Veriqoo** is an automated compliance inspection system designed to audit packaged commodities against Indian statutory weights and measures regulations, specifically:
- **The Legal Metrology Act, 2009**
- **The Legal Metrology (Packaged Commodities) Rules, 2011** (and all subsequent amendments)

Veriqoo transforms multi-angle package photographs into verified legal compliance audits in seconds, replacing tedious manual inspection processes with cryptographic evidence capture, localized optical character recognition (OCR), deterministic legal applicability gating, vector-based Legal RAG retrieval, and constrained multimodal reasoning.

---

## 2. Problem Being Solved

Under Indian law, every pre-packaged commodity sold in retail or via e-commerce must display non-negotiable mandatory declarations (Rule 6 of the Packaged Commodities Rules). These include:
- Manufacturer / Packer / Importer name and complete address
- Common or generic name of the commodity
- Net quantity in standard metric units
- Month and year of manufacture, packing, or import
- Maximum Retail Price (MRP) inclusive of all taxes
- Consumer care contact details
- Country of origin (for imported goods)
- Unit Sale Price (USP) per standard unit

### The Inspection Challenge
1. **High Volume, Low Bandwidth**: Enforcement officers and marketplace compliance teams inspect thousands of SKUs daily with limited human resources.
2. **Subtle Non-Compliance**: Common violations include missing unit sale price, non-metric unit symbols (e.g., using `gms` instead of `g`), omitted consumer care phone numbers, and misleading date declarations.
3. **Complex Legal Amendments**: Rules change frequently (e.g., electronic product QR rules, revised unit sale price exemptions, garment labelling updates). Static checklists fail to track temporal legal applicability.
4. **Scattered Evidence**: Paper inspection logs lack cryptographic integrity and cannot easily correlate observations across multiple package panels.

---

## 3. Core Workflow

Veriqoo guides inspections through a strict seven-stage pipeline:

```text
[ Capture / Upload ] ──► [ SHA-256 Ingestion ] ──► [ Multi-Image OCR ]
                                                           │
                                                           ▼
[ Verification Report ] ◄── [ Gemini Reasoning ] ◄── [ Applicability + RAG ]
```

1. **Capture**: Capture or upload multi-panel photographs of the product package (front, back, sides, bottom).
2. **Ingestion & Validation**: Validate image headers, MIME types, and dimensions; compute SHA-256 hashes for deduplication.
3. **OCR Processing**: PaddleOCR extracts localized text tokens, bounding boxes, and orientation-corrected text lines.
4. **Applicability Gating**: The applicability engine evaluates package attributes (weight, commodity category, import status) to filter out non-applicable statutory rules.
5. **Hybrid Legal RAG**: Retrieves applicable statutory rules, schedules, and historical amendments via vector search and direct provision lookup.
6. **Constrained AI Reasoning**: Google Gemini analyzes OCR text grounded strictly within the retrieved legal provisions to evaluate compliance without hallucination.
7. **Report & Persistence**: Generates a tamper-evident audit report with PASS/FAIL determinations, verbatim evidence quotes, and stores records in Supabase.

---

## 4. System Architecture

```text
                       ┌───────────────────────────────┐
                       │          CLIENT APPS          │
                       │  • Flutter Mobile/Web App     │
                       │  • Telegram Field Bot         │
                       └───────────────┬───────────────┘
                                       │ HTTPS / JWT
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI BACKEND SERVICE                           │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ REST API Router (/api/v1) & Supabase JWT Auth Middleware              │  │
│  └───────────────────────────────────┬───────────────────────────────────┘  │
│                                      │                                      │
│  ┌───────────────────────────────────▼───────────────────────────────────┐  │
│  │ Inspection Orchestration Pipeline                                     │  │
│  │                                                                       │  │
│  │  1. Evidence Normalizer ──► 2. PaddleOCR + UVDoc Engine               │  │
│  │                                    │                                  │  │
│  │  3. Applicability Gating ◄─────────┘                                  │  │
│  │          │                                                            │  │
│  │  4. Legal RAG (pgvector + Rule Graph Expansion)                       │  │
│  │          │                                                            │  │
│  │  5. Gemini 2.5 Flash Constrained Reasoning                            │  │
│  │          │                                                            │  │
│  │  6. Deterministic Verification & Final Audit Synthesis                │  │
│  └───────────────────────────────────┬───────────────────────────────────┘  │
└──────────────────────────────────────┼──────────────────────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
        ┌─────────────────────────┐           ┌───────────────────────┐
        │     SUPABASE CLOUD      │           │     GOOGLE GEMINI     │
        │ • PostgreSQL 17         │           │ • text-embedding-004  │
        │ • pgvector search       │           │ • gemini-2.5-flash    │
        │ • Durable Image Storage │           │ • Structured JSON     │
        │ • Row Level Security    │           └───────────────────────┘
        └─────────────────────────┘
```

---

## 5. Backend

The backend is built with **FastAPI** (`backend/app/`), running on Python 3.11+.

- **Asynchronous Execution**: Long-running OCR and AI inference run as non-blocking background tasks (`backend/app/services/inspection/execution.py`).
- **Strict Error Envelopes**: Consistent API error format with machine-readable codes (`INVALID_REQUEST`, `AUTHENTICATION_REQUIRED`, `INSPECTION_NOT_FOUND`).
- **Modular Services**:
  - `backend/app/api/`: REST endpoints and dependencies
  - `backend/app/auth/`: JWT verification and user isolation
  - `backend/app/services/evidence/`: Image validation and hashing
  - `backend/app/services/ocr/`: Local OCR engine wrappers
  - `backend/app/services/applicability/`: Rule evaluation and linting
  - `backend/app/services/legal_rag/`: Hybrid legal retrieval
  - `backend/app/services/gemini/`: Multimodal reasoning client
  - `backend/app/services/storage/`: Cloud image storage adapters
  - `backend/app/telegram/`: Telegram bot logic and account linking

---

## 6. Flutter Frontend

The frontend is a cross-platform **Flutter** application (`lib/`) targeting Android, iOS, Web, and Desktop.

- **Dashboard**: Overview of recent inspections, compliance metrics, and status breakdowns.
- **Inspection Workflow**: Multi-image package photo capture and inspection session management.
- **Detailed Findings View**: Requirement-by-requirement drill-down showing PASS/FAIL status, rule citations, extracted declarations, and evidence snippets.
- **Runtime Configuration**: Secure injection of Supabase and Gemini endpoints via `--dart-define` parameters.

---

## 7. Legal Corpus

Veriqoo models the statutory provisions of the **Legal Metrology (Packaged Commodities) Rules, 2011** relationally in PostgreSQL:
- **Hierarchical Depth**: Models `Document` $\to$ `Provision` $\to$ `Sub-Rule` $\to$ `Clause` $\to$ `Schedule` $\to$ `Table`.
- **Temporal Validity**: Each provision tracks `effective_from` and `effective_to` timestamps, allowing audits of older packages against the legal rules in force at their manufacturing date.
- **Schedules & Tables Covered**:
  - First Schedule: Units of weight, measure, or number
  - Second Schedule: Standard symbols for metric units
  - Third Schedule: Commodities required to be packed in specified standard quantities
  - Fifth Schedule: Tolerances and maximum permissible errors

---

## 8. Optical Character Recognition (OCR)

The OCR subsystem (`backend/app/services/ocr/`) runs high-accuracy computer vision models locally:
- **PaddleOCR (PP-OCRv6)**: High-speed detection and recognition optimized for dense packaging typography.
- **UVDoc & Orientation Correction**: Corrects perspective distortion, curved package wrappers, and multi-angle orientation.
- **Quality & Confidence Scoring**: Assigns character- and word-level confidence metrics to guard against low-contrast or blurry labels.

---

## 9. Applicability Engine

Statutory rules are not universally applicable to all packages. The applicability engine (`backend/app/services/applicability/`):
- Determines whether a specific provision applies based on:
  - Commodity type (food, cosmetic, industrial, general)
  - Net content quantity and unit
  - Package type (retail vs. wholesale, small packaging exemptions)
  - Distribution channel (physical shelf vs. e-commerce)
  - Origin (imported vs. domestic)
- Uses deterministic boolean gating to eliminate irrelevant rules before prompting the AI, reducing latency and cost.
- Includes a built-in authoring linter to validate rule syntax and prevent logic gaps.

---

## 10. Legal RAG (Retrieval-Augmented Generation)

Veriqoo uses a hybrid retrieval pipeline combining:
1. **Direct Provision Lookup**: Instant resolution for mandatory baseline rules (Rules 6(1)(a) through 6(1)(h)).
2. **Dense Vector Search**: Powered by Google `text-embedding-004` (768 dimensions) with PostgreSQL `pgvector` cosine similarity indexing.
3. **Graph Expansion**: Dynamically pulls referenced schedules, penalty clauses, and relevant gazette amendments.
4. **Deduplication & Ranking**: Merges vector and direct lookup results, filtering out superseded provisions.

---

## 11. Gemini Evidence Reasoning

The reasoning module (`backend/app/services/gemini/`) utilizes **Gemini 2.5 Flash**:
- **Strict Evidence Grounding**: The LLM is supplied with OCR-extracted text and applicable rule definitions. It is strictly constrained to cite verbatim observations.
- **Structured Schema Envelopes**: Outputs conform to Pydantic schemas, outputting deterministic status enumerations: `PASS`, `FAIL`, `NOT_VISIBLE`, `REVIEW_REQUIRED`.
- **Cross-Image Contradiction Detection**: Detects and highlights conflicts across package sides (e.g., front label states 500g while back label states 450g).

---

## 12. Inspection Pipeline

The end-to-end inspection lifecycle is governed by an asynchronous state machine:

```text
[CREATED] ──► [UPLOADING] ──► [PROCESSING] ──► [COMPLETED]
                                     │
                                     └──► [FAILED]
```

- Inspections are assigned a unique UUID.
- Images are accepted in batches, hashed, and linked.
- The pipeline executes asynchronously; clients poll `/api/v1/inspections/{id}` or await completion.
- Audit results, itemized findings, and execution errors are atomically saved to PostgreSQL.

---

## 13. Supabase Integration

Veriqoo leverages **Supabase** for database, authentication, and durable cloud storage:
- **PostgreSQL 17**: Relational tables for legal documents, provisions, inspection records, and findings.
- **pgvector**: High-dimensional vector indexing (`HNSW` / `IVFFlat`) for legal text embeddings.
- **Storage Buckets**: `inspection-images` bucket for durable image storage using SHA-256 hashed paths.
- **Row Level Security (RLS)**: Policies ensure inspectors only view and modify their own records.

---

## 14. Telegram Integration

Field inspectors can operate entirely via the **Telegram Bot** (`telegram_bot/`):
- **Album Upload**: Send multiple package photos in a single Telegram album.
- **Command Set**:
  - `/start`: Welcome message and instructions
  - `/new`: Initialize a fresh inspection session
  - `/run`: Trigger the verification pipeline on uploaded photos
  - `/status`: Check background processing state
  - `/report`: View formatted compliance audit report
  - `/link`: Secure account linking workflow
- **Security Redaction**: Built-in sanitization scrubs JWTs, passwords, and sensitive keys from bot messages.

---

## 15. Authentication & Authorization

All protected API endpoints require **Supabase Auth JWT** bearer tokens (`backend/app/auth/`):
- Validates cryptographic signatures (`HS256`, `RS256`, `ES256`).
- Enforces token expiration (`exp`) and audience (`aud`).
- Extracts subject identity (`sub`) to guarantee strict user isolation.
- Prevents Insecure Direct Object References (IDOR): cross-user access attempts return `401 AUTHENTICATION_REQUIRED` or `404 INSPECTION_NOT_FOUND`.

---

## 16. Development Setup

### Prerequisites
- Python 3.11+
- Flutter SDK 3.x
- Dart SDK 3.x
- Git

### Clone the Repository
```bash
git clone https://github.com/vishaldaregave/Veriqoo.git
cd Veriqoo
```

### Python Virtual Environment Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 17. Environment Variables

Copy `.env.example` to `.env` and provide your service credentials:

```bash
cp .env.example .env
```

| Variable | Description | Example |
|---|---|---|
| `ENVIRONMENT` | Runtime environment | `development` / `production` |
| `GEMINI_API_KEY` | Google Gemini API Key | `AIzaSy...` |
| `SUPABASE_URL` | Supabase Project URL | `https://xyz.supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase Anonymous Public Key | `eyJhbGci...` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Service Role Key | `eyJhbGci...` |
| `SUPABASE_STORAGE_BUCKET` | Image storage bucket | `inspection-images` |
| `SUPABASE_JWT_SECRET` | Supabase JWT Secret for token verification | `your_jwt_secret` |
| `SUPABASE_JWT_AUDIENCE` | Expected JWT audience claim | `authenticated` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API Token | `123456789:ABC...` |
| `TELEGRAM_BOT_ENABLED` | Toggle Telegram background runner | `true` / `false` |

---

## 18. Running the Backend

With the virtual environment activated:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --app-dir backend --port 8010
```

The FastAPI OpenAPI documentation is accessible at:
- Swagger UI: `http://127.0.0.1:8010/docs`
- ReDoc: `http://127.0.0.1:8010/redoc`
- Health check: `http://127.0.0.1:8010/api/v1/health`

### Running the Telegram Bot
In a separate terminal:
```powershell
.\.venv\Scripts\Activate.ps1
python telegram_bot/telegram_bot.py
```

### Running the Flutter Client
```powershell
flutter pub get
flutter run -d chrome `
  --dart-define=SUPABASE_URL="https://your-project.supabase.co" `
  --dart-define=SUPABASE_KEY="your-anon-key" `
  --dart-define=GEMINI_API_KEY="your-gemini-key"
```

---

## 19. Running Tests

The test suite covers all 9 implementation phases with **670 automated unit and integration tests**.

Run the full test suite with Python's built-in `unittest` runner:

```powershell
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -p "test_*.py"
```

Expected output:
```text
Ran 670 tests in 119.796s

OK
```

Run a specific test module:
```powershell
python -m unittest tests/test_phase8a_api.py
```

---

## 20. Repository Structure

```text
Veriqoo/
├── backend/                        # FastAPI Backend Application
│   ├── app/
│   │   ├── api/                    # REST routes, schemas, and dependencies
│   │   │   └── v1/
│   │   │       ├── endpoints/      # Health, inspections, and Telegram link
│   │   │       └── router.py       # API v1 router
│   │   ├── auth/                   # Supabase JWT authentication & IDOR security
│   │   ├── schemas/                # Shared compliance Pydantic models
│   │   ├── services/
│   │   │   ├── applicability/      # Legal applicability gating engine & linter
│   │   │   ├── evidence/           # Multi-image ingestion, hashing & validation
│   │   │   ├── gemini/             # Gemini 2.5 Flash constrained reasoning
│   │   │   ├── inspection/         # Inspection repository, lifecycle & background exec
│   │   │   ├── inspection_pipeline/# Unified orchestrator & audit report generator
│   │   │   ├── legal_rag/          # Hybrid vector retrieval & provision graph
│   │   │   ├── ocr/                # PaddleOCR & UVDoc text extraction
│   │   │   ├── storage/            # Supabase Storage client
│   │   │   └── verification/       # Deterministic rule verification
│   │   ├── telegram/               # Telegram bot adapter & account linking
│   │   ├── config.py               # Application settings
│   │   └── main.py                 # FastAPI application factory
│   ├── requirements.txt            # Backend dependencies
│   └── .env.example                # Backend environment template
│
├── lib/                            # Flutter Client Application Source
│   ├── main.dart                   # Flutter application entrypoint
│   ├── screens/                    # Dashboard, inspection details, products
│   └── services/                   # Supabase, Gemini, and compliance services
│
├── assets/                         # Application Assets
│   ├── Book_on_Legal_Metrology_Packaged_Commodities_Rules,2011_with_all_amendments_whatsnews.pdf
│   └── Practice.png
│
├── images/                         # Sample package inspection photos & test evidence
│
├── docs/                           # Technical & Architectural Documentation
│   ├── api/
│   │   └── api_contract.md         # OpenAPI contract specifications & endpoints
│   ├── architecture/
│   │   └── system_architecture.md  # Comprehensive system architecture & dataflow
│   ├── legal/
│   │   └── legal_corpus.md         # Legal Metrology statutory framework & schemas
│   ├── phases/
│   │   └── implementation_phases.md# Locked phases 1-9e & verification roadmap
│   └── telegram/
│       └── telegram_integration.md # Telegram bot architecture & account linking
│
├── supabase/                       # Supabase PostgreSQL & Database Migrations
│   ├── migrations/                 # Versioned SQL migration files (Phases 1-9e)
│   └── .temp/                      # Supabase CLI project metadata
│
├── scripts/                        # Ingestion, Embedding & Benchmarking CLI Scripts
│   ├── benchmark_legal_retrieval.py
│   ├── ingest_legal_rules.py
│   ├── legal_corpus_parser.py
│   ├── legal_corpus_phase2.py
│   ├── load_legal_corpus_phase2.py
│   └── populate_legal_corpus_embeddings.py
│
├── telegram_bot/                   # Standalone Telegram Bot Process
│   └── telegram_bot.py
│
├── test/                           # Flutter Unit & Widget Tests
│   ├── compliance_analysis_test.dart
│   └── widget_test.dart
│
├── tests/                          # Python Automated Test Suite (670 Tests)
│   ├── test_applicability_*.py
│   ├── test_legal_*.py
│   └── test_phase*.py
│
├── .env.example                    # Root environment configuration template
├── .gitignore                      # Comprehensive Git exclusion policy
├── pubspec.yaml                    # Flutter package configuration
├── requirements.txt                # Python root dependencies
└── README.md                       # Main repository documentation
```

---

## License

This project was developed for the **CraftVerse 2.0 Hackathon (2026)** at Pimpri Chinchwad College of Engineering and Research, Pune.
All rights reserved.
