# Phase 1 Causal Design

**Design ID:** `phase1_causal_v1`
**Primary Goal:** Causal effect estimation (defensible dose-response curves)
**Secondary Goal:** High-precision IC50 estimation with tight confidence intervals
**NOT FOR:** Broad manifold mapping, multiple compound screening

---

## Design Philosophy

Phase 1 is **focused causal estimation** under controlled conditions. After Phase 0 identifies the "shape of your system" (nuisance structure, batch effects, artifacts), Phase 1 asks:

> **"What is the causal effect of this specific intervention?"**

This requires a fundamentally different design than Phase 0:
- **Single compound per cell line** (focused, not exploratory)
- **High replication** (8 reps per dose, 12 vehicle controls)
- **Within-plate randomization** (prevents spatial confounding)
- **Single timepoint** (temporal clarity, no kinetic confounding)

---

## Key Differences from Phase 0

| Feature | Phase 0 (Shape Learning) | Phase 1 (Causal) |
|---------|-------------------------|------------------|
| **Goal** | Learn system shape, identify nuisance | Estimate causal effects |
| **Compounds** | 5-10 per cell line (exploratory) | 1 per cell line (focused) |
| **Replication** | 2 per dose (efficient screening) | 8 per dose + 12 vehicle (defensible) |
| **Randomization** | Per-cell-line shuffle (stable positions) | Per-plate shuffle (prevent confounding) |
| **Timepoints** | Multiple (12h, 24h, 48h) | Single (24h) |
| **Plates** | 24 (2 cell lines × 2 days × 2 ops × 3 time) | 8 (2 cell lines × 2 days × 2 ops × 1 time) |
| **Power** | Medium (screening) | High (causal estimation) |
| **Use Case** | Calibration, artifact detection | Publishable dose-response curves |

---

## Design Structure

### Well Budget (88 wells per plate)

**Experimental wells: 60**
- **12 vehicle controls (DMSO)** - explicit causal baseline
- **48 dose-response wells** - 6 doses × 8 replicates

**Sentinels: 28 (biological) + 2 (instrument)**
- **28 biological sentinels** - fixed scaffold positions (same as Phase 0)
- **2 instrument sentinels** - A01, A12 (excluded positions, outside 88-well budget)

### Total: 90 wells per plate in JSON
- 60 experimental + 28 biological = **88 budgeted wells** ✓
- +2 instrument sentinels at excluded positions = **90 total**

---

## Causal Core Parameters

### Dose Ladder (IC50-scaled)
```python
dose_multipliers = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0]
```
- **0.1×**: Sub-threshold (should see minimal effect)
- **0.3×**: Early response
- **1.0×**: IC50 (by definition, 50% effect)
- **3.0×**: Strong response
- **10.0×**: Near-maximal
- **30.0×**: Saturating

### Replication Strategy
```python
reps_per_dose = 8      # High power for EC50 estimation
vehicle_reps = 12      # Extra baseline for causal contrast
```

**Why 8 replicates?**
- EC50 confidence intervals scale as ~1/√n
- 2 reps → wide CIs (screening-level)
- 4 reps → moderate CIs (exploratory)
- **8 reps → tight CIs (defensible/publishable)**

**Why 12 vehicle controls?**
- Need tight baseline for causal contrast
- Vehicle variance sets denominator for effect size
- More vehicle reps = tighter baseline = cleaner dose-response

---

## Within-Plate Randomization (Critical!)

### Phase 0 Position Strategy (Position Stability)
```python
# Phase 0: Per-cell-line shuffle (same position across all plates)
rng = make_rng(seed, f"exp_positions|{cell_line}")
positions = available_positions.copy()
rng.shuffle(positions)  # ONE shuffle for entire cell line

# Same position = same condition across all plates
# Good for: identifiability, calibration, "position as fingerprint"
# Bad for: spatial confounding (if plate has gradient, it's consistent)
```

### Phase 1 Position Strategy (Within-Plate Randomization)
```python
# Phase 1: Per-plate shuffle (different positions per plate)
rng = make_rng(seed, f"plate_assign|{plate_id}")
positions = available_positions.copy()
rng.shuffle(positions)  # NEW shuffle for EACH plate

# Same position ≠ same condition across plates
# Good for: prevents spatial confounding (gradient can't bias one dose)
# Bad for: position no longer useful as identity tag
```

### Why This Matters

**Phase 0 (calibration phase):**
- You WANT position stability → if position drifts, you can detect it
- Plate gradients are less concerning because you're not making causal claims
- Goal: learn the shape of the system

**Phase 1 (causal phase):**
- You DON'T want position confounding → if plate has row gradient, it shouldn't bias dose X
- Randomize within plate so any spatial artifact averages out across conditions
- Goal: estimate causal effect cleanly

