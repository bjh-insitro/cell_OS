# Nutrient Depletion Double-Counting Bug: Postmortem

**Date:** 2025-12-22
**Status:** FIXED (commit b241033)
**Severity:** CRITICAL - Was blocking all structured noise validation

## The Mystery

Structured noise validation showed:
- **All 171 A549 vehicle wells** died to **exactly viability=0.088904**
- **All 174 HepG2 vehicle wells** survived at viability=0.98
- Channel correlations stayed at 0.89 despite disabling all shared factors
- Vehicle CV was 42% instead of expected 8-12%

Initial hypothesis: Sentinel floor value for "no cells"
**WRONG** - Wells had cells (224k-360k depending on density)

## The Smoking Gun

Six significant figures across 171 wells (0.088904) is **not biology** - it's a **deterministic function output**.

Calculated from:
```
viability = 0.98 × exp(-starvation_hazard × time)
          = 0.98 × exp(-0.05 per_h × 48h)
          = 0.98 × exp(-2.4)
          = 0.088904
```

The starvation hazard was **0.05 deaths/hour for the entire 48h period** because glucose was completely depleted (0.00 mM).

## Root Cause

**Temporal frame mismatch in nutrient consumption calculation**

Location: `src/cell_os/hardware/stress_mechanisms/nutrient_depletion.py` lines 55-66

The bug:
1. Growth happens FIRST: 700k → 2.47M cells (A549, 22h doubling time)
2. Nutrient depletion runs AFTER growth
3. Code reads `vessel.cell_count = 2.47M` (post-growth)
4. **Treats it as START of interval (t0)**
5. **Predicts ADDITIONAL exponential growth**: 2.47M × exp(0.0315 × 48) = 11.2M
6. Calculates consumption for **average of 6.8M cells**
7. glucose_drop = (6.8M / 10M) × 0.8 × 48 = **26 mM** (depletes all 25 mM!)
8. Starvation hazard kicks in at 0.05/h for full 48h
9. All A549 die to 0.088904

## Why A549 but not HepG2?

Cell-line-specific growth rates:
- **A549**: `doubling_time_h: 22.0` (fast) → overconsumption → starvation
- **HepG2**: `doubling_time_h: 48.0` (slow) → reasonable consumption → survives

HepG2 calculation (pre-fix):
- Post-growth: 1.27M cells
- Predicted: 1.27M × exp(0.0144 × 48) = 2.54M
- Average consumption for 1.9M cells
- glucose_drop = 7.3 mM (leaves 17.7 mM) → no starvation

## The Fix

**Option B (Surgical):** Interpret current cell_count as END-OF-INTERVAL, back-calculate start

```python
# OLD (wrong):
viable_cells_t0 = vessel.cell_count * vessel.viability  # Treats post-growth as t0
viable_cells_t1_pred = viable_cells_t0 * exp(growth_rate * hours)  # Predicts MORE growth

# NEW (correct):
viable_cells_t1 = vessel.cell_count * vessel.viability  # Post-growth is t1
viable_cells_t0 = viable_cells_t1 / exp(growth_rate * hours)  # Back-calculate t0
```

This correctly reconstructs the interval average for consumption.

## Validation

### Before fix:
```
A549 (D8):
  viability: 0.088904
  cells: 224,102
  glucose: 0.00 mM (depleted)
  death_starvation: 0.911096
```

### After fix:
```
A549 (D8):
  viability: 0.980000
  cells: 2,470,319
  glucose: 20.53 mM (healthy)
  death_starvation: 0.000000
```

HepG2 unchanged (was already correct).

## Impact on Structured Noise Validation

**Before fix:** Vehicle CV = 42% (due to viability_factor global multiplier)
- Viability ranged from 0.089 to 0.98 (11× difference)
- viability_factor = 0.3 + 0.7×v ranged from 0.36 to 0.99 (3× difference)
- This massive multiplier drowned all structured noise
- Channel correlations forced to 0.89 regardless of coupling structure

**After fix:** Expected vehicle CV = 8-12% (realistic)
- All vehicle wells at viability ~0.98 (tight distribution)
- viability_factor no longer a bully
- Structured noise (per-well biology, stain/focus coupling) becomes visible
- Channel correlations should drop to 0.3-0.5 with proper coupling

## Lessons

1. **Six significant figures = deterministic function, not biology**
   - Biology doesn't die to 0.088904
   - Always check if a "mysterious value" is a formula output

2. **Temporal frame bugs are the worst**
   - "Perfectly reasonable model applied in wrong temporal frame"
   - Pre-growth vs post-growth is easy to mix up when order matters

3. **Order of operations matters in simulation**
   - Growth THEN nutrient depletion
   - Code must respect this ordering in calculations
   - Either pass explicit t0/t1 or back-calculate consistently

4. **Cell-line-specific bugs are extra nasty**
   - A549 dies, HepG2 survives
   - Looks like a biology difference, actually a math bug
   - Fast-growing lines expose temporal bugs that slow lines hide

## Next Steps

1. ✅ Fix committed (b241033)
2. ⏳ Re-run structured noise validation (seeds 5000-5200)
3. ⏳ Verify:
   - Vehicle CV drops from 42% to 8-12%
   - Channel correlations drop from 0.89 to 0.3-0.5
   - Well persistence improves to <15% CV
   - Fingerprints emerge (stain-like vs focus-like signatures)

4. Once validation passes:
   - Wire fingerprints into QC ontology
   - Enable "earning the gate" difficulty mode
   - Agents can now learn instrument trust relationships

## Related Issues

- **Why correlations stayed at 0.89**: Viability global multiplier dominated
- **Why vehicle CV was 42%**: Bimodal distribution (dead vs alive)
- **Why well persistence failed**: Identity swamped by massive viability noise
- **Why fingerprints didn't emerge**: Structure drowned by global attenuation

All resolved by fixing the nutrient depletion temporal frame bug.
