-- Distinct accessions ingested for a ticker: the thesis cache fingerprint.
create or replace function public.ticker_accessions(p_ticker text)
returns setof text
language sql
stable
set search_path = ''
as $$
  select distinct c.accession
  from public.chunks c
  where c.ticker = p_ticker
  order by c.accession;
$$;

revoke execute on function public.ticker_accessions(text) from public, anon, authenticated;
grant execute on function public.ticker_accessions(text) to service_role;
