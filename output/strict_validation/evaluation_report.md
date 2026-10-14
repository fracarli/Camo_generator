# Camo scene evaluation

This report compares generated uniform mockups against environmental photographs.
Lower `visibility_score` means lower local contrast in this proxy metric.
It is not a field concealment measurement and should be paired with blinded human tests.

## Results

| Pattern | Background environment | Scenes | Mean visibility score |
|---|---:|---:|---:|
| desert | desert | 5 | 0.1408 |
| desert | forest | 5 | 0.0594 |
| desert | jungle | 5 | 0.0976 |
| desert | mountain | 5 | 0.0630 |
| desert | snow | 5 | 0.1060 |
| desert | taiga | 5 | 0.0894 |
| desert | tundra | 5 | 0.0544 |
| desert | urban | 5 | 0.0826 |
| forest | desert | 5 | 0.1789 |
| forest | forest | 5 | 0.0689 |
| forest | jungle | 5 | 0.0748 |
| forest | mountain | 5 | 0.1035 |
| forest | snow | 5 | 0.1665 |
| forest | taiga | 5 | 0.0900 |
| forest | tundra | 5 | 0.1032 |
| forest | urban | 5 | 0.0741 |
| jungle | desert | 5 | 0.2073 |
| jungle | forest | 5 | 0.0886 |
| jungle | jungle | 5 | 0.0864 |
| jungle | mountain | 5 | 0.1284 |
| jungle | snow | 5 | 0.1803 |
| jungle | taiga | 5 | 0.1167 |
| jungle | tundra | 5 | 0.1250 |
| jungle | urban | 5 | 0.1054 |
| mountain | desert | 5 | 0.1439 |
| mountain | forest | 5 | 0.0578 |
| mountain | jungle | 5 | 0.0806 |
| mountain | mountain | 5 | 0.0714 |
| mountain | snow | 5 | 0.1040 |
| mountain | taiga | 5 | 0.0631 |
| mountain | tundra | 5 | 0.0529 |
| mountain | urban | 5 | 0.0690 |
| snow | desert | 5 | 0.1658 |
| snow | forest | 5 | 0.1291 |
| snow | jungle | 5 | 0.1603 |
| snow | mountain | 5 | 0.0820 |
| snow | snow | 5 | 0.0750 |
| snow | taiga | 5 | 0.1356 |
| snow | tundra | 5 | 0.1013 |
| snow | urban | 5 | 0.1348 |
| taiga | desert | 5 | 0.1546 |
| taiga | forest | 5 | 0.0509 |
| taiga | jungle | 5 | 0.0889 |
| taiga | mountain | 5 | 0.0691 |
| taiga | snow | 5 | 0.1312 |
| taiga | taiga | 5 | 0.0600 |
| taiga | tundra | 5 | 0.0653 |
| taiga | urban | 5 | 0.0631 |
| tundra | desert | 5 | 0.1592 |
| tundra | forest | 5 | 0.0677 |
| tundra | jungle | 5 | 0.0784 |
| tundra | mountain | 5 | 0.0883 |
| tundra | snow | 5 | 0.1488 |
| tundra | taiga | 5 | 0.0908 |
| tundra | tundra | 5 | 0.0806 |
| tundra | urban | 5 | 0.0685 |
| universal | desert | 5 | 0.1490 |
| universal | forest | 5 | 0.0638 |
| universal | jungle | 5 | 0.0864 |
| universal | mountain | 5 | 0.0681 |
| universal | snow | 5 | 0.1196 |
| universal | taiga | 5 | 0.0739 |
| universal | tundra | 5 | 0.0675 |
| universal | urban | 5 | 0.0688 |
| urban | desert | 5 | 0.1332 |
| urban | forest | 5 | 0.0789 |
| urban | jungle | 5 | 0.1036 |
| urban | mountain | 5 | 0.0552 |
| urban | snow | 5 | 0.0931 |
| urban | taiga | 5 | 0.0829 |
| urban | tundra | 5 | 0.0607 |
| urban | urban | 5 | 0.0824 |

## Universal versus environment-specific pattern

The comparison below uses the same scenes and scale for Universal and the matching environment pattern.
Lower scores are preferred by this proxy metric.

| Environment | Universal | Specific | Recommended by proxy | Specific minus Universal |
|---|---:|---:|---|---:|
| forest | 0.0638 | 0.0689 | universal | +0.0051 |
| desert | 0.1490 | 0.1408 | desert | -0.0081 |
| mountain | 0.0681 | 0.0714 | universal | +0.0033 |
| urban | 0.0688 | 0.0824 | universal | +0.0136 |
| jungle | 0.0864 | 0.0864 | universal | +0.0000 |
| snow | 0.1196 | 0.0750 | snow | -0.0446 |
| taiga | 0.0739 | 0.0600 | taiga | -0.0139 |
| tundra | 0.0675 | 0.0806 | universal | +0.0131 |

## Interpretation

- Compare patterns on the same background set and at the same scale.
- Use the anonymous images in `human_test/` for a forced-choice recognition test.
- Add representative local photographs before making design decisions.
