CREATE TABLE IF NOT EXISTS public.applicability_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text,
    CONSTRAINT applicability_rules_rule_key_nonempty CHECK (length(btrim(rule_key)) > 0),
    CONSTRAINT applicability_rules_rule_key_unique UNIQUE (rule_key)
);

CREATE TABLE IF NOT EXISTS public.applicability_rule_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id uuid NOT NULL REFERENCES public.applicability_rules(id) ON DELETE RESTRICT,
    version_number integer NOT NULL,
    interpretation_status text NOT NULL,
    valid_from date,
    valid_to date,
    amendment_id uuid REFERENCES public.legal_amendments(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text,
    reviewed_at timestamptz,
    reviewed_by text,
    review_note text,
    CONSTRAINT applicability_rule_versions_number_positive CHECK (version_number > 0),
    CONSTRAINT applicability_rule_versions_status_check
        CHECK (interpretation_status IN ('draft', 'in_review', 'approved', 'rejected', 'retired')),
    CONSTRAINT applicability_rule_versions_date_order
        CHECK (valid_from IS NULL OR valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT applicability_rule_versions_rule_version_unique UNIQUE (rule_id, version_number)
);

CREATE TABLE IF NOT EXISTS public.applicability_condition_groups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_version_id uuid NOT NULL REFERENCES public.applicability_rule_versions(id) ON DELETE RESTRICT,
    parent_group_id uuid REFERENCES public.applicability_condition_groups(id) ON DELETE RESTRICT,
    group_purpose text NOT NULL,
    boolean_operator text NOT NULL,
    sequence integer NOT NULL,
    review_status text NOT NULL,
    reviewed_at timestamptz,
    reviewed_by text,
    CONSTRAINT applicability_condition_groups_purpose_check
        CHECK (group_purpose IN ('applicability', 'exception')),
    CONSTRAINT applicability_condition_groups_operator_check
        CHECK (boolean_operator IN ('AND', 'OR')),
    CONSTRAINT applicability_condition_groups_sequence_positive CHECK (sequence > 0),
    CONSTRAINT applicability_condition_groups_review_status_check
        CHECK (review_status IN ('draft', 'in_review', 'approved', 'rejected')),
    CONSTRAINT applicability_condition_groups_not_own_parent
        CHECK (parent_group_id IS NULL OR parent_group_id <> id)
);

CREATE TABLE IF NOT EXISTS public.applicability_conditions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id uuid NOT NULL REFERENCES public.applicability_condition_groups(id) ON DELETE RESTRICT,
    fact_key text NOT NULL,
    operator text NOT NULL,
    expected_value jsonb,
    expected_unit text,
    sequence integer NOT NULL,
    review_status text NOT NULL,
    reviewed_at timestamptz,
    reviewed_by text,
    CONSTRAINT applicability_conditions_fact_key_nonempty CHECK (length(btrim(fact_key)) > 0),
    CONSTRAINT applicability_conditions_operator_check
        CHECK (operator IN ('equals', 'not_equals', 'one_of', 'greater_than', 'greater_or_equal', 'less_than', 'less_or_equal', 'range_inclusive', 'exists')),
    CONSTRAINT applicability_conditions_expected_value_check
        CHECK (
            CASE
                WHEN operator = 'exists' THEN true
                WHEN operator = 'one_of' THEN
                    CASE
                        WHEN jsonb_typeof(expected_value) = 'array' THEN jsonb_array_length(expected_value) > 0
                        ELSE false
                    END
                WHEN operator = 'range_inclusive' THEN
                    CASE
                        WHEN jsonb_typeof(expected_value) = 'array' THEN jsonb_array_length(expected_value) = 2
                        ELSE false
                    END
                ELSE expected_value IS NOT NULL
            END
        ),
    CONSTRAINT applicability_conditions_sequence_positive CHECK (sequence > 0),
    CONSTRAINT applicability_conditions_review_status_check
        CHECK (review_status IN ('draft', 'in_review', 'approved', 'rejected'))
);

