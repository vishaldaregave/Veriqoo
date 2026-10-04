-- Migration: 20261008000000_t3_3_consumer_issues.sql
-- Description: T3-3 Consumer Issue Reporting schema with complaint retention and RLS
-- References auth.users, public.inspection_sessions, and public.saved_products

CREATE TABLE IF NOT EXISTS public.consumer_issues (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    inspection_id uuid REFERENCES public.inspection_sessions(id) ON DELETE SET NULL,
    saved_product_id uuid REFERENCES public.saved_products(id) ON DELETE SET NULL,
    issue_type text NOT NULL,
    title text NOT NULL,
    description text NOT NULL,
    status text NOT NULL DEFAULT 'SUBMITTED',
    resolution_notes text,
    evidence_images jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT consumer_issues_user_inspection_type_unique UNIQUE (user_id, inspection_id, issue_type),
    CONSTRAINT consumer_issues_issue_type_check
        CHECK (issue_type IN ('MISLEADING_LABEL', 'PRICE_TAMPERING', 'EXPIRED_PRODUCT', 'WEIGHT_SHORTAGE', 'MISSING_MANDATORY_INFO', 'OTHER')),
    CONSTRAINT consumer_issues_status_check
        CHECK (status IN ('SUBMITTED', 'UNDER_REVIEW', 'RESOLVED', 'REJECTED')),
    CONSTRAINT consumer_issues_user_id_nonempty
        CHECK (user_id != '00000000-0000-0000-0000-000000000000'::uuid),
    CONSTRAINT consumer_issues_title_nonempty
        CHECK (length(trim(title)) > 0),
    CONSTRAINT consumer_issues_description_nonempty
        CHECK (length(trim(description)) > 0),
    CONSTRAINT consumer_issues_evidence_images_array
        CHECK (jsonb_typeof(evidence_images) = 'array')
);

-- Query-optimized composite index for user listing ordered by created_at DESC
CREATE INDEX IF NOT EXISTS idx_consumer_issues_user_created_at
    ON public.consumer_issues(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_consumer_issues_inspection_id
    ON public.consumer_issues(inspection_id);

CREATE INDEX IF NOT EXISTS idx_consumer_issues_saved_product_id
    ON public.consumer_issues(saved_product_id);

CREATE INDEX IF NOT EXISTS idx_consumer_issues_status
    ON public.consumer_issues(status);

-- Reliable updated_at maintenance trigger
CREATE OR REPLACE FUNCTION public.set_consumer_issues_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_consumer_issues_updated_at ON public.consumer_issues;
CREATE TRIGGER trigger_consumer_issues_updated_at
    BEFORE UPDATE ON public.consumer_issues
    FOR EACH ROW
    EXECUTE FUNCTION public.set_consumer_issues_updated_at();

-- Enable Row Level Security
ALTER TABLE public.consumer_issues ENABLE ROW LEVEL SECURITY;

-- RLS Policy 1: Authenticated users can select their own submitted issues
DROP POLICY IF EXISTS consumer_issues_select_own ON public.consumer_issues;
CREATE POLICY consumer_issues_select_own
    ON public.consumer_issues FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- RLS Policy 2: Authenticated users can insert issue reports owned by themselves in SUBMITTED state
DROP POLICY IF EXISTS consumer_issues_insert_own ON public.consumer_issues;
CREATE POLICY consumer_issues_insert_own
    ON public.consumer_issues FOR INSERT
    TO authenticated
    WITH CHECK (
        auth.uid() = user_id
        AND status = 'SUBMITTED'
        AND resolution_notes IS NULL
    );

-- RLS Policy 3: Authenticated users can delete their own issue if status is SUBMITTED
-- Direct consumer UPDATE via PostgREST is disallowed; updates are restricted to trusted backend/authority
DROP POLICY IF EXISTS consumer_issues_delete_own ON public.consumer_issues;
CREATE POLICY consumer_issues_delete_own
    ON public.consumer_issues FOR DELETE
    TO authenticated
    USING (auth.uid() = user_id AND status = 'SUBMITTED');
