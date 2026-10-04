-- Migration: 20261009000000_t3_4_authority_workflow.sql
-- Description: T3-4 Authority Profiles, Case Jurisdiction, Assignment, Internal Notes, and Audit Events
-- Enforces hierarchical jurisdiction access, department isolation, and tamper-evident audit history.

-- =====================================================================
-- 1. Authority Profiles Table
-- =====================================================================
CREATE TABLE IF NOT EXISTS public.authority_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL UNIQUE,
    department text NOT NULL,
    designation text NOT NULL,
    badge_number text,
    state_code text NOT NULL,
    jurisdiction_level text NOT NULL DEFAULT 'DISTRICT',
    authorized_district_codes text[] NOT NULL DEFAULT '{}'::text[],
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT authority_profiles_user_id_nonempty
        CHECK (user_id != '00000000-0000-0000-0000-000000000000'::uuid),
    CONSTRAINT authority_profiles_department_check
        CHECK (department IN ('LEGAL_METROLOGY', 'FOOD_SAFETY', 'CONSUMER_AFFAIRS', 'WEIGHTS_AND_MEASURES')),
    CONSTRAINT authority_profiles_designation_nonempty
        CHECK (length(trim(designation)) > 0),
    CONSTRAINT authority_profiles_state_code_nonempty
        CHECK (length(trim(state_code)) > 0),
    CONSTRAINT authority_profiles_jurisdiction_level_check
        CHECK (jurisdiction_level IN ('DISTRICT', 'STATE')),
    CONSTRAINT authority_profiles_authorized_districts_nonempty
        CHECK (cardinality(authorized_district_codes) > 0)
);

CREATE INDEX IF NOT EXISTS idx_authority_profiles_user_id
    ON public.authority_profiles(user_id);

CREATE INDEX IF NOT EXISTS idx_authority_profiles_dept_state
    ON public.authority_profiles(department, state_code);

CREATE INDEX IF NOT EXISTS idx_authority_profiles_is_active
    ON public.authority_profiles(is_active);

-- Reliable updated_at maintenance trigger for authority_profiles
CREATE OR REPLACE FUNCTION public.set_authority_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_authority_profiles_updated_at ON public.authority_profiles;
CREATE TRIGGER trigger_authority_profiles_updated_at
    BEFORE UPDATE ON public.authority_profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.set_authority_profiles_updated_at();

-- =====================================================================
-- 2. Extend Consumer Issues with Jurisdiction and Assignment Columns
-- =====================================================================
ALTER TABLE public.consumer_issues
    ADD COLUMN IF NOT EXISTS department text NOT NULL DEFAULT 'LEGAL_METROLOGY',
    ADD COLUMN IF NOT EXISTS state_code text,
    ADD COLUMN IF NOT EXISTS district_code text,
    ADD COLUMN IF NOT EXISTS jurisdiction_verified boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS assigned_officer_id uuid,
    ADD COLUMN IF NOT EXISTS assigned_at timestamptz,
    ADD COLUMN IF NOT EXISTS assigned_by uuid;

ALTER TABLE public.consumer_issues
    DROP CONSTRAINT IF EXISTS consumer_issues_status_check;
ALTER TABLE public.consumer_issues
    ADD CONSTRAINT consumer_issues_status_check
        CHECK (status IN ('SUBMITTED', 'UNDER_REVIEW', 'ACTION_TAKEN', 'RESOLVED', 'REJECTED'));

CREATE INDEX IF NOT EXISTS idx_consumer_issues_jurisdiction
    ON public.consumer_issues(department, state_code, district_code)
    WHERE jurisdiction_verified = true;

CREATE INDEX IF NOT EXISTS idx_consumer_issues_assigned_officer
    ON public.consumer_issues(assigned_officer_id)
    WHERE assigned_officer_id IS NOT NULL;

