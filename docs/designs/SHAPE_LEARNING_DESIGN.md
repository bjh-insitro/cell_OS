# Shape Learning Design

**Design ID:** `phase0_shape_learning_v1`
**Primary Goal:** Nuisance model identification (separating instrument truth from biological truth)
**Secondary Goal:** Coarse response manifold characterization
**NOT FOR:** Mechanism claims, causal inference

---

## Design Philosophy

This design is optimized for **learning the shape of your system** by explicitly separating:
- **Instrument artifacts** (imaging drift, staining variability, edge effects)
- **Biological truth** (compound responses, cell-line differences)

It improves upon phase0_v2 by adding explicit diagnostic controls and measurement geometry.

---

## Key Improvements Over phase0_v2

### 1. Instrument Sentinel Class (Non-Biological Controls)
**What:** 2 wells per plate that report imaging/staining stability independent of biological stressors
**Type:** DMSO vehicle wells explicitly labeled as `sentinel_type: "instrument"`
**Purpose:** Detect plate-level drift that has nothing to do with biology
**Impact:**
- If instrument sentinels move, the plate is lying → catch it before interpreting biology
- Baseline stability measurement for SPC (Statistical Process Control)

**Wells per plate:** 2
**Total across experiment:** 48 (2 × 24 plates)

---

### 2. Diagnostic Sentinel Geometry
**What:** Sentinel placement enforces detection of spatial gradients
**Strategy:**
- At least one sentinel in **near-edge** region (rows B/G, cols 2/11)
- At least one sentinel in **center** region (rows C-F, cols 4-9)
- At least one sentinel in each **half** (top/bottom, left/right)

**Why:** If you don't place sentinels to test gradients, you're hoping gradients reveal themselves. They won't — they'll bias you quietly.

**Example:** If DMSO vehicle shows dose-response pattern (impossible biologically), gradient detected.

---

### 3. Bridge Controls Across Day/Operator
**What:** Extra replicates of select sentinels to measure batch effects with high confidence
**Strategy:**
- **Vehicle control:** +2 replicates per plate (8 → 10 total, but 2 are marked as bridge controls)
- **ER_mid (thapsigargin):** +2 replicates per plate (3 → 5 total, 2 are bridge controls)

**Purpose:** Stable anchor across all day/operator combinations for:
- Estimating day effect with tight confidence intervals
- Estimating operator effect independently
- Detecting interaction effects

**Wells per plate:** 4 (2 vehicle + 2 ER_mid)
**Total:** 96 (4 × 24 plates)

---

### 4. Absolute Dose Anchor (Calibration Control)
**What:** Fixed-dose ladder independent of IC50 priors
**Compounds:** tBHQ (A549) and oligomycin (HepG2)
**Doses:** 0.3 µM and 3.0 µM (fixed, not IC50-scaled)
**Purpose:** Disentangle "wrong IC50 prior" from "weird biology" from "broken plate"

**Why:** If everything is IC50-relative, you can't tell if weirdness is from wrong priors or real biology. Absolute doses provide calibration anchor.

**Wells:** 2 doses per anchor compound = 4 total per plate

---

### 5. Timepoint Perturbation (Temporal Aliasing Detection)
**What:** One compound gets an **off-grid timepoint** to expose temporal aliasing
**Compound:** Thapsigargin (ER stress)
**Standard timepoints:** 12h, 24h, 48h
**Perturbed:** Day 1, Operator_A gets **6h, 24h, 48h** (6h instead of 12h)

**Why:** Tests whether "structure" is actually just time-aliasing. If 6h vs 12h changes everything, your system is more time-sensitive than you thought.

**Plates affected:** 3 (1 day × 1 operator × 3 timepoints for one cell line)

---

### 6. Enhanced Metadata for Audit Trail
**What:** Explicit design goals and constraints in metadata

```json
{
  "primary_goal": "nuisance_model_identification",
  "secondary_goal": "coarse_response_manifold",
  "not_for": ["mechanism_claims", "causal_inference"],
  "enhancements": {
    "instrument_sentinels": true,
    "diagnostic_sentinel_geometry": true,
    "bridge_controls": true,
    "timepoint_perturbation": {...}
  }
}
```

**Why:** Future-you will forget what this was for. This prevents over-interpretation.

---

## Well Budget (88 wells per plate)

| Category | Wells | Notes |
|----------|-------|-------|
| **Experimental** | 60 | See breakdown below |
| **Sentinels** | 28 | Breakdown below |
| **Total** | 88 | Exact fill (no partial plates) |

### Experimental Well Breakdown (60 per plate)

**A549 compounds:**
- tBHQ (anchor): 12 IC50-scaled + 2 absolute = **14 wells**
- H2O2: 12 IC50-scaled = **12 wells**
- Tunicamycin: 12 IC50-scaled = **12 wells**
- Thapsigargin: 12 IC50-scaled = **12 wells**
- CCCP: 10 IC50-scaled (5 doses) = **10 wells**

**HepG2 compounds:**
- Oligomycin (anchor): 12 IC50-scaled + 2 absolute = **14 wells**
- Etoposide: 12 IC50-scaled = **12 wells**
- MG132: 12 IC50-scaled = **12 wells**
- Nocodazole: 12 IC50-scaled = **12 wells**
- Paclitaxel: 10 IC50-scaled (5 doses) = **10 wells**

### Sentinel Breakdown (28 per plate)

