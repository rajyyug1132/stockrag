-- Hybrid retrieval for one ticker: vector leg + full-text leg, fused with
-- reciprocal rank fusion (k = 60). Each hit carries its section neighbours
-- (chunk_index within +-win, same accession and section, hit included,
-- ordered by char_start) so the API can widen context without a second query.
--
-- EMBED_DIM PLACEHOLDER: see 20261115120100_chunks.sql.
--
-- SECURITY INVOKER on purpose: with RLS on and no policies only service_role
-- gets rows. DEFINER would bypass RLS. A new overload gets Supabase's default
-- grants again and needs its own revoke.
create or replace function public.hybrid_search(
  q           text,
  q_embedding extensions.vector(2048),
  p_ticker    text,
  n           integer default 30,
  win         integer default 1
)
returns table (
  id          text,
  ticker      text,
  form        text,
  filing_date text,
  accession   text,
  section     text,
  chunk_index integer,
  char_start  integer,
  char_end    integer,
  content     text,
  score       double precision,
  neighbours  jsonb
)
language sql
stable
set search_path = ''
as $$
  with terms as (
    -- Natural-language questions must not be AND-ed: OR the stemmed terms
    -- of q. Each lexeme goes through plainto_tsquery('simple') so odd
    -- characters are quoted safely; no terms (empty or all stopwords) gives
    -- a NULL query, which matches nothing.
    select string_agg('(' || t::text || ')', ' | ')::tsquery as tsq
    from unnest(tsvector_to_array(to_tsvector('english'::regconfig, q))) as l(lexeme),
         lateral plainto_tsquery('simple'::regconfig, l.lexeme) as t
    where t::text <> ''
  ),
  vec as (
    select c.id,
           row_number() over (order by c.embedding operator(extensions.<=>) q_embedding, c.id) as rnk
    from public.chunks c
    where c.ticker = p_ticker
    order by c.embedding operator(extensions.<=>) q_embedding, c.id
    limit n
  ),
  txt as (
    select c.id,
           row_number() over (order by ts_rank_cd(c.fts, terms.tsq) desc, c.id) as rnk
    from public.chunks c, terms
    where c.ticker = p_ticker and c.fts @@ terms.tsq
    order by ts_rank_cd(c.fts, terms.tsq) desc, c.id
    limit n
  ),
  fused as (
    select coalesce(v.id, t.id) as hit_id,
           coalesce(1.0 / (60 + v.rnk), 0) + coalesce(1.0 / (60 + t.rnk), 0) as rrf
    from vec v
    full outer join txt t on t.id = v.id
    order by rrf desc, hit_id
    limit n
  )
  select c.id, c.ticker, c.form, c.filing_date, c.accession, c.section,
         c.chunk_index, c.char_start, c.char_end, c.content,
         f.rrf::double precision,
         (select jsonb_agg(
                   jsonb_build_object('char_start', nb.char_start,
                                      'char_end', nb.char_end,
                                      'content', nb.content)
                   order by nb.char_start, nb.chunk_index)
            from public.chunks nb
           where nb.accession = c.accession
             and nb.section = c.section
             and nb.chunk_index between c.chunk_index - win and c.chunk_index + win)
  from fused f
  join public.chunks c on c.id = f.hit_id
  order by f.rrf desc, c.id;
$$;

revoke execute on function public.hybrid_search(text, extensions.vector, text, integer, integer)
  from public, anon, authenticated;
grant execute on function public.hybrid_search(text, extensions.vector, text, integer, integer)
  to service_role;
