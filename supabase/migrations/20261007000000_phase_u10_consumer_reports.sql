-- =====================================================================
-- Phase U10: Consumer -> Authority Action Bridge + Case Integration
--
-- Additive, non-destructive migration creating persistent consumer reports table.
-- Stores frozen, evidence-backed regulatory report packages submitted by consumers.
-- Enforces idempotent single-report per (inspection_id, user_id) relationship.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.consumer_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id text NOT NULL UNIQUE,
    inspection_id uuid NOT NULL REFERENCES public.inspection_sessions(id) ON DELETE CASCADE,
    user_id uuid NOT NULL,
    status text NOT NULL DEFAULT 'SUBMITTED',
    canonical_overall_status text NOT NULL,
    consumer_overall_result text NOT NULL,
    consumer_description text,
    product_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    identity_confidence text NOT NULL DEFAULT 'UNKNOWN',
    scan_quality jsonb NOT NULL DEFAULT '{}'::jsonb,
    findings jsonb NOT NULL DEFAULT '[]'::jsonb,
    priority_score integer NOT NULL DEFAULT 0,
    priority_band text NOT NULL DEFAULT 'MEDIUM',
    priority_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
    risk_signals jsonb NOT NULL DEFAULT '[]'::jsonb,
    location jsonb,
    inspection_created_at timestamptz,
    report_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT unique_consumer_report_user_inspection UNIQUE (inspection_id, user_id),
    CONSTRAINT consumer_reports_product_summary_object CHECK (jsonb_typeof(product_summary) = 'object'),
    CONSTRAINT consumer_reports_scan_quality_object CHECK (jsonb_typeof(scan_quality) = 'object'),
    CONSTRAINT consumer_reports_findings_array CHECK (jsonb_typeof(findings) = 'array'),
    CONSTRAINT consumer_reports_risk_signals_array CHECK (jsonb_typeof(risk_signals) = 'array'),
    CONSTRAINT consumer_reports_metadata_object CHECK (jsonb_typeof(metadata) = 'object')
);

-- Indexes for rapid lookup by report_id, inspection_id, user_id, and authority priority triage
CREATE INDEX IF NOT EXISTS idx_consumer_reports_report_id
    ON public.consumer_reports(report_id);

CREATE INDEX IF NOT EXISTS idx_consumer_reports_inspection_id
    ON public.consumer_reports(inspection_id);

CREATE INDEX IF NOT EXISTS idx_consumer_reports_user_id
    ON public.consumer_reports(user_id);

CREATE INDEX IF NOT EXISTS idx_consumer_reports_status
    ON public.consumer_reports(status);

CREATE INDEX IF NOT EXISTS idx_consumer_reports_priority
    ON public.consumer_reports(priority_band, priority_score DESC);
