# Phase 0 Go/No-Go Specification

**Date**: 2026-01-17
**Purpose**: Define exact plots, data requirements, and decision criteria for Phase 0 wet run

---

## Canonical Data Objects

### 1. Well-Level Results (`df_wells`)

Source: `thalamus_results` table, one row per well.

| Column | Type | Description |
|--------|------|-------------|
| `design_id` | str | Design identifier |
| `well_id` | str | Well position (A01-P24) |
| `plate_id` | str | Plate identifier |
| `passage` | int | Passage number (1, 2, 3) - extracted from `day` |
| `timepoint_h` | float | 24.0 or 48.0 |
| `dose_uM` | float | [0, 2, 4, 6, 8, 15] |
| `is_sentinel` | bool | Sentinel vs experimental |
| `viability_fraction` | float | 0-1 scale |
| `morph_er` | float | ER channel intensity |
| `morph_mito` | float | Mito channel intensity |
| `morph_nucleus` | float | Nuclear channel intensity |
| `morph_actin` | float | Actin channel intensity |
| `morph_rna` | float | RNA channel intensity |
| `template` | str | A, B, or C - derived from plate_id |

### 2. Plate-Level Aggregates (`df_plates`)

Aggregation: group by `(plate_id, dose_uM, timepoint_h)`, compute mean/std.

| Column | Type | Description |
|--------|------|-------------|
| `plate_id` | str | Plate identifier |
| `passage` | int | Passage number |
| `timepoint_h` | float | Timepoint |
| `template` | str | Template A/B/C |
| `dose_uM` | float | Dose level |
| `n_wells` | int | Count of wells |
| `viability_mean` | float | Mean viability |
| `viability_std` | float | Std viability |
| `morph_er` | float | Mean ER intensity |
| `morph_mito` | float | Mean Mito intensity |
| `morph_nucleus` | float | Mean Nucleus intensity |
| `morph_actin` | float | Mean Actin intensity |
| `morph_rna` | float | Mean RNA intensity |

Note: Store morph columns directly rather than as an array. Array-in-DataFrame is inconvenient for pandas operations. Use `morph_cols = ['morph_er', 'morph_mito', 'morph_nucleus', 'morph_actin', 'morph_rna']` to slice when needed.

### 3. Morphology Feature Semantics

**What `morph_*` columns represent**: Mean fluorescence intensities per well, strictly positive (no negative values). These are raw intensity measurements, not engineered features.

### 4. Vehicle-Normalized Features (`df_normalized`)

For each plate, z-score normalize using vehicle wells as reference:

```python
morph_cols = ['morph_er', 'morph_mito', 'morph_nucleus', 'morph_actin', 'morph_rna']

# Per-plate vehicle statistics
vehicle_stats = df_wells[df_wells.dose_uM == 0].groupby('plate_id')[morph_cols].agg(['mean', 'std'])

# Z-score normalization: (x - vehicle_mean) / vehicle_std
def normalize_plate(group):
    plate_id = group['plate_id'].iloc[0]
    v_mean = vehicle_stats.loc[plate_id, (morph_cols, 'mean')].values
    v_std = vehicle_stats.loc[plate_id, (morph_cols, 'std')].values
    v_std = np.where(v_std < 1e-6, 1.0, v_std)  # prevent division by zero
    return (group[morph_cols].values - v_mean) / v_std

df_normalized = df_wells.copy()
for plate_id in df_wells['plate_id'].unique():
    mask = df_wells['plate_id'] == plate_id
    df_normalized.loc[mask, morph_cols] = normalize_plate(df_wells[mask])
```

### 5. Noise Definition (Vehicle Dispersion)

**Definition**: Noise is the within-plate dispersion of vehicle wells, measured as the median distance from each vehicle well to the plate's vehicle centroid.

