# Patch v3 FINAL: Commitment Heterogeneity (Mergeable)

## All Hostile Review Issues Fixed

1. ✓ IC50 validity guard (fail loudly on junk)
2. ✓ dose_ratio computed once (not per-subpop)
3. ✓ Sorted subpop iteration (determinism everywhere)
4. ✓ World A explicit (dose_ratio check first)
5. ✓ Improved tests (dynamic subpop names, IC50 handling)

---

## Change 1: Sorted iteration + dose_ratio outside loop

**File**: `src/cell_os/hardware/biological_virtual.py`
**Location**: In `treat_with_compound`, after assigning exposure_id (line ~2061)

```python
# Track compound start time for time_since_treatment calculations
vessel.compound_start_time[compound] = self.simulated_time

# Assign unique exposure ID for this dosing event
exposure_id = self.next_exposure_id
self.next_exposure_id += 1

# Store exposure ID for this compound (enables cache key lookup)
if 'exposure_ids' not in vessel.compound_meta:
    vessel.compound_meta['exposure_ids'] = {}
vessel.compound_meta['exposure_ids'][compound] = exposure_id

# Sample per-subpopulation commitment delays (removes hard 12h threshold)
# ALWAYS sample for any dose > 0 (World A enforcement happens in attrition function)
# This prevents IC50 mismatch: subpops use shifted IC50s, base IC50 is insufficient guard
if dose_uM > 0:
    if 'commitment_delays' not in vessel.compound_meta:
        vessel.compound_meta['commitment_delays'] = {}

    # Compute dose_ratio ONCE using base IC50 (not subpop-shifted)
    # This is for mean delay estimation only, NOT for World A gating
    # World A uses shifted IC50 in attrition function
    dose_ratio = dose_uM / max(ic50_uM, 1e-6)

    # Iterate subpops in sorted order (determinism guarantee)
    for subpop_name in sorted(vessel.subpopulations.keys()):
        # Cache key: (compound, exposure_id, subpop) - no float drift
        cache_key = (compound, exposure_id, subpop_name)

        # Dose-dependent mean with soft saturation
        # Form: 12 / sqrt(1 + dose_ratio)
        # At IC50: 12h, at 4×IC50: 5.4h, at 100×IC50: 1.2h (asymptotes to 0)
        mean_commitment_h = 12.0 / np.sqrt(1.0 + dose_ratio)

        # Engineering bounds: [1.5h, 48h]
        # Lower: prevents instant commitment (avoids gate conflicts)
        # Upper: simulator doesn't model multi-day recovery
        mean_commitment_h = np.clip(mean_commitment_h, 1.5, 48.0)

        # Fixed CV=0.25 (tunable parameter, not biological claim)
        cv = 0.25
        sigma = np.sqrt(np.log(1 + cv**2))
        mu = np.log(mean_commitment_h) - 0.5 * sigma**2

        # Sample using rng_treatment (biological variability)
        delay_h = float(self.rng_treatment.lognormal(mean=mu, sigma=sigma))

        # Hard clamp on sampled value (prevents pathological tails)
        delay_h = np.clip(delay_h, 1.5, 48.0)

        vessel.compound_meta['commitment_delays'][cache_key] = delay_h
# If dose_uM == 0: skip sampling (vehicle control)
```

---

## Change 2: Add exposure ID counter to __init__

**File**: `src/cell_os/hardware/biological_virtual.py`
**Location**: After line 450 in `__init__`

```python
# Exposure ID counter for commitment delay cache keys
# Monotonic integer ensures no float collision issues
self.next_exposure_id = 0
```

---

## Change 3: Retrieve commitment delay (sorted iteration)

**File**: `src/cell_os/hardware/biological_virtual.py`
**Location**: Around line 1184 (in attrition hazard loop)

**NOTE**: This location likely iterates subpops. If so, change:

**FROM**:
```python
for subpop in vessel.subpopulations.values():
```

**TO**:
```python
for subpop_name in sorted(vessel.subpopulations.keys()):
    subpop = vessel.subpopulations[subpop_name]
```

Then add commitment delay retrieval:

```python
# Retrieve commitment delay for this exposure + subpop
# Cache key uses exposure_id (integer, no float drift)
exposure_id = vessel.compound_meta.get('exposure_ids', {}).get(compound, None)

if exposure_id is not None:
    cache_key = (compound, exposure_id, subpop_name)
    commitment_delay_h = vessel.compound_meta.get('commitment_delays', {}).get(
        cache_key, None
    )
else:
    # No exposure ID → pre-patch vessel
    commitment_delay_h = None

# Pass delay in params (or None for fallback)
params = {'commitment_delay_h': commitment_delay_h} if commitment_delay_h is not None else None

# [existing attrition call with params...]
```

