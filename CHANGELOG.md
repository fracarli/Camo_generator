# Changelog

## Unreleased

- Web game: Squad first, Duel retired, Flash exposure raised from 250 to
  500 ms.
- Reference patterns in the style of MultiCam, Flecktarn, Vegetato and
  Digital Flora, played as game D, Camo Showdown (`references2`, /versus/).
  The four were redrawn from public swatch images; Digital Flora is the
  Russian EMR pixel pattern.
- Home page progress bar: games collected towards a goal of 100, read from
  the `game_count()` function (migration_003_game_count.sql).
- The beta section and the first comparison study (/beta/) were removed.
- Squad analysis: taps less than 700 ms apart tie, neutral rounds are
  counted, the left-to-right position effect is removed, and mean time to
  find is reported. Games are described as taking less than a minute.
- Home page legend: one square per pattern in play, for games A–C and D.
- Universal v2: re-optimized with 240 candidates, environments interleaved,
  a 14-background warm-up before pruning and a worst-environment penalty
  (new optimizer options `--background-order`, `--warmup`,
  `--score-aggregation environment_worst`). Camo Showdown (`references3`)
  shows v1 and v2 side by side; `scripts/compare_universal.py` compares them
  on held-out backgrounds.
- Added a non-interactive `demo.py` entry point for fresh clones.
- Added visual README documentation for generated patterns, uniform mockups,
  and environmental validation scenes.
- Added an optional ML environment diagnostic script.
- Added a baseline-versus-semantic benchmark summary.
- Added GitHub Actions regression tests and project licensing.
