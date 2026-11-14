# Regression validation — 13 November 2026

All changes were developed on `refactor`. Corrections were preceded by a
reproduction that failed on the faulty behavior. No historical result images
were regenerated in the source checkout.

## Covered behavior

| Area | Regression checked |
|---|---|
| Generation | The demo generates its selected environment; filename-based terrain classes also reach the image statistics. |
| Demo sessions | Concurrent sessions retain separate uploads; regenerating a pattern invalidates the previous human test; the report shows the input image count. |
| Proposer | A requested checkpoint is loaded, its predictions reach the renderer, and loading errors propagate. Optimizer detail and blur parameters become training targets. |
| Paired evaluation | Identical patterns receive identical placement and scores. Changing pattern order does not change the comparison, and the seed controls placement. |
| Dataset split | Shared sources, identical bytes, and transitive copies stay in one split. Splits are repeatable; a single source cannot be presented as independent training and test data. |
| Reference statistics | Training manifests constrain generation and optimization. Legacy background slices also constrain references when both corpora coincide; independent reference corpora retain their inputs. |
| Neural evaluation | Variants of one background remain in one training or test partition when their evaluation mapping is available. |
| Human-test responses | Offline, server and Streamlit CSVs are accepted. Invalid timings and malformed response fields are rejected before writing. HTTP failures retain the trial for retry. Old scene files absent from the current mapping are not offered. |
| Pipeline outputs | Baselines are generated within the experiment. Skipped neural stages cannot reuse old previews. Grids, mockups and the presentation use current results; incomplete exports fail instead of falling back to historical images. |

## Executed checks

- **38 tests passed**, including the optional PyTorch, Streamlit and Node.js
  checks. Optional checks are skipped when their runtime is absent.
- The procedural pipeline completed as one command in a disposable checkout
  containing **16 real photographs**, two per environment. It generated all
  nine pattern groups and **72 held-out scenes per version**. Baseline and
  optimized reference paths were restricted to the training manifest.
- With one candidate, the identical baseline and optimized patterns received
  exactly matching positions and metrics in all 72 paired scenes.
- The official corpus still contains 124 records: **94 train / 30 test**,
  with no overlap by path, recorded source or SHA-256 image content.
- A real parameter proposer was trained for five epochs on CPU, loaded by the
  CLI and applied to all nine groups. Its training references excluded held-out
  images, and reported generator parameters matched actual model predictions.
- SegFormer loaded its real public checkpoint, produced semantic masks and
  generated patterns on CPU. The final check used the local model cache offline.
- Grid, outfit mockup, comparison and PDF generation completed successfully.
- Python sources compiled successfully and `git diff --check` passed.

Browser rendering was not automated: browser access was unavailable. Streamlit
integration used its actual file-uploader and button testing API; the web
response controller was also executed as JavaScript without a browser.

These checks validate the listed software behaviors. They do not measure
real-world camouflage effectiveness or the accuracy of the bootstrap model.

## Reproduction

```bash
python -m pip install -e '.[demo,ml]'
python -m unittest discover -s tests -v
```

Node.js must be available to execute the JavaScript response-controller test.
For a normal procedural experiment, use:

```bash
python scripts/run_pipeline.py --skip-neural
```

The bounded smoke experiment used `--candidates 1 --test-fraction 0.5` only in
its disposable, two-images-per-environment checkout.

Validated environment: Python 3.11.15, NumPy 2.4.6, Pillow 13.0.0,
PyTorch 2.15.0, torchvision 0.29.2, Transformers 5.23.0 and Streamlit 1.67.0.


## Package refactor verification

The organizational refactor was completed on `refactor` after the corrections
above. The final suite passed **41 tests**, including the optional PyTorch,
Streamlit and Node.js checks. Three package workflow tests add coverage for all
31 CLI help routes, legacy/new JSON configuration equivalence from outside the
checkout, rendering without historical assets, and web-page compatibility.

Additional executed checks:

- A snapshot immediately preceding the organizational refactor was exercised
  with 16 real photographs and fixed seeds. All nine standard and custom group
  reports, 38 PNG SHA-256 hashes, uniform/mask/scene pixels, visibility metrics,
  a mockup PNG and a real proposer prediction matched the refactored version
  exactly in the same dependency environment.
- A wheel was built and installed into a separate directory, then imported
  outside the checkout. Its packaged assets were verified, and its demo ran
  child generation commands without checkout scripts. Mockup export also
  succeeded without historical `output/` assets. The wheel excludes datasets,
  experiment results and compatibility scripts.
- The unified CLI completed a fresh procedural pipeline in a temporary
  workspace with 16 photographs, eight training and eight held-out records,
  and one candidate. It produced nine pattern groups, 72 held-out scenes per
  version, nine mockups, a comparison board and the PDF presentation. Positions
  and metrics matched exactly for all 72 baseline/optimized pairs. Baseline
  reference paths were restricted to the training manifest.
- The provenance audit still reports 124 images and 124 matching entries,
  with no missing or stale entries. The standalone human-test server's help
  also runs with `python -S`, without third-party dependencies.

These checks establish behavior preservation for the exercised inputs and
workflows; they do not assert correctness for every possible input, dependency
version or external service. Historical outputs in the source checkout were
retained.


## Dependency consolidation and minimal installation

Dependency declarations now live only in `pyproject.toml`; the duplicate
requirements manifests were removed. Installation guides and runtime messages
use the same core install and `demo`, `ml`, and `human` extras.

Checking an environment containing only NumPy and Pillow reproduced a failure
in `terrainweave studio --help`: the command attempted to run absent Streamlit.
The help command now works without that extra; attempting to launch the studio
reports the installation command. The existing package workflow test covers
this case when run in the core-only CI environment.

Executed after the correction:

- Core-only environment: 41 tests discovered, 38 passed and three optional
  PyTorch/Streamlit tests skipped; Node.js coverage ran.
- Full environment: all 41 tests passed.
- A newly built wheel was installed into the isolated core environment.
  `pip check` passed, package metadata declared the expected extras, and CLI
  help succeeded outside the checkout without Streamlit or PyTorch.
- The standard-library human-test server still supports `python -S`.


## Development checks — 14 November 2026

Regression tests now import the application package directly. Training,
optimization and benchmarking import their image, palette, model and settings
dependencies from their defining modules. The pipeline invokes registered CLI
commands directly. Streamlit tests execute the packaged studio in a temporary
workspace.

Ruff 0.17.5 is declared in the `dev` extra. Import, unused-name, syntax and
formatting checks pass across all 78 Python files. The final full environment
passes all 41 regression tests. The core-only environment passes 38 tests and
skips three optional tests after installing the newly built wheel. Dependency
checks pass in both environments.

The installed wheel's demo completed outside the checkout and launched its
child generator through the CLI. The final characterization still matches the
pre-refactor snapshot exactly, including 38 generated PNG hashes, nine
standard/custom group reports, rendering pixels, scene metrics, the mockup
and the real proposer prediction.

GitHub Actions is configured to check code, build and install the wheel and
run regressions on Python 3.10, 3.11 and 3.12. A separate job installs the
optional dependencies and runs the full suite. Local execution used Python
3.11.15. The updated GitHub workflow will run when the branch is pushed.
