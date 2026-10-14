# Neural vision roadmap

## Current state

The project already supports an optional pretrained SegFormer model for input
semantic segmentation. It can remove likely sky, water, people, vehicles, and
animals before palette extraction. This is inference with a pretrained model;
the project does not train a neural network yet.

## Phase 1: neural input quality

The first trainable objective is semantic evidence extraction, not direct
pattern generation. The model should identify:

- sky and clouds;
- water;
- vegetation;
- soil and sand;
- rock and mountain surfaces;
- snow and ice;
- buildings and artificial surfaces.

The output should be a pixel mask plus environment probabilities. These outputs
will replace the current color-only exclusions and weighted palette heuristic.

## Phase 2: dataset and labels

Use explicit train, validation, and test folders. Keep the last split untouched
until final evaluation. Start with manually verified masks for a small subset,
then expand with pretrained-model suggestions that are reviewed by a person.
Ten images per environment are enough for a demonstration but not enough to
train a segmentation model from scratch.

## Phase 3: integration

The pipeline will become:

```text
photo set -> neural masks -> environment classifier -> weighted palette
          -> procedural generator -> explainable optimizer -> evaluation
```

The existing procedural generator remains the controlled output layer. This
makes color count, palette limits, pattern density, and reproducibility easy to
control.

## Phase 4: evaluation

Compare the neural-assisted pipeline with the current baseline using:

- held-out segmentation accuracy;
- palette changes caused by masks;
- automatic visibility proxy;
- repeated human recognition tests;
- CPU and Apple Silicon inference time.

Direct neural pattern generation is postponed until a substantially larger,
licensed, and labeled dataset is available.
