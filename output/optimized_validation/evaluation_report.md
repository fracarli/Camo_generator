# Camo scene evaluation

This report compares generated uniform mockups against environmental photographs.
Lower `visibility_score` means lower local contrast in this proxy metric.
It is not a field concealment measurement and should be paired with blinded human tests.

## Results

| Pattern | Background environment | Scenes | Mean visibility score |
|---|---:|---:|---:|
| desert | desert | 5 | 0.1408 |
| desert | forest | 5 | 0.0949 |
| desert | jungle | 5 | 0.0976 |
| desert | mountain | 5 | 0.0630 |
| desert | snow | 5 | 0.1060 |
| desert | taiga | 5 | 0.0894 |
| desert | tundra | 5 | 0.0544 |
| desert | urban | 5 | 0.0826 |
| forest | desert | 5 | 0.1828 |
| forest | forest | 5 | 0.0809 |
| forest | jungle | 5 | 0.0746 |
| forest | mountain | 5 | 0.1050 |
| forest | snow | 5 | 0.1689 |
| forest | taiga | 5 | 0.0916 |
| forest | tundra | 5 | 0.1066 |
| forest | urban | 5 | 0.0764 |
| jungle | desert | 5 | 0.2008 |
| jungle | forest | 5 | 0.0680 |
| jungle | jungle | 5 | 0.0812 |
| jungle | mountain | 5 | 0.1180 |
| jungle | snow | 5 | 0.1696 |
| jungle | taiga | 5 | 0.1111 |
| jungle | tundra | 5 | 0.1152 |
| jungle | urban | 5 | 0.0983 |
| mountain | desert | 5 | 0.1439 |
| mountain | forest | 5 | 0.0883 |
| mountain | jungle | 5 | 0.0806 |
| mountain | mountain | 5 | 0.0714 |
| mountain | snow | 5 | 0.1040 |
| mountain | taiga | 5 | 0.0631 |
| mountain | tundra | 5 | 0.0529 |
| mountain | urban | 5 | 0.0690 |
| snow | desert | 5 | 0.1658 |
| snow | forest | 5 | 0.1393 |
| snow | jungle | 5 | 0.1603 |
| snow | mountain | 5 | 0.0820 |
| snow | snow | 5 | 0.0750 |
| snow | taiga | 5 | 0.1356 |
| snow | tundra | 5 | 0.1013 |
| snow | urban | 5 | 0.1348 |
| taiga | desert | 5 | 0.1522 |
| taiga | forest | 5 | 0.0887 |
| taiga | jungle | 5 | 0.0898 |
| taiga | mountain | 5 | 0.0677 |
| taiga | snow | 5 | 0.1287 |
| taiga | taiga | 5 | 0.0600 |
| taiga | tundra | 5 | 0.0630 |
| taiga | urban | 5 | 0.0663 |
| tundra | desert | 5 | 0.1592 |
| tundra | forest | 5 | 0.0818 |
| tundra | jungle | 5 | 0.0784 |
| tundra | mountain | 5 | 0.0883 |
| tundra | snow | 5 | 0.1488 |
| tundra | taiga | 5 | 0.0908 |
| tundra | tundra | 5 | 0.0806 |
| tundra | urban | 5 | 0.0685 |
| universal | desert | 5 | 0.1464 |
| universal | forest | 5 | 0.0859 |
| universal | jungle | 5 | 0.0874 |
| universal | mountain | 5 | 0.0634 |
| universal | snow | 5 | 0.1130 |
| universal | taiga | 5 | 0.0723 |
| universal | tundra | 5 | 0.0623 |
| universal | urban | 5 | 0.0673 |
| urban | desert | 5 | 0.1332 |
| urban | forest | 5 | 0.0915 |
| urban | jungle | 5 | 0.0937 |
| urban | mountain | 5 | 0.0567 |
| urban | snow | 5 | 0.0984 |
| urban | taiga | 5 | 0.0758 |
| urban | tundra | 5 | 0.0521 |
| urban | urban | 5 | 0.0727 |

## Universal versus environment-specific pattern

The comparison below uses the same scenes and scale for Universal and the matching environment pattern.
Lower scores are preferred by this proxy metric.

| Environment | Universal | Specific | Recommended by proxy | Specific minus Universal |
|---|---:|---:|---|---:|
| forest | 0.0859 | 0.0809 | forest | -0.0050 |
| desert | 0.1464 | 0.1408 | desert | -0.0056 |
| mountain | 0.0634 | 0.0714 | universal | +0.0080 |
| urban | 0.0673 | 0.0727 | universal | +0.0054 |
| jungle | 0.0874 | 0.0812 | jungle | -0.0062 |
| snow | 0.1130 | 0.0750 | snow | -0.0380 |
| taiga | 0.0723 | 0.0600 | taiga | -0.0123 |
| tundra | 0.0623 | 0.0806 | universal | +0.0182 |

## Interpretation

- Compare patterns on the same background set and at the same scale.
- Use the anonymous images in `human_test/` for a forced-choice recognition test.
- Add representative local photographs before making design decisions.