| Type | Wells | Purpose |
|------|-------|---------|
| Instrument | 2 | Non-biological imaging stability |
| Vehicle | 6 | Baseline control |
| Vehicle (bridge) | 2 | Cross-batch anchor |
| ER_mid | 3 | ER stress reference |
| ER_mid (bridge) | 2 | Cross-batch anchor |
| Mito_mid | 5 | Mitochondrial stress reference |
| Proteostasis | 5 | Proteasome reference |
| Oxidative | 3 | Oxidative stress reference |
| **Total** | 28 | - |

---

## Plate Structure

**Total plates:** 24
**Format:** 96-well
**Exclusions:** A01, A06, A07, A12, H01, H06, H07, H12 (8 wells)
**Available:** 88 wells per plate

**Batch structure:**
- 2 cell lines (A549, HepG2) — **separate plates**
- 2 days (biological replicates)
- 2 operators (technical variability)
- 3 timepoints (12h, 24h, 48h) — **except perturbed conditions**

**Calculation:** 2 cell lines × 2 days × 2 operators × 3 timepoints = **24 plates**

---

## Spatial Design Features

### Position Stability
- **Per-cell-line shuffle:** Same position = same condition across all plates within a cell line
- **Deterministic RNG:** Seed-based (seed=42) for reproducibility
- **Tradeoff:** Position becomes "fixed fingerprint" → good for identifiability, carries plate-specific artifacts consistently

### Sentinel Placement Logic
1. Group sentinels by type (instrument, vehicle, ER_mid, etc.)
2. For each type, enforce:
   - At least one in near-edge region
   - At least one in center region
   - Spread across top/bottom and left/right halves
3. Randomize within constraints using deterministic RNG

---

## What This Design Detects

### ✅ Can Detect
- **Plate-level imaging drift** (instrument sentinels)
- **Row/column gradients** (diagnostic geometry)
- **Edge effects** (near-edge vs center sentinels)
- **Day effects** (bridge controls across days)
- **Operator effects** (bridge controls across operators)
- **Temporal sensitivity** (timepoint perturbation)
- **Spatial confounding** (position stability + scatter)

### ❌ Cannot Detect (By Design)
- **Mechanism** (not enough resolution, not the goal)
- **Causal direction** (observational, not interventional beyond compound)
- **Cell-type-specific vs. universal** (only 2 cell lines)
- **Long-term kinetics** (max 48h, except one 6h perturbation)

---

## Analysis Recommendations

### 1. Instrument Sentinel Check (First Priority)
```python
# If instrument sentinels show variance > threshold, flag plate
instrument_wells = [w for w in wells if w['sentinel_type'] == 'instrument']
if std(instrument_wells) > THRESHOLD:
    print(f"WARNING: Plate {plate_id} imaging unstable")
```

### 2. Gradient Detection
```python
# Compare near-edge vs center for each sentinel type
for stype in ['vehicle', 'ER_mid', 'mito_mid']:
    edge_vals = [w for w in wells if w['sentinel_type'] == stype and w['well_pos'] in near_edge]
    center_vals = [w for w in wells if w['sentinel_type'] == stype and w['well_pos'] in center]
    if mean(edge_vals) - mean(center_vals) > THRESHOLD:
        print(f"WARNING: {stype} shows edge effect")
```

### 3. Batch Effect Estimation
```python
# Use bridge controls to estimate day and operator effects
bridge_vehicle = [w for w in wells if w['is_bridge_control'] and w['compound'] == 'DMSO']
day_effect = group_by(bridge_vehicle, 'day').mean_diff()
operator_effect = group_by(bridge_vehicle, 'operator').mean_diff()
```

### 4. Temporal Aliasing Check
```python
# Compare thapsigargin at 6h vs 12h (Day 1, Operator_A only)
thasp_6h = [w for w in wells if w['compound'] == 'thapsigargin' and w['timepoint_h'] == 6.0]
thasp_12h = [w for w in wells if w['compound'] == 'thapsigargin' and w['timepoint_h'] == 12.0]
if correlation(thasp_6h, thasp_12h) < THRESHOLD:
    print("WARNING: System highly time-sensitive, early dynamics important")
```

---

## Limitations and Future Directions

### Not Included (To Maintain 88-Well Budget)
1. **Absolute dose ladder** — removed to fit within 88 wells
   - Can be added by reducing replicates from 2 → 1 for some conditions
   - Or by removing highest dose (30× IC50) for some compounds
2. **More cell lines** — only A549 and HepG2
   - Adding iPSC_NGN2 would double plate count (24 → 36)
3. **Higher-resolution timepoints** — only one perturbation
   - Full time-series would require many more plates

### Recommended Next Steps After Phase 0
1. **Analyze nuisance structure** — use instrument sentinels to build correction model
2. **Estimate batch effects** — use bridge controls for precise day/operator offsets
3. **Check gradient assumptions** — verify diagnostic geometry reveals (or doesn't) gradients
4. **Assess temporal resolution needs** — use timepoint perturbation to decide if finer sampling needed

---

## File Locations

**Generated design:** `data/designs/phase0_shape_learning_v1.json`
**Generator script:** `scripts/design_generator_shape_learning.py`
**This document:** `docs/SHAPE_LEARNING_DESIGN.md`

---

## Quick Summary

> **What changed:** Added instrument sentinels (non-biological), diagnostic sentinel geometry (edge vs center), bridge controls (cross-batch anchors), and timepoint perturbation (temporal aliasing test).
>
> **Why:** To separate instrument truth from biological truth and detect nuisance structure before making biological claims.
>
> **Cost:** No additional plates (still 24), but redistributed 28 sentinel wells for better diagnostics.
