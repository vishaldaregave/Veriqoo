-- Migration: 20261015000000_t3_4_1_establishment_registry.sql
-- Description: Phase 7.4.1 Persistent Establishment Registry and Complaint Jurisdiction Verification Foundation
-- 1. Creates public.retail_establishments table with strict LGD jurisdiction mappings and verification status
-- 2. Extends public.consumer_issues with establishment binding and verification provenance
-- 3. Configures Row Level Security (RLS) restricting establishment access and write operations
-- 4. Introduces public.authority_verify_complaint_jurisdiction atomic RPC function
-- Security Boundary: SECURITY DEFINER with fixed search_path = public, pg_temp, and EXECUTE granted EXCLUSIVELY to service_role.

-- =====================================================================
-- 1. Retail Establishments Table
-- =====================================================================
CREATE TABLE IF NOT EXISTS public.retail_establishments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_name text NOT NULL,
    legal_name text,
    gstin varchar(15) UNIQUE,
    lm_license_number text,
    shop_establishment_number text,
    state_code text NOT NULL,
    district_code text NOT NULL,
    pincode varchar(6),
    physical_address text,
    verification_status varchar(30) NOT NULL DEFAULT 'PENDING',
    verification_provenance varchar(50) NOT NULL DEFAULT 'MANUAL',
    verification_authority_id uuid REFERENCES public.authority_profiles(id) ON DELETE SET NULL,
    verification_date timestamptz,
    verification_notes text,
    is_active boolean NOT NULL DEFAULT true,
    created_by uuid,
    updated_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT retail_establishments_trade_name_nonempty
        CHECK (length(trim(trade_name)) > 0),
    CONSTRAINT retail_establishments_state_code_nonempty
        CHECK (length(trim(state_code)) > 0),
    CONSTRAINT retail_establishments_district_code_nonempty
        CHECK (length(trim(district_code)) > 0),
    CONSTRAINT retail_establishments_verification_status_check
        CHECK (verification_status IN ('PENDING', 'VERIFIED', 'SUSPENDED', 'REVOKED')),
    CONSTRAINT retail_establishments_verification_provenance_check
        CHECK (verification_provenance IN ('MANUAL', 'ESTABLISHMENT_QR', 'VERIFIED_GSTIN_INVOICE', 'ADMIN_TRIAGE_VERIFICATION', 'OFFICIAL_REGISTRY'))
);

CREATE INDEX IF NOT EXISTS idx_retail_establishments_jurisdiction
    ON public.retail_establishments(state_code, district_code);

CREATE INDEX IF NOT EXISTS idx_retail_establishments_gstin
    ON public.retail_establishments(gstin)
    WHERE gstin IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_retail_establishments_verification
    ON public.retail_establishments(verification_status, is_active);

-- Reliable updated_at maintenance trigger for retail_establishments
CREATE OR REPLACE FUNCTION public.set_retail_establishments_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_retail_establishments_updated_at ON public.retail_establishments;
CREATE TRIGGER trigger_retail_establishments_updated_at
    BEFORE UPDATE ON public.retail_establishments
    FOR EACH ROW
    EXECUTE FUNCTION public.set_retail_establishments_updated_at();

-- =====================================================================
-- 2. Extend Consumer Issues with Establishment Association & Provenance
-- =====================================================================
ALTER TABLE public.consumer_issues
    ADD COLUMN IF NOT EXISTS establishment_id uuid REFERENCES public.retail_establishments(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS jurisdiction_provenance varchar(50) NOT NULL DEFAULT 'UNVERIFIED',
    ADD COLUMN IF NOT EXISTS jurisdiction_verified_at timestamptz,
    ADD COLUMN IF NOT EXISTS jurisdiction_verified_by uuid REFERENCES public.authority_profiles(id) ON DELETE SET NULL;

ALTER TABLE public.consumer_issues
    DROP CONSTRAINT IF EXISTS consumer_issues_provenance_check;
ALTER TABLE public.consumer_issues
    ADD CONSTRAINT consumer_issues_provenance_check
        CHECK (jurisdiction_provenance IN ('UNVERIFIED', 'ESTABLISHMENT_QR', 'VERIFIED_GSTIN_INVOICE', 'ADMIN_TRIAGE_VERIFICATION'));

CREATE INDEX IF NOT EXISTS idx_consumer_issues_establishment
    ON public.consumer_issues(establishment_id)
    WHERE establishment_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_consumer_issues_provenance
    ON public.consumer_issues(jurisdiction_provenance);

-- =====================================================================
-- 3. Row Level Security (RLS) Policies for Establishments
-- =====================================================================
ALTER TABLE public.retail_establishments ENABLE ROW LEVEL SECURITY;

-- Policy 1: Authenticated users can view active, verified establishments
DROP POLICY IF EXISTS retail_establishments_select_verified ON public.retail_establishments;
CREATE POLICY retail_establishments_select_verified
    ON public.retail_establishments FOR SELECT
    TO authenticated
    USING (verification_status = 'VERIFIED' AND is_active = true);

-- Policy 2: Active authority personnel can view establishments within their authorized jurisdiction
DROP POLICY IF EXISTS retail_establishments_select_authority ON public.retail_establishments;
CREATE POLICY retail_establishments_select_authority
    ON public.retail_establishments FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.authority_profiles ap
            WHERE ap.user_id = auth.uid()
              AND ap.is_active = true
              AND retail_establishments.state_code = ap.state_code
              AND retail_establishments.district_code = ANY(ap.authorized_district_codes)
        )
    );

