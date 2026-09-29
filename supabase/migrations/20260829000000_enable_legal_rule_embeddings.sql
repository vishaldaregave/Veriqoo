-- Enable pgvector and add the exact dimension used by gemini-embedding-001.
create extension if not exists vector with schema extensions;

do $$
begin
  if not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'legal_rules'
      and column_name = 'embedding'
  ) then
    alter table public.legal_rules
      add column embedding extensions.vector(3072);
  elsif (
    select format_type(a.atttypid, a.atttypmod)
    from pg_attribute a
    join pg_class c on c.oid = a.attrelid
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relname = 'legal_rules'
      and a.attname = 'embedding'
      and not a.attisdropped
  ) <> 'vector(3072)' then
    raise exception
      'public.legal_rules.embedding must be vector(3072) for gemini-embedding-001';
  end if;
end
$$;

comment on column public.legal_rules.embedding is
  'RETRIEVAL_DOCUMENT embedding from gemini-embedding-001; 3072 dimensions';
