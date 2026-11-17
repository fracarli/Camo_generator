# Web game

The public game has three modes that share the same scenes:

| Mode | Task | What it measures |
|---|---|---|
| A · Hunt (`find`) | Tap the figure as fast as possible, 15 s limit | Time to find and found rate per pattern |
| B · Duel (`duel`) | Two copies of a landscape with different patterns; tap the figure in either | Which of two patterns is found first |
| C · Flash (`flash`) | 250 ms exposure and a noise mask, then yes/no; half the scenes are empty | Hit rate, false alarms and d′ |

Every scene uses a held-out background from `evaluation/splits/test.json` with
one fixed figure position. Only the pattern changes: TerrainWeave optimized,
baseline, universal, and a plain olive control. The page assigns patterns at
random and balances them within each game. The tutorial example uses a
training photo so no game scene is revealed in advance.

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
   Visitors can insert rounds but cannot read them.
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

Compare patterns within a single `build_id`. The rows also record device type
and image width, so phone and desktop results can be analyzed separately.