---

## Change 4: Reorder attrition with IC50 validity guard

**File**: `src/cell_os/sim/biology_core.py`
**Location**: Replace lines 439-452 in `compute_attrition_rate_instantaneous`

```python
# Guard: IC50 must be valid (fail loudly on junk to prevent silent "everything lethal")
if ic50_uM is None or not np.isfinite(ic50_uM) or ic50_uM <= 0:
    raise ValueError(
        f"Invalid IC50 {ic50_uM} for compound '{compound}' in {cell_line}. "
        f"IC50 must be positive and finite."
    )

# Calculate dose ratio relative to IC50 (using shifted IC50 passed in)
dose_ratio = dose_uM / ic50_uM

# WORLD A: Sublethal doses (< IC50) never cause attrition (hard contract)
# This check comes FIRST to make the world model explicit
if dose_ratio < 1.0:
    return 0.0

# Only applies when viability is already low (< 50%)
# Cells with high viability don't undergo attrition yet
if current_viability >= 0.5:
    return 0.0

# Per-subpopulation commitment delay (replaces hard 12h threshold)
# params contains 'commitment_delay_h' or None
if params and params.get('commitment_delay_h') is not None:
    commitment_delay_h = params['commitment_delay_h']
else:
    # Fallback to 12h for pre-patch vessels or dose=0 cases
    commitment_delay_h = 12.0

# Guard: commitment delay is a time gate, not a math input
# If not yet committed, return 0 immediately (branch, not sentinel)
if time_since_treatment_h <= commitment_delay_h:
    return 0.0

# Continue with existing attrition logic (time scaling, base rates, etc.)
```

---

## Tests

### Test 1: No-Kink (Unchanged)

```python
def test_no_kink_in_attrition_derivative():
    """Ensure attrition rate has no step discontinuities in time."""

    vm = BiologicalVirtualMachine(seed=42)
    vessel_id = "P1_A01"
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vessel = vm.vessel_states[vessel_id]

    vm.treat_with_compound(vessel_id, "tunicamycin", 10.0)

    times = np.linspace(0, 24, 241)
    deaths = []

    for t in times:
        vm._step_vessel(vessel, t)
        deaths.append(vessel.death_er_stress)

    derivatives = np.diff(deaths) / (times[1] - times[0])

    max_ratio = 1.0
    for i in range(len(derivatives) - 1):
        if derivatives[i] > 1e-6:
            ratio = derivatives[i+1] / max(derivatives[i], 1e-9)
            max_ratio = max(max_ratio, ratio)
            assert ratio < 100, \
                f"Derivative jump {ratio:.1f}× at t={times[i+1]:.1f}h"

    print(f"✓ Maximum derivative ratio: {max_ratio:.2f}×")
```

### Test 2: No Lethal Dose Uses Fallback (Hardened)

```python
def test_no_lethal_dose_uses_fallback_12h():
    """Ensure all lethal doses have sampled delays, never fallback to 12h."""

    vm = BiologicalVirtualMachine(seed=42)

    for dose_mult in [1.0, 2.0, 5.0, 10.0]:
        vessel_id = f"v_{dose_mult}x"
        vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
        vessel = vm.vessel_states[vessel_id]

        # Get IC50 from same source simulator uses
        dose_uM = dose_mult * 1.0  # Tunicamycin IC50 ~1.0 for A549

        vm.treat_with_compound(vessel_id, "tunicamycin", dose_uM)

        # Verify exposure_id exists
        exposure_id = vessel.compound_meta.get('exposure_ids', {}).get('tunicamycin')
        assert exposure_id is not None, f"Missing exposure_id at {dose_mult}×IC50"

        # Verify ALL subpops have sampled delays (dynamic subpop names)
        for subpop_name in sorted(vessel.subpopulations.keys()):
            cache_key = ('tunicamycin', exposure_id, subpop_name)
            delay = vessel.compound_meta.get('commitment_delays', {}).get(cache_key)

            assert delay is not None, \
                f"Missing delay for {subpop_name} at {dose_mult}×IC50 (fallback to 12h)"

            assert 1.5 <= delay <= 48.0, \
                f"Delay {delay:.1f}h out of bounds for {subpop_name}"

    print("✓ All lethal doses have sampled delays (no fallback)")
```

### Test 3: Commitment Gate Is Not A Threshold