```python
def compute_vehicle_dispersion(df_wells, plate_id, morph_cols):
    """Compute median distance of vehicle wells to their centroid."""
    vehicle = df_wells[(df_wells.plate_id == plate_id) & (df_wells.dose_uM == 0)]
    centroid = vehicle[morph_cols].mean().values
    distances = np.linalg.norm(vehicle[morph_cols].values - centroid, axis=1)
    return np.median(distances)

# Per-plate vehicle dispersion
vehicle_dispersion = {
    plate_id: compute_vehicle_dispersion(df_normalized, plate_id, morph_cols)
    for plate_id in df_normalized['plate_id'].unique()
}
```

This provides a meaningful baseline: "morph_shift > 2× noise" means the treated shift exceeds twice the typical vehicle well scatter.

---

## Go/No-Go Plots

### Plot 1: Morphology Shift vs Dose

**Data requirement**: `df_plates` with morphology centroid distance to vehicle.

**Aggregation**:
```python
# Per plate: compute centroid of normalized morph features
plate_centroids = df_normalized.groupby(['plate_id', 'dose_uM', 'timepoint_h'])[morph_cols].mean()

# Vehicle centroid per plate
vehicle_centroids = plate_centroids.xs(0.0, level='dose_uM')

# Shift = Euclidean distance from vehicle centroid
def morph_shift(row, vehicle):
    plate = row.name[0]  # plate_id
    v = vehicle.loc[plate].values
    t = row[morph_cols].values
    return np.linalg.norm(t - v)

plate_centroids['morph_shift'] = plate_centroids.apply(
    lambda r: morph_shift(r, vehicle_centroids), axis=1
)

# Aggregate across plates for each dose/timepoint
plot1_data = plate_centroids.groupby(['dose_uM', 'timepoint_h'])['morph_shift'].agg(['mean', 'std', 'count'])
plot1_data['sem'] = plot1_data['std'] / np.sqrt(plot1_data['count'])
```

**X-axis**: dose_uM (categorical: 0, 2, 4, 6, 8, 15)
**Y-axis**: morph_shift (mean ± SEM across plates)
**Facet**: timepoint_h (24h, 48h panels)
**Reference line**: 2× median vehicle dispersion (computed per timepoint across plates)

```python
# Add noise reference line
median_noise = np.median(list(vehicle_dispersion.values()))
# Plot horizontal line at 2 * median_noise
```

**Pass criterion**: Candidate doses (6-8 µM) show morph_shift > 2× vehicle dispersion. Clear monotonic rise through 2-8 µM, not flat + noise.

---

### Plot 2: Viability vs Dose

**Data requirement**: `df_plates` viability stats.

**Aggregation**:
```python
plot2_data = df_wells.groupby(['dose_uM', 'timepoint_h', 'plate_id'])['viability_fraction'].mean()
plot2_data = plot2_data.groupby(['dose_uM', 'timepoint_h']).agg(['mean', 'std', 'count'])
plot2_data['sem'] = plot2_data['std'] / np.sqrt(plot2_data['count'])
```

**X-axis**: dose_uM
**Y-axis**: viability_fraction (mean ± SEM)
**Facet**: timepoint_h

**Pass criterion**: 6-8 µM on shoulder (60-80% viability), 15 µM is cliff (<30%).

---

### Plot 3: Morphology Shift vs Viability (Money Plot)

**Data requirement**: Per-plate (dose, timepoint) with both metrics.

**Aggregation**:
```python
# Already have from Plot 1 and Plot 2
plot3_data = plate_centroids.reset_index()
plot3_data = plot3_data.merge(
    df_wells.groupby(['plate_id', 'dose_uM', 'timepoint_h'])['viability_fraction'].mean().reset_index(),
    on=['plate_id', 'dose_uM', 'timepoint_h']
)
```

**X-axis**: viability_fraction (per plate-dose aggregate)
**Y-axis**: morph_shift
**Color**: dose_uM
**Facet**: timepoint_h

