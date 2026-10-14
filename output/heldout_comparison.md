# Held-out baseline versus semantic comparison

Both pattern sets were optimized on the first five sorted backgrounds
and evaluated on the remaining five. Lower visibility score is better
within this proxy metric; this is not field evidence.

| Environment | Baseline | Semantic | Change | Semantic better |
|---|---:|---:|---:|:---:|
| desert | 0.1288 | 0.1253 | +2.66% | yes |
| forest | 0.3858 | 0.3671 | +4.84% | yes |
| jungle | 0.1230 | 0.1225 | +0.41% | yes |
| mountain | 0.1009 | 0.1009 | +0.00% | no |
| snow | 0.1199 | 0.1176 | +1.87% | yes |
| taiga | 0.2061 | 0.2035 | +1.23% | yes |
| tundra | 0.0453 | 0.0453 | +0.00% | no |
| urban | 0.0799 | 0.0799 | +0.00% | no |

Universal mean across held-out environments: baseline `0.2397`, semantic `0.2431`.

The semantic pipeline should not replace the baseline globally yet. It is promising for environment-specific patterns, while Universal requires more backgrounds and a better balanced objective.
