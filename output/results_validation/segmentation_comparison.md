# Neural segmentation comparison

This report compares the median internal generator score with and without
the pretrained semantic segmentation stage. Lower is better for this
diagnostic; it is not a measure of real-world concealment.

| Group | Baseline median | Semantic median | Change | Semantic better |
|---|---:|---:|---:|:---:|
| desert | 0.014478 | 0.014579 | -0.70% | no |
| forest | 0.018324 | 0.018633 | -1.69% | no |
| jungle | 0.020269 | 0.019977 | +1.44% | yes |
| mountain | 0.016702 | 0.016402 | +1.80% | yes |
| snow | 0.014786 | 0.015183 | -2.69% | no |
| taiga | 0.015889 | 0.014918 | +6.11% | yes |
| tundra | 0.016604 | 0.015519 | +6.53% | yes |
| universal | 0.017470 | 0.016181 | +7.38% | yes |
| urban | 0.018352 | 0.017257 | +5.97% | yes |

A negative change means the semantic run scored worse than the baseline.
Use the held-out evaluation and human test before drawing practical conclusions.
