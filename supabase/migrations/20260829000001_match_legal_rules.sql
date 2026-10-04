-- Match legal-rule embeddings by cosine similarity.
do $migration$
begin
  if not exists (
    select 1
    from pg_proc function_row
    join pg_namespace function_namespace on function_namespace.oid = function_row.pronamespace
    where function_namespace.nspname = 'public'
      and function_row.proname = 'match_legal_rules'
      and function_row.pronargs = 2
      and function_row.proargtypes[0] = 'extensions.vector'::regtype
      and function_row.proargtypes[1] = 'pg_catalog.int4'::regtype
  ) then
    execute $create_function$
      create function public.match_legal_rules(
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
      as $function_body$
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
      $function_body$;
    $create_function$;

    execute $comment_function$
      comment on function public.match_legal_rules(extensions.vector, integer) is
        'Returns legal rules ranked by cosine similarity to a 3072-dimensional embedding.';
    $comment_function$;
  end if;
end
$migration$;

-- Optional ANN index. The RPC remains correct without it, especially for 51 rows.
-- Run after embeddings are populated and only if the table grows substantially.
-- create index if not exists legal_rules_embedding_cosine_idx
--   on public.legal_rules using ivfflat (embedding extensions.vector_cosine_ops)
--   with (lists = 1);
