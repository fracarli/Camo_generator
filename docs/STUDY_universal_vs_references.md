# Study plan: TerrainWeave universal versus reference patterns

Draft for preregistration (for example on OSF) before data collection starts.
Fill in the dates and the final numbers, then freeze this file.

## Question

Is the TerrainWeave **universal** pattern harder for people to find than
established multi-purpose reference patterns, across environments and in the
environment where each pattern performs worst?

## Patterns (study `references`)

| Name | Role |
|---|---|
| `universal` | TerrainWeave universal pattern under test |
| `transitional` | Generic multi-environment design: soft gradient base, soft blobs, thin branches (in the spirit of transitional patterns, no proprietary artwork) |
| `digital3` | Three-colour grey digital family, after the US UCP |
| `woodland` | Four-colour woodland family, after the US M81 |
| `control` | Plain olive green, lower anchor |

The reference patterns are original renditions drawn by
`terrainweave game references`. All patterns use the same figure, lighting and
fabric scale (about 2.6 px per cm on a 500 px texture). The three-colour desert
family (`desert3`) is available for a desert-specific follow-up.

### Second set (study `references2`, played at `/beta2/`)

| Name | Role |
|---|---|
| `universal` | TerrainWeave universal pattern under test (shared anchor) |
| `multiterrain` | Seven-colour multi-terrain design in the spirit of MultiCam: tan-to-green gradient, soft vertical blobs, cream highlights, thin twigs |
| `flecktarn` | Five-colour dot family, after the German Flecktarn |
| `vegetato` | Four-colour leaf and brushstroke family, after the Italian Vegetato |
| `digitalflora` | The same leaf family pixelated at about 1.2 cm, after the Italian Digital Flora |
| `control` | Plain olive green (shared anchor) |

Squad hides six figures per photo in this set, so a missed figure ranks 7.
The hypotheses H1 and H2 apply to each set separately; `universal` and
`control` link the two sets.

## Material

Held-out backgrounds only: `evaluation/splits/test.json` and
`evaluation/game_backgrounds/game.json`, none of which is used to generate or
optimize patterns. Backgrounds with a soft foreground are excluded
automatically. Figure positions are fixed per background; in Squad the
patterns rotate over the same positions (Latin square).

## Primary outcome

**Squad discovery rank.** In every Squad round all five patterns appear in the
same photo; each figure gets its discovery order (1 = found first). A figure
not found within 25 s ranks 6. Higher mean rank = better concealment.

## Hypotheses

- **H1 (overall):** the mean rank of `universal` is higher than that of each
  reference pattern (`transitional`, `digital3`, `woodland`).
- **H2 (worst case):** across the eight environments, the lowest per-environment
  mean rank of `universal` is higher than the lowest per-environment mean rank
  of `digital3` and `transitional`.
- **Sanity check:** every pattern ranks above `control` overall.

## Secondary outcomes

- Hunt: time to find (timeouts at 15 s treated as censored) and found rate.
- Duel: pairwise survival rate (the other pattern was found first).
- Flash: hit rate and d′ against empty scenes.
- Calibration: Spearman correlation between the automatic visibility score
  and the median Hunt time per scene and pattern (`terrainweave game calibrate`).

## Analysis

- Only rows from the study build (`build_id`), excluding test sessions
  (`session_id` starting with `TEST`).
- Main model: mean rank per pattern with a mixed model including random
  effects for player session and background (or, as a robust alternative,
  per-round rank comparisons with a sign test).
- Report effect sizes with 95% confidence intervals, per environment and
  overall; report phone and desktop separately as a robustness check.

## Sample size

With a rank standard deviation of about 1.4 and a smallest difference of
interest of 0.3 rank positions, about 350 Squad rounds are needed for the
overall comparison (two-sided, alpha 0.05, power 0.8), that is about 60 Squad
games of six rounds. Per-environment estimates (H2) need about 40 rounds per
environment, about 320 rounds in total; the target is **100 Squad games**.
Stop collecting when the target is reached or after four weeks.

## Limitations

On-screen photographs with a static, headless figure; no motion, distance
variation, near-infrared or material effects. Results show relative visual
concealment on screens, not field performance.
