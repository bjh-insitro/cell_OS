# Design Generator Guide

The Design Generator (`scripts/design_catalog.py`) creates custom experimental designs for Cell Thalamus with full control over all parameters.

## Quick Start

```python
from scripts.design_catalog import DesignGenerator

generator = DesignGenerator()

design = generator.create_design(
    design_id='my_custom_design_v1',
    description='My custom experiment',

    # Customize any parameters you want
    cell_lines=['A549', 'HepG2', 'iPSC_NGN2', 'iPSC_Microglia'],
    compounds=['tBHQ', 'CCCP', 'tunicamycin'],
    dose_multipliers=[0, 0.1, 1.0, 10.0],
    replicates_per_dose=3,
    plate_format=96,
    checkerboard=False,
)
```

## All Parameters

### Cell Lines & Compounds

**`cell_lines`** (default: `['A549', 'HepG2']`)
- Available: `A549`, `HepG2`, `iPSC_NGN2` (neurons), `iPSC_Microglia`
- List of cell lines to test

**`compounds`** (default: all 10 Phase 0 compounds)
- Available: `tBHQ`, `H2O2`, `tunicamycin`, `thapsigargin`, `CCCP`, `oligomycin`, `etoposide`, `MG132`, `nocodazole`, `paclitaxel`
- List of compounds to test

### Dose Configuration

**`n_doses`** (default: `4`)
- Number of dose levels per compound
- Ignored if `dose_multipliers` is provided

**`dose_multipliers`** (default: `[0, 0.1, 1.0, 10.0]`)
- Dose positions **relative to compound IC50**
- Examples:
  - `[0, 0.1, 1.0, 10.0]` → vehicle, 0.1×IC50, 1×IC50, 10×IC50
  - `[0, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0]` → 8-point dose response for 384-well
- `0` = vehicle control (no compound)

**Example dose calculation:**
- `tBHQ` IC50 = 30 µM
- `dose_multipliers = [0, 0.1, 1.0, 10.0]`
- Actual doses: 0 µM, 3 µM, 30 µM, 300 µM

### Replicates & Batch Structure

**`replicates_per_dose`** (default: `3`)
- Technical replicates per dose level
- Trade-off: More reps = better statistics but fewer compounds/doses fit

**`days`** (default: `[1, 2]`)
- Experimental days (biological replicates)
- Each day = independent experiment run

**`operators`** (default: `['Operator_A', 'Operator_B']`)
- Operators performing the experiment
- Captures operator-to-operator variability

**`timepoints_h`** (default: `[12.0, 48.0]`)
- Timepoints in hours
- Examples: `[12.0]` (single), `[6.0, 12.0, 24.0, 48.0]` (kinetics)

### Sentinel Wells (QC Controls)

**`sentinel_config`** (default: standard QC sentinels)

Format:
```python
{
    'compound_name': {
        'dose_uM': float,      # Exact dose in µM
        'n_per_cell': int      # Count per cell line
    }
}
```

Default:
```python
{
    'DMSO': {'dose_uM': 0.0, 'n_per_cell': 4},
    'tBHQ': {'dose_uM': 10.0, 'n_per_cell': 2},
    'tunicamycin': {'dose_uM': 2.0, 'n_per_cell': 2},
}
```

**Purpose:** QC sentinels for Statistical Process Control (SPC):
- Detect plate-to-plate drift
- Monitor assay stability over time
- Identify systematic errors

### Plate Layout

**`plate_format`** (default: `96`)
- Options: `96` (96-well plate) or `384` (384-well plate)
- 384-well allows higher throughput:
  - 96-well: 8 rows (A-H) × 12 columns = 96 wells
  - 384-well: 16 rows (A-P) × 24 columns = 384 wells

**`checkerboard`** (default: `False`)
- `False`: Separate physical plates per cell line
  - Example: Plate_A549_Day1_... and Plate_HepG2_Day1_...
- `True`: Mix cell lines on same plate in checkerboard pattern
  - Example: Plate_Day1_... contains both A549 and HepG2
  - Good for: Side-by-side comparison, reduced batch effects
  - Bad for: Fewer wells available per cell line

**`exclude_corners`** (default: `False`)
- Exclude corner wells (A1, A12, H1, H12 for 96-well)
- Common QC practice: corner wells often show artifacts

**`exclude_edges`** (default: `False`)
- Exclude all edge wells (entire first/last row/column)
- Reduces: evaporation, temperature gradient effects
- Cost: ~40% fewer usable wells (96-well: 96→48, 384-well: 384→216)

### Output

**`output_path`** (default: `data/designs/<design_id>.json`)
- Where to save the design JSON file
- File is ready for `standalone_cell_thalamus.py --design-json`

## Design Examples

### Example 1: All 4 Cell Lines (Neurons + Microglia)

```python
design = generator.create_design(
    design_id='phase0_4cell_neurons_microglia_v1',
    description='Test all 4 cell lines with focused compound panel',

    cell_lines=['A549', 'HepG2', 'iPSC_NGN2', 'iPSC_Microglia'],
    compounds=['tBHQ', 'CCCP', 'tunicamycin', 'nocodazole'],
    dose_multipliers=[0, 0.1, 1.0, 10.0],
    replicates_per_dose=2,  # Reduced to fit 4 cell lines

    days=[1],
    operators=['Operator_A'],
    timepoints_h=[12.0, 48.0],

    plate_format=96,
    checkerboard=False,  # 8 separate plates (4 cell lines × 2 timepoints)
)
```

