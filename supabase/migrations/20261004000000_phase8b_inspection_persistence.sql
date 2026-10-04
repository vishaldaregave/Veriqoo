-- =====================================================================
-- Phase 8B: Inspection Persistence Schema Migration
-- 
-- Introduces durable PostgreSQL/Supabase tables for multi-image inspection
-- containers, image artifact references, OCR observations, evidence candidates,
-- requirement verification results, and final inspection assessment reports.
--
-- Reuses existing Phase 3A runtime tables for applicability evaluation:
-- - applicability_runs
-- - inspection_facts
-- - applicability_decisions
-- - applicability_decision_evidence
--
-- Non-destructive: Does NOT alter or modify authoritative legal corpus tables.
-- =====================================================================

-- 1. Root Inspection Sessions Container
CREATE TABLE IF NOT EXISTS public.inspection_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'COLLECTING',
    started_at timestamptz,
    completed_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT inspection_sessions_status_check
        CHECK (status IN ('COLLECTING', 'READY')),
    CONSTRAINT inspection_sessions_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

-- 2. Inspection Image References (Preserves Phase 5A ImageArtifact provenance & ordering)
CREATE TABLE IF NOT EXISTS public.inspection_images (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_id uuid NOT NULL REFERENCES public.inspection_sessions(id) ON DELETE CASCADE,
    image_id text NOT NULL,
    sequence integer NOT NULL,
    source_hash text NOT NULL,
    normalized_hash text NOT NULL,
    source_format text NOT NULL,
    normalized_format text NOT NULL,
    original_width integer NOT NULL,
    original_height integer NOT NULL,
    normalized_width integer NOT NULL,
    normalized_height integer NOT NULL,
    file_size_bytes integer NOT NULL,
    source_file_size_bytes integer NOT NULL,
    color_mode text NOT NULL DEFAULT 'RGB',
    was_resized boolean NOT NULL DEFAULT false,
    was_orientation_corrected boolean NOT NULL DEFAULT false,
    storage_path text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT inspection_images_sequence_positive
        CHECK (sequence > 0),
    CONSTRAINT inspection_images_inspection_sequence_unique
        UNIQUE (inspection_id, sequence),
    CONSTRAINT inspection_images_dimensions_positive
        CHECK (original_width > 0 AND original_height > 0 AND normalized_width > 0 AND normalized_height > 0),
    CONSTRAINT inspection_images_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

-- 3. Raw OCR Observations (Preserves Phase 5C PaddleOCR technical observations)
CREATE TABLE IF NOT EXISTS public.inspection_ocr_observations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_id uuid NOT NULL REFERENCES public.inspection_sessions(id) ON DELETE CASCADE,
    image_id text NOT NULL,
    observation_id text NOT NULL,
    raw_text text NOT NULL,
    confidence double precision,
    bounding_box jsonb,
    engine text NOT NULL DEFAULT 'PaddleOCR',
    engine_version text NOT NULL DEFAULT '3.7.0',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT inspection_ocr_observations_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

-- 4. Extracted Evidence Candidates (Preserves Phase 5D normalized evidence)
CREATE TABLE IF NOT EXISTS public.inspection_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_id uuid NOT NULL REFERENCES public.inspection_sessions(id) ON DELETE CASCADE,
    evidence_id text NOT NULL,
    observation_id text NOT NULL DEFAULT '',
    image_id text NOT NULL DEFAULT '',
    field text NOT NULL,
    raw_text text NOT NULL,
    normalized_text text NOT NULL,
    parsed_value jsonb,
    parsed_unit text,
    ocr_confidence double precision,
    parser_confidence double precision NOT NULL DEFAULT 1.0,
    confidence double precision NOT NULL DEFAULT 1.0,
    status text NOT NULL DEFAULT 'UNPARSED',
    parser text NOT NULL DEFAULT 'GenericParser',
    parser_version text NOT NULL DEFAULT '1.0.0',
    sequence integer NOT NULL DEFAULT 0,
    bounding_box jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT inspection_evidence_status_check
        CHECK (status IN ('VALID', 'AMBIGUOUS', 'UNPARSED', 'INSUFFICIENT_EVIDENCE')),
    CONSTRAINT inspection_evidence_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

-- 5. Statutory Requirement Verification Results (Preserves Phase 5E & Phase 7 requirement outcomes)
CREATE TABLE IF NOT EXISTS public.inspection_requirement_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_id uuid NOT NULL REFERENCES public.inspection_sessions(id) ON DELETE CASCADE,
    verification_id text NOT NULL,
    requirement_id text NOT NULL,
    applicability_decision_id uuid REFERENCES public.applicability_decisions(id) ON DELETE SET NULL,
    status text NOT NULL,
    reason text NOT NULL,
    confidence double precision,
    review_required boolean NOT NULL DEFAULT false,
    evidence_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    source_observation_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    image_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT inspection_requirement_results_status_check
        CHECK (status IN ('PASS', 'FAIL', 'NOT_VISIBLE', 'NOT_APPLICABLE', 'REVIEW_REQUIRED')),
    CONSTRAINT inspection_requirement_results_arrays_check
        CHECK (
            jsonb_typeof(evidence_ids) = 'array'
            AND jsonb_typeof(source_observation_ids) = 'array'
            AND jsonb_typeof(image_ids) = 'array'
        ),
    CONSTRAINT inspection_requirement_results_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

-- 6. Inspection Assessment Reports (Preserves Phase 7 InspectionReport serialized payload)
CREATE TABLE IF NOT EXISTS public.inspection_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_id uuid NOT NULL REFERENCES public.inspection_sessions(id) ON DELETE CASCADE,
    overall_status text NOT NULL,
    summary text NOT NULL,
    counts jsonb NOT NULL,
    report_payload jsonb NOT NULL,
    schema_version text NOT NULL DEFAULT '1.0.0',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT inspection_reports_inspection_id_unique
        UNIQUE (inspection_id),
    CONSTRAINT inspection_reports_overall_status_check
        CHECK (overall_status IN ('PASS', 'FAIL', 'REVIEW_REQUIRED')),
    CONSTRAINT inspection_reports_objects_check
        CHECK (jsonb_typeof(counts) = 'object' AND jsonb_typeof(report_payload) = 'object')
);

