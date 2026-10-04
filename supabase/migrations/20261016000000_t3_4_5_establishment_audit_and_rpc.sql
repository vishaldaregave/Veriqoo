-- Migration: 20261016000000_t3_4_5_establishment_audit_and_rpc.sql
-- Description: Phase 7.5 Atomic Establishment Review, Row Locking, Concurrency Tokens, and Audit Trail
-- 1. Creates public.retail_establishment_audit_events table for tamper-evident review history
-- 2. Configures Row Level Security (RLS) restricting audit event read access to authorized territorial authorities
-- 3. Creates public.authority_review_establishment atomic RPC function with:
--    - Exclusive row locking (FOR UPDATE)
--    - Mandatory expected-status optimistic concurrency token (ERRCODE 40001 on conflict)
--    - Actor active-profile, department, role, and jurisdiction verification
--    - Explicit rejection of terminal (REVOKED) or disallowed lifecycle state transitions
--    - Distinction of original certifying officer (verification_authority_id) vs. latest reviewer (updated_by)
--    - Atomic audit event insertion with full transactional rollback
-- Security Boundary: SECURITY DEFINER with fixed search_path = public, pg_temp, and EXECUTE granted EXCLUSIVELY to service_role.

-- =====================================================================
-- 1. Retail Establishment Audit Events Table
-- =====================================================================
CREATE TABLE IF NOT EXISTS public.retail_establishment_audit_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    establishment_id uuid NOT NULL REFERENCES public.retail_establishments(id) ON DELETE CASCADE,
    actor_id uuid NOT NULL,
    actor_role text NOT NULL,
    action text NOT NULL,
    event_type text NOT NULL,
    previous_status text NOT NULL,
    new_status text NOT NULL,
    previous_is_active boolean NOT NULL,
    new_is_active boolean NOT NULL,
    notes text,
    provenance text NOT NULL DEFAULT 'MANUAL',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT retail_establishment_audit_events_actor_id_nonempty
        CHECK (actor_id != '00000000-0000-0000-0000-000000000000'::uuid),
    CONSTRAINT retail_establishment_audit_events_action_check
        CHECK (action IN ('VERIFY', 'SUSPEND', 'REVOKE')),
    CONSTRAINT retail_establishment_audit_events_metadata_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_retail_est_audit_est_created
    ON public.retail_establishment_audit_events(establishment_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_retail_est_audit_actor_created
    ON public.retail_establishment_audit_events(actor_id, created_at DESC);

-- =====================================================================
-- 2. Row Level Security (RLS) for Audit Events
-- =====================================================================
ALTER TABLE public.retail_establishment_audit_events ENABLE ROW LEVEL SECURITY;

-- Policy: Active authority officers can view audit events for establishments in their jurisdiction
DROP POLICY IF EXISTS retail_establishment_audit_events_select_authority ON public.retail_establishment_audit_events;
CREATE POLICY retail_establishment_audit_events_select_authority
    ON public.retail_establishment_audit_events FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.authority_profiles ap
            JOIN public.retail_establishments re ON re.id = retail_establishment_audit_events.establishment_id
            WHERE ap.user_id = auth.uid()
              AND ap.is_active = true
              AND re.state_code = ap.state_code
              AND (ap.jurisdiction_level = 'STATE' OR re.district_code = ANY(ap.authorized_district_codes))
        )
    );

-- Note: No client INSERT/UPDATE/DELETE policies are granted on retail_establishment_audit_events.
-- Audit events are inserted exclusively through the atomic SECURITY DEFINER RPC.

