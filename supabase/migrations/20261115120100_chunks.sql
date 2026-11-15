-- Filing chunks: one row per "{accession}:{chunk_index}", same ids and
-- metadata as the Chroma collection.
--
-- EMBED_DIM PLACEHOLDER: 2048 is provisional until scripts/probe_nim_embed.py
-- confirms the NIM embedding model. Every vector(N) in these migrations must
-- equal settings.nvidia_embed_dim (tests/test_migrations.py checks it).
create table public.chunks (
  id          text primary key,
  ticker      text    not null,
  form        text    not null default '',
  filing_date text    not null default '',
  accession   text    not null,
  section     text    not null default '',
  chunk_index integer not null,
  char_start  integer not null,
  char_end    integer not null,
  content     text    not null,
  embedding   extensions.vector(2048) not null,
  fts         tsvector generated always as (to_tsvector('english', content)) stored
);

-- No vector index: the corpus is small and exact search per ticker is fine.
-- (ticker, accession) also serves ticker-only filters and ticker_accessions().
create index chunks_ticker_idx on public.chunks (ticker, accession);
create index chunks_neighbour_idx on public.chunks (accession, section, chunk_index);
create index chunks_fts_idx on public.chunks using gin (fts);

-- Service role only: RLS on with no policies, and no grants to the public roles.
alter table public.chunks enable row level security;
revoke all on table public.chunks from anon, authenticated;