**Example attack on Phase 0 design used for causal claims:**
> "Your Phase 0 design has tunicamycin always at position C03. If row C has 10% higher signal due to edge effects, your dose-response is confounded. You can't tell if the effect is from the drug or from the row."

**Defense with Phase 1 design:**
> "In Phase 1, tunicamycin positions are randomized within each plate. Row effects average out across doses. The dose-response curve is unconfounded."

---

## Batch Structure

### Current Design
```python
days = [1, 2]                    # Biological replicates
operators = ["Operator_A", "Operator_B"]  # Technical variability
timepoints_h = [24.0]            # Single timepoint (causal clarity)
cell_lines = ["A549", "HepG2"]   # Separate plates per cell line
```

**Total plates:** 2 cell lines × 2 days × 2 operators × 1 timepoint = **8 plates**

### Why Single Timepoint?

**Phase 0:** Multiple timepoints (12h, 24h, 48h) to capture kinetics
**Phase 1:** Single timepoint (24h) for causal clarity

**Rationale:**
- **Causal estimand is time-specific:** "What is the dose-response at 24h?"
- **Multiple timepoints introduce kinetic confounding:** Early vs late responders
- **Simplifies interpretation:** No need to model time × dose interaction
- **Power concentration:** All replication focused on one time point

**If you need kinetics:**
- Run **separate Phase 1 designs** at different timepoints (e.g., Phase1-12h, Phase1-24h, Phase1-48h)
- Don't mix timepoints within a causal estimation plate set
- Each timepoint gets its own power budget

---

## Compound Selection

### Current Defaults
```python
compound_by_cell_line = {
    "A549": "tunicamycin",     # ER stress (N-glycosylation inhibitor)
    "HepG2": "oligomycin",     # Mitochondrial (ATP synthase inhibitor)
}
```

### How to Choose

**From Phase 0 screening:**
1. Identify compound with **strongest, cleanest response**
2. Check Phase 0 dose-response looks **monotonic** (not biphasic)
3. Verify IC50 estimate is **in range** (not too low/high)
4. Confirm **no batch confounding** in Phase 0

**Bad choices:**
- Compound with weak/noisy Phase 0 response → low power even with 8 reps
- Compound with biphasic curve → hard to interpret
- Compound with batch confounding in Phase 0 → may still be confounded

**Good choices:**
- Strong, clean, monotonic response in Phase 0
- IC50 in middle of tested range (not edge case)
- Consistent across Phase 0 batch factors

---

## Statistical Power

### EC50 Confidence Interval Width (Simulation)

Estimated from bootstrap (50 iterations) on synthetic data:

| Design | Reps/Dose | Mean EC50 CI Width (µM) | vs Phase 0 v2 |
|--------|-----------|-------------------------|---------------|
| Phase 0 v2 | 2 | 2.64 | 1.00× (baseline) |
| **Phase 1 causal** | 8 | **0.66** | **0.25× (4× tighter)** ✓ |

**Interpretation:**
- Phase 0 v2: CI width ≈ 2.64 µM (screening-level precision)
- Phase 1 causal: CI width ≈ 0.66 µM (publishable precision)
- **4× improvement** in EC50 precision from 2 → 8 replicates

**Note:** This is synthetic data. Real improvement depends on biological variance.

---

## Sentinels (Same as Phase 0)

Phase 1 preserves the **fixed sentinel scaffold** from Phase 0:

### Biological Sentinels (28 per plate, budgeted)
- **8 DMSO (vehicle)** - baseline QC
- **5 tBHQ (30 µM)** - oxidative stress reference
- **5 thapsigargin (0.5 µM)** - ER stress reference
- **5 oligomycin (1 µM)** - mitochondrial reference
- **5 MG132 (1 µM)** - proteasome reference

**Scaffold provenance:**
- `scaffold_id`: `phase0_v2_scaffold_v1`
- `scaffold_hash`: `901ffeb4603019fe`

### Instrument Sentinels (2 per plate, unbudgeted)
- **A01, A12** (excluded corner positions)
- `compound: None`, `readout_model: "instrument_only"`
- Detect plate-level imaging drift independent of biology

### Why Keep Phase 0 Sentinels in Phase 1?

**Consistency:** Direct comparison to Phase 0 calibration data
**Quality Control:** Same SPC (Statistical Process Control) thresholds
**Batch Effect Detection:** Same anchor points across phases

**Note:** Phase 1 sentinels are **NOT marked as bridge controls** (unlike Phase 0 shape learning). They're diagnostic, not for batch effect estimation (Phase 1 uses within-plate randomization instead).

---

## When to Use Phase 1 vs Phase 0

