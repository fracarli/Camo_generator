# Web game

The public game has four modes. A to C share the same backgrounds and the
`launch` study; D is a separate build of the `references3` study:

| Mode | Task | What it measures |
|---|---|---|
| A · Squad (`squad`) | Four figures in one photo, one per pattern; find them all in 25 s | Discovery order per pattern and environment |
| B · Hunt (`find`) | Tap the figure as fast as possible, 15 s limit | Time to find and found rate per pattern |
| C · Flash (`flash`) | 500 ms exposure and a noise mask, then yes/no; half the scenes are empty | Hit rate, false alarms and d′ |
| D · Camo Showdown (*Sfida delle mimetiche*, `squad` at `/versus/`) | Six figures in one photo: universal v1 and v2 against MultiCam-, Flecktarn-, Vegetato- and EMR-style patterns (no plain control | Discovery order of universal against the reference patterns |

Flash used a 250 ms exposure until players reported seeing nothing; every row
stores the measured `exposure_ms`, so analyze the two exposures separately.
Duel (`duel`, two copies of a landscape with different patterns) was retired
because it added little over Squad; `game analyze` still reads its old rows.

Camo Showdown is listed last among the game cards on the home page and opens
its own page at `/versus/`. That page keeps its records and progress apart from
the main game, and its rows carry their own `build_id`. The first comparison
study (`references`: transitional, grey digital, woodland) ran briefly at
`/beta/` and is no longer deployed; its rows keep build id `95dddadb02cc`.
The `references2` version of Camo Showdown (with the plain control instead of
universal v2) ran until universal v2 was added; its rows keep build id
`24cdd01b4305`.

Every scene uses a held-out background with one fixed figure position. The
backgrounds come from `evaluation/splits/test.json` and from
[evaluation/game_backgrounds/](../evaluation/game_backgrounds/), a game-only set
of sharp, ground-level Wikimedia Commons photos that are never used to generate
or optimize patterns. The build skips any background whose lower half, where
the figures stand, is too soft (`MIN_FOREGROUND_SHARPNESS`): a sharp figure on
a blurred photo stands out regardless of its pattern. Only the pattern changes: TerrainWeave optimized,
baseline, universal, and a plain olive control. The page assigns patterns at
random and balances them within each game. In Squad, each background has
four layouts that rotate the patterns over the same four positions, so the
discovery order measures the pattern rather than the position. The tutorial example uses a
training photo so no game scene is revealed in advance.

## Studies and reference patterns

A study fixes which patterns appear together. `launch` (the published game)
compares the TerrainWeave optimized, baseline and universal patterns with a
plain olive control. `references`, `references2` and `references3` compare
universal with reference pattern families drawn from scratch (`references2` adds
`multiterrain`, `flecktarn`, `vegetato` and `digitalflora`). They are original
renditions that follow published colours and element sizes; no artwork is
copied:

```bash
terrainweave game references                 # writes results/references/
terrainweave game build --study references --output output/game-references
terrainweave game build --study references3 --output output/game-references3
```

Squad shows one figure per pattern, so `references` hides five figures per
photo. Each build stores the automatic visibility score of every scene and
pattern; after collecting Hunt data, check whether that score predicts people:

```bash
terrainweave game calibrate --input game_events.csv --manifest output/game-site/manifest.json
```

The study plan is in [STUDY_universal_vs_references.md](STUDY_universal_vs_references.md).

The deploy workflow builds two studies: `launch` at the site root and
`references3` at `/versus/`. Analyze each build on its own:

```bash
terrainweave game analyze --input game_events.csv --build-id <build_id>
```

Without `--build-id`, `game analyze` lists the builds found in the export.

## Test sessions

Open the game once with `?test=1` (for example
`https://fracarli.github.io/Camo_generator/?test=1`) to mark that browser's
games as tests; a TEST badge appears next to the logo and session ids start
with `TEST`. `?test=0` switches it off. Remove test rows with
`delete from game_events where session_id like 'TEST%';`.

## More backgrounds

```bash
python scripts/collect_game_backgrounds.py --per-group 12
python scripts/collect_game_backgrounds.py --approve approved.txt
```

The first command searches Commons, skips files already in the corpus, keeps
free licenses and sharp foregrounds, and writes
`output/game_background_candidates.jpg`. Write the indices of suitable photos
(no people, signs, artwork, close-ups or water where figures would stand) to a
text file and approve them; the others are deleted.

## Build and preview

```bash
terrainweave game build            # writes output/game-site and a review sheet
python -m http.server -d output/game-site 8765
```

Check `output/game-site-review.jpg` before publishing. List any background that
does not suit the game in [configs/game_exclude.txt](../configs/game_exclude.txt)
and rebuild. Without Supabase settings the page keeps answers only in the
browser console.

## Free hosting

1. Create a free Supabase project. In the SQL editor, run
   [supabase_schema.sql](../src/terrainweave/assets/game/supabase_schema.sql).
   Visitors can insert rounds but cannot read them. A table created before the
   Squad mode needs [migration_002_squad.sql](../src/terrainweave/assets/game/migration_002_squad.sql),
   and one created before the progress bar needs
   [migration_003_game_count.sql](../src/terrainweave/assets/game/migration_003_game_count.sql).
2. In the GitHub repository, open **Settings → Pages** and set **Source** to
   **GitHub Actions**.
3. In **Settings → Secrets and variables → Actions → Variables**, add
   `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` (Project settings → API keys).
   The publishable key is meant for browsers.
4. Push to `main` or run the **game** workflow manually. The site is published
   at `https://<user>.github.io/<repository>/`.

The free Supabase plan pauses a project after a week without requests;
restore it from the dashboard if that happens.

## Progress bar

The home page shows how many games have been collected against a goal of 100
(`GOAL` in [index.html](../src/terrainweave/assets/game/index.html)), with a
message that changes at 25, 50, 75 and 100 %. The count comes from the
`game_count()` database function: the number of distinct non-test sessions,
across the main game and Camo Showdown. It exposes that single number and no
rows. Until the function exists the bar stays hidden.

## Analysis

Export `game_events` from the Supabase table editor as CSV, then run:

```bash
terrainweave game analyze --input game_events.csv --json output/game_summary.json
```

The Squad section ranks the patterns in each environment by mean discovery
rank (a missed figure ranks last + 1). Players who see every figure at once
tap them in scanning order, left to right or the reverse, and that order says
nothing about the patterns. The analysis therefore:

- **ties quick taps:** consecutive finds less than 700 ms apart (`--tie-ms`)
  share the mean of their ranks, so one sweep of the finger counts as a draw;
- **reports neutral rounds:** rounds where every figure was found in one sweep
  carry no ranking information and are counted separately;
- **prints the gaps between taps** (10th to 90th percentile), to check where the
  tie threshold sits against real players;
- **removes the position effect:** figures are numbered left to right and the
  Latin square moves every pattern over every position, so the mean rank of
  each position is subtracted (`mean_rank_adjusted`);
- **adds the mean time to find**, with a missed figure counted as 25 s, and the
  raw tap order (`mean_order`) for comparison.

Compare patterns within a single `build_id`. The rows also record device type
and image width, so phone and desktop results can be analyzed separately.

## Social media assets

```bash
python scripts/make_social_assets.py --site output/game-site --output output/linkedin
```

The script writes a six-slide carousel (`carousel_1.png` to `carousel_6.png`
and `carousel.pdf` for LinkedIn document posts), a single image with a QR code
(`post_single.png`), a standalone `qr_code.png` and a 25-second vertical video
(`video_trova_omino.mp4`, requires ffmpeg). The text is in Italian;
add `--lang en` for English captions (the video is then
`video_find_the_figure.mp4`). The challenge scenes are chosen by photo title
in `CHALLENGE`.
