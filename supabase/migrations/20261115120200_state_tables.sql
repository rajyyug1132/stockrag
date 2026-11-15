-- Server state that used to live on local disk (data/metrics, data/thesis),
-- so the API can run without a writable volume.
create table public.request_metrics (
  id         bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  record     jsonb not null
);

create table public.thesis_cache (
  ticker      text primary key,
  fingerprint text not null,
  payload     jsonb not null,
  updated_at  timestamptz not null default now()
);

-- Service role only: RLS on with no policies, and no grants to the public roles.
alter table public.request_metrics enable row level security;
alter table public.thesis_cache enable row level security;
revoke all on table public.request_metrics from anon, authenticated;
revoke all on table public.thesis_cache from anon, authenticated;
revoke all on sequence public.request_metrics_id_seq from anon, authenticated;
