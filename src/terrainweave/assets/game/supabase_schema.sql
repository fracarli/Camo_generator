-- TerrainWeave web game: one row per played round.
-- Run once in the Supabase SQL editor (free plan is enough).
create table if not exists public.game_events (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  build_id text not null check (char_length(build_id) <= 32),
  session_id text not null check (char_length(session_id) <= 64),
  game text not null check (game in ('find', 'duel', 'flash', 'squad')),
  round smallint not null check (round between 0 and 99),
  scene_id text not null check (char_length(scene_id) <= 40),
  environment text check (char_length(environment) <= 20),
  variant text check (char_length(variant) <= 20),
  variant_b text check (char_length(variant_b) <= 20),
  outcome text not null check (outcome in ('found', 'timeout', 'answered')),
  chosen text check (char_length(chosen) <= 20),
  latency_ms integer check (latency_ms between 0 and 600000),
  misses smallint check (misses between 0 and 99),
  tap_x real,
  tap_y real,
  exposure_ms smallint,
  figure_present boolean,
  answer text check (answer in ('yes', 'no')),
  correct boolean,
  lang text check (lang in ('it', 'en')),
  device text check (device in ('phone', 'tablet', 'desktop')),
  viewport_w smallint,
  viewport_h smallint,
  image_w smallint,
  dpr real,
  target smallint,
  found_order smallint,
  layout smallint,
  constraint game_events_unique_round
    unique nulls not distinct (session_id, game, round, scene_id, target)
);

alter table public.game_events enable row level security;
grant insert on table public.game_events to anon;
grant usage on sequence public.game_events_id_seq to anon;
drop policy if exists "anonymous game inserts" on public.game_events;
create policy "anonymous game inserts"
  on public.game_events for insert to anon with check (true);
-- No select policy: visitors can add rounds but cannot read anyone's data.

-- Progress bar: one number (distinct non-test game sessions), no rows exposed.
create or replace function public.game_count()
returns integer
language sql
stable
security definer
set search_path = public
as $$
  select count(distinct session_id)::integer
  from public.game_events
  where session_id not like 'TEST%';
$$;
revoke all on function public.game_count() from public;
grant execute on function public.game_count() to anon;
-- Export from the dashboard (Table editor -> Export to CSV) and run:
--   terrainweave game analyze --input game_events.csv
