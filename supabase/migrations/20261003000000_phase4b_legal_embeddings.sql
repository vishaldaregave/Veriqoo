-- Phase 4B: Persistent vector embeddings for normalized legal corpus entities.
-- Decoupled from core statutory tables (legal_requirements, legal_provisions, etc.).
-- Preserves legacy public.legal_rules (51 rows) and match_legal_rules unchanged.

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

CREATE TABLE IF NOT EXISTS public.legal_corpus_embeddings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL CHECK (
        entity_type IN (
            'requirement',
            'provision',
            'schedule_entry',
            'table',
            'amendment'
        )
    ),
    entity_id text NOT NULL,
    source_identifier text NOT NULL,
    provider text NOT NULL DEFAULT 'gemini',
    model text NOT NULL DEFAULT 'gemini-embedding-001',
    dimension integer NOT NULL DEFAULT 3072,
    embedding_text_version text NOT NULL DEFAULT 'v1',
    embedding_text text NOT NULL,
    embedding_text_hash text NOT NULL,
    embedding extensions.vector(3072) NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_legal_corpus_embedding_version UNIQUE (
        entity_type,
        entity_id,
        model,
        embedding_text_version
    )
);

CREATE INDEX IF NOT EXISTS idx_legal_corpus_embeddings_entity
    ON public.legal_corpus_embeddings(entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_legal_corpus_embeddings_source
    ON public.legal_corpus_embeddings(source_identifier);

CREATE INDEX IF NOT EXISTS idx_legal_corpus_embeddings_model_version
    ON public.legal_corpus_embeddings(model, embedding_text_version);

CREATE INDEX IF NOT EXISTS idx_legal_corpus_embeddings_hash
    ON public.legal_corpus_embeddings(embedding_text_hash);

COMMENT ON TABLE public.legal_corpus_embeddings IS
    'Persistent vector embeddings for normalized legal corpus entities (Phase 4B). Decoupled from core statutory tables.';

COMMENT ON COLUMN public.legal_corpus_embeddings.embedding IS
    'RETRIEVAL_DOCUMENT vector embedding with 3072 dimensions from gemini-embedding-001.';
