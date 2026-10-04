-- Migration: 20261010000000_t3_4_atomic_authority_rpc.sql
-- Description: T3-4 Phase 5 & 5.1 Atomic Authority Workflow RPC Functions
-- Provides atomic, concurrency-safe case assignment and status transitions with integrated audit logging.
-- Security Boundary: SECURITY DEFINER with fixed search_path, restricted service_role execution, mandatory concurrency tokens, and actor validation.

-- =====================================================================
-- 1. Atomic Case Assignment RPC Function
-- =====================================================================
CREATE OR REPLACE FUNCTION public.authority_assign_case(
    p_case_id uuid,
    p_target_officer_id uuid,
    p_actor_id uuid,
    p_expected_assigned_officer_id uuid DEFAULT NULL,
    p_enforce_concurrency boolean DEFAULT false
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_case public.consumer_issues%ROWTYPE;
    v_updated_case public.consumer_issues%ROWTYPE;
    v_actor_profile public.authority_profiles%ROWTYPE;
    v_target_profile public.authority_profiles%ROWTYPE;
    v_actor_role text;
    v_event_type text;
    v_audit_event public.consumer_issue_audit_events%ROWTYPE;
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

    -- 2. Lock Case Row Concurrency-Safely
    SELECT * INTO v_case
    FROM public.consumer_issues
    WHERE id = p_case_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'CASE_NOT_FOUND: Case % was not found', p_case_id USING ERRCODE = 'P0002';
    END IF;

    -- 3. Verify Case Jurisdiction
    IF v_case.jurisdiction_verified IS NOT TRUE THEN
        RAISE EXCEPTION 'JURISDICTION_UNVERIFIED: Case % jurisdiction is not verified', p_case_id USING ERRCODE = '42501';
    END IF;

    IF v_case.department IS NULL OR v_case.state_code IS NULL OR v_case.district_code IS NULL THEN
        RAISE EXCEPTION 'MALFORMED_JURISDICTION: Case % has malformed jurisdiction', p_case_id USING ERRCODE = '42501';
    END IF;

    -- 4. Validate Actor Active Profile & Case Jurisdiction Access
    SELECT * INTO v_actor_profile
    FROM public.authority_profiles
    WHERE user_id = p_actor_id;

    IF NOT FOUND OR v_actor_profile.is_active IS NOT TRUE THEN
        RAISE EXCEPTION 'ACTOR_UNAUTHORIZED: Actor % is not an active, provisioned authority', p_actor_id USING ERRCODE = '42501';
    END IF;

    -- Retrieve and validate actor app_role from user_profiles
    SELECT app_role INTO v_actor_role
    FROM public.user_profiles
    WHERE user_id = p_actor_id;

    IF v_actor_role IS NULL OR v_actor_role NOT IN ('authority', 'admin') THEN
        RAISE EXCEPTION 'ACTOR_ROLE_DENIED: Actor % does not have an authority or admin role (role: %)',
            p_actor_id, v_actor_role USING ERRCODE = '42501';
    END IF;

    -- Strict jurisdiction check (Admins do NOT receive global access; must match case jurisdiction)
    IF v_actor_profile.department != v_case.department
       OR v_actor_profile.state_code != v_case.state_code
       OR NOT (v_case.district_code = ANY(v_actor_profile.authorized_district_codes)) THEN
        RAISE EXCEPTION 'ACTOR_JURISDICTION_DENIED: Actor % is not authorized for case jurisdiction (% / % / %)',
            p_actor_id, v_case.department, v_case.state_code, v_case.district_code USING ERRCODE = '42501';
    END IF;

    -- 5. Validate Target Officer
    IF p_target_officer_id = p_actor_id THEN
        -- Self-assignment: actor profile already validated
        v_target_profile := v_actor_profile;
    ELSE
        SELECT * INTO v_target_profile
        FROM public.authority_profiles
        WHERE user_id = p_target_officer_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'TARGET_OFFICER_NOT_FOUND: Target officer % has no provisioned authority profile',
                p_target_officer_id USING ERRCODE = 'P0002';
        END IF;

        IF v_target_profile.is_active IS NOT TRUE THEN
            RAISE EXCEPTION 'TARGET_OFFICER_INACTIVE: Target officer % is inactive',
                p_target_officer_id USING ERRCODE = '42501';
        END IF;

        IF v_target_profile.department != v_case.department THEN
            RAISE EXCEPTION 'TARGET_DEPARTMENT_MISMATCH: Target officer department % does not match case department %',
                v_target_profile.department, v_case.department USING ERRCODE = '42501';
        END IF;

        IF v_target_profile.state_code != v_case.state_code
           OR NOT (v_case.district_code = ANY(v_target_profile.authorized_district_codes)) THEN
            RAISE EXCEPTION 'TARGET_JURISDICTION_MISMATCH: Case location (% / %) is outside target officer authorized jurisdiction',
                v_case.state_code, v_case.district_code USING ERRCODE = '42501';
        END IF;
    END IF;

    -- 6. Concurrency Check (Optimistic Locking Token)
    IF p_enforce_concurrency IS TRUE AND v_case.assigned_officer_id IS DISTINCT FROM p_expected_assigned_officer_id THEN
        RAISE EXCEPTION 'CONCURRENT_UPDATE_CONFLICT: Expected assigned officer %, but current assigned officer is %',
            p_expected_assigned_officer_id, v_case.assigned_officer_id USING ERRCODE = 'P0004';
    END IF;

    -- 7. Determine Audit Event Type
    IF v_case.assigned_officer_id IS NULL THEN
        v_event_type := 'CASE_ASSIGNED';
    ELSE
        v_event_type := 'CASE_REASSIGNED';
    END IF;

    -- 8. Atomic Update of Case Assignment
    UPDATE public.consumer_issues
    SET assigned_officer_id = p_target_officer_id,
        assigned_by = p_actor_id,
        assigned_at = v_now,
        updated_at = v_now
    WHERE id = p_case_id
    RETURNING * INTO v_updated_case;

    -- 9. Atomic Insert of Audit Event
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
        v_event_type,
        v_case.assigned_officer_id::text,
        p_target_officer_id::text,
        jsonb_build_object(
            'assigned_by', p_actor_id,
            'assigned_officer_id', p_target_officer_id,
            'previous_officer_id', v_case.assigned_officer_id,
            'assigned_at', v_now
        ),
        v_now
    )
    RETURNING * INTO v_audit_event;

    -- 10. Return Composite State as JSON
    RETURN jsonb_build_object(
        'case', to_jsonb(v_updated_case),
        'audit_event', to_jsonb(v_audit_event)
    );
