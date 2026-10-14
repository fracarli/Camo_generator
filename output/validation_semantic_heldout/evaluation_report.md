# Camo scene evaluation

This report compares generated uniform mockups against environmental photographs.
Lower `visibility_score` means lower local contrast in this proxy metric.
It is not a field concealment measurement and should be paired with blinded human tests.

## Results

| Pattern | Background environment | Scenes | Mean visibility score |
|---|---:|---:|---:|
| desert | desert | 5 | 0.1253 |
| desert | forest | 5 | 0.0702 |
| desert | jungle | 5 | 0.0832 |
| desert | mountain | 5 | 0.0895 |
| desert | snow | 5 | 0.0994 |
| desert | taiga | 5 | 0.1576 |
| desert | tundra | 5 | 0.0577 |
| desert | urban | 5 | 0.1590 |
| forest | desert | 5 | 0.2429 |
| forest | forest | 5 | 0.3671 |
| forest | jungle | 5 | 0.1274 |
| forest | mountain | 5 | 0.3394 |
| forest | snow | 5 | 0.2830 |
| forest | taiga | 5 | 0.2188 |
| forest | tundra | 5 | 0.3458 |
| forest | urban | 5 | 0.1518 |
| jungle | desert | 5 | 0.2049 |
| jungle | forest | 5 | 0.0813 |
| jungle | jungle | 5 | 0.1225 |
| jungle | mountain | 5 | 0.0898 |
| jungle | snow | 5 | 0.2389 |
| jungle | taiga | 5 | 0.1228 |
| jungle | tundra | 5 | 0.0678 |
| jungle | urban | 5 | 0.0975 |
| mountain | desert | 5 | 0.1950 |
| mountain | forest | 5 | 0.1207 |
| mountain | jungle | 5 | 0.0675 |
| mountain | mountain | 5 | 0.1009 |
| mountain | snow | 5 | 0.1680 |
| mountain | taiga | 5 | 0.0493 |
| mountain | tundra | 5 | 0.0823 |
| mountain | urban | 5 | 0.1385 |
| snow | desert | 5 | 0.1828 |
| snow | forest | 5 | 0.2374 |
| snow | jungle | 5 | 0.2110 |
| snow | mountain | 5 | 0.1316 |
| snow | snow | 5 | 0.1176 |
| snow | taiga | 5 | 0.1637 |
| snow | tundra | 5 | 0.1863 |
| snow | urban | 5 | 0.2199 |
| taiga | desert | 5 | 0.2159 |
| taiga | forest | 5 | 0.3939 |
| taiga | jungle | 5 | 0.0590 |
| taiga | mountain | 5 | 0.2679 |
| taiga | snow | 5 | 0.2213 |
| taiga | taiga | 5 | 0.2035 |
| taiga | tundra | 5 | 0.3453 |
| taiga | urban | 5 | 0.2789 |
| tundra | desert | 5 | 0.1781 |
| tundra | forest | 5 | 0.1373 |
| tundra | jungle | 5 | 0.1098 |
| tundra | mountain | 5 | 0.0863 |
| tundra | snow | 5 | 0.1072 |
| tundra | taiga | 5 | 0.0900 |
| tundra | tundra | 5 | 0.0453 |
| tundra | urban | 5 | 0.1136 |
| universal | desert | 5 | 0.2260 |
| universal | forest | 5 | 0.3365 |
| universal | jungle | 5 | 0.1081 |
| universal | mountain | 5 | 0.3167 |
| universal | snow | 5 | 0.2988 |
| universal | taiga | 5 | 0.1489 |
| universal | tundra | 5 | 0.3144 |
| universal | urban | 5 | 0.1957 |
| urban | desert | 5 | 0.1404 |
| urban | forest | 5 | 0.0963 |
| urban | jungle | 5 | 0.0982 |
| urban | mountain | 5 | 0.0931 |
| urban | snow | 5 | 0.0995 |
| urban | taiga | 5 | 0.0639 |
| urban | tundra | 5 | 0.0748 |
| urban | urban | 5 | 0.0799 |

## Universal versus environment-specific pattern

The comparison below uses the same scenes and scale for Universal and the matching environment pattern.
Lower scores are preferred by this proxy metric.

| Environment | Universal | Specific | Recommended by proxy | Specific minus Universal |
|---|---:|---:|---|---:|
| forest | 0.3365 | 0.3671 | universal | +0.0306 |
| desert | 0.2260 | 0.1253 | desert | -0.1006 |
| mountain | 0.3167 | 0.1009 | mountain | -0.2158 |
| urban | 0.1957 | 0.0799 | urban | -0.1158 |
| jungle | 0.1081 | 0.1225 | universal | +0.0145 |
| snow | 0.2988 | 0.1176 | snow | -0.1812 |
| taiga | 0.1489 | 0.2035 | universal | +0.0546 |
| tundra | 0.3144 | 0.0453 | tundra | -0.2691 |

## Interpretation

- Compare patterns on the same background set and at the same scale.
- Use the anonymous images in `human_test/` for a forced-choice recognition test.
- Add representative local photographs before making design decisions.
