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
  elsif not exists (
    select 1
    from pg_attribute column_row
    join pg_class table_row on table_row.oid = column_row.attrelid
    join pg_namespace table_namespace on table_namespace.oid = table_row.relnamespace
    join pg_type type_row on type_row.oid = column_row.atttypid
    join pg_namespace type_namespace on type_namespace.oid = type_row.typnamespace
    where table_namespace.nspname = 'public'
      and table_row.relname = 'legal_rules'
      and column_row.attname = 'embedding'
      and not column_row.attisdropped
      and type_namespace.nspname = 'extensions'
      and type_row.typname = 'vector'
      and column_row.atttypmod = 3072
  ) then
    raise exception
      'public.legal_rules.embedding must be vector(3072) for gemini-embedding-001';
  end if;
end
$$;

comment on column public.legal_rules.embedding is
  'RETRIEVAL_DOCUMENT embedding from gemini-embedding-001; 3072 dimensions';
