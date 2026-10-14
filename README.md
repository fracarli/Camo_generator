# Camo

An explainable Python prototype that generates camouflage-like patterns from reference landscape photographs.

The program:

- extracts a representative color palette;
- excludes likely sky and water pixels;
- analyzes luminance and texture at three scales;
- measures directional bias, transitions, and fine-edge density to reject weak shapes;
- generates several procedural patterns;
- ranks candidates and saves the best pattern for each environment.

This is an experimental image-statistics tool, not a guarantee of real-world concealment.

## Project layout

```text
photos/
├── forest/
├── mountain/
├── taiga/
├── tundra/
├── jungle/
├── desert/
├── urban/
├── snow/
└── other/

output/
├── universal/
├── forest/
├── mountain/
├── taiga/
├── tundra/
├── jungle/
├── desert/
├── urban/
├── snow/
├── other/
├── all_patterns_grid.png
├── report.json
├── validation_report.json
├── validation_report.md
├── summary_grid.json
└── segmentation_masks/       # created only when semantic segmentation is used
```

The `universal` pattern uses all non-snow reference images and gives every non-snow environment group equal weight, regardless of how many pixels or photographs it contains. Snow references are deliberately excluded from Universal because their very bright palette would make the mixed pattern less useful for the other environments. Taiga, tundra, and jungle references are included because they represent useful non-snow environments. Environment-specific patterns use only images in the corresponding group. Urban images contribute to both `urban` and `universal` outputs; snow images contribute only to `snow`.

Each environment uses a small style profile. Forest, taiga, and jungle patterns preserve more fine detail and use smaller, denser organic blobs. Desert patterns use larger, broader regions with a flatter aspect ratio. Mountain and tundra patterns use medium-to-large irregular regions, urban patterns use more elongated fragmented shapes, and snow patterns use larger cold regions with strong contrast. The selected profile is recorded in each group's `report.json`.

The universal palette reserves one matte forest-green color when forest references are available. This keeps green visible in the mixed environment result without allowing bright or saturated colors to dominate. Palette colors are gently anchored to Fosco-style matte military tone families: Olive Drab, NATO Green, Service/Mud Brown, Tropentarn Sand, and NATO Black. These are approximate style references, not exact colorimetric reproductions of a specific product.

Universal output also balances the effective pixel coverage of the palette. After generating the competing regions, the script calibrates their area so that one color cannot become an oversized background by chance.

The generator deliberately does not copy directional high-frequency texture from source photos. It combines competing smooth fields with blurred organic blob fields at several scales: large regions break the silhouette, medium regions create transitions, and small regions add controlled detail. Adjacent regions can share boundaries and merge instead of producing only isolated islands inside one background color. The candidate score also applies a small penalty to strongly directional or excessively fragmented structures, which helps reject stripe-like results.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The neural input stage is optional. Install its dependencies only when needed:

```bash
python -m pip install --timeout 600 --retries 10 -r requirements-ml.txt
```

## Usage

Run the default 500x500 generation:

```bash
python camo.py --input photos --output output
```

When started without `--mode`, the terminal asks whether to use `standard`, `custom`, or `optimized` mode. Choosing `standard` preserves the current generator behavior and defaults. Choosing `custom` asks for pattern density, the maximum Universal color share, the Universal green share, and the dark-color share. Choosing `optimized` applies the best configuration found by the current benchmark: semantic input segmentation, high pattern density, and five colors. Explicit CLI values still take precedence. All prompts and generated reports are in English.

Run the benchmark-selected configuration with:

```bash
python camo.py --mode optimized --device cpu --save-segmentation-masks
```

The optimized mode is based on the project's internal diagnostics, not on a
validated field concealment test. It should be treated as the recommended
experimental default until printed and real-scene evaluations are available.

The same custom settings can be supplied without interactive prompts:

```bash
python camo.py --mode custom --density high --max-color-share 0.30 --green-share 0.22 --dark-share 0.10
```

Available density levels are `low`, `standard`, and `high`. The color-share values are fractions from `0.00` to `1.00`, for example `0.22` means 22% of the Universal output. The color count can still be selected with `--colors 2` through `--colors 5`.

The default palette contains 5 colors, which is suitable for a first industrial-style test. When running interactively, the program asks for the number of colors; pressing Enter keeps 5. The supported range is 2 to 5 colors. The default pattern now uses denser shape scales, so more distinct spots remain visible in the 500x500 output.

You can also select the number directly from the command line:

```bash
python camo.py --colors 3
```

## Optional neural input segmentation

