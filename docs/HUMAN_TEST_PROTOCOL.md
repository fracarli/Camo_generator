# Human recognition test protocol

This experiment measures how quickly an observer notices the uniform in a
generated scene. It is a usability comparison, not evidence of operational
camouflage performance.

## Preparation

1. After generating patterns, run
   `terrainweave evaluate --output output/human_test` and
   `terrainweave human prepare`. To use the published trial images, run
   `terrainweave human prepare --input evaluation/human_test/scenes`.
2. Keep the evaluation report away from observers. It maps trial images to
   their patterns and environments.
3. Use one observer at a time, preferably on the same monitor and at the same
   viewing distance.
4. Open `output/human_test/human_test.html` in a browser. The page randomizes
   the trials and measures reaction time with the browser's high-resolution
   `performance.now()` clock.

## Trial procedure

For each image in the browser page:

1. Show the image for 100 ms.
2. Ask: “Was a person or uniform present?”
3. Click “Yes” or “No” after the image disappears. The page records the
   reaction time automatically in milliseconds in `latency_ms`.
4. Download `responses.csv` at the end of the run.
5. Repeat the same test at 250 ms and 500 ms only in separate runs, not in
   the same randomized sheet.

If desired, add `confidence` from 1 to 5 and unusual observations to `notes`
in the downloaded CSV. Take a short break between runs to reduce fatigue. Use
the same instructions and timings for every observer.

## Analysis

After completing the CSV, run:

```bash
terrainweave human analyze
```

For the published scenes, pass
`--report evaluation/human_test/evaluation_report.json` so the analysis uses
the matching trial map.

Compare detection rate and mean latency only between tests with the same number
of trials, exposure time, observer instructions, and environment mix. Keep the
raw CSV and the generated JSON summary together, but keep the mapping report
private while observers are performing the test.

## Limitations

The current scenes use a fixed synthetic uniform silhouette and a proxy
compositing model. Results can be affected by monitor, observer experience,
image order, scene composition, and visual salience. They do not replace field,
material, movement, lighting, or safety testing.

The generated project test set uses a 25% uniform height, nine candidate
positions, and an explicit heuristic that avoids positions dominated by
blue-dominant sky or water pixels. This heuristic is intentionally conservative;
it is not a semantic segmentation model and should be validated visually.

## Web server and deploy

Run `terrainweave human serve --port 8502` and open
[http://localhost:8502](http://localhost:8502/). The server uses the published
scenes from a fresh checkout. When `output/human_test/human_test/` exists, it
uses those local scenes and their corresponding evaluation report instead.
Web responses go to `output/human_test/web_responses.csv`. Pass that file to
`terrainweave human analyze --input` to analyze it.

[render.yaml](../render.yaml) starts the server from source using Python's
standard library. For persistent storage on Render, create the table with
the [Supabase schema](../src/terrainweave/assets/human_test/supabase_schema.sql).
Set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in the service environment.
`SUPABASE_ANON_KEY` is also supported. The server uses the insert-only policy
and keeps a local CSV copy. Render's local filesystem is ephemeral.

Install the `human` extra to generate a QR code with
`terrainweave human qr <public-https-url>`.
