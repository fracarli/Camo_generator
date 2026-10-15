# Curated results

Start with [`results_comparison/initial_vs_optimized.png`](results_comparison/initial_vs_optimized.png).
It puts the baseline pattern, the optimized pattern, and the optimized
validation scenes in one row per environment. The score change is printed below
each optimized pattern.

The individual final patterns are in [`optimized_final/`](optimized_final/),
with one `optimized_pattern.png` and one `optimizer_report.json` per group.
The original baseline patterns are in the environment folders directly under
`output/`, for example [`forest/best_pattern.png`](forest/best_pattern.png).

The comparison data is also available in
[`results_comparison/comparison_report.json`](results_comparison/comparison_report.json)
and [`results_comparison/README.md`](results_comparison/README.md).

Older experiment folders remain in `output/` for reproducibility and are not
the primary presentation.