The generator can use a pretrained SegFormer semantic segmentation model before computing image statistics. It predicts a class for each pixel and removes likely sky, water, people, vehicles, and animals from the reference evidence. Manual masks still have priority, and the existing color-based filter remains as a safety fallback.

Run it explicitly with:

```bash
python camo.py --mode standard --segmentation semantic --save-segmentation-masks
```

The default model is `nvidia/segformer-b0-finetuned-ade-512-512`. Its weights are downloaded and cached on the first run. On Apple Silicon, `--device auto` uses MPS when available; use `--device cpu` for a compatibility fallback. Neural masks are saved under `output/segmentation_masks/` when `--save-segmentation-masks` is provided, and each group report records the mask source and labels detected in the input images.

The ML environment includes both `torch` and `torchvision`; they must be installed as a compatible pair because Transformers uses `torchvision` for the SegFormer image processor. A Hugging Face token is optional for this public model; the unauthenticated warning only indicates lower download limits.

The neural stage improves input selection; it does not generate the camouflage pattern itself and it is not a guarantee of real-world concealment. Validate the masks visually before relying on them for new image types.

Increase the search effort while keeping the industrial five-color limit:

```bash
python camo.py --candidates 300 --colors 5
```

## Configuration benchmark

Use `benchmark.py` to compare controlled combinations of density, palette size,
random seed, and optional semantic segmentation. The default benchmark tests
the three density levels with 3 and 5 colors, using 16 candidates per group.
It writes a ranked JSON/Markdown report and a Universal contact sheet under
`output/benchmark/`.

```bash
python benchmark.py --segmentation none --clean
```

After installing the optional ML dependencies, compare the automatic mask and
the neural mask in one run:

```bash
python benchmark.py --segmentation both --device cpu --clean
```

For a faster smoke test:

```bash
python benchmark.py --densities standard --colors 5 --candidates 4 --clean
```

The benchmark score is an internal diagnostic for color, luminance, texture,
and shape structure. It is useful for comparing code changes, but it is not a
measurement of real-world concealment.

## Outfit mockups

Generate realistic headless full-uniform visualizations from the exact generated
patterns. Each mockup uses a neutral product-photography reference with a
combat shirt, cargo trousers, and combat boots. The pattern is composited over
the extracted garment surface while preserving folds, seams, pockets, and
volume shading. The result is a visual comparison aid, not a manufacturing
template.

```bash
python generate_outfit_mockups.py
```

The default output contains Universal, Desert, Mountain, Snow, and Jungle
mockups plus a contact sheet under `output/outfit_mockups/`. Other groups can be
selected explicitly:

```bash
python generate_outfit_mockups.py --groups universal,forest,taiga,tundra,urban
```

The folder also contains the AI-generated neutral uniform reference image used
for the garment mask and shading. The actual mockups use the project's PNG
patterns procedurally so their colors are not altered by image generation.

Each generated group contains:

- `best_pattern.png`: the selected 500x500 pattern;
- `palette.png`: the colors and their estimated weights;
- `report.json`: input files, mask coverage, semantic exclusions, score components, the ten best candidate summaries, and parameters.

The output root also contains `all_patterns_grid.png`, a configurable overview of selected pattern groups. When no selection is provided, the default grid contains Universal, Desert, Mountain, Snow, and Jungle. The grid is regenerated automatically after every run.

To choose the groups in the summary image interactively, press Enter to accept the default or enter a comma-separated list such as:

```text
universal,forest,taiga,tundra,jungle
```

The same selection can be provided directly:

```bash
python camo.py --summary-groups universal,desert,mountain,snow,jungle
```

The selected groups are recorded in `summary_grid.json`.

The output root also contains `validation_report.json` and `validation_report.md`. These measure the rendered PNGs after blur, including actual palette coverage, maximum color share, color entropy, mean luminance, edge density, horizontal/vertical edge balance, directional bias, transition density, fine-edge density, and the candidate score. They are intended to guide later improvements and are not a measure of real-world concealment.

## Masks

For precise control, place a grayscale mask beside an image:

```text
photos/forest/landscape.jpg
photos/forest/landscape_mask.png
```

White pixels are included and black pixels are excluded. If no mask exists, the program applies a conservative automatic filter for blue water and bright sky. To disable it:

```bash
python camo.py --no-auto-mask
```

## Limitations

The score measures color, luminance, and texture similarity. It does not measure object detection, shape visibility, movement, shadows, material reflectance, or print behavior. Validate patterns visually and with printed samples before drawing practical conclusions.
# Camo_generator
