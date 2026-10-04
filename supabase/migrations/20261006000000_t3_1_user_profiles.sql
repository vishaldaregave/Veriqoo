-- Migration: 20261006000000_t3_1_user_profiles.sql
-- Description: T3-1 User Profile Table for Veriqoo
-- References auth.users (Supabase built-in identity).

CREATE TABLE IF NOT EXISTS public.user_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL UNIQUE,
    display_name text,
    language_preference text NOT NULL DEFAULT 'en'
        CONSTRAINT user_profiles_language_check
            CHECK (language_preference IN ('en', 'hi', 'mr', 'ta', 'te', 'kn', 'gu', 'bn', 'pa')),
    app_role text NOT NULL DEFAULT 'consumer'
        CONSTRAINT user_profiles_app_role_check
            CHECK (app_role IN ('consumer', 'inspector', 'authority', 'admin')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT user_profiles_user_id_nonempty
        CHECK (user_id != '00000000-0000-0000-0000-000000000000'::uuid)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_profiles_user_id
    ON public.user_profiles(user_id);

CREATE INDEX IF NOT EXISTS idx_user_profiles_app_role
    ON public.user_profiles(app_role);