**Pass criterion**: Candidate operating points (6-8 µM) in upper-right quadrant (high shift, viable). 15 µM in collapse region (viability low; morphology shift may be large but is death-dominated and ineligible).

---

### Plot 4: Replicate Agreement Heatmap (Effect Vectors)

**Data requirement**: Per-plate **effect vectors** (treated - vehicle), pairwise similarity.

**Key insight**: Raw centroids contain plate idiosyncrasies. What we want to compare is "what menadione did" (the effect), not "what this plate looked like".

**Aggregation**:
```python
from sklearn.metrics.pairwise import cosine_similarity

# Compute effect vectors: treated centroid - vehicle centroid for each plate
def compute_effect_vectors(plate_centroids, vehicle_centroids):
    """
    effect_vec(plate, dose, tp) = centroid(plate, dose, tp) - centroid(plate, vehicle, tp)
    """
    effect_vectors = plate_centroids.copy()
    for (plate_id, dose, tp), row in plate_centroids.iterrows():
        if dose == 0:
            # Vehicle effect is zero by definition
            effect_vectors.loc[(plate_id, dose, tp), morph_cols] = 0.0
        else:
            v = vehicle_centroids.loc[(plate_id, tp), morph_cols].values
            effect_vectors.loc[(plate_id, dose, tp), morph_cols] = row[morph_cols].values - v
    return effect_vectors

effect_vectors = compute_effect_vectors(plate_centroids, vehicle_centroids)

def replicate_agreement(dose, timepoint):
    """Cosine similarity of effect vectors across plates for a condition."""
    if dose == 0:
        return 1.0, 0.0  # Vehicle effect is zero, similarity undefined/perfect
    subset = effect_vectors.xs((dose, timepoint), level=('dose_uM', 'timepoint_h'))
    vectors = subset[morph_cols].values  # shape: (n_plates, 5)
    sim_matrix = cosine_similarity(vectors)
    # Return upper triangle mean (excluding diagonal)
    n = len(sim_matrix)
    upper_tri = sim_matrix[np.triu_indices(n, k=1)]
    return upper_tri.mean(), upper_tri.std()

plot4_data = []
for dose in [2, 4, 6, 8, 15]:  # Skip vehicle (effect is zero)
    for tp in [24.0, 48.0]:
        mean_sim, std_sim = replicate_agreement(dose, tp)
        plot4_data.append({'dose_uM': dose, 'timepoint_h': tp,
                          'mean_similarity': mean_sim, 'std_similarity': std_sim})
```

**Display**: Heatmap with dose_uM × timepoint_h, color = mean cosine similarity of effect vectors.

**Pass criterion**: Within-condition effect similarities > 0.7 for candidate doses (6-8 µM). Indicates plates agree on *what menadione does*, not just *what plates look like*.

---

### Plot 5: Technical Clustering (PCA) with Dose Dominance Test

**Data requirement**: Plate-level **effect vectors** (not raw centroids).

**Key insight**: PCA on raw centroids confounds plate effects with treatment effects. Use effect vectors so we're asking "does dose dominate the direction of change?"

**Aggregation**:
```python
from sklearn.decomposition import PCA
from scipy import stats
import statsmodels.api as sm
from statsmodels.formula.api import ols

# Use effect vectors (computed in Plot 4)
# Exclude vehicle since effect is zero
effect_nonvehicle = effect_vectors[effect_vectors.index.get_level_values('dose_uM') != 0]
X = effect_nonvehicle[morph_cols].values

pca = PCA(n_components=2)
coords = pca.fit_transform(X)

plot5_data = effect_nonvehicle.reset_index()[['plate_id', 'dose_uM', 'timepoint_h']].copy()
plot5_data['PC1'] = coords[:, 0]
plot5_data['PC2'] = coords[:, 1]
# Use existing template column from df_wells, don't re-derive
plot5_data = plot5_data.merge(
    df_wells[['plate_id', 'passage', 'template']].drop_duplicates(),
    on='plate_id'
)
```

