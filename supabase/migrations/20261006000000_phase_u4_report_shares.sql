-- =====================================================================
-- Phase U4: Secure Inspection Report Sharing & QR Resolution
--
-- Additive, non-destructive migration creating persistent report shares table.
-- Stores cryptographically hashed tokens, expiration, and revocation metadata.
-- Raw tokens are NEVER persisted.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.inspection_report_shares (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_id uuid NOT NULL REFERENCES public.inspection_sessions(id) ON DELETE CASCADE,
    token_hash text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    revoked_at timestamptz,
    created_by uuid,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT inspection_report_shares_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

-- Indexes for rapid token hash lookup, inspection relationship, and active share queries
CREATE INDEX IF NOT EXISTS idx_inspection_report_shares_token_hash
    ON public.inspection_report_shares(token_hash);

CREATE INDEX IF NOT EXISTS idx_inspection_report_shares_inspection_id
    ON public.inspection_report_shares(inspection_id);

CREATE INDEX IF NOT EXISTS idx_inspection_report_shares_active
    ON public.inspection_report_shares(inspection_id, revoked_at, expires_at);
