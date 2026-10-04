-- =====================================================================
-- Phase U25: Evidence Trust & Chain of Custody Schema Migration
-- 
-- Introduces append-oriented cryptographic custody tracking:
-- 1. inspection_evidence_records: Canonical evidence identity and immutable content hashes.
-- 2. evidence_chain_events: Tamper-evident cryptographic provenance event chain.
-- =====================================================================

-- 1. Canonical Evidence Records
CREATE TABLE IF NOT EXISTS public.inspection_evidence_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id text NOT NULL UNIQUE,
    inspection_id uuid NOT NULL REFERENCES public.inspection_sessions(id) ON DELETE CASCADE,
    image_id text,
    content_hash text NOT NULL,
    hash_algorithm text NOT NULL DEFAULT 'SHA-256',
    byte_size integer NOT NULL DEFAULT 0,
    media_type text NOT NULL DEFAULT 'image/png',
    original_filename text,
    storage_reference text,
    captured_at timestamptz,
    received_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    submitted_by text,
    source_type text NOT NULL DEFAULT 'upload',
    integrity_status text NOT NULL DEFAULT 'UNVERIFIED',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT inspection_evidence_records_integrity_status_check
        CHECK (integrity_status IN ('VERIFIED', 'UNVERIFIED', 'MISSING', 'HASH_MISMATCH', 'CORRUPTED', 'REVIEW_REQUIRED')),
    CONSTRAINT inspection_evidence_records_byte_size_nonnegative
        CHECK (byte_size >= 0),
    CONSTRAINT inspection_evidence_records_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_inspection_evidence_records_inspection_id
    ON public.inspection_evidence_records (inspection_id);

CREATE INDEX IF NOT EXISTS idx_inspection_evidence_records_content_hash
    ON public.inspection_evidence_records (content_hash);

-- 2. Append-Oriented Tamper-Evident Chain Events
CREATE TABLE IF NOT EXISTS public.evidence_chain_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id text NOT NULL UNIQUE,
    evidence_id text NOT NULL REFERENCES public.inspection_evidence_records(evidence_id) ON DELETE CASCADE,
    inspection_id uuid NOT NULL REFERENCES public.inspection_sessions(id) ON DELETE CASCADE,
    event_type text NOT NULL,
    actor_type text NOT NULL DEFAULT 'system',
    actor_id text,
    timestamp timestamptz NOT NULL DEFAULT now(),
    previous_event_hash text,
    event_hash text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    operation_id text,
    CONSTRAINT evidence_chain_events_type_check
        CHECK (event_type IN (
            'CAPTURED',
            'RECEIVED',
            'STORED',
            'HASHED',
            'OCR_STARTED',
            'OCR_COMPLETED',
            'EVIDENCE_EXTRACTED',
            'FACT_DERIVED',
            'REQUIREMENT_EVALUATED',
            'REPORT_GENERATED',
            'REVALIDATED',
            'INTEGRITY_CHECKED',
            'HASH_MISMATCH_DETECTED'
        )),
    CONSTRAINT evidence_chain_events_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_evidence_chain_events_evidence_id
    ON public.evidence_chain_events (evidence_id);

CREATE INDEX IF NOT EXISTS idx_evidence_chain_events_inspection_id
    ON public.evidence_chain_events (inspection_id);

CREATE INDEX IF NOT EXISTS idx_evidence_chain_events_timestamp
    ON public.evidence_chain_events (timestamp);
