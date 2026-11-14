# Evaluation data

- [backgrounds/](backgrounds/) contains 124 reviewed image files from 123 distinct
  photographs. The Iceland Mid-Atlantic Ridge photograph appears under both
  `mountain` and `snow`. Both copies stay in the training split. Sources and
  recorded licenses are in [SOURCES.md](SOURCES.md) and [sources.json](sources.json).
- [splits/](splits/) contains the reference split of 94 training and 30 held-out
  records, grouped by source and image content. Each pipeline run writes its own
  split under `output/pipeline/splits/`.
- [review_candidates/](review_candidates/README.md) contains the review board
  and candidate decisions.
- [human_test/](human_test/scenes/) contains the 48 published trial images and
  their [evaluation report](human_test/evaluation_report.json). The web server
  uses this set from a fresh checkout.
