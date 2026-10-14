# Camo scene evaluation

This report compares generated uniform mockups against environmental photographs.
Lower `visibility_score` means lower local contrast in this proxy metric.
It is not a field concealment measurement and should be paired with blinded human tests.

## Results

| Pattern | Background environment | Scenes | Mean visibility score |
|---|---:|---:|---:|
| desert | desert | 1 | 0.1293 |
| desert | forest | 1 | 0.1174 |
| desert | jungle | 1 | 0.1074 |
| desert | mountain | 1 | 0.0389 |
| desert | snow | 1 | 0.2827 |
| desert | taiga | 1 | 0.0584 |
| desert | tundra | 1 | 0.2699 |
| desert | urban | 1 | 0.2081 |
| forest | desert | 1 | 0.2942 |
| forest | forest | 1 | 0.0666 |
| forest | jungle | 1 | 0.0730 |
| forest | mountain | 1 | 0.1160 |
| forest | snow | 1 | 0.3649 |
| forest | taiga | 1 | 0.0256 |
| forest | tundra | 1 | 0.3971 |
| forest | urban | 1 | 0.0116 |
| jungle | desert | 1 | 0.2901 |
| jungle | forest | 1 | 0.0930 |
| jungle | jungle | 1 | 0.1168 |
| jungle | mountain | 1 | 0.1423 |
| jungle | snow | 1 | 0.3916 |
| jungle | taiga | 1 | 0.0505 |
| jungle | tundra | 1 | 0.0642 |
| jungle | urban | 1 | 0.0372 |
| mountain | desert | 1 | 0.2623 |
| mountain | forest | 1 | 0.1070 |
| mountain | jungle | 1 | 0.2187 |
| mountain | mountain | 1 | 0.0491 |
| mountain | snow | 1 | 0.2945 |
| mountain | taiga | 1 | 0.1267 |
| mountain | tundra | 1 | 0.0849 |
| mountain | urban | 1 | 0.1200 |
| snow | desert | 1 | 0.1892 |
| snow | forest | 1 | 0.1546 |
| snow | jungle | 1 | 0.2080 |
| snow | mountain | 1 | 0.0766 |
| snow | snow | 1 | 0.1924 |
| snow | taiga | 1 | 0.1123 |
| snow | tundra | 1 | 0.2375 |
| snow | urban | 1 | 0.2765 |
| universal | desert | 1 | 0.2019 |
| universal | forest | 1 | 0.0354 |
| universal | jungle | 1 | 0.1310 |
| universal | mountain | 1 | 0.0713 |
| universal | snow | 1 | 0.3208 |
| universal | taiga | 1 | 0.0319 |
| universal | tundra | 1 | 0.3650 |
| universal | urban | 1 | 0.1531 |

## Universal versus environment-specific pattern

The comparison below uses the same scenes and scale for Universal and the matching environment pattern.
Lower scores are preferred by this proxy metric.

| Environment | Universal | Specific | Recommended by proxy | Specific minus Universal |
|---|---:|---:|---|---:|
| forest | 0.0354 | 0.0666 | universal | +0.0312 |
| desert | 0.2019 | 0.1293 | desert | -0.0726 |
| mountain | 0.0713 | 0.0491 | mountain | -0.0222 |
| jungle | 0.1310 | 0.1168 | jungle | -0.0142 |
| snow | 0.3208 | 0.1924 | snow | -0.1284 |

## Interpretation

- Compare patterns on the same background set and at the same scale.
- Use the anonymous images in `human_test/` for a forced-choice recognition test.
- Add representative local photographs before making design decisions.