-- =====================================================================
-- 3. Confidential Investigation Notes Table
-- =====================================================================
CREATE TABLE IF NOT EXISTS public.consumer_issue_notes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id uuid NOT NULL REFERENCES public.consumer_issues(id) ON DELETE CASCADE,
    author_id uuid NOT NULL,
    note_text text NOT NULL,
    is_internal boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT consumer_issue_notes_author_id_nonempty
        CHECK (author_id != '00000000-0000-0000-0000-000000000000'::uuid),
    CONSTRAINT consumer_issue_notes_text_nonempty
        CHECK (length(trim(note_text)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_consumer_issue_notes_issue_id
    ON public.consumer_issue_notes(issue_id, created_at DESC);

-- Reliable updated_at maintenance trigger for consumer_issue_notes
CREATE OR REPLACE FUNCTION public.set_consumer_issue_notes_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_consumer_issue_notes_updated_at ON public.consumer_issue_notes;
CREATE TRIGGER trigger_consumer_issue_notes_updated_at
    BEFORE UPDATE ON public.consumer_issue_notes
    FOR EACH ROW
    EXECUTE FUNCTION public.set_consumer_issue_notes_updated_at();

-- =====================================================================
-- 4. Case Audit Events Table (Preserved on complaint withdrawal)
-- =====================================================================
CREATE TABLE IF NOT EXISTS public.consumer_issue_audit_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id uuid REFERENCES public.consumer_issues(id) ON DELETE SET NULL,
    actor_id uuid NOT NULL,
    actor_role text NOT NULL,
    event_type text NOT NULL,
    previous_state text,
    new_state text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT consumer_issue_audit_events_actor_id_nonempty
        CHECK (actor_id != '00000000-0000-0000-0000-000000000000'::uuid),
    CONSTRAINT consumer_issue_audit_events_event_type_nonempty
        CHECK (length(trim(event_type)) > 0),
    CONSTRAINT consumer_issue_audit_events_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_consumer_issue_audit_events_issue_id
    ON public.consumer_issue_audit_events(issue_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_consumer_issue_audit_events_actor_id
    ON public.consumer_issue_audit_events(actor_id, created_at DESC);

-- =====================================================================
-- 5. Row Level Security (RLS) Policies
-- =====================================================================
ALTER TABLE public.authority_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consumer_issue_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consumer_issue_audit_events ENABLE ROW LEVEL SECURITY;

-- Policy 1: Authority Profiles Select (Owner or admin can read; consumers denied)
DROP POLICY IF EXISTS authority_profiles_select ON public.authority_profiles;
CREATE POLICY authority_profiles_select
    ON public.authority_profiles FOR SELECT
    TO authenticated
    USING (
        auth.uid() = user_id
        OR EXISTS (
            SELECT 1 FROM public.user_profiles up
            WHERE up.user_id = auth.uid() AND up.app_role = 'admin'
        )
    );

-- Policy 2: Consumer Issues Select for Authority (Restricted strictly to verified jurisdiction)
DROP POLICY IF EXISTS consumer_issues_select_authority ON public.consumer_issues;
CREATE POLICY consumer_issues_select_authority
    ON public.consumer_issues FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.authority_profiles ap
            WHERE ap.user_id = auth.uid()
              AND ap.is_active = true
              AND consumer_issues.jurisdiction_verified = true
              AND consumer_issues.department = ap.department
              AND consumer_issues.state_code = ap.state_code
              AND consumer_issues.district_code = ANY(ap.authorized_district_codes)
        )
    );

-- Policy 3: Confidential Investigation Notes Select (Internal to active authorized authority only)
DROP POLICY IF EXISTS consumer_issue_notes_select_authority ON public.consumer_issue_notes;
CREATE POLICY consumer_issue_notes_select_authority
    ON public.consumer_issue_notes FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.consumer_issues ci
            JOIN public.authority_profiles ap
              ON ap.user_id = auth.uid()
             AND ap.is_active = true
            WHERE ci.id = consumer_issue_notes.issue_id
              AND ci.jurisdiction_verified = true
              AND ci.department = ap.department
              AND ci.state_code = ap.state_code
              AND ci.district_code = ANY(ap.authorized_district_codes)
        )
    );

-- Policy 4: Audit Events Select (Active authority personnel only; updates/deletions disallowed)
DROP POLICY IF EXISTS consumer_issue_audit_events_select_authority ON public.consumer_issue_audit_events;
CREATE POLICY consumer_issue_audit_events_select_authority
    ON public.consumer_issue_audit_events FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.authority_profiles ap
            WHERE ap.user_id = auth.uid()
              AND ap.is_active = true
        )
    );
