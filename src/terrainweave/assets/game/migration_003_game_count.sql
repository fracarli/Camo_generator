-- Lets the home page show how many games have been collected (progress bar).
-- Run once in the Supabase SQL editor. Safe to run more than once.
-- Visitors still cannot read any row: the function returns only one number,
-- the count of distinct game sessions, leaving out test sessions.
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