CREATE TABLE IF NOT EXISTS public.applicability_rule_sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_version_id uuid NOT NULL REFERENCES public.applicability_rule_versions(id) ON DELETE RESTRICT,
    requirement_id uuid NOT NULL REFERENCES public.legal_requirements(id) ON DELETE RESTRICT,
    provision_id bigint NOT NULL REFERENCES public.legal_provisions(id) ON DELETE RESTRICT,
    schedule_id uuid REFERENCES public.legal_schedules(id) ON DELETE RESTRICT,
    schedule_entry_id uuid REFERENCES public.legal_schedule_entries(id) ON DELETE RESTRICT,
    table_id uuid REFERENCES public.legal_tables(id) ON DELETE RESTRICT,
    amendment_id uuid REFERENCES public.legal_amendments(id) ON DELETE RESTRICT,
    condition_group_id uuid REFERENCES public.applicability_condition_groups(id) ON DELETE RESTRICT,
    condition_id uuid REFERENCES public.applicability_conditions(id) ON DELETE RESTRICT,
    source_role text NOT NULL,
    source_quote text NOT NULL,
    source_reference jsonb NOT NULL,
    review_status text NOT NULL,
    reviewed_at timestamptz,
    reviewed_by text,
    CONSTRAINT applicability_rule_sources_role_check
        CHECK (source_role IN ('supports', 'condition', 'exception', 'schedule_scope', 'amends')),
    CONSTRAINT applicability_rule_sources_quote_nonempty CHECK (length(btrim(source_quote)) > 0),
    CONSTRAINT applicability_rule_sources_reference_object CHECK (jsonb_typeof(source_reference) = 'object'),
    CONSTRAINT applicability_rule_sources_role_links_check
        CHECK (
            (source_role = 'supports')
            OR (source_role = 'condition' AND (condition_group_id IS NOT NULL OR condition_id IS NOT NULL))
            OR (source_role = 'exception' AND condition_group_id IS NOT NULL)
            OR (source_role = 'schedule_scope' AND (schedule_id IS NOT NULL OR schedule_entry_id IS NOT NULL OR table_id IS NOT NULL))
            OR (source_role = 'amends' AND amendment_id IS NOT NULL)
        ),
    CONSTRAINT applicability_rule_sources_review_status_check
        CHECK (review_status IN ('draft', 'in_review', 'approved', 'rejected'))
);

CREATE TABLE IF NOT EXISTS public.applicability_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_reference text NOT NULL,
    inspection_date date,
    created_at timestamptz NOT NULL DEFAULT now(),
    engine_version text NOT NULL,
    status text NOT NULL,
    CONSTRAINT applicability_runs_reference_nonempty CHECK (length(btrim(inspection_reference)) > 0),
    CONSTRAINT applicability_runs_engine_version_nonempty CHECK (length(btrim(engine_version)) > 0),
    CONSTRAINT applicability_runs_status_check
        CHECK (status IN ('draft', 'evaluated', 'review_required', 'finalized'))
);

CREATE TABLE IF NOT EXISTS public.inspection_facts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES public.applicability_runs(id) ON DELETE RESTRICT,
    fact_key text NOT NULL,
    value jsonb,
    unit text,
    fact_status text NOT NULL,
    origin text NOT NULL,
    evidence_reference jsonb,
    observed_text text,
    sequence integer NOT NULL,
    review_status text NOT NULL,
    CONSTRAINT inspection_facts_key_nonempty CHECK (length(btrim(fact_key)) > 0),
    CONSTRAINT inspection_facts_status_check
        CHECK (fact_status IN ('known', 'unknown', 'not_observed', 'not_applicable')),
    CONSTRAINT inspection_facts_value_status_check
        CHECK ((fact_status = 'known' AND value IS NOT NULL) OR (fact_status <> 'known' AND value IS NULL)),
    CONSTRAINT inspection_facts_sequence_positive CHECK (sequence > 0),
    CONSTRAINT inspection_facts_review_status_check
        CHECK (review_status IN ('draft', 'in_review', 'approved', 'rejected')),
    CONSTRAINT inspection_facts_evidence_reference_object
        CHECK (evidence_reference IS NULL OR jsonb_typeof(evidence_reference) = 'object')
);

CREATE TABLE IF NOT EXISTS public.applicability_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES public.applicability_runs(id) ON DELETE RESTRICT,
    rule_version_id uuid NOT NULL REFERENCES public.applicability_rule_versions(id) ON DELETE RESTRICT,
    result text NOT NULL,
    reason text NOT NULL,
    evidence_needed jsonb NOT NULL DEFAULT '[]'::jsonb,
    review_status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    reviewed_by text,
    CONSTRAINT applicability_decisions_result_check
        CHECK (result IN ('applicable', 'not_applicable', 'unknown')),
    CONSTRAINT applicability_decisions_reason_nonempty CHECK (length(btrim(reason)) > 0),
    CONSTRAINT applicability_decisions_evidence_needed_array CHECK (jsonb_typeof(evidence_needed) = 'array'),
    CONSTRAINT applicability_decisions_review_status_check
        CHECK (review_status IN ('draft', 'in_review', 'approved', 'rejected')),
    CONSTRAINT applicability_decisions_run_version_unique UNIQUE (run_id, rule_version_id)
);

