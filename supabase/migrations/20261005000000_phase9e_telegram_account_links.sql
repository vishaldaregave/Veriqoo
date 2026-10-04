-- Phase 9E-A: Secure Telegram Account Linking
-- Non-destructive migration creating persistent account link table.

CREATE TABLE IF NOT EXISTS public.telegram_account_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_user_id BIGINT NOT NULL UNIQUE,
    supabase_user_id UUID NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'REVOKED')),
    linked_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Unique constraint ensuring one active Telegram user per Supabase account
CREATE UNIQUE INDEX IF NOT EXISTS idx_telegram_active_supabase_user
    ON public.telegram_account_links (supabase_user_id)
    WHERE status = 'ACTIVE';

-- Index for rapid lookup by telegram_user_id
CREATE INDEX IF NOT EXISTS idx_telegram_account_links_tg_user
    ON public.telegram_account_links (telegram_user_id)
    WHERE status = 'ACTIVE';

