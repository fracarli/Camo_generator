# Camo scene evaluation

This report compares generated uniform mockups against environmental photographs.
Lower `visibility_score` means lower local contrast in this proxy metric.
It is not a field concealment measurement and should be paired with blinded human tests.

## Results

| Pattern | Background environment | Scenes | Mean visibility score |
|---|---:|---:|---:|
| desert | desert | 5 | 0.1288 |
| desert | forest | 5 | 0.0717 |
| desert | jungle | 5 | 0.0773 |
| desert | mountain | 5 | 0.0895 |
| desert | snow | 5 | 0.0993 |
| desert | taiga | 5 | 0.1556 |
| desert | tundra | 5 | 0.0562 |
| desert | urban | 5 | 0.1595 |
| forest | desert | 5 | 0.2604 |
| forest | forest | 5 | 0.3858 |
| forest | jungle | 5 | 0.1314 |
| forest | mountain | 5 | 0.3582 |
| forest | snow | 5 | 0.3006 |
| forest | taiga | 5 | 0.2304 |
| forest | tundra | 5 | 0.3647 |
| forest | urban | 5 | 0.1698 |
| jungle | desert | 5 | 0.2038 |
| jungle | forest | 5 | 0.0815 |
| jungle | jungle | 5 | 0.1230 |
| jungle | mountain | 5 | 0.0893 |
| jungle | snow | 5 | 0.2385 |
| jungle | taiga | 5 | 0.1226 |
| jungle | tundra | 5 | 0.0677 |
| jungle | urban | 5 | 0.0966 |
| mountain | desert | 5 | 0.1950 |
| mountain | forest | 5 | 0.1207 |
| mountain | jungle | 5 | 0.0675 |
| mountain | mountain | 5 | 0.1009 |
| mountain | snow | 5 | 0.1680 |
| mountain | taiga | 5 | 0.0493 |
| mountain | tundra | 5 | 0.0823 |
| mountain | urban | 5 | 0.1385 |
| snow | desert | 5 | 0.1815 |
| snow | forest | 5 | 0.2297 |
| snow | jungle | 5 | 0.2063 |
| snow | mountain | 5 | 0.1249 |
| snow | snow | 5 | 0.1199 |
| snow | taiga | 5 | 0.1603 |
| snow | tundra | 5 | 0.1786 |
| snow | urban | 5 | 0.2152 |
| taiga | desert | 5 | 0.2292 |
| taiga | forest | 5 | 0.4190 |
| taiga | jungle | 5 | 0.0669 |
| taiga | mountain | 5 | 0.2913 |
| taiga | snow | 5 | 0.2432 |
| taiga | taiga | 5 | 0.2061 |
| taiga | tundra | 5 | 0.3698 |
| taiga | urban | 5 | 0.2942 |
| tundra | desert | 5 | 0.1781 |
| tundra | forest | 5 | 0.1373 |
| tundra | jungle | 5 | 0.1098 |
| tundra | mountain | 5 | 0.0863 |
| tundra | snow | 5 | 0.1072 |
| tundra | taiga | 5 | 0.0900 |
| tundra | tundra | 5 | 0.0453 |
| tundra | urban | 5 | 0.1136 |
| universal | desert | 5 | 0.2215 |
| universal | forest | 5 | 0.3319 |
| universal | jungle | 5 | 0.1068 |
| universal | mountain | 5 | 0.3121 |
| universal | snow | 5 | 0.2942 |
| universal | taiga | 5 | 0.1477 |
| universal | tundra | 5 | 0.3101 |
| universal | urban | 5 | 0.1930 |
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
| forest | 0.3319 | 0.3858 | universal | +0.0539 |
| desert | 0.2215 | 0.1288 | desert | -0.0927 |
| mountain | 0.3121 | 0.1009 | mountain | -0.2112 |
| urban | 0.1930 | 0.0799 | urban | -0.1131 |
| jungle | 0.1068 | 0.1230 | universal | +0.0162 |
| snow | 0.2942 | 0.1199 | snow | -0.1744 |
| taiga | 0.1477 | 0.2061 | universal | +0.0584 |
| tundra | 0.3101 | 0.0453 | tundra | -0.2648 |

## Interpretation

- Compare patterns on the same background set and at the same scale.
- Use the anonymous images in `human_test/` for a forced-choice recognition test.
- Add representative local photographs before making design decisions.
