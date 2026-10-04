-- =====================================================================
-- Phase U24-B: Durable Sync Operations Schema Migration
--
-- Introduces durable PostgreSQL/Supabase table for offline synchronization
-- operations, idempotency tracking, operation state tracking, and receipts.
--
-- Table: public.inspection_sync_operations
-- Non-destructive: Does NOT alter existing inspection or legal tables.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.inspection_sync_operations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_id text NOT NULL,
    inspection_id text NOT NULL,
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    operation_type text NOT NULL DEFAULT 'CREATE',
    content_hash text NOT NULL,
    dependency_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL DEFAULT 'PENDING',
    attempt_count integer NOT NULL DEFAULT 0,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_code text,
    error_message text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    acknowledged_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT inspection_sync_operations_operation_id_unique
        UNIQUE (operation_id),
    CONSTRAINT inspection_sync_operations_status_check
        CHECK (status IN ('PENDING', 'PROCESSING', 'ACKNOWLEDGED', 'ALREADY_APPLIED', 'RETRYABLE_FAILURE', 'REJECTED')),
    CONSTRAINT inspection_sync_operations_entity_type_check
        CHECK (entity_type IN ('INSPECTION', 'IMAGE', 'OCR_OBSERVATION', 'EVIDENCE', 'FACT', 'APPLICABILITY', 'REQUIREMENT_RESULT', 'REPORT')),
    CONSTRAINT inspection_sync_operations_operation_type_check
        CHECK (operation_type IN ('CREATE', 'UPSERT')),
    CONSTRAINT inspection_sync_operations_attempt_count_positive
        CHECK (attempt_count >= 0),
    CONSTRAINT inspection_sync_operations_dependency_ids_array
        CHECK (jsonb_typeof(dependency_ids) = 'array'),
    CONSTRAINT inspection_sync_operations_payload_object
        CHECK (jsonb_typeof(payload) = 'object'),
    CONSTRAINT inspection_sync_operations_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

-- Performance Indices for fast sync querying and reconciliation
CREATE INDEX IF NOT EXISTS idx_sync_ops_inspection_id
    ON public.inspection_sync_operations (inspection_id);

CREATE INDEX IF NOT EXISTS idx_sync_ops_status
    ON public.inspection_sync_operations (status);

CREATE INDEX IF NOT EXISTS idx_sync_ops_entity_lookup
    ON public.inspection_sync_operations (inspection_id, entity_type, entity_id);

-- Enable Row Level Security (RLS)
ALTER TABLE public.inspection_sync_operations ENABLE ROW LEVEL SECURITY;

-- Service Role Policy for Server-Side Ingestion Operations
CREATE POLICY "Service role full access on inspection_sync_operations"
    ON public.inspection_sync_operations
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
