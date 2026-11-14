create table if not exists public.human_test_responses (
  timestamp timestamptz not null,
  session_id text not null,
  language text not null check (language in ('en', 'it')),
  trial_id text not null,
  pattern_group text,
  background_group text,
  exposure_ms integer not null,
  detected text not null check (detected in ('yes', 'no')),
  latency_ms integer not null,
  confidence text
);

alter table public.human_test_responses enable row level security;
grant insert on table public.human_test_responses to anon;
create policy "allow anonymous test inserts"
  on public.human_test_responses for insert
  to anon with check (detected in ('yes', 'no') and language in ('en', 'it'));
