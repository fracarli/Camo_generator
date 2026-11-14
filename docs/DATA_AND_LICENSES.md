# Data and licenses

The code is distributed under the [MIT License](../LICENSE). Background
photographs retain the terms recorded in their source metadata.

## Public corpus

[Evaluation data](../evaluation/README.md) contains the reviewed photographs,
source manifests, train/test manifests and the scenes used by the web test.
Keep photograph attributions and source metadata with the data. To check
coverage from the checkout, run `terrainweave data audit`.

## Local reference photos

Pass a folder to `terrainweave generate --input /path/to/photos` or to
`terrainweave benchmark --input /path/to/photos`. Group photos into
environment subfolders when working with multiple environments. Optional
grayscale masks can sit beside the inputs as `<filename-stem>_mask.png`.
White includes pixels and black excludes them.

Keep private photographs in a local folder. If you use `photos/` inside this
repository, Git ignores the folder. Record the source, author, license or
permission for each image before redistributing it.
