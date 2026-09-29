-- Match legal-rule embeddings by cosine similarity.
create or replace function public.match_legal_rules(
  query_embedding extensions.vector(3072),
  match_count integer default 5
)
returns table (
  id bigint,
  source text,
  rule_number text,
  title text,
  content text,
  category text,
  similarity float
)
language sql
stable
security invoker
set search_path = public, extensions
as $$
  select
    legal_rules.id,
    legal_rules.source,
    legal_rules.rule_number,
    legal_rules.title,
    legal_rules.content,
    legal_rules.category,
    (1 - (legal_rules.embedding <=> query_embedding))::float as similarity
  from public.legal_rules
  where legal_rules.embedding is not null
  order by legal_rules.embedding <=> query_embedding
  limit greatest(match_count, 0);
$$;

comment on function public.match_legal_rules(extensions.vector(3072), integer) is
  'Returns legal rules ranked by cosine similarity to a 3072-dimensional embedding.';

-- Optional ANN index. The RPC remains correct without it, especially for 51 rows.
-- Run after embeddings are populated and only if the table grows substantially.
-- create index if not exists legal_rules_embedding_cosine_idx
--   on public.legal_rules using ivfflat (embedding extensions.vector_cosine_ops)
--   with (lists = 1);