**Dose Dominance Test** (computable criterion):
```python
# Linear regression: PC1 ~ dose (ordinal)
r2_dose = stats.linregress(plot5_data['dose_uM'], plot5_data['PC1']).rvalue ** 2

# ANOVA: PC1 ~ template + passage + dose (categorical)
model = ols('PC1 ~ C(template) + C(passage) + C(dose_uM)', data=plot5_data).fit()
anova_table = sm.stats.anova_lm(model, typ=2)

# Compute eta-squared for each factor
ss_total = anova_table['sum_sq'].sum()
eta_sq = anova_table['sum_sq'] / ss_total

dose_eta_sq = eta_sq['C(dose_uM)']
template_eta_sq = eta_sq['C(template)']
passage_eta_sq = eta_sq['C(passage)']

# Pass if dose effect size > template AND > passage
dose_dominates = (dose_eta_sq > template_eta_sq) and (dose_eta_sq > passage_eta_sq)
```

**X-axis**: PC1
**Y-axis**: PC2
**Color**: dose_uM
**Shape**: passage
**Outline**: template

**Pass criterion**:
1. `dose_eta_sq > template_eta_sq` (dose effect larger than template effect)
2. `dose_eta_sq > passage_eta_sq` (dose effect larger than passage effect)
3. Visual: dose gradient visible along PC1 axis

---

### Plot 6: Sentinel SPC Control Chart

**Data requirement**: Sentinel wells only, per-plate summary.

**Key insight**: Control limits must be **global** across plates (within each timepoint), not per-plate. We're asking "is this plate consistent with the batch?"

**Aggregation**:
```python
sentinels = df_wells[df_wells.is_sentinel]

# Per-plate sentinel summaries
sentinel_summary = []
for plate_id in sentinels['plate_id'].unique():
    plate_sent = sentinels[sentinels.plate_id == plate_id]
    tp = plate_sent['timepoint_h'].iloc[0]

    # Vehicle: viability + effect vector magnitude (should be ~0)
    veh = plate_sent[plate_sent.dose_uM == 0]
    veh_viability = veh['viability_fraction'].mean()
    # Effect magnitude for vehicle sentinels should be near zero
    veh_effect_mag = 0.0  # by definition

    # Shoulder (6 µM): viability + effect magnitude
    shoulder = plate_sent[plate_sent.dose_uM == 6]
    shoulder_viability = shoulder['viability_fraction'].mean() if len(shoulder) > 0 else np.nan
    # Compute effect: shoulder centroid - vehicle centroid for this plate
    if len(shoulder) > 0 and len(veh) > 0:
        shoulder_effect = np.linalg.norm(
            shoulder[morph_cols].mean().values - veh[morph_cols].mean().values
        )
    else:
        shoulder_effect = np.nan

    # Collapse (15 µM): viability only
    collapse = plate_sent[plate_sent.dose_uM == 15]
    collapse_viability = collapse['viability_fraction'].mean() if len(collapse) > 0 else np.nan

    sentinel_summary.append({
        'plate_id': plate_id,
        'timepoint_h': tp,
        'vehicle_viability': veh_viability,
        'shoulder_viability': shoulder_viability,
        'shoulder_effect_mag': shoulder_effect,
        'collapse_viability': collapse_viability
    })

sentinel_df = pd.DataFrame(sentinel_summary)

# Compute GLOBAL control limits across plates (within timepoint)
def compute_control_limits(series):
    """Compute mean ± 3σ control limits."""
    mean = series.mean()
    std = series.std()
    return mean - 3*std, mean, mean + 3*std

# Control limits per timepoint
control_limits = {}
for tp in [24.0, 48.0]:
    tp_data = sentinel_df[sentinel_df.timepoint_h == tp]
    control_limits[tp] = {
        'vehicle_viability': compute_control_limits(tp_data['vehicle_viability']),
        'shoulder_viability': compute_control_limits(tp_data['shoulder_viability']),
        'shoulder_effect_mag': compute_control_limits(tp_data['shoulder_effect_mag']),
        'collapse_viability': compute_control_limits(tp_data['collapse_viability'])
    }

# Flag plates outside limits
def flag_plate(row):
    tp = row['timepoint_h']
    flags = []
    for metric in ['vehicle_viability', 'shoulder_viability', 'shoulder_effect_mag', 'collapse_viability']:
        lcl, center, ucl = control_limits[tp][metric]
        val = row[metric]
        if pd.notna(val) and (val < lcl or val > ucl):
            flags.append(metric)
    return flags

sentinel_df['flags'] = sentinel_df.apply(flag_plate, axis=1)
flagged_plates = sentinel_df[sentinel_df['flags'].apply(len) > 0]
```

