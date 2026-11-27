# Universal versions and reference patterns on held-out backgrounds

Backgrounds: `evaluation/splits/test.json` (27 photos, snow excluded), 3 positions each, identical for every pattern. Visibility proxy: lower is better. Sorted by the optimizer criterion, 0.5 x mean over environments + 0.5 x worst environment.
This is an automatic proxy on screen images; people decide in the web game.

| Pattern | desert | forest | jungle | mountain | taiga | tundra | urban | Mean | Worst |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| universal | 0.0902 | 0.1280 | 0.0964 | 0.0810 | 0.1253 | 0.0637 | 0.1413 | 0.1037 | 0.1413 (urban) |
| vegetato | 0.0891 | 0.1288 | 0.0989 | 0.0830 | 0.1268 | 0.0600 | 0.1418 | 0.1041 | 0.1418 (urban) |
| universal2 | 0.0812 | 0.0890 | 0.0849 | 0.1024 | 0.1488 | 0.0361 | 0.1530 | 0.0993 | 0.1530 (urban) |
| digitalflora | 0.0822 | 0.0924 | 0.0865 | 0.1017 | 0.1465 | 0.0365 | 0.1527 | 0.0998 | 0.1527 (urban) |
| flecktarn | 0.0802 | 0.0777 | 0.0865 | 0.1134 | 0.1581 | 0.0342 | 0.1584 | 0.1012 | 0.1584 (urban) |
| woodland | 0.0810 | 0.0628 | 0.0869 | 0.1249 | 0.1718 | 0.0394 | 0.1647 | 0.1045 | 0.1718 (taiga) |
| multiterrain | 0.1076 | 0.1913 | 0.1308 | 0.0891 | 0.0934 | 0.1221 | 0.1333 | 0.1239 | 0.1913 (forest) |
| digital3 | 0.1165 | 0.2029 | 0.1399 | 0.0991 | 0.0898 | 0.1336 | 0.1342 | 0.1309 | 0.2029 (forest) |

## Universal v2 search

- 240 candidates (v1: 24), five colours, with v1 itself among them; v1 lost.
- Training backgrounds: `evaluation/splits/train.json`, 84 photos, snow excluded.
- Environments interleaved; every candidate scored on 14 backgrounds (two per
  environment) before the beam of 24 started pruning (v1 pruned to 8 after the
  first forest photo).
- Ranking: 0.5 x mean over environments + 0.5 x worst environment.
- Training score: v2 0.1066, v1 0.1143.

```bash
terrainweave optimize --groups universal --background-manifest evaluation/splits/train.json \
  --pattern-root <folder with universal/best_pattern.png = v1> --output output/optimized_v2 \
  --candidates 240 --beam-size 24 --background-limit 0 --background-order interleaved \
  --warmup 14 --score-aggregation environment_worst
python scripts/compare_universal.py --output results/optimized_v2/heldout_comparison.md
```