CREATE TABLE IF NOT EXISTS public.applicability_decision_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id uuid NOT NULL REFERENCES public.applicability_decisions(id) ON DELETE RESTRICT,
    condition_id uuid REFERENCES public.applicability_conditions(id) ON DELETE RESTRICT,
    fact_id uuid REFERENCES public.inspection_facts(id) ON DELETE RESTRICT,
    source_link_id uuid REFERENCES public.applicability_rule_sources(id) ON DELETE RESTRICT,
    evaluation text NOT NULL,
    reason text NOT NULL,
    CONSTRAINT applicability_decision_evidence_evaluation_check
        CHECK (evaluation IN ('true', 'false', 'unknown', 'not_evaluated')),
    CONSTRAINT applicability_decision_evidence_reason_nonempty CHECK (length(btrim(reason)) > 0),
    CONSTRAINT applicability_decision_evidence_has_reference
        CHECK (condition_id IS NOT NULL OR fact_id IS NOT NULL OR source_link_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_applicability_rule_versions_rule_status
    ON public.applicability_rule_versions(rule_id, interpretation_status);
CREATE INDEX IF NOT EXISTS idx_applicability_rule_versions_validity
    ON public.applicability_rule_versions(valid_from, valid_to);
CREATE INDEX IF NOT EXISTS idx_applicability_condition_groups_version_purpose
    ON public.applicability_condition_groups(rule_version_id, group_purpose);
CREATE INDEX IF NOT EXISTS idx_applicability_condition_groups_parent_sequence
    ON public.applicability_condition_groups(parent_group_id, sequence);
CREATE INDEX IF NOT EXISTS idx_applicability_conditions_group_sequence
    ON public.applicability_conditions(group_id, sequence);
CREATE INDEX IF NOT EXISTS idx_applicability_conditions_fact_status
    ON public.applicability_conditions(fact_key, review_status);
CREATE INDEX IF NOT EXISTS idx_applicability_rule_sources_requirement
    ON public.applicability_rule_sources(requirement_id);
CREATE INDEX IF NOT EXISTS idx_applicability_rule_sources_provision
    ON public.applicability_rule_sources(provision_id);
CREATE INDEX IF NOT EXISTS idx_applicability_rule_sources_schedule_entry
    ON public.applicability_rule_sources(schedule_id, schedule_entry_id);
CREATE INDEX IF NOT EXISTS idx_applicability_rule_sources_amendment
    ON public.applicability_rule_sources(amendment_id);
CREATE INDEX IF NOT EXISTS idx_applicability_runs_inspection_created
    ON public.applicability_runs(inspection_reference, created_at);
CREATE INDEX IF NOT EXISTS idx_applicability_runs_inspection_date
    ON public.applicability_runs(inspection_date);
CREATE INDEX IF NOT EXISTS idx_inspection_facts_run_key
    ON public.inspection_facts(run_id, fact_key);
CREATE INDEX IF NOT EXISTS idx_inspection_facts_run_status
    ON public.inspection_facts(run_id, fact_status);
CREATE INDEX IF NOT EXISTS idx_applicability_decisions_run_result
    ON public.applicability_decisions(run_id, result);
CREATE INDEX IF NOT EXISTS idx_applicability_decisions_version_review
    ON public.applicability_decisions(rule_version_id, review_status);
CREATE INDEX IF NOT EXISTS idx_applicability_decision_evidence_decision
    ON public.applicability_decision_evidence(decision_id);
CREATE INDEX IF NOT EXISTS idx_applicability_decision_evidence_condition
    ON public.applicability_decision_evidence(condition_id);
CREATE INDEX IF NOT EXISTS idx_applicability_decision_evidence_fact
    ON public.applicability_decision_evidence(fact_id);

COMMENT ON COLUMN public.applicability_decisions.rule_version_id IS
    'The applicability engine/service must reject every version whose interpretation_status is not approved; this cross-table gate is not enforced by a CHECK constraint.';