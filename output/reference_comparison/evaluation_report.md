# Camo scene evaluation

This report compares generated uniform mockups against environmental photographs.
Lower `visibility_score` means lower local contrast in this proxy metric.
It is not a field concealment measurement and should be paired with blinded human tests.

## Results

| Pattern | Background environment | Scenes | Mean visibility score |
|---|---:|---:|---:|
| mtp_style | desert | 10 | 0.1448 |
| mtp_style | forest | 10 | 0.0733 |
| mtp_style | jungle | 10 | 0.0868 |
| mtp_style | mountain | 10 | 0.1144 |
| mtp_style | snow | 10 | 0.2179 |
| mtp_style | taiga | 10 | 0.1273 |
| mtp_style | tundra | 10 | 0.0890 |
| mtp_style | urban | 10 | 0.1559 |
| multicam_style | desert | 10 | 0.1442 |
| multicam_style | forest | 10 | 0.0741 |
| multicam_style | jungle | 10 | 0.1270 |
| multicam_style | mountain | 10 | 0.1218 |
| multicam_style | snow | 10 | 0.1955 |
| multicam_style | taiga | 10 | 0.1413 |
| multicam_style | tundra | 10 | 0.0939 |
| multicam_style | urban | 10 | 0.1715 |
| universal | desert | 10 | 0.1413 |
| universal | forest | 10 | 0.1150 |
| universal | jungle | 10 | 0.1103 |
| universal | mountain | 10 | 0.1096 |
| universal | snow | 10 | 0.1791 |
| universal | taiga | 10 | 0.1548 |
| universal | tundra | 10 | 0.0749 |
| universal | urban | 10 | 0.1748 |
| vegetata_style | desert | 10 | 0.1786 |
| vegetata_style | forest | 10 | 0.0658 |
| vegetata_style | jungle | 10 | 0.0977 |
| vegetata_style | mountain | 10 | 0.1641 |
| vegetata_style | snow | 10 | 0.2460 |
| vegetata_style | taiga | 10 | 0.1496 |
| vegetata_style | tundra | 10 | 0.0914 |
| vegetata_style | urban | 10 | 0.1885 |

## Universal versus environment-specific pattern

The comparison below uses the same scenes and scale for Universal and the matching environment pattern.
Lower scores are preferred by this proxy metric.

| Environment | Universal | Specific | Recommended by proxy | Specific minus Universal |
|---|---:|---:|---|---:|

## Interpretation

- Compare patterns on the same background set and at the same scale.
- Use the anonymous images in `human_test/` for a forced-choice recognition test.
- Add representative local photographs before making design decisions.
