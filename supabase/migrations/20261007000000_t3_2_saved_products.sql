-- Migration: 20261007000000_t3_2_saved_products.sql
-- Description: T3-2 Saved Products table for Veriqoo
-- References auth.users and public.inspection_sessions

CREATE TABLE IF NOT EXISTS public.saved_products (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    inspection_id uuid NOT NULL REFERENCES public.inspection_sessions(id) ON DELETE CASCADE,
    product_name text,
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT saved_products_user_inspection_unique UNIQUE (user_id, inspection_id),
    CONSTRAINT saved_products_user_id_nonempty CHECK (user_id != '00000000-0000-0000-0000-000000000000'::uuid)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_products_user_inspection
    ON public.saved_products(user_id, inspection_id);

CREATE INDEX IF NOT EXISTS idx_saved_products_user_id
    ON public.saved_products(user_id);

CREATE INDEX IF NOT EXISTS idx_saved_products_created_at
    ON public.saved_products(created_at DESC);