**Display**: Four control charts (time-ordered by plate, faceted by timepoint):
1. Vehicle viability (should be stable, ~95-100%)
2. Shoulder viability (should be ~70%, stable)
3. Shoulder effect magnitude (should be positive, stable)
4. Collapse viability (should be <30%, stable)

Each chart shows: data points, center line (mean), and ±3σ control limits (computed globally across plates within timepoint).

**Pass criterion**:
1. No plates outside ±3σ control limits
2. Collapse viability consistently < 50% (assay working)
3. Vehicle viability consistently > 80% (cells healthy)

---

## Go/No-Go Rubric

### GO if ALL of:

1. **Morphology signal exists**: At least one of {6, 8} µM at either timepoint shows morph_shift > 2× vehicle dispersion (Plot 1)

2. **Signal is reproducible**: Effect vector cosine similarity > 0.7 for candidate doses (Plot 4)

3. **Viability is shoulder**: Candidate dose viability is 50-85%, not collapsed (Plot 2)

4. **Dose dominates**: `dose_eta_sq > template_eta_sq` AND `dose_eta_sq > passage_eta_sq` (Plot 5)

5. **Sentinels are stable**: No plates outside ±3σ global control limits (Plot 6)

### NO-GO if ANY of:

1. **No signal**: morph_shift at all doses < 1.5× vehicle dispersion

2. **Technical dominates**: `template_eta_sq > dose_eta_sq` OR `passage_eta_sq > dose_eta_sq` (Plot 5)

3. **Replicate disagreement**: Mean effect vector similarity < 0.5 for candidate doses (Plot 4)

4. **Assay broken**: 15 µM viability > 50% (no collapse observed)

5. **Unstable platform**: > 2 plates flagged by sentinel SPC (outside ±3σ)

### Decision Output

Single nominated operating point: `{dose_uM, timepoint_h}` with:
- Largest reproducible morph_shift
- Viability > 50% (pooled-compatible)
- Clear separation from vehicle

---

## Implementation Notes

### Required Functions

```python
def compute_morph_shift(df_wells: pd.DataFrame) -> pd.DataFrame:
    """Compute per-plate morphology shift vs vehicle."""
    pass

def compute_replicate_similarity(df_wells: pd.DataFrame) -> pd.DataFrame:
    """Compute within-condition cosine similarity."""
    pass

def run_sentinel_spc(df_wells: pd.DataFrame) -> dict:
    """Run SPC on sentinel wells, return flagged plates."""
    pass

def generate_gonogo_report(design_id: str) -> dict:
    """Generate all 6 plots and GO/NO-GO decision."""
    pass
```

### Data Flow

```
thalamus_results (SQLite)
    ↓
df_wells (per-well, ~6876 rows)
    ↓
df_normalized (vehicle-normalized per plate)
    ↓
plate_centroids (per plate-dose-timepoint, ~108 rows)
    ↓
[Plot 1-6 aggregations]
    ↓
GO/NO-GO decision
```
