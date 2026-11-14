# Architecture

`terrainweave` is the application package. The console entry point and
`python -m terrainweave` use the same lazy command registry in `cli.py`.
Each command loads its implementation on demand. The human-test server uses
the standard library.

## Dependencies

Dependencies are declared in `pyproject.toml`. The core requires NumPy and
Pillow. See [optional dependencies](WORKFLOWS.md#optional-dependencies).

## Implementation boundaries

| Modules | Responsibility |
|---|---|
| `configuration`, `models` | Generator settings, style profiles and shared records |
| `images` | Reference discovery, masking, optional semantic segmentation and statistics extraction |
| `palette`, `patterns`, `metrics` | Palette constraints, deterministic procedural rendering and diagnostics |
| `generation` | Generation workflow and the previous public generator API |
| `rendering` | Shared uniform masking, shading, compositing layers, palette previews and grids |
| `evaluation`, `optimization`, `benchmark` | Scene evaluation, candidate search and controlled comparisons |
| `datasets` | Downloading, review, promotion, grouped splits and provenance audit |
| `ml`, `training` | Neural models and training commands |
| `human`, `human_server` | Offline response workflows and the standard-library HTTP service |
| `reports`, `visuals`, `presentation` | Numerical reports and visual exports |
| `studio` | Interactive Streamlit application |
| `project` | Pipeline, demo, configuration runner and verification |
| `cli`, `paths` | Command dispatch, workspace selection and installed assets |

Generation, evaluation and optimization share the uniform renderer.

## Workspace and assets

`paths.workspace_root()` checks `TERRAINWEAVE_WORKSPACE`, the source checkout,
then the current directory. Setting `TERRAINWEAVE_WORKSPACE` or using the CLI's
`--workspace` flag also sets the working directory for relative paths.

Immutable assets live under `terrainweave/assets/` and ship in the wheel.
The package serves the web page and includes its Supabase schema from
`assets/human_test/`. The evaluation dataset and published results live in the
checkout. Fresh runs write to `output/`.

## Compatibility

`run-config` maps known legacy script names to CLI commands. External scripts
still run as Python files. See [migration examples](WORKFLOWS.md#migrating-old-commands).

## Checking changes

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
```

CI tests the wheel on Python 3.10, 3.11 and 3.12. A separate job installs the
optional dependencies and publishes the coverage report, including Python
subprocesses launched by the tests.

To reproduce that report locally:

```bash
python -m pip install -e '.[dev,demo,ml,human]'
python -m coverage erase
python -m coverage run -m unittest discover -s tests -v
python -m coverage combine
python -m coverage report -m
```

See the [historical validation report](archive/regression-validation.md) for
earlier output comparisons.
