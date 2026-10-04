-- Phase 4C: Vector similarity search RPC for normalized legal corpus embeddings.
-- Searches public.legal_corpus_embeddings without touching legacy public.match_legal_rules.
-- Vector dimension: 3072 (gemini-embedding-001).

CREATE OR REPLACE FUNCTION public.match_legal_corpus_embeddings(
    query_embedding extensions.vector(3072),
    match_count integer DEFAULT 10,
    filter_entity_type text DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    entity_type text,
    entity_id text,
    source_identifier text,
    provider text,
    model text,
    dimension integer,
    embedding_text_version text,
    embedding_text text,
    embedding_text_hash text,
    metadata jsonb,
    similarity float
)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, extensions
AS $$
    SELECT
        lce.id,
        lce.entity_type,
        lce.entity_id,
        lce.source_identifier,
        lce.provider,
        lce.model,
        lce.dimension,
        lce.embedding_text_version,
        lce.embedding_text,
        lce.embedding_text_hash,
        lce.metadata,
        (1 - (lce.embedding <=> query_embedding))::float AS similarity
    FROM public.legal_corpus_embeddings AS lce
    WHERE (filter_entity_type IS NULL OR lce.entity_type = filter_entity_type)
    ORDER BY lce.embedding <=> query_embedding
    LIMIT GREATEST(match_count, 1);
$$;

COMMENT ON FUNCTION public.match_legal_corpus_embeddings(extensions.vector, integer, text) IS
    'Returns matching legal corpus entity embeddings ranked by cosine similarity (Phase 4C). Preserves exact source and entity identity.';

-- Vector Index Note:
-- Exact cosine scan (<=>) for the bounded legal corpus (~960 entities) executes in <1 ms without an index.
-- IVFFlat requires training on substantial data (hundreds to thousands of rows) and HNSW introduces memory overhead.
-- Production ANN index creation is deferred until after complete embedding population and retrieval correctness validation.