**Result:** 296 wells across 8 plates

### Example 2: High-Throughput 384-Well Screening

```python
design = generator.create_design(
    design_id='phase0_384well_highthroughput_v1',
    description='High-throughput screening with 8-point dose response',

    cell_lines=['A549', 'HepG2'],
    compounds=['tBHQ', 'H2O2', 'tunicamycin', 'thapsigargin', 'CCCP',
              'oligomycin', 'etoposide', 'MG132', 'nocodazole', 'paclitaxel'],
    dose_multipliers=[0, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0],  # 8 doses
    replicates_per_dose=2,

    days=[1],
    operators=['Operator_A'],
    timepoints_h=[48.0],  # Single endpoint

    sentinel_config={
        'DMSO': {'dose_uM': 0.0, 'n_per_cell': 8},
        'tBHQ': {'dose_uM': 10.0, 'n_per_cell': 4},
        'tunicamycin': {'dose_uM': 2.0, 'n_per_cell': 4},
    },

    plate_format=384,
    checkerboard=True,  # Both cell lines on same plate
    exclude_corners=True,
)
```

**Result:** 352 wells on 1 plate (fits in 380 available wells with corners excluded)

### Example 3: Minimal Pilot Design

```python
design = generator.create_design(
    design_id='phase0_pilot_minimal_v1',
    description='Quick proof-of-concept with minimal wells',

    cell_lines=['A549'],
    compounds=['tBHQ', 'CCCP', 'tunicamycin'],
    dose_multipliers=[0, 0.1, 1.0, 10.0],
    replicates_per_dose=3,

    days=[1],
    operators=['Operator_A'],
    timepoints_h=[12.0],

    sentinel_config={'DMSO': {'dose_uM': 0.0, 'n_per_cell': 4}},

    plate_format=96,
    checkerboard=False,
)
```

**Result:** 40 wells on 1 plate (perfect for quick validation)

### Example 4: Kinetics Study (Multi-Timepoint)

```python
design = generator.create_design(
    design_id='phase0_kinetics_time_course_v1',
    description='Time-course study with 4 timepoints',

    cell_lines=['A549', 'HepG2'],
    compounds=['tBHQ', 'tunicamycin', 'CCCP'],
    dose_multipliers=[0, 1.0, 10.0],  # Just 3 doses
    replicates_per_dose=2,

    days=[1],
    operators=['Operator_A'],
    timepoints_h=[6.0, 12.0, 24.0, 48.0],  # 4 timepoints

    plate_format=96,
    checkerboard=False,
)
```

**Result:** Captures early (6h) vs late (48h) response dynamics

## Well Capacity Calculator

**96-well plate:**
- Total wells: 96
- Exclude corners: 92 available
- Exclude edges: 48 available

**384-well plate:**
- Total wells: 384
- Exclude corners: 380 available
- Exclude edges: 216 available

**Wells needed formula:**
```
wells_per_cell_line = (n_compounds × n_doses × replicates_per_dose) + n_sentinels

If checkerboard:
    total_needed = wells_per_cell_line × n_cell_lines
Else:
    total_needed = wells_per_cell_line  (per plate)
    n_plates = n_cell_lines × n_days × n_operators × n_timepoints
```

**Example:**
- 4 compounds, 4 doses, 3 reps = 48 experimental wells
- 8 sentinels
- **Total: 56 wells per cell line**
- With 2 cell lines (separate plates): 2 plates needed
- With 2 cell lines (checkerboard): 112 wells needed (fits in 96 if no edge exclusion)

## Troubleshooting

### Error: "Not enough wells!"

**Problem:** Design requires more wells than available on plate.

**Solutions:**
1. Reduce `replicates_per_dose` (e.g., 3 → 2)
2. Reduce number of compounds
3. Reduce number of doses (e.g., `[0, 0.1, 1.0, 10.0]` → `[0, 1.0, 10.0]`)
4. Use 384-well format instead of 96-well
5. Turn off `exclude_edges` or `exclude_corners`
6. Use separate plates instead of checkerboard

### Error: StopIteration

**Problem:** Generator ran out of well positions mid-design.

**Solution:** Same as "Not enough wells" - reduce complexity or use larger plate format.

## Running Simulations with Custom Designs

After generating a design:

```bash
# 1. Upload to JupyterHub
scp data/designs/my_custom_design_v1.json jupyterhub.insitro.com:/mnt/shared/brig/cell_OS/data/designs/

# 2. SSH to JupyterHub
ssh jupyterhub.insitro.com
cd /mnt/shared/brig/cell_OS

# 3. Run simulation
python3 standalone_cell_thalamus.py --design-json data/designs/my_custom_design_v1.json --seed 0 --workers 64

# 4. Sync results to Mac
./scripts/sync_aws_db.sh

# 5. View in dashboard
# Open http://localhost:5173/cell-thalamus
```

## Design Philosophy

**Separation of Concerns:**
- **Design Catalog** = "What to test" (compounds, doses, replicates)
- **Standalone Script** = "How to simulate" (physics engine, RNG, noise models)

**Benefits:**
- Version-controlled designs (track evolution over time)
- Reusable designs (run same design with different seeds)
- Easy to share (JSON file = complete experiment specification)
- Validation before running (check well count fits plate format)

**When to Create New Designs:**
- Testing new cell lines (neurons, microglia)
- Different compound panels
- Different dose ranges
- Different replicate strategies
- Different plate layouts (checkerboard vs separate)
