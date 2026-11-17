-- Adds the squad game (several figures per photo) to an existing game_events table.
-- Run once in the Supabase SQL editor. Safe to run more than once.
alter table public.game_events drop constraint if exists game_events_game_check;
alter table public.game_events add constraint game_events_game_check
  check (game in ('find', 'duel', 'flash', 'squad'));
alter table public.game_events add column if not exists target smallint;
alter table public.game_events add column if not exists found_order smallint;
alter table public.game_events add column if not exists layout smallint;
alter table public.game_events
  drop constraint if exists game_events_session_id_game_round_scene_id_key;
alter table public.game_events drop constraint if exists game_events_unique_round;
alter table public.game_events add constraint game_events_unique_round
  unique nulls not distinct (session_id, game, round, scene_id, target);
