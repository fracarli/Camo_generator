# Web game

The public game has four modes that share the same backgrounds:

| Mode | Task | What it measures |
|---|---|---|
| A · Hunt (`find`) | Tap the figure as fast as possible, 15 s limit | Time to find and found rate per pattern |
| B · Duel (`duel`) | Two copies of a landscape with different patterns; tap the figure in either | Which of two patterns is found first |
| C · Flash (`flash`) | 250 ms exposure and a noise mask, then yes/no; half the scenes are empty | Hit rate, false alarms and d′ |
| D · Squad (`squad`) | Four figures in one photo, one per pattern; find them all in 25 s | Discovery order per pattern and environment |

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
plain olive control. `references` compares universal with reference pattern
families drawn from scratch:

```bash
terrainweave game references                 # writes results/references/
terrainweave game build --study references --output output/game-references
```

Squad shows one figure per pattern, so `references` hides five figures per
photo. Each build stores the automatic visibility score of every scene and
pattern; after collecting Hunt data, check whether that score predicts people:

```bash
terrainweave game calibrate --input game_events.csv --manifest output/game-site/manifest.json
```

The study plan is in [STUDY_universal_vs_references.md](STUDY_universal_vs_references.md).

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
   Squad mode needs [migration_002_squad.sql](../src/terrainweave/assets/game/migration_002_squad.sql).
2. In the GitHub repository, open **Settings → Pages** and set **Source** to
   **GitHub Actions**.
3. In **Settings → Secrets and variables → Actions → Variables**, add
   `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` (Project settings → API keys).
   The publishable key is meant for browsers.
4. Push to `main` or run the **game** workflow manually. The site is published
   at `https://<user>.github.io/<repository>/`.

The free Supabase plan pauses a project after a week without requests;
restore it from the dashboard if that happens.

## Analysis

Export `game_events` from the Supabase table editor as CSV, then run:

```bash
terrainweave game analyze --input game_events.csv --json output/game_summary.json
```

The Squad section ranks the patterns in each environment by mean discovery
order (a missed figure counts as 5). Compare patterns within a single `build_id`. The rows also record device type
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
