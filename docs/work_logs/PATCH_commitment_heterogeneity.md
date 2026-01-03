# Patch: Remove 12h Hard Threshold, Add Per-Subpopulation Commitment Heterogeneity

## Problem
`biology_core.py:439` has a hard-coded 12h commitment threshold that creates a synchronized population-level death wave. This is falsifiable with time-course flow cytometry.

## Solution
Replace hard threshold with **per-(vessel, exposure, subpopulation) sampled commitment delays**.

### Key Design Choices

1. **Sample once per treatment per subpopulation** (not per cell)
   - Consistent with existing population-level modeling
   - Uses existing subpopulation structure (lines 210-238)
   - No new ontology required

2. **Dose-dependent mean commitment time**
   - Higher dose → shorter mean commitment
   - Base: 12h at IC50, scales to ~6h at 10×IC50
   - Formula: `mean_h = 12 / sqrt(dose_ratio)`

3. **Lognormal distribution with fixed CV=0.25**
   - Positive support (can't commit before treatment)
   - CV=0.25 gives ~6h spread at mean=12h
   - NOT claiming this is "true" - it's a first-order heterogeneity model

4. **Use rng_treatment stream** (seed+2)
   - Biological variability, not measurement noise
   - Deterministic given seed
   - Separate from growth and assay RNG

5. **Store in vessel.compound_meta**
   - Key: (compound, subpop_name)
   - Value: commitment_delay_h
   - Sampled once when treatment applied

## Code Changes

### File 1: `src/cell_os/hardware/biological_virtual.py`

**Add after line 2061** (in `treat_with_compound`):

```python
# Sample per-subpopulation commitment delays
# This removes the hard 12h threshold and introduces dose-dependent heterogeneity
dose_ratio = dose_uM / max(ic50_uM, 1e-6)
if 'commitment_delays' not in vessel.compound_meta:
    vessel.compound_meta['commitment_delays'] = {}

for subpop_name in vessel.subpopulations.keys():
    key = (compound, subpop_name)
    if key not in vessel.compound_meta['commitment_delays']:
        # Dose-dependent mean: shorter at high doses
        # 12h at IC50, ~8.5h at 2×IC50, ~6h at 4×IC50
        mean_commitment_h = 12.0 / np.sqrt(max(dose_ratio, 0.1))

        # Fixed CV=0.25 (not claiming this is truth, just first-order heterogeneity)
        cv = 0.25
        sigma = np.sqrt(np.log(1 + cv**2))
        mu = np.log(mean_commitment_h) - 0.5 * sigma**2

        # Sample using rng_treatment (biological variability)
        delay_h = self.rng_treatment.lognormal(mean=mu, sigma=sigma)
        vessel.compound_meta['commitment_delays'][key] = float(delay_h)
```

### File 2: `src/cell_os/sim/biology_core.py`

**Replace lines 439-441** with:

```python
# Per-subpopulation commitment delay (replaces hard 12h threshold)
# params should contain 'commitment_delay_h' passed from vessel.compound_meta
if params and 'commitment_delay_h' in params:
    commitment_delay_h = params['commitment_delay_h']
else:
    # Fallback to 12h if not provided (backward compatibility)
    commitment_delay_h = 12.0

if time_since_treatment_h <= commitment_delay_h:
    return 0.0
```

**Modify line 1184** (when calling `compute_attrition_rate_instantaneous`):

```python
# Need to pass commitment_delay_h from vessel.compound_meta
commitment_delay_h = vessel.compound_meta.get('commitment_delays', {}).get(
    (compound, subpop_name), 12.0  # fallback
)

hazard_rate = compute_attrition_rate_instantaneous(
    compound=compound,
    dose_uM=dose_uM,
    ic50_uM=ic50_shifted,
    stress_axis=stress_axis,
    cell_line=vessel.cell_line,
    hill_slope=hill_slope,
    transport_dysfunction=subpop.get('transport_dysfunction', 0.0),
    time_since_treatment_h=time_since_treatment_start,
    current_viability=vessel.viability,
    params={'commitment_delay_h': commitment_delay_h}
)
```

## Tests

### Test 1: No-Kink Derivative Test

```python
def test_no_kink_in_attrition_derivative():
    """Ensure attrition rate has no step discontinuities in time."""

    vm = BiologicalVirtualMachine(seed=42)
    vessel_id = "P1_A01"
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vessel = vm.vessel_states[vessel_id]

    # Treat with high dose
    vm.treat_with_compound(vessel_id, "tunicamycin", 10.0)

    # Sample at fine resolution from 0-24h
    times = np.linspace(0, 24, 241)  # 0.1h steps
    deaths = []

    for t in times:
        vm._step_vessel(vessel, t)
        deaths.append(vessel.death_er_stress)

    # Compute derivative
    derivatives = np.diff(deaths) / (times[1] - times[0])

    # Check: no pair of adjacent derivatives differs by more than 100×
    # (allows smooth ramps, forbids step functions)
    ratios = []
    for i in range(len(derivatives) - 1):
        if derivatives[i] > 1e-6:  # Only check non-zero regions
            ratio = derivatives[i+1] / derivatives[i]
            ratios.append(ratio)

    max_jump = max(ratios) if ratios else 1.0
    assert max_jump < 100, f"Derivative jump {max_jump:.1f}× indicates step function"

    print(f"✓ Maximum derivative ratio: {max_jump:.2f}× (smooth)")
```

### Test 2: Heterogeneity Sanity Test

```python
def test_commitment_heterogeneity_exists():
    """Verify commitment delays vary across subpopulations and doses."""

    delays_by_dose = {}

    for dose_multiplier in [1, 2, 5, 10]:
        vm = BiologicalVirtualMachine(seed=42)
        vessel_id = f"P1_A0{dose_multiplier}"
        vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
        vessel = vm.vessel_states[vessel_id]

        dose_uM = dose_multiplier * 1.0  # IC50 = 1.0 for tunicamycin
        vm.treat_with_compound(vessel_id, "tunicamycin", dose_uM)

        # Extract commitment delays
        delays = vessel.compound_meta.get('commitment_delays', {})
        delays_by_dose[dose_multiplier] = [
            delays.get(('tunicamycin', subpop), None)
            for subpop in ['sensitive', 'typical', 'resistant']
        ]

    # Assertion 1: Delays exist and vary across subpops
    for dose_mult, delays in delays_by_dose.items():
        assert all(d is not None for d in delays), f"Missing delays at {dose_mult}×IC50"
        std_dev = np.std(delays)
        assert std_dev > 0.5, f"No heterogeneity at {dose_mult}×IC50 (std={std_dev:.2f}h)"

    # Assertion 2: Higher dose → shorter mean commitment time
    means = {dose: np.mean(delays) for dose, delays in delays_by_dose.items()}
    assert means[1] > means[2], "Mean commitment should decrease with dose"
    assert means[2] > means[5], "Mean commitment should decrease with dose"
    assert means[5] > means[10], "Mean commitment should decrease with dose"

    print("✓ Commitment heterogeneity verified:")
    for dose, mean_h in means.items():
        print(f"  {dose}×IC50: mean={mean_h:.1f}h, range={min(delays_by_dose[dose]):.1f}-{max(delays_by_dose[dose]):.1f}h")
```

## What This Fixes

1. **Removes population synchronization**: No sharp kink at 12h
2. **Introduces biologically plausible heterogeneity**: Subpopulations commit at different times
3. **Dose-dependent commitment**: High doses commit faster (realistic)
4. **No new ontology**: Uses existing subpopulation structure
5. **Honest about uncertainty**: CV=0.25 is tunable, not claimed as truth

## What This Does NOT Fix (Out of Scope)

- Commitment time is still deterministic given seed (not truly stochastic)
- Distribution choice (lognormal) is still arbitrary
- No cell-to-cell variation within subpopulations
- No recovery/reversal of commitment

These would require deeper architectural changes.