-- =====================================================================
-- 3. Atomic Establishment Review RPC Function
-- =====================================================================
CREATE OR REPLACE FUNCTION public.authority_review_establishment(
    p_establishment_id uuid,
    p_action text,
    p_actor_id uuid,
    p_expected_status text,
    p_notes text DEFAULT NULL,
    p_provenance text DEFAULT 'MANUAL'
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_est public.retail_establishments%ROWTYPE;
    v_updated_est public.retail_establishments%ROWTYPE;
    v_actor_profile public.authority_profiles%ROWTYPE;
    v_actor_role text;
    v_clean_action text;
    v_clean_expected text;
    v_clean_provenance text;
    v_new_status text;
    v_new_is_active boolean;
    v_audit_event public.retail_establishment_audit_events%ROWTYPE;
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

    -- 2. Concurrency Precondition Validation (Mandatory Expected Status Token)
    v_clean_expected := trim(COALESCE(p_expected_status, ''));
    IF length(v_clean_expected) = 0 THEN
        RAISE EXCEPTION 'CONCURRENCY_TOKEN_REQUIRED: expected_status token is mandatory for establishment review'
            USING ERRCODE = '22023';
    END IF;

    -- 3. Action Validation
    v_clean_action := upper(trim(COALESCE(p_action, '')));
    IF v_clean_action NOT IN ('VERIFY', 'SUSPEND', 'REVOKE') THEN
        RAISE EXCEPTION 'INVALID_REVIEW_ACTION: Action % is not valid (must be VERIFY, SUSPEND, or REVOKE)',
            p_action USING ERRCODE = '22023';
    END IF;

    -- 4. Validate Actor Active Profile & Role
    SELECT * INTO v_actor_profile
    FROM public.authority_profiles
    WHERE user_id = p_actor_id;

    IF NOT FOUND OR v_actor_profile.is_active IS NOT TRUE THEN
        RAISE EXCEPTION 'ACTOR_UNAUTHORIZED: Actor % is not an active, provisioned authority',
            p_actor_id USING ERRCODE = '42501';
    END IF;

    SELECT app_role INTO v_actor_role
    FROM public.user_profiles
    WHERE user_id = p_actor_id;

    IF v_actor_role IS NULL OR v_actor_role NOT IN ('authority', 'admin') THEN
        RAISE EXCEPTION 'ACTOR_ROLE_DENIED: Actor % does not have an authority or admin role (role: %)',
            p_actor_id, v_actor_role USING ERRCODE = '42501';
    END IF;

    -- 5. Lock Establishment Row Exclusively (Row-level concurrency protection)
    SELECT * INTO v_est
    FROM public.retail_establishments
    WHERE id = p_establishment_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'ESTABLISHMENT_NOT_FOUND: Establishment % was not found',
            p_establishment_id USING ERRCODE = 'P0002';
    END IF;

    -- 6. Strict Territorial Jurisdiction Enforcement
    IF v_actor_profile.state_code != v_est.state_code
       OR (v_actor_profile.jurisdiction_level = 'DISTRICT' AND NOT (v_est.district_code = ANY(v_actor_profile.authorized_district_codes))) THEN
        RAISE EXCEPTION 'ACTOR_JURISDICTION_DENIED: Actor % is not authorized for establishment jurisdiction (% / %)',
            p_actor_id, v_est.state_code, v_est.district_code USING ERRCODE = '42501';
    END IF;

    -- 7. Concurrency Conflict Precondition Check (Optimistic Locking)
    IF v_est.verification_status != v_clean_expected THEN
        RAISE EXCEPTION 'CONCURRENT_UPDATE_CONFLICT: Establishment status is % but expected %',
            v_est.verification_status, v_clean_expected USING ERRCODE = '40001';
    END IF;

    -- 8. Lifecycle State Transition Rules
    -- Terminal check: Revoked establishments cannot be modified
    IF v_est.verification_status = 'REVOKED' THEN
        RAISE EXCEPTION 'TERMINAL_ESTABLISHMENT_STATE: Establishment % is permanently revoked and cannot be transitioned',
            p_establishment_id USING ERRCODE = '22023';
    END IF;

    -- Pending establishments cannot be suspended prior to initial verification
    IF v_est.verification_status = 'PENDING' AND v_clean_action = 'SUSPEND' THEN
        RAISE EXCEPTION 'INVALID_LIFECYCLE_TRANSITION: Cannot suspend establishment % from PENDING status',
            p_establishment_id USING ERRCODE = '22023';
    END IF;

    -- 9. Determine Target State
    IF v_clean_action = 'VERIFY' THEN
        v_new_status := 'VERIFIED';
        v_new_is_active := TRUE;
        v_clean_provenance := upper(trim(COALESCE(p_provenance, 'MANUAL')));
        IF v_clean_provenance NOT IN ('MANUAL', 'ESTABLISHMENT_QR', 'VERIFIED_GSTIN_INVOICE', 'ADMIN_TRIAGE_VERIFICATION', 'OFFICIAL_REGISTRY') THEN
            v_clean_provenance := 'MANUAL';
        END IF;
    ELSIF v_clean_action = 'SUSPEND' THEN
        v_new_status := 'SUSPENDED';
        v_new_is_active := FALSE;
        v_clean_provenance := v_est.verification_provenance;
    ELSIF v_clean_action = 'REVOKE' THEN
        v_new_status := 'REVOKED';
        v_new_is_active := FALSE;
        v_clean_provenance := v_est.verification_provenance;
    END IF;

    -- 10. Atomic Update of Retail Establishment Row
    -- Crucial: Preserves original certifying officer (verification_authority_id) on suspension/revocation,
    -- while recording the review actor in updated_by and the audit trail.
    UPDATE public.retail_establishments
    SET verification_status = v_new_status,
        is_active = v_new_is_active,
        verification_provenance = v_clean_provenance,
        verification_notes = CASE WHEN p_notes IS NOT NULL THEN trim(p_notes) ELSE verification_notes END,
        verification_authority_id = CASE WHEN v_clean_action = 'VERIFY' THEN v_actor_profile.id ELSE verification_authority_id END,
        verification_date = CASE WHEN v_clean_action = 'VERIFY' THEN v_now ELSE verification_date END,
        updated_by = p_actor_id,
        updated_at = v_now
    WHERE id = p_establishment_id
    RETURNING * INTO v_updated_est;

    -- 11. Atomic Insert of Tamper-Evident Audit Event (commits or rolls back together)
    INSERT INTO public.retail_establishment_audit_events (
        establishment_id,
        actor_id,
        actor_role,
        action,
        event_type,
        previous_status,
        new_status,
        previous_is_active,
        new_is_active,
        notes,
        provenance,
        metadata,
        created_at
    ) VALUES (
        p_establishment_id,
        p_actor_id,
        v_actor_role,
        v_clean_action,
        'ESTABLISHMENT_' || v_clean_action,
        v_est.verification_status,
        v_new_status,
        v_est.is_active,
        v_new_is_active,
        trim(p_notes),
        v_clean_provenance,
        jsonb_build_object(
            'actor_id', p_actor_id,
            'actor_role', v_actor_role,
            'authority_profile_id', v_actor_profile.id,
            'action', v_clean_action,
            'previous_status', v_est.verification_status,
            'new_status', v_new_status,
            'previous_is_active', v_est.is_active,
            'new_is_active', v_new_is_active,
            'notes', trim(p_notes),
            'provenance', v_clean_provenance,
            'timestamp', v_now
        ),
        v_now
    )
    RETURNING * INTO v_audit_event;

    -- 12. Return Composite JSON State
    RETURN jsonb_build_object(
        'establishment', to_jsonb(v_updated_est),
        'audit_event', to_jsonb(v_audit_event)
    );
END;
$$;

COMMENT ON FUNCTION public.authority_review_establishment(uuid, text, uuid, text, text, text) IS
'Atomically validates authority scope, locks establishment row, checks expected status concurrency token, updates establishment status, and records tamper-evident audit event.';

-- =====================================================================
-- 4. Security Grants
-- =====================================================================
-- Revoke direct execution from public and standard authenticated clients
REVOKE ALL ON FUNCTION public.authority_review_establishment(uuid, text, uuid, text, text, text) FROM PUBLIC, authenticated;

-- Grant execution EXCLUSIVELY to trusted backend service_role
GRANT EXECUTE ON FUNCTION public.authority_review_establishment(uuid, text, uuid, text, text, text) TO service_role;
