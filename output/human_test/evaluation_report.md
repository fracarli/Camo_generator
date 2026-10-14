# Camo scene evaluation

This report compares generated uniform mockups against environmental photographs.
Lower `visibility_score` means lower local contrast in this proxy metric.
It is not a field concealment measurement and should be paired with blinded human tests.

## Results

| Pattern | Background environment | Scenes | Mean visibility score |
|---|---:|---:|---:|
| desert | desert | 1 | 0.1288 |
| desert | forest | 1 | 0.1268 |
| desert | jungle | 1 | 0.1737 |
| desert | mountain | 1 | 0.0504 |
| desert | snow | 1 | 0.2811 |
| desert | taiga | 1 | 0.0495 |
| desert | tundra | 1 | 0.0838 |
| desert | urban | 1 | 0.2177 |
| forest | desert | 1 | 0.3007 |
| forest | forest | 1 | 0.0126 |
| forest | jungle | 1 | 0.1349 |
| forest | mountain | 1 | 0.1303 |
| forest | snow | 1 | 0.3635 |
| forest | taiga | 1 | 0.0373 |
| forest | tundra | 1 | 0.0698 |
| forest | urban | 1 | 0.0248 |
| jungle | desert | 1 | 0.2764 |
| jungle | forest | 1 | 0.0174 |
| jungle | jungle | 1 | 0.1155 |
| jungle | mountain | 1 | 0.1567 |
| jungle | snow | 1 | 0.3900 |
| jungle | taiga | 1 | 0.0789 |
| jungle | tundra | 1 | 0.0602 |
| jungle | urban | 1 | 0.0104 |
| mountain | desert | 1 | 0.2602 |
| mountain | forest | 1 | 0.0235 |
| mountain | jungle | 1 | 0.1614 |
| mountain | mountain | 1 | 0.0613 |
| mountain | snow | 1 | 0.2928 |
| mountain | taiga | 1 | 0.1191 |
| mountain | tundra | 1 | 0.3402 |
| mountain | urban | 1 | 0.1378 |
| snow | desert | 1 | 0.1919 |
| snow | forest | 1 | 0.1864 |
| snow | jungle | 1 | 0.1898 |
| snow | mountain | 1 | 0.0628 |
| snow | snow | 1 | 0.1908 |
| snow | taiga | 1 | 0.0831 |
| snow | tundra | 1 | 0.2273 |
| snow | urban | 1 | 0.2225 |
| universal | desert | 1 | 0.1995 |
| universal | forest | 1 | 0.0101 |
| universal | jungle | 1 | 0.0950 |
| universal | mountain | 1 | 0.0852 |
| universal | snow | 1 | 0.3191 |
| universal | taiga | 1 | 0.0218 |
| universal | tundra | 1 | 0.0350 |
| universal | urban | 1 | 0.0986 |

## Universal versus environment-specific pattern

The comparison below uses the same scenes and scale for Universal and the matching environment pattern.
Lower scores are preferred by this proxy metric.

| Environment | Universal | Specific | Recommended by proxy | Specific minus Universal |
|---|---:|---:|---|---:|
| forest | 0.0101 | 0.0126 | universal | +0.0025 |
| desert | 0.1995 | 0.1288 | desert | -0.0707 |
| mountain | 0.0852 | 0.0613 | mountain | -0.0238 |
| jungle | 0.0950 | 0.1155 | universal | +0.0204 |
| snow | 0.3191 | 0.1908 | snow | -0.1283 |

## Interpretation

- Compare patterns on the same background set and at the same scale.
- Use the anonymous images in `human_test/` for a forced-choice recognition test.
- Add representative local photographs before making design decisions.
