# Workflows

Run these commands from a checkout after installing the package. Use
`terrainweave <command> --help` for the available options.

## Run a configuration or an experiment

```bash
terrainweave run-config configs/generation_standard.json --dry-run
terrainweave run-config configs/generation_standard.json
terrainweave pipeline --skip-neural
```

The pipeline saves its own train/test manifests in `output/pipeline/splits/`.
Generation and optimization use the training manifest. Evaluation uses the
held-out manifest. Patterns, reports, mockups and `presentation.pdf` go in the
same run directory. For a different workspace, put
`--workspace /path/to/workspace` before the subcommand. The workspace needs its
own `evaluation/` data for corpus-based workflows.

| Path within a run | Contents |
|---|---|
| `splits/` | Training and held-out manifests |
| `baseline/`, `optimized/`, `neural/` | Pattern images and per-group reports. The neural directory is optional. |
| `evaluation_baseline/`, `evaluation_optimized/`, `evaluation_neural/` | Rendered scenes, contact sheets and JSON evaluation reports |
| `comparison/` | Visual comparison boards and `comparison_report.json` |
| `mockups/`, `presentation.pdf` | Uniform renders and the experiment presentation |

Each pipeline run needs a new output directory. After the first run, use
`terrainweave pipeline --skip-neural --output output/pipeline-repeat`.
If the neural stage fails, the command reports failure and leaves the
procedural comparison available in the selected directory.

`terrainweave data split` writes to `output/splits/`. Use
`--output evaluation/splits` to update the checked-in reference split.

After running the pipeline in the default `output/pipeline/` directory,
`terrainweave run-config configs/optimization_balanced.json` uses its baseline
patterns and training manifest. For a custom run directory, update the paths
in a copy of the configuration. This command requires the `ml` extra.

The demo and benchmark default to the reviewed corpus under
`evaluation/backgrounds/`. Both accept `--input` for a different photo set.

| Command | Use |
|---|---|
| `generate`, `optimize`, `evaluate`, `benchmark` | Generate patterns, run comparisons or evaluate patterns you already generated |
| `report compare`, `report grid`, `report mockups`, `report presentation` | Export reports and visual assets |
| `data download`, `data review`, `data promote`, `data split`, `data audit` | Maintain the public corpus |
| `human prepare`, `human serve`, `human analyze`, `human exposures`, `human qr` | Run and analyze the observer test |
| `ml train-proposer`, `ml train-evaluator`, `ml check` | Train or check optional models |

`terrainweave report compare` reads pattern images and evaluation reports from
`output/pipeline/`. Run the pipeline first or set the input paths shown by
`terrainweave report compare --help`. For a procedural run, pass `--skip-neural`
to both commands. For a custom run directory, pass the corresponding pattern
roots and evaluation reports to `report compare`. For each shared pattern,
the reports must contain matching backgrounds, scales and positions. New
evaluation reports also identify the evaluated pattern by its SHA-256 digest.

## Optional dependencies

```bash
python -m pip install -e '.[demo]'
terrainweave studio

python -m pip install -e '.[ml]'
terrainweave ml check
terrainweave pipeline --output output/pipeline-neural

python -m pip install -e '.[human]'
```

The `human` extra adds QR-code export. The web server itself uses Python's
standard library. Extras can be combined, for example
`python -m pip install -e '.[demo,ml,human]'`.

Studio accepts local image uploads and displays the generated pattern, palette
and report. The neural pipeline uses a pretrained SegFormer model that is
downloaded and cached on first use. The pipeline creates its comparison and
PDF automatically. To regenerate a PDF for a specific run, use
`terrainweave report presentation --pipeline-root output/pipeline-neural`.
With no arguments, `report presentation` uses the published results.

## Migrating old commands

| Previous command | Current command |
|---|---|
| `python camo.py` | `terrainweave generate` |
| `python demo.py` | `terrainweave demo` |
| `streamlit run app.py` | `terrainweave studio` |
| `python scripts/run_pipeline.py` | `terrainweave pipeline` |
| `python scripts/run_from_config.py` | `terrainweave run-config` |
| `python human_test_web/server.py` | `terrainweave human serve` |

Old JSON configs with a known `script` value still resolve through
`terrainweave run-config`. Use `"command": "generate"` or another CLI command
for new configurations. The former `camo` import is available in the package.
