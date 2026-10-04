-- legal_documents and legal_provisions are created by Phase 1; their schema is authoritative.

CREATE TABLE IF NOT EXISTS public.legal_schedules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_identifier text NOT NULL UNIQUE,
    document_id bigint NOT NULL REFERENCES public.legal_documents(id) ON DELETE RESTRICT,
    schedule_number text NOT NULL,
    referenced_rule_number text,
    title text NOT NULL,
    raw_content text NOT NULL,
    normalized_content text NOT NULL,
    source_page integer,
    source_page_end integer,
    source_line_start integer,
    source_line_end integer,
    sequence integer NOT NULL,
    structure_status text NOT NULL,
    source_provision_id bigint NOT NULL REFERENCES public.legal_provisions(id) ON DELETE RESTRICT,
    referenced_provision_id bigint REFERENCES public.legal_provisions(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.legal_schedule_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_identifier text NOT NULL UNIQUE,
    schedule_id uuid NOT NULL REFERENCES public.legal_schedules(id) ON DELETE RESTRICT,
    table_id uuid,
    parent_entry_id uuid REFERENCES public.legal_schedule_entries(id) ON DELETE RESTRICT,
    entry_key text NOT NULL,
    entry_number text,
    entry_type text NOT NULL,
    item_text text,
    commodity_text text,
    quantity_text text,
    permitted_package_quantity text,
    cells jsonb NOT NULL DEFAULT '[]'::jsonb,
    raw_content text NOT NULL,
    normalized_content text NOT NULL,
    source_page integer,
    source_page_end integer,
    source_line_start integer,
    source_line_end integer,
    sequence integer NOT NULL,
    structure_status text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.legal_tables (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_identifier text NOT NULL UNIQUE,
    document_id bigint NOT NULL REFERENCES public.legal_documents(id) ON DELETE RESTRICT,
    schedule_id uuid REFERENCES public.legal_schedules(id) ON DELETE RESTRICT,
    provision_id bigint REFERENCES public.legal_provisions(id) ON DELETE RESTRICT,
    table_identifier text NOT NULL,
    title text,
    headers jsonb NOT NULL DEFAULT '[]'::jsonb,
    raw_content text NOT NULL,
    normalized_content text NOT NULL,
    source_page integer,
    source_page_end integer,
    source_line_start integer,
    source_line_end integer,
    sequence integer NOT NULL,
    structure_status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_legal_schedule_entries_table'
          AND conrelid = 'public.legal_schedule_entries'::regclass
    ) THEN
        ALTER TABLE public.legal_schedule_entries
            ADD CONSTRAINT fk_legal_schedule_entries_table
            FOREIGN KEY (table_id)
            REFERENCES public.legal_tables(id)
            ON DELETE RESTRICT;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS public.legal_amendments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_identifier text NOT NULL UNIQUE,
    document_id bigint NOT NULL REFERENCES public.legal_documents(id) ON DELETE RESTRICT,
    affected_provision_id bigint REFERENCES public.legal_provisions(id) ON DELETE RESTRICT,
    affected_schedule_id uuid REFERENCES public.legal_schedules(id) ON DELETE RESTRICT,
    amendment_identifier text,
    amendment_date date,
    effective_date date,
    raw_content text NOT NULL,
    normalized_content text NOT NULL,
    source_page integer,
    source_page_end integer,
    source_line_start integer,
    source_line_end integer,
    sequence integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.legal_requirements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_identifier text NOT NULL UNIQUE,
    provision_id bigint NOT NULL REFERENCES public.legal_provisions(id) ON DELETE RESTRICT,
    schedule_entry_id uuid REFERENCES public.legal_schedule_entries(id) ON DELETE RESTRICT,
    requirement_type text NOT NULL,
    requirement_text text NOT NULL,
    normalized_requirement text NOT NULL,
    subject text,
    condition_text text,
    obligation text,
    exception_text text,
    applicability_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    evidence_type text[] NOT NULL DEFAULT ARRAY[]::text[],
    source_quote text NOT NULL,
    source_reference jsonb NOT NULL,
    sequence integer NOT NULL,
    review_status text NOT NULL CHECK (review_status IN ('requires_review', 'reviewed')),
    effective_from date,
    effective_to date,
    is_active boolean,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_legal_provisions_rule_number
    ON public.legal_provisions(document_id, rule_number);
CREATE INDEX IF NOT EXISTS idx_legal_schedules_document_sequence
    ON public.legal_schedules(document_id, sequence);
CREATE INDEX IF NOT EXISTS idx_legal_schedule_entries_schedule_sequence
    ON public.legal_schedule_entries(schedule_id, sequence);
CREATE INDEX IF NOT EXISTS idx_legal_tables_schedule_sequence
    ON public.legal_tables(schedule_id, sequence);
CREATE INDEX IF NOT EXISTS idx_legal_tables_provision_sequence
    ON public.legal_tables(provision_id, sequence);
CREATE INDEX IF NOT EXISTS idx_legal_amendments_document_sequence
    ON public.legal_amendments(document_id, sequence);
CREATE INDEX IF NOT EXISTS idx_legal_requirements_provision_sequence
    ON public.legal_requirements(provision_id, sequence);
CREATE INDEX IF NOT EXISTS idx_legal_requirements_applicability
    ON public.legal_requirements USING gin(applicability_metadata);
CREATE INDEX IF NOT EXISTS idx_legal_requirements_effective_dates
    ON public.legal_requirements(effective_from, effective_to)
    WHERE is_active;

CREATE OR REPLACE FUNCTION public.set_legal_phase2_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    target_table text;
    trigger_name text;
BEGIN
    FOREACH target_table IN ARRAY ARRAY[
        'legal_documents',
        'legal_provisions',
        'legal_schedules',
        'legal_schedule_entries',
        'legal_tables',
        'legal_amendments',
        'legal_requirements'
    ] LOOP
        trigger_name := 'trg_' || target_table || '_phase2_updated_at';
        IF NOT EXISTS (
            SELECT 1
            FROM pg_trigger trigger_row
            JOIN pg_class table_row ON table_row.oid = trigger_row.tgrelid
            JOIN pg_namespace schema_row ON schema_row.oid = table_row.relnamespace
            WHERE trigger_row.tgname = trigger_name
              AND table_row.relname = target_table
              AND schema_row.nspname = 'public'
              AND NOT trigger_row.tgisinternal
        ) THEN
            EXECUTE format(
                'CREATE TRIGGER %I BEFORE UPDATE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.set_legal_phase2_updated_at()',
                trigger_name,
                target_table
            );
        END IF;
    END LOOP;
END
$$;