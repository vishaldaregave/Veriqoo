-- Migration: 20261010000001_t3_4_phase5_2_hardening.sql
-- Description: T3-4 Phase 5.2 Atomic Authority Hardening
-- 1. Assignment Concurrency: Always enforced with explicit unassigned representation (p_expect_unassigned boolean)
-- 2. Reassignment Least-Privilege: Cross-officer reassignment disabled in database RPC; only self-assignment is permitted until a verified supervisor hierarchy is established
-- 3. Atomic Investigation Notes: Introduces public.authority_create_case_note executing note insertion and NOTE_ADDED audit logging in a single atomic transaction
-- Security Boundary: SECURITY DEFINER with fixed search_path = public, pg_temp, and EXECUTE granted EXCLUSIVELY to service_role.

-- =====================================================================
-- 1. Clean Up Obsolete authority_assign_case Overloads
-- =====================================================================
REVOKE ALL ON FUNCTION public.authority_assign_case(uuid, uuid, uuid, uuid) FROM PUBLIC, authenticated, service_role;
DROP FUNCTION IF EXISTS public.authority_assign_case(uuid, uuid, uuid, uuid);

REVOKE ALL ON FUNCTION public.authority_assign_case(uuid, uuid, uuid, uuid, boolean) FROM PUBLIC, authenticated, service_role;
DROP FUNCTION IF EXISTS public.authority_assign_case(uuid, uuid, uuid, uuid, boolean);

-- =====================================================================
-- 2. Hardened Atomic Case Assignment RPC Function
-- =====================================================================
CREATE OR REPLACE FUNCTION public.authority_assign_case(
    p_case_id uuid,
    p_target_officer_id uuid,
    p_actor_id uuid,
    p_expected_assigned_officer_id uuid,
    p_expect_unassigned boolean
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

    -- 2. Least-Privilege Assignment Policy: Cross-officer assignment is disabled
    -- Only self-assignment is permitted until a verified supervisor hierarchy is approved.
    IF p_target_officer_id IS DISTINCT FROM p_actor_id THEN
        RAISE EXCEPTION 'CROSS_OFFICER_ASSIGNMENT_DENIED: Cross-officer assignment is disabled. Only self-assignment is permitted.'
            USING ERRCODE = '42501';
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

    -- 6. Mandatory Concurrency Precondition Enforcement
    IF p_expect_unassigned IS NULL THEN
        RAISE EXCEPTION 'CONCURRENCY_TOKEN_REQUIRED: p_expect_unassigned must be explicitly specified (true or false)'
            USING ERRCODE = '22023';
    END IF;

    IF p_expect_unassigned IS TRUE THEN
        IF v_case.assigned_officer_id IS NOT NULL THEN
            RAISE EXCEPTION 'CONCURRENT_UPDATE_CONFLICT: Expected case to be unassigned, but currently assigned to %',
                v_case.assigned_officer_id USING ERRCODE = 'P0004';
        END IF;
    ELSE
        IF p_expected_assigned_officer_id IS NULL THEN
            RAISE EXCEPTION 'CONCURRENCY_TOKEN_REQUIRED: expected_assigned_officer_id cannot be null when expect_unassigned is false'
                USING ERRCODE = '22023';
        END IF;

        IF v_case.assigned_officer_id IS DISTINCT FROM p_expected_assigned_officer_id THEN
            RAISE EXCEPTION 'CONCURRENT_UPDATE_CONFLICT: Expected assigned officer %, but current assigned officer is %',
                p_expected_assigned_officer_id, v_case.assigned_officer_id USING ERRCODE = 'P0004';
        END IF;
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
'Atomically self-assigns an investigating officer to a complaint with concurrent row locking, mandatory expected assignment precondition, and audit logging.';

REVOKE ALL ON FUNCTION public.authority_assign_case(uuid, uuid, uuid, uuid, boolean) FROM PUBLIC, authenticated;
GRANT EXECUTE ON FUNCTION public.authority_assign_case(uuid, uuid, uuid, uuid, boolean) TO service_role;


-- =====================================================================
-- 3. Atomic Investigation Note RPC Function
-- =====================================================================
CREATE OR REPLACE FUNCTION public.authority_create_case_note(
    p_case_id uuid,
    p_actor_id uuid,
    p_note_text text,
    p_metadata jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_case public.consumer_issues%ROWTYPE;
    v_actor_profile public.authority_profiles%ROWTYPE;
    v_actor_role text;
    v_clean_text text;
    v_note_id uuid := gen_random_uuid();
    v_note public.consumer_issue_notes%ROWTYPE;
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

    -- 2. Validate Note Content Length
    v_clean_text := trim(COALESCE(p_note_text, ''));
    IF length(v_clean_text) < 1 THEN
        RAISE EXCEPTION 'NOTE_EMPTY: Investigation note text cannot be empty or whitespace' USING ERRCODE = '22023';
    END IF;

    IF length(v_clean_text) > 5000 THEN
        RAISE EXCEPTION 'NOTE_TOO_LONG: Investigation note exceeds maximum allowed length of 5000 characters' USING ERRCODE = '22023';
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

    -- 6. Insert Confidential Investigation Note
    INSERT INTO public.consumer_issue_notes (
        id,
        issue_id,
        author_id,
        note_text,
        is_internal,
        created_at,
        updated_at
    ) VALUES (
        v_note_id,
        p_case_id,
        p_actor_id,
        v_clean_text,
        true,
        v_now,
        v_now
    )
    RETURNING * INTO v_note;

    -- 7. Atomic Insert of Audit Event (avoid storing confidential note text in audit metadata)
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
        'NOTE_ADDED',
        NULL,
        NULL,
        jsonb_build_object(
            'note_id', v_note_id,
            'author_id', p_actor_id,
            'note_length', length(v_clean_text)
        ),
        v_now
    )
    RETURNING * INTO v_audit_event;

    -- 8. Return Created Note and Audit Event Metadata
    RETURN jsonb_build_object(
        'note', to_jsonb(v_note),
        'audit_event', to_jsonb(v_audit_event)
    );
END;
$$;

COMMENT ON FUNCTION public.authority_create_case_note(uuid, uuid, text, jsonb) IS
'Atomically inserts a confidential investigation note and writes a NOTE_ADDED audit record with actor validation and row locking.';

REVOKE ALL ON FUNCTION public.authority_create_case_note(uuid, uuid, text, jsonb) FROM PUBLIC, authenticated;
GRANT EXECUTE ON FUNCTION public.authority_create_case_note(uuid, uuid, text, jsonb) TO service_role;
