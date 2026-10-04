# Veriqoo Phase U4 — QR Detailed Reports

## 1. Executive Summary

Phase U4 introduces a secure, shareable QR-based inspection report mechanism for the Veriqoo compliance verification platform.
It enables field inspectors and businesses to share verified compliance reports via compact QR codes and HTTPS references without exposing internal infrastructure, private storage paths, raw database UUIDs, or authenticated user claims.

---

## 2. Security Architecture

```
+---------------------+
| Inspection Completed|
+----------+----------+
           |
           v
+---------------------+
|   InspectionReport  |
+----------+----------+
           |
           v  (POST /api/v1/inspections/{id}/share - Authenticated & Owned)
+---------------------+
| Generate Share Ref  |
| - secrets.token_urlsafe(32) -> vqr_<token>
| - SHA-256(token) -> token_hash
+----------+----------+
           |
           +---------------------------------------+
           |                                       |
           v (Persisted to DB)                     v (Returned to Client)
+----------------------------+            +----------------------------+
| public.inspection_report_  |            | Structured QRPayload       |
| shares (token_hash only)   |            | URL: https://<host>/r/<tok>|
+----------------------------+            +----------------------------+
                                                   |
                                                   v (Flutter Scanner / Web)
                                          +----------------------------+
                                          | GET /r/<token>?lang=hi     |
                                          +--------------+-------------+
                                                         |
                                                         v
                                          +----------------------------+
                                          | Public Report Resolution   |
                                          | 1. SHA-256(token)          |
                                          | 2. Verify status & expiry  |
                                          | 3. Localize presentation   |
                                          | 4. Strip sensitive fields  |
                                          +--------------+-------------+
                                                         |
                                                         v
                                          +----------------------------+
                                          | PublicInspectionReport     |
                                          +----------------------------+
```

### 2.1 Token Design & Entropy
- **Format**: `vqr_<secrets.token_urlsafe(32)>` (e.g. `vqr_4q9c...`).
- **High Entropy**: Cryptographically generated via Python's `secrets` module with 256 bits of underlying randomness.
- **Persistence**: **Zero Raw Token Persistence**. Only the SHA-256 hash (`token_hash`) is stored in the database.
- **Revocation**: Explicit `revoked_at` timestamp. Revocation takes effect immediately.
- **Expiration**: Optional `expires_at` support (configurable between 60 seconds and 30 days).

### 2.2 Security Boundaries & Data Minimization
- **Ownership Protection**: Creating or revoking share tokens requires Phase 9D authentication and verified session ownership.
- **Safe Public Projection**:
  - `owner_id` is excluded.
  - User emails, JWT claims, and Telegram IDs are excluded.
  - Private storage paths (`storage_path`) and internal filesystem paths are omitted.
  - Exception traces and pipeline diagnostics are omitted.
- **No Side-Effects on Public Lookups**:
  - Public lookup does NOT invoke OCR, Gemini AI, or Legal RAG embeddings.
  - Lookup operates entirely over the completed persisted report artifact.

---

## 3. Database Schema

Additive migration `supabase/migrations/20261006000000_phase_u4_report_shares.sql`:

```sql
CREATE TABLE IF NOT EXISTS public.inspection_report_shares (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_id uuid NOT NULL REFERENCES public.inspection_sessions(id) ON DELETE CASCADE,
    token_hash text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    revoked_at timestamptz,
    created_by uuid,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_inspection_report_shares_token_hash ON public.inspection_report_shares(token_hash);
CREATE INDEX idx_inspection_report_shares_inspection_id ON public.inspection_report_shares(inspection_id);
CREATE INDEX idx_inspection_report_shares_active ON public.inspection_report_shares(inspection_id, revoked_at, expires_at);
```

---

## 4. API Endpoints

### 4.1 Create Share (Protected)
- **Method**: `POST /api/v1/inspections/{inspection_id}/share`
- **Auth**: Required (`Bearer <JWT>`)
- **Request Body**:
  ```json
  {
    "expires_in_seconds": 86400,
    "metadata": {"channel": "qr_print"}
  }
  ```
- **Response**: `201 Created`
  ```json
  {
    "share_id": "8f0a2c91-...",
    "inspection_id": "1b2c3d4e-...",
    "qr": {
      "url": "https://reports.veriqoo.ai/r/vqr_k8xL9p2...",
      "token_id": "8f0a2c91-...",
      "format": "url",
      "version": 1
    },
    "created_at": "2026-10-06T10:00:00Z",
    "expires_at": "2026-10-07T10:00:00Z",
    "status": "ACTIVE"
  }
  ```

### 4.2 Revoke Share (Protected)
- **Method**: `POST /api/v1/inspections/{inspection_id}/share/{share_id}/revoke`
- **Auth**: Required (`Bearer <JWT>`)
- **Response**: `200 OK`
  ```json
  {
    "share_id": "8f0a2c91-...",
    "inspection_id": "1b2c3d4e-...",
    "status": "REVOKED",
    "revoked_at": "2026-10-06T11:00:00Z"
  }
  ```

### 4.3 Public Report Resolution (Public)
- **Method**: `GET /r/{share_token}` (or `GET /api/v1/public/reports/{share_token}`)
- **Auth**: None (Public)
- **Query Parameters**: `lang=en|hi|mr` (Optional)
- **Response**: `200 OK` (`PublicInspectionReportResponse`)
  - Preserves U1 Compliance Score & Verification Results.
  - Preserves U2 Visual Evidence Annotations (Geometry & Highlighting types).
  - Dynamically localizes via U3 `LocalizationService`.