### Use Phase 0 (Shape Learning)
✓ First time using this system
✓ New cell line or compound class
✓ Need to detect artifacts/batch effects
✓ Want to screen multiple compounds
✓ Calibrating for future experiments
✓ Budget/throughput limited (fewer plates)

### Use Phase 1 (Causal)
✓ Already ran Phase 0 (know your system)
✓ Need publishable dose-response curves
✓ Making causal claims about specific compound
✓ Need tight EC50 confidence intervals
✓ Regulatory submission or validation
✓ Have good IC50 prior from Phase 0

### Don't Use Phase 1 If...
❌ Haven't run Phase 0 (don't know nuisance structure)
❌ Want to test many compounds (use Phase 0 or high-throughput)
❌ Need kinetic trajectories (use dedicated time-course)
❌ Making exploratory/mechanism claims (use Phase 2+)

---

## Design Invariants (Same as Phase 0)

All Phase 0 invariants apply to Phase 1, **except**:

### Modified Invariant: Position Stability
**Phase 0:** Same position = same condition across plates (position stability enforced)
**Phase 1:** Position randomized within plate (position stability **NOT** enforced)

**Why the difference?**
- Phase 0: Position stability enables identifiability (position = fingerprint)
- Phase 1: Position randomization prevents spatial confounding (causal clarity)

### All Other Invariants Preserved
✓ Sentinel scaffold exact match (cryptographic provenance)
✓ Plate capacity (88 budgeted wells)
✓ Condition multiset identical (per cell line)
✓ Spatial dispersion (bbox area ≥ 40) - still applies to sentinels
✓ Sentinel placement quality (edge/center spread)
✓ Batch balance (equal wells across strata)

---

## Example Use Case

### Scenario
You ran **Phase 0 shape learning** and found:
- Tunicamycin (ER stress) shows strong, clean dose-response in A549
- IC50 estimate from Phase 0: ~1.0 µM (Phase 0 CI: 0.5-2.0 µM, wide)
- No major batch confounding detected
- Want to publish this dose-response with tight CIs

### Phase 1 Design
```python
create_phase1_causal_design(
    design_id="phase1_tunicamycin_A549_v1",
    cell_lines=["A549"],
    compound_by_cell_line={"A549": "tunicamycin"},
    ic50_by_compound={"tunicamycin": 1.0},  # From Phase 0
    days=[1, 2, 3],  # Extra biological reps for publication
    operators=["Operator_A"],  # Single operator is fine
    timepoints_h=[24.0],
    reps_per_dose=8,
    vehicle_reps=12,
)
```

**Plates:** 1 cell line × 3 days × 1 operator × 1 timepoint = **3 plates**
**Power:** 8 reps × 3 days = **24 measurements per dose**
**Expected CI width:** ~0.4 µM (vs Phase 0: 1.5 µM)

### Result
- Tight dose-response curve with narrow CIs
- Defensible EC50 estimate for publication
- Within-plate randomization prevents spatial confounding claims

---

## Limitations

### What Phase 1 Does NOT Do

❌ **Mechanism mapping** - not enough compounds/conditions
❌ **Kinetic trajectories** - single timepoint only
❌ **Cell-line comparisons** - focused on one compound per cell line
❌ **Broad screening** - use Phase 0 or high-throughput instead

### What Phase 1 Requires

⚠️ **Good IC50 prior** - from Phase 0 or literature (dose ladder centered on IC50)
⚠️ **Known system behavior** - Phase 0 calibration recommended
⚠️ **Specific hypothesis** - "What is the effect of X on Y?"
⚠️ **Commitment** - 8 plates per cell line (with 2 days × 2 operators)

---

## Next Phase (Phase 2+)

After Phase 1 causal estimation, you might want:

### Phase 2: Mechanism Mapping
- Multiple compounds targeting same pathway
- Combination screening (synergy/antagonism)
- Adaptive dose selection
- Higher resolution (more doses, focused range)

### Phase 3: Temporal Dynamics
- Dense time sampling (6h, 12h, 18h, 24h, 36h, 48h)
- Single compound from Phase 1
- Kinetic parameter estimation (lag, rate, plateau)

**Design principle:** Each phase builds on the previous
**Phase 0 → Phase 1 → Phase 2 → Phase 3**

---

## File Locations

**Generated design:** `data/designs/phase1_causal_v1.json`
**Generator script:** `scripts/design_generator_phase1_causal.py`
**This document:** `docs/designs/PHASE1_CAUSAL_DESIGN.md`

---

## Quick Summary

> **Phase 1 is for causal claims with defensible power.**
> Single compound, high replication (8 reps), within-plate randomization, single timepoint.
> Use after Phase 0 calibration. Not for screening or exploration.
> Produces publishable dose-response curves with tight confidence intervals.

**Key innovation:** Within-plate randomization prevents the spatial confounding attack that plagues observational dose-response studies.