END;
$$;

COMMENT ON FUNCTION public.authority_assign_case(uuid, uuid, uuid, uuid, boolean) IS
'Atomically assigns a primary investigating officer to a complaint with concurrent row locking, actor validation, and audit logging.';

-- =====================================================================
-- 2. Atomic Status Transition RPC Function
-- =====================================================================
CREATE OR REPLACE FUNCTION public.authority_transition_status(
    p_case_id uuid,
    p_new_status text,
    p_actor_id uuid,
    p_expected_status text,
    p_resolution_notes text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_case public.consumer_issues%ROWTYPE;
    v_updated_case public.consumer_issues%ROWTYPE;
    v_actor_profile public.authority_profiles%ROWTYPE;
    v_actor_role text;
    v_audit_event public.consumer_issue_audit_events%ROWTYPE;
    v_clean_notes text;
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

    -- 2. Concurrency Precondition Validation (Mandatory Token)
    IF p_expected_status IS NULL OR length(trim(p_expected_status)) = 0 THEN
        RAISE EXCEPTION 'CONCURRENCY_TOKEN_REQUIRED: expected_status token is mandatory for status transitions'
            USING ERRCODE = '22023';
    END IF;

    -- 3. Lock Case Row Concurrency-Safely
    SELECT * INTO v_case
    FROM public.consumer_issues
    WHERE id = p_case_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'CASE_NOT_FOUND: Case % was not found', p_case_id USING ERRCODE = 'P0002';
    END IF;

    -- 4. Verify Case Jurisdiction
    IF v_case.jurisdiction_verified IS NOT TRUE THEN
        RAISE EXCEPTION 'JURISDICTION_UNVERIFIED: Case % jurisdiction is not verified', p_case_id USING ERRCODE = '42501';
    END IF;

    IF v_case.department IS NULL OR v_case.state_code IS NULL OR v_case.district_code IS NULL THEN
        RAISE EXCEPTION 'MALFORMED_JURISDICTION: Case % has malformed jurisdiction', p_case_id USING ERRCODE = '42501';
    END IF;

    -- 5. Validate Actor Active Profile & Case Jurisdiction Access
    SELECT * INTO v_actor_profile
    FROM public.authority_profiles
    WHERE user_id = p_actor_id;

    IF NOT FOUND OR v_actor_profile.is_active IS NOT TRUE THEN
        RAISE EXCEPTION 'ACTOR_UNAUTHORIZED: Actor % is not an active, provisioned authority', p_actor_id USING ERRCODE = '42501';
    END IF;

    -- Retrieve and validate actor app_role from user_profiles
    SELECT app_role INTO v_actor_role
    FROM public.user_profiles
    WHERE user_id = p_actor_id;

    IF v_actor_role IS NULL OR v_actor_role NOT IN ('authority', 'admin') THEN
        RAISE EXCEPTION 'ACTOR_ROLE_DENIED: Actor % does not have an authority or admin role (role: %)',
            p_actor_id, v_actor_role USING ERRCODE = '42501';
    END IF;

    -- Strict jurisdiction check (Admins do NOT receive global access; must match case jurisdiction)
    IF v_actor_profile.department != v_case.department
       OR v_actor_profile.state_code != v_case.state_code
       OR NOT (v_case.district_code = ANY(v_actor_profile.authorized_district_codes)) THEN
        RAISE EXCEPTION 'ACTOR_JURISDICTION_DENIED: Actor % is not authorized for case jurisdiction (% / % / %)',
            p_actor_id, v_case.department, v_case.state_code, v_case.district_code USING ERRCODE = '42501';
    END IF;

    -- 6. Concurrency Check (Optimistic Locking)
    IF v_case.status != trim(p_expected_status) THEN
        RAISE EXCEPTION 'CONCURRENT_UPDATE_CONFLICT: Expected status %, but current status is %',
            p_expected_status, v_case.status USING ERRCODE = 'P0004';
    END IF;

    -- 7. Validate New Status Value
    IF p_new_status NOT IN ('SUBMITTED', 'UNDER_REVIEW', 'ACTION_TAKEN', 'RESOLVED', 'REJECTED') THEN
        RAISE EXCEPTION 'INVALID_STATUS: Status % is not recognized', p_new_status USING ERRCODE = '22023';
    END IF;

    -- 8. Validate Status Transition Matrix
    IF v_case.status = 'SUBMITTED' THEN
        IF p_new_status NOT IN ('UNDER_REVIEW', 'REJECTED') THEN
            RAISE EXCEPTION 'INVALID_STATUS_TRANSITION: Cannot transition case from SUBMITTED to %',
                p_new_status USING ERRCODE = '22023';
        END IF;
    ELSIF v_case.status = 'UNDER_REVIEW' THEN
        IF p_new_status NOT IN ('ACTION_TAKEN', 'RESOLVED', 'REJECTED') THEN
            RAISE EXCEPTION 'INVALID_STATUS_TRANSITION: Cannot transition case from UNDER_REVIEW to %',
                p_new_status USING ERRCODE = '22023';
        END IF;
    ELSIF v_case.status = 'ACTION_TAKEN' THEN
        IF p_new_status NOT IN ('RESOLVED', 'REJECTED') THEN
            RAISE EXCEPTION 'INVALID_STATUS_TRANSITION: Cannot transition case from ACTION_TAKEN to %',
                p_new_status USING ERRCODE = '22023';
        END IF;
    ELSIF v_case.status IN ('RESOLVED', 'REJECTED') THEN
        RAISE EXCEPTION 'INVALID_STATUS_TRANSITION: Case % is in terminal status % and cannot be transitioned',
            p_case_id, v_case.status USING ERRCODE = '22023';
    ELSE
        RAISE EXCEPTION 'INVALID_STATUS_TRANSITION: Unrecognized current status %',
            v_case.status USING ERRCODE = '22023';
    END IF;

    -- 9. Validate Required Resolution Notes
    v_clean_notes := trim(COALESCE(p_resolution_notes, ''));
    IF p_new_status IN ('ACTION_TAKEN', 'RESOLVED', 'REJECTED') THEN
        IF length(v_clean_notes) < 5 THEN
            RAISE EXCEPTION 'RESOLUTION_NOTES_REQUIRED: Transition to % requires substantive resolution notes (minimum 5 characters)',
                p_new_status USING ERRCODE = '22023';
        END IF;
    END IF;

    -- 10. Atomic Update of Case Status
    UPDATE public.consumer_issues
    SET status = p_new_status,
        resolution_notes = CASE
            WHEN length(v_clean_notes) > 0 THEN v_clean_notes
            ELSE resolution_notes
        END,
        updated_at = v_now
    WHERE id = p_case_id
    RETURNING * INTO v_updated_case;

    -- 11. Atomic Insert of Audit Event
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
        'STATUS_CHANGED',
        v_case.status,
        p_new_status,
        jsonb_build_object(
            'actor_id', p_actor_id,
            'actor_role', v_actor_role,
            'previous_status', v_case.status,
            'new_status', p_new_status,
            'resolution_notes', v_updated_case.resolution_notes
        ),
        v_now
    )
    RETURNING * INTO v_audit_event;

    -- 12. Return Composite State as JSON
    RETURN jsonb_build_object(
        'case', to_jsonb(v_updated_case),
        'audit_event', to_jsonb(v_audit_event)
    );
END;
$$;

COMMENT ON FUNCTION public.authority_transition_status(uuid, text, uuid, text, text) IS
'Atomically validates and transitions a complaint status with concurrent row locking, mandatory expected_status concurrency token, and audit logging.';

-- =====================================================================
-- 3. Security Boundary & Role Grants (Hardened in Phase 5.1)
-- =====================================================================
-- Prevent direct client manipulation: revoke default public AND authenticated access
REVOKE ALL ON FUNCTION public.authority_assign_case(uuid, uuid, uuid, uuid, boolean) FROM PUBLIC, authenticated;
REVOKE ALL ON FUNCTION public.authority_transition_status(uuid, text, uuid, text, text) FROM PUBLIC, authenticated;

-- Grant execution EXCLUSIVELY to trusted backend service_role.
-- Clients cannot invoke these RPCs directly over PostgREST; all requests must flow through FastAPI.
GRANT EXECUTE ON FUNCTION public.authority_assign_case(uuid, uuid, uuid, uuid, boolean) TO service_role;
GRANT EXECUTE ON FUNCTION public.authority_transition_status(uuid, text, uuid, text, text) TO service_role;
