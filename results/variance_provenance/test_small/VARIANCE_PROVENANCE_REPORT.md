# Variance Provenance Report

Decomposition of detector-induced variance into components.

## Run Configuration

- **Profile**: realistic
- **Design**: dmso_only (biology held constant)
- **Seed**: 42
- **Plate format**: 96-well
- **Small mode**: True
- **Replicates**: 1

## Counterfactual Toggles

Five measurements per well with different realism layer combinations:

1. **bio**: All layers OFF (biology-only baseline)
2. **geo**: Position effects (row/col gradients + edge dimming)
3. **noise**: Edge noise inflation (heteroscedastic detector noise)
4. **path**: QC pathologies (channel dropout, focus miss, noise spike)
5. **obs**: All layers ON (observed, full profile)

## Variance Budget

Per-channel variance decomposition:

| Channel | Var(total) | Var(geo) | Var(noise) | Var(path) | Var(resid) |
|---------|------------|----------|------------|-----------|------------|
| er      |       6.72 |     6.72 |       0.00 |      0.00 |       0.00 |
| mito    |      13.18 |    13.18 |       0.00 |      0.00 |       0.00 |
| nucleus |      22.30 |    22.30 |       0.00 |      0.00 |       0.00 |
| actin   |       6.99 |     6.99 |       0.00 |      0.00 |       0.00 |
| rna     |      17.82 |    17.82 |       0.00 |      0.00 |       0.00 |

## Variance Fractions

Fraction of total variance attributable to each component:

| Channel | Geo (%) | Noise (%) | Path (%) | Resid (%) |
|---------|---------|-----------|----------|----------|
| er      |   100.0 |       0.0 |      0.0 |       0.0 |
| mito    |   100.0 |       0.0 |      0.0 |       0.0 |
| nucleus |   100.0 |       0.0 |      0.0 |       0.0 |
| actin   |   100.0 |       0.0 |      0.0 |       0.0 |
| rna     |   100.0 |       0.0 |      0.0 |       0.0 |

**Summary**:
- Total variance explained (geo + noise + path): 100.0%
- Mean residual fraction: 0.0%

## Residual Interpretation

The **residual** quantifies non-additivity and interactions between layers.

- **Small residual (<10%)**: Layers are roughly independent (additive variance)
- **Large residual (>20%)**: Layers interact (e.g., edge noise inflation is multiplicative with geometry)

**Note**: A large residual is not a bug—it's honest accounting of layer interactions.

## Output Files

- `bio_wells.csv` - Biology-only measurements
- `geo_wells.csv` - Geometry-only measurements
- `noise_wells.csv` - Noise-only measurements
- `path_wells.csv` - Pathology-only measurements
- `obs_wells.csv` - Observed measurements (all layers)
- `deltas.csv` - Per-well deltas for all components
- `variance_budget.csv` - Per-channel variance budget
- `variance_fractions_stacked.png` - Stacked bar plot of variance fractions
- `delta_heatmaps_er.png` - Plate heatmaps of delta components
- `variance_total_by_channel.png` - Total variance by channel