-- Indexes for efficient querying and foreign key lookups
CREATE INDEX IF NOT EXISTS idx_inspection_sessions_status
    ON public.inspection_sessions(status);
CREATE INDEX IF NOT EXISTS idx_inspection_sessions_created_at
    ON public.inspection_sessions(created_at);

CREATE INDEX IF NOT EXISTS idx_inspection_images_inspection_id
    ON public.inspection_images(inspection_id);
CREATE INDEX IF NOT EXISTS idx_inspection_images_image_id
    ON public.inspection_images(image_id);
CREATE INDEX IF NOT EXISTS idx_inspection_images_sequence
    ON public.inspection_images(inspection_id, sequence);

CREATE INDEX IF NOT EXISTS idx_inspection_ocr_inspection_id
    ON public.inspection_ocr_observations(inspection_id);
CREATE INDEX IF NOT EXISTS idx_inspection_ocr_image_id
    ON public.inspection_ocr_observations(image_id);

CREATE INDEX IF NOT EXISTS idx_inspection_evidence_inspection_id
    ON public.inspection_evidence(inspection_id);
CREATE INDEX IF NOT EXISTS idx_inspection_evidence_field
    ON public.inspection_evidence(field);

CREATE INDEX IF NOT EXISTS idx_inspection_req_results_inspection_id
    ON public.inspection_requirement_results(inspection_id);
CREATE INDEX IF NOT EXISTS idx_inspection_req_results_requirement_id
    ON public.inspection_requirement_results(requirement_id);

CREATE INDEX IF NOT EXISTS idx_inspection_reports_inspection_id
    ON public.inspection_reports(inspection_id);
CREATE INDEX IF NOT EXISTS idx_inspection_reports_overall_status
    ON public.inspection_reports(overall_status);

