# Generated results

This folder contains the selected outputs of the Camo project. Intermediate
candidate searches and large per-scene image dumps are intentionally omitted.

## Start here

- `all_patterns_grid.png`: standard patterns generated from the source photos.
- `optimized_final/all_optimized_patterns_grid.png`: final optimized patterns for all environments.
- `outfit_mockups/outfit_contact_sheet.png`: standard uniform mockups.
- `optimized_mockups/outfit_contact_sheet.png`: uniform mockups using the optimized patterns.

## Final pattern folders

- `universal/`, `forest/`, `taiga/`, `tundra/`, `urban/`, `desert/`, `mountain/`, `snow/`, and `jungle/` contain standard outputs.
- `optimized_final/<group>/optimized_pattern.png` contains the optimized result for that environment.
- Each optimized group also contains `optimizer_report.json` with the selected configuration and proxy scores.

## Reports

- `optimized_final/optimizer_report.json`: optimization summary for all groups.
- `optimized_validation/evaluation_report.md`: earlier validation-slice comparison.
- `strict_validation/evaluation_report.md`: strict train-first-five/test-last-five comparison.
- `human_test/human_test/`: 48 anonymous scenes for a blinded recognition test. The mapping is in `human_test/evaluation_report.json`.
- `human_test/human_test_exposure_summary.md`: comparison of the 100, 250, and 500 ms CSV sessions.
- `evaluation/evaluation_report.md`: earlier standard-pattern scene evaluation.
- `benchmark/benchmark_report.md`: generator benchmark summary.
- `validation_report.md`: image-structure diagnostics for standard outputs.

The visibility scores are internal comparison metrics, not evidence of real-world
concealment performance.