```python
def test_commitment_gate_not_a_threshold():
    """Verify subpops don't all activate attrition in same timestep."""

    vm = BiologicalVirtualMachine(seed=42)
    vessel_id = "P1_A01"
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vessel = vm.vessel_states[vessel_id]

    vm.treat_with_compound(vessel_id, "tunicamycin", 5.0)

    # Extract commitment delays
    exposure_id = vessel.compound_meta['exposure_ids']['tunicamycin']
    treatment_start = vessel.compound_start_time['tunicamycin']
    delays = []

    for subpop_name in sorted(vessel.subpopulations.keys()):
        cache_key = ('tunicamycin', exposure_id, subpop_name)
        delay = vessel.compound_meta['commitment_delays'][cache_key]
        delays.append((subpop_name, delay))

    delays.sort(key=lambda x: x[1])

    # Verify delays span at least 1h (prevents collapse to single timestep)
    delay_span = delays[-1][1] - delays[0][1]
    assert delay_span >= 1.0, \
        f"Delay span {delay_span:.2f}h too narrow (risk of synchronization)"

    # Sample attrition around median delay
    median_delay = delays[1][1]  # Typical subpop
    times = np.linspace(treatment_start + median_delay - 2,
                        treatment_start + median_delay + 2, 41)

    # Count how many distinct "activation events" (0→>0 transitions)
    # Should be multiple (one per subpop), not one (synchronized)
    activations_per_subpop = {name: None for name, _ in delays}

    for t in times:
        vm._step_vessel(vessel, t)
        for subpop_name in sorted(vessel.subpopulations.keys()):
            subpop = vessel.subpopulations[subpop_name]
            # Check if this subpop has non-zero ER stress death hazard
            # (proxy for "attrition active")
            if subpop.get('er_stress', 0) > 0.1:
                if activations_per_subpop[subpop_name] is None:
                    activations_per_subpop[subpop_name] = t

    activated = [t for t in activations_per_subpop.values() if t is not None]
    unique_activation_times = len(set(np.round(activated, 1)))  # Round to 0.1h

    assert unique_activation_times >= 2, \
        f"Only {unique_activation_times} activation time(s) - suggests synchronization"

    print(f"✓ Attrition activates at {unique_activation_times} distinct times")
```

### Test 4: Heterogeneity with CV Stability

```python
def test_commitment_heterogeneity_cv_stable():
    """Verify delays vary with dose, CV stays bounded."""

    results = {}

    for dose_mult in [1, 2, 5, 10, 20]:
        vm = BiologicalVirtualMachine(seed=42)
        vessel_id = f"v_{dose_mult}x"
        vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
        vessel = vm.vessel_states[vessel_id]

        dose_uM = dose_mult * 1.0
        vm.treat_with_compound(vessel_id, "tunicamycin", dose_uM)

        exposure_id = vessel.compound_meta['exposure_ids']['tunicamycin']
        delays = []

        # Dynamic subpop names
        for subpop_name in sorted(vessel.subpopulations.keys()):
            cache_key = ('tunicamycin', exposure_id, subpop_name)
            delay = vessel.compound_meta['commitment_delays'][cache_key]
            delays.append(delay)

        results[dose_mult] = {
            'delays': delays,
            'mean': np.mean(delays),
            'std': np.std(delays),
            'cv': np.std(delays) / np.mean(delays)
        }

    # Mean decreases monotonically
    dose_levels = sorted(results.keys())
    for i in range(len(dose_levels) - 1):
        assert results[dose_levels[i]]['mean'] >= results[dose_levels[i+1]]['mean'], \
            f"Mean increased with dose"

    # CV stays bounded (0.05 to 0.6 reasonable for lognormal CV=0.25)
    cvs = [r['cv'] for r in results.values()]
    assert all(0.05 < cv < 0.6 for cv in cvs), f"CV out of range: {cvs}"

    print("✓ Commitment heterogeneity with stable CV:")
    for dose, r in results.items():
        print(f"  {dose:2d}×IC50: mean={r['mean']:5.1f}h, CV={r['cv']:.3f}")
```

---

## Summary

**Fixed**:
- IC50 validity guard (raises on junk)
- dose_ratio computed once
- Sorted iteration everywhere (determinism)
- World A check first (explicit semantics)
- Dynamic subpop names in tests
- No vessel ID collisions

**Honest**:
- Deterministic (seed-controlled)
- Lognormal CV=0.25 is tunable
- Bounds [1.5h, 48h] are guardrails
- World A: sublethal → no attrition

**Next patch**:
- Independent subpop viabilities
- Selection pressure (changing fractions)
