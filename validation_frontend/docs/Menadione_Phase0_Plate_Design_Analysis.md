# Menadione Phase 0 Plate Design Analysis

**Date**: 2026-01-16
**Templates**: MENADIONE_PHASE0_TEMPLATE_A, B, C
**Format**: 384-well plate

## Design Overview

| Component | Count | Purpose |
|-----------|-------|---------|
| Total wells | 382 | 2 empty corner wells |
| Sentinel wells | 64 (16.8%) | Fixed positions for SPC and edge detection |
| Experimental wells | 318 | Randomized positions for dose-response |
| Doses | 6 | 0, 5, 15, 35, 75, 150 µM |
| Replicates per dose | 53 | Sufficient power for 10% viability differences |

## Sentinel Structure

### Vehicle Sentinels (40 wells, 0 µM DMSO)

**Edge wells (20):**
```
A01, A03, A06, A12, A18, A21, A24
D01, D24, H01, H24, L01, L24
P01, P03, P06, P12, P18, P21, P24
```

**Interior wells (20):**
```
C03, C08, C13, C18, C22
F05, F10, F15, F20
G12, K12
J05, J10, J15, J20
M03, M08, M13, M18, M22
```

### Treatment Sentinels (24 wells)

**Mild menadione (12 wells, 15 µM):**
```
D11, D14, E06, E19, G08, G17, J08, J17, L06, L19, M11, M14
```

**Strong menadione (12 wells, 75 µM):**
```
D09, D16, E08, E17, G06, G19, J06, J19, L08, L17, M09, M16
```

### Sentinel Spatial Layout

```
    1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24
A   V  .  V  .  .  V  .  .  .  .  .  V  .  .  .  .  .  V  .  .  V  .  .  V
B   .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
C   .  .  V  .  .  .  .  V  .  .  .  .  V  .  .  .  .  V  .  .  .  V  .  .
D   V  .  .  .  .  .  .  .  S  .  M  .  .  M  .  S  .  .  .  .  .  .  .  V
E   .  .  .  .  .  M  .  S  .  .  .  .  .  .  .  .  S  .  M  .  .  .  .  .
F   .  .  .  .  V  .  .  .  .  V  .  .  .  .  V  .  .  .  .  V  .  .  .  .
G   .  .  .  .  .  S  .  M  .  .  .  V  .  .  .  .  M  .  S  .  .  .  .  .
H   V  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  V
I   .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
J   .  .  .  .  V  S  .  M  .  V  .  .  .  .  V  .  M  .  S  V  .  .  .  .
K   .  .  .  .  .  .  .  .  .  .  .  V  .  .  .  .  .  .  .  .  .  .  .  .
L   V  .  .  .  .  M  .  S  .  .  .  .  .  .  .  .  S  .  M  .  .  .  .  V
M   .  .  V  .  .  .  .  V  S  .  M  .  V  M  .  S  .  V  .  .  .  V  .  .
N   .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
O   .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .  .
P   V  .  V  .  .  V  .  .  .  .  .  V  .  .  .  .  .  V  .  .  V  .  .  V

V = Vehicle (0 µM), M = Mild (15 µM), S = Strong (75 µM)
```

## Template Randomization Strategy

| Template | Seed | Sentinel Positions | Experimental Positions |
|----------|------|-------------------|------------------------|
| A | 1001 | Fixed (identical) | Randomized |
| B | 2002 | Fixed (identical) | Randomized |
| C | 3003 | Fixed (identical) | Randomized |

**Experimental well overlap between templates:** ~15-20%

This means each dose has ~80% of its wells at different positions across templates, enabling position effect averaging while maintaining some position replication for direct comparison.

## Variance Partitioning Capability

### What This Design Can Detect

| Effect Type | Capability | Mechanism |
|-------------|------------|-----------|
| Edge effects | ✓ Good | 20 edge + 20 interior vehicle sentinels |
| Illumination gradients | ✓ Good | Vehicle sentinels span all 4 quadrants |
| Focus drift | ✓ Good | Top-to-bottom sentinel distribution |
| Cross-plate reproducibility | ✓ Good | 24 fixed treatment sentinels for SPC |
| Cross-passage variation | ✓ Good | 53 reps/dose with fixed normalizers |
| Position-specific bias | ✓ Good | Fixed sentinels track same positions |
| Out-of-well/neighbor effects | △ Limited | Would need dedicated neighbor design |

### Quadrant Balance (Experimental Wells)

Each dose has reasonable distribution across all four quadrants:

| Dose (µM) | Top-Left | Top-Right | Bottom-Left | Bottom-Right |
|-----------|----------|-----------|-------------|--------------|
| 0 | 11-13 | 11-16 | 10-18 | 12-14 |
| 5 | 10-16 | 11-13 | 10-17 | 13-15 |
| 15 | 9-15 | 14-24 | 5-16 | 9-17 |
| 35 | 12-14 | 9-16 | 11-18 | 12-16 |
| 75 | 14-16 | 10-14 | 12-16 | 9-15 |
| 150 | 10-13 | 12-16 | 10-13 | 15-18 |

## Design Assessment

### Strengths

1. **Sufficient replication**: 53 wells per dose provides good statistical power
2. **Fixed SPC anchors**: Identical sentinel positions across templates enables direct cross-plate comparison
3. **Edge effect quantification**: Explicit 50/50 split between edge and interior vehicle sentinels
4. **Balanced randomization**: Different seeds give position averaging while maintaining ~15-20% overlap for validation
5. **Practical execution**: Standard 384-well format, no complex blocking schemes

### Limitations

1. **Neighbor effects**: No systematic way to quantify well-to-well contamination
2. **Gradient sentinels**: No dedicated rows for measuring diffusion from high-dose wells
3. **Corner wells**: 2 empty wells (not using A24 corners for all treatments)

### Would More Sentinels Help?

**No.** Current 64 sentinels (16.8%) is sufficient for Phase 0 goals. The trade-off:

| Change | Benefit | Cost |
|--------|---------|------|
| +20 vehicle | Marginal position coverage gain | -20 experimental reps |
| +8 per treatment | Tighter SPC confidence intervals | -16 experimental reps |

The limiting factor is not sentinel count but the absence of dedicated neighbor-effect wells. If variance analysis reveals unexpected position effects, a targeted follow-up experiment can address this.

## Conclusion

This design is well-suited for Phase 0 objectives:

1. **Establish dose-response curve** - 53 reps/dose is adequate power
2. **Quantify major variance components** - passage, plate, position are addressable
3. **Set up SPC infrastructure** - fixed sentinels provide the baseline

The randomization strategy is pragmatic. It averages out position effects without requiring complex blocked designs that would be harder to execute and analyze.

**Recommendation**: Run the plates, examine the data, let the results inform whether second-order effects (neighbor contamination, gradient artifacts) warrant dedicated investigation.
