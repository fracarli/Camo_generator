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
to both commands.

## Optional dependencies

```bash
python -m pip install -e '.[demo]'
terrainweave studio

python -m pip install -e '.[ml]'
terrainweave ml check
terrainweave pipeline

python -m pip install -e '.[human]'
```

The `human` extra adds QR-code export. The web server itself uses Python's
standard library. Extras can be combined, for example
`python -m pip install -e '.[demo,ml,human]'`.

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