-- Note: Direct client INSERT/UPDATE/DELETE on retail_establishments is disallowed.
-- Modifications must flow through trusted administrative RPCs or backend service_role.

-- =====================================================================
-- 4. Atomic Jurisdiction Verification RPC Function
-- =====================================================================
CREATE OR REPLACE FUNCTION public.authority_verify_complaint_jurisdiction(
    p_case_id uuid,
    p_establishment_id uuid,
    p_actor_id uuid,
    p_provenance text,
    p_verification_notes text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_case public.consumer_issues%ROWTYPE;
    v_updated_case public.consumer_issues%ROWTYPE;
    v_est public.retail_establishments%ROWTYPE;
    v_actor_profile public.authority_profiles%ROWTYPE;
    v_actor_role text;
    v_audit_event public.consumer_issue_audit_events%ROWTYPE;
    v_clean_provenance text;
    v_now timestamptz := clock_timestamp();
BEGIN
    -- 1. Actor Identity Validation
    IF p_actor_id IS NULL THEN
        RAISE EXCEPTION 'ACTOR_REQUIRED: Actor ID cannot be null' USING ERRCODE = '22023';
    END IF;

    -- If executed in an authenticated user session, prevent actor ID spoofing
    IF auth.uid() IS NOT NULL AND p_actor_id != auth.uid() THEN
        RAISE EXCEPTION 'ACTOR_MISMATCH: Provided actor ID % does not match authenticated identity %',
            p_actor_id, auth.uid() USING ERRCODE = '42501';
    END IF;

    -- 2. Validate Actor Active Profile
    SELECT * INTO v_actor_profile
    FROM public.authority_profiles
    WHERE user_id = p_actor_id;

    IF NOT FOUND OR v_actor_profile.is_active IS NOT TRUE THEN
        RAISE EXCEPTION 'ACTOR_UNAUTHORIZED: Actor % is not an active, provisioned authority',
            p_actor_id USING ERRCODE = '42501';
    END IF;

    -- Retrieve and validate actor app_role from user_profiles
    SELECT app_role INTO v_actor_role
    FROM public.user_profiles
    WHERE user_id = p_actor_id;

    IF v_actor_role IS NULL OR v_actor_role NOT IN ('authority', 'admin') THEN
        RAISE EXCEPTION 'ACTOR_ROLE_DENIED: Actor % does not have an authority or admin role (role: %)',
            p_actor_id, v_actor_role USING ERRCODE = '42501';
    END IF;

    -- 3. Lock Case Row Concurrency-Safely
    SELECT * INTO v_case
    FROM public.consumer_issues
    WHERE id = p_case_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'CASE_NOT_FOUND: Case % was not found', p_case_id USING ERRCODE = 'P0002';
    END IF;

    -- Case must not be terminal
    IF v_case.status IN ('RESOLVED', 'REJECTED') THEN
        RAISE EXCEPTION 'INVALID_CASE_STATUS: Terminal case % cannot have jurisdiction verified',
            p_case_id USING ERRCODE = '22023';
    END IF;

    -- Case department must match actor department
    IF v_actor_profile.department != v_case.department THEN
        RAISE EXCEPTION 'DEPARTMENT_MISMATCH: Case department % does not match officer department %',
            v_case.department, v_actor_profile.department USING ERRCODE = '42501';
    END IF;

    -- 4. Lock and Validate Establishment Row
    IF p_establishment_id IS NULL THEN
        RAISE EXCEPTION 'ESTABLISHMENT_REQUIRED: Establishment ID cannot be null' USING ERRCODE = '22023';
    END IF;

    SELECT * INTO v_est
    FROM public.retail_establishments
    WHERE id = p_establishment_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'ESTABLISHMENT_NOT_FOUND: Establishment % was not found',
            p_establishment_id USING ERRCODE = 'P0002';
    END IF;

    IF v_est.is_active IS NOT TRUE THEN
        RAISE EXCEPTION 'ESTABLISHMENT_INACTIVE: Establishment % is inactive',
            p_establishment_id USING ERRCODE = '42501';
    END IF;

    IF v_est.verification_status != 'VERIFIED' THEN
        RAISE EXCEPTION 'ESTABLISHMENT_UNVERIFIED: Establishment % is not verified (status: %)',
            p_establishment_id, v_est.verification_status USING ERRCODE = '42501';
    END IF;

    -- 5. Strict Jurisdiction Check: Officer must have jurisdiction over the establishment
    -- An officer must not verify complaints outside their authorized department, state, and district scope.
    IF v_actor_profile.state_code != v_est.state_code
       OR NOT (v_est.district_code = ANY(v_actor_profile.authorized_district_codes)) THEN
        RAISE EXCEPTION 'ACTOR_JURISDICTION_DENIED: Actor % is not authorized for establishment jurisdiction (% / %)',
            p_actor_id, v_est.state_code, v_est.district_code USING ERRCODE = '42501';
    END IF;

    -- 6. Validate Provenance
    v_clean_provenance := trim(COALESCE(p_provenance, ''));
    IF v_clean_provenance NOT IN ('ESTABLISHMENT_QR', 'VERIFIED_GSTIN_INVOICE', 'ADMIN_TRIAGE_VERIFICATION') THEN
        RAISE EXCEPTION 'INVALID_PROVENANCE: Provenance % is not valid',
            p_provenance USING ERRCODE = '22023';
    END IF;

    -- 7. Atomic Update of Case Row
    UPDATE public.consumer_issues
    SET state_code = v_est.state_code,
        district_code = v_est.district_code,
        jurisdiction_verified = TRUE,
        establishment_id = v_est.id,
        jurisdiction_provenance = v_clean_provenance,
        jurisdiction_verified_at = v_now,
        jurisdiction_verified_by = v_actor_profile.id,
        updated_at = v_now
    WHERE id = p_case_id
    RETURNING * INTO v_updated_case;

    -- 8. Atomic Insert of Audit Event
    INSERT INTO public.consumer_issue_audit_events (
        issue_id,
        actor_id,
        actor_role,
        event_type,
        previous_state,
        new_state,
        metadata,
        created_at
    ) VALUES (
        p_case_id,
        p_actor_id,
        v_actor_role,
        'JURISDICTION_VERIFIED',
        CASE WHEN v_case.jurisdiction_verified THEN 'VERIFIED' ELSE 'UNVERIFIED' END,
        'VERIFIED',
        jsonb_build_object(
            'actor_id', p_actor_id,
            'actor_role', v_actor_role,
            'establishment_id', v_est.id,
            'trade_name', v_est.trade_name,
            'state_code', v_est.state_code,
            'district_code', v_est.district_code,
            'provenance', v_clean_provenance,
            'verification_notes', trim(COALESCE(p_verification_notes, ''))
        ),
        v_now
    )
    RETURNING * INTO v_audit_event;

    -- 9. Return Composite State as JSON
    RETURN jsonb_build_object(
        'case', to_jsonb(v_updated_case),
        'establishment', to_jsonb(v_est),
        'audit_event', to_jsonb(v_audit_event)
    );
END;
$$;

COMMENT ON FUNCTION public.authority_verify_complaint_jurisdiction(uuid, uuid, uuid, text, text) IS
'Atomically validates authority scope against verified retail premises and binds consumer complaint to verified jurisdiction with audit event.';

-- =====================================================================
-- 5. Security Grants
-- =====================================================================
-- Revoke direct client access
REVOKE ALL ON FUNCTION public.authority_verify_complaint_jurisdiction(uuid, uuid, uuid, text, text) FROM PUBLIC, authenticated;

-- Grant execution EXCLUSIVELY to trusted backend service_role
GRANT EXECUTE ON FUNCTION public.authority_verify_complaint_jurisdiction(uuid, uuid, uuid, text, text) TO service_role;
