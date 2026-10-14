# Camo scene evaluation

This report compares generated uniform mockups against environmental photographs.
Lower `visibility_score` means lower local contrast in this proxy metric.
It is not a field concealment measurement and should be paired with blinded human tests.

## Results

| Pattern | Background environment | Scenes | Mean visibility score |
|---|---:|---:|---:|
| desert | desert | 10 | 0.0925 |
| desert | forest | 10 | 0.0891 |
| desert | jungle | 10 | 0.1135 |
| desert | mountain | 10 | 0.0911 |
| desert | snow | 7 | 0.1129 |
| desert | urban | 10 | 0.0998 |
| forest | desert | 10 | 0.1268 |
| forest | forest | 10 | 0.0648 |
| forest | jungle | 10 | 0.0771 |
| forest | mountain | 10 | 0.1048 |
| forest | snow | 7 | 0.1765 |
| forest | urban | 10 | 0.1140 |
| jungle | desert | 10 | 0.1389 |
| jungle | forest | 10 | 0.0706 |
| jungle | jungle | 10 | 0.0708 |
| jungle | mountain | 10 | 0.1261 |
| jungle | snow | 7 | 0.1846 |
| jungle | urban | 10 | 0.1369 |
| mountain | desert | 10 | 0.1251 |
| mountain | forest | 10 | 0.0642 |
| mountain | jungle | 10 | 0.0662 |
| mountain | mountain | 10 | 0.1188 |
| mountain | snow | 7 | 0.1695 |
| mountain | urban | 10 | 0.1234 |
| snow | desert | 10 | 0.0965 |
| snow | forest | 10 | 0.0785 |
| snow | jungle | 10 | 0.1223 |
| snow | mountain | 10 | 0.0751 |
| snow | snow | 7 | 0.0835 |
| snow | urban | 10 | 0.1087 |
| taiga | desert | 10 | 0.1228 |
| taiga | forest | 10 | 0.0696 |
| taiga | jungle | 10 | 0.0763 |
| taiga | mountain | 10 | 0.0990 |
| taiga | snow | 7 | 0.1603 |
| taiga | urban | 10 | 0.1078 |
| tundra | desert | 10 | 0.1310 |
| tundra | forest | 10 | 0.0702 |
| tundra | jungle | 10 | 0.0779 |
| tundra | mountain | 10 | 0.1206 |
| tundra | snow | 7 | 0.1844 |
| tundra | urban | 10 | 0.1290 |
| universal | desert | 10 | 0.1248 |
| universal | forest | 10 | 0.0662 |
| universal | jungle | 10 | 0.0735 |
| universal | mountain | 10 | 0.1104 |
| universal | snow | 7 | 0.1721 |
| universal | urban | 10 | 0.1229 |
| urban | desert | 10 | 0.0978 |
| urban | forest | 10 | 0.0727 |
| urban | jungle | 10 | 0.0838 |
| urban | mountain | 10 | 0.0958 |
| urban | snow | 7 | 0.1437 |
| urban | urban | 10 | 0.1055 |

## Universal versus environment-specific pattern

The comparison below uses the same scenes and scale for Universal and the matching environment pattern.
Lower scores are preferred by this proxy metric.

| Environment | Universal | Specific | Recommended by proxy | Specific minus Universal |
|---|---:|---:|---|---:|
| forest | 0.0662 | 0.0648 | forest | -0.0014 |
| desert | 0.1248 | 0.0925 | desert | -0.0323 |
| mountain | 0.1104 | 0.1188 | universal | +0.0083 |
| urban | 0.1229 | 0.1055 | urban | -0.0174 |
| jungle | 0.0735 | 0.0708 | jungle | -0.0027 |
| snow | 0.1721 | 0.0835 | snow | -0.0886 |

## Interpretation

- Compare patterns on the same background set and at the same scale.
- Use the anonymous images in `human_test/` for a forced-choice recognition test.
- Add representative local photographs before making design decisions.
