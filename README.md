# TerrainWeave

TerrainWeave generates patterns from landscape photographs and compares them
in synthetic scenes. Choose a specific environment or use the experimental
`universal` profile to combine reference images from multiple environments.

## Getting started

From the repository root with Python 3.10 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
terrainweave demo
```

The demo writes its grid to `output/demo/all_patterns_grid.png`.
To use your own photographs, pass their directory to the generator:

```bash
terrainweave generate --input /path/to/photos --mode standard --output output/my_patterns
```

## Repository layout

| Path | Contents |
|---|---|
| [src/terrainweave/](src/terrainweave/) | Application code, CLI and packaged assets |
| [configs/](configs/) | Reproducible configurations |
| [evaluation/](evaluation/) | Public photographs, provenance, splits and web-test scenes |
| [results/](results/README.md) | Selected historical results |
| [tests/](tests/) | Automated tests |
| [docs/](docs/README.md) | Workflows, architecture, data and human-test documentation |
| `output/` | Local run outputs, ignored by Git |

Use `terrainweave --help` for commands. The [workflow guide](docs/WORKFLOWS.md)
covers JSON configs, the pipeline, Studio and optional dependencies.
See [architecture and verification](docs/ARCHITECTURE.md) for development.
