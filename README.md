# Camo

An explainable Python prototype that generates camouflage-like patterns from reference landscape photographs.

The program:

- extracts a representative color palette;
- excludes likely sky and water pixels;
- analyzes luminance and texture at three scales;
- generates several procedural patterns;
- ranks candidates and saves the best pattern for each environment.

This is an experimental image-statistics tool, not a guarantee of real-world concealment.

## Project layout

```text
photos/
├── forest/
├── mountain/
├── desert/
└── other/

output/
├── universal/
├── forest/
├── mountain/
├── desert/
└── other/
```

The `universal` pattern uses all reference images. Environment-specific patterns use only images in the corresponding group.

Each environment uses a small style profile: forest patterns preserve more fine detail, desert patterns use lighter and less saturated colors, and mountain patterns use a softer neutral palette. The selected profile is recorded in each group's `report.json`.

The generator deliberately does not copy directional high-frequency texture from source photos. This keeps the output clean and avoids visible lines while preserving multi-scale texture matching for candidate selection.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Usage

Run the default 500x500 generation:

```bash
python camo.py --input photos --output output
```

Increase the search size or palette size:

```bash
python camo.py --candidates 300 --colors 16
```

Each generated group contains:

- `best_pattern.png`: the selected 500x500 pattern;
- `palette.png`: the colors and their estimated weights;
- `report.json`: input files, mask coverage, score components, and parameters.

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
