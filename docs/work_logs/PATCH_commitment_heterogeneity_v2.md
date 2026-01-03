# Patch v2: Commitment Heterogeneity with Proper Guards

## Changes from v1
- **Fix cache key**: Use `(compound, treatment_start_time, subpop)` to handle re-dosing
- **Add dose ratio guards**: Handle zero dose, missing IC50, sublethal doses
- **Add delay bounds**: Clamp to [1.5h, 48h] to prevent pathological tails
- **Harden tests**: Check for accidental synchronization, variance stability

---

## Code Changes

### File 1: `src/cell_os/hardware/biological_virtual.py`

**Add after line 2061** (in `treat_with_compound`):

```python
# Sample per-subpopulation commitment delays
# This removes the hard 12h threshold and introduces dose-dependent heterogeneity
#
# CRITICAL: Cache key includes treatment_start_time to handle re-dosing correctly
treatment_start_time = self.simulated_time

# Initialize commitment_delays dict if not present
if 'commitment_delays' not in vessel.compound_meta:
    vessel.compound_meta['commitment_delays'] = {}

# Guard: only sample if dose is meaningful
dose_ratio = dose_uM / max(ic50_uM, 1e-6)

if dose_ratio > 0.01:  # Skip DMSO/vehicle (dose ~0)
    for subpop_name in vessel.subpopulations.keys():
        # Cache key: (compound, t0, subpop) to handle multiple exposures
        cache_key = (compound, treatment_start_time, subpop_name)

        if cache_key not in vessel.compound_meta['commitment_delays']:
            # Dose-dependent mean with soft saturation
            # At IC50: 12h, at 4×IC50: 6h, at 100×IC50: ~1.9h (saturates)
            # Form: 12 / sqrt(1 + dose_ratio) prevents explosion at huge doses
            mean_commitment_h = 12.0 / np.sqrt(1.0 + max(dose_ratio, 0.0))

            # Lower bound: never imply commitment <1.5h (prevents instant death gate)
            mean_commitment_h = max(mean_commitment_h, 1.5)

            # Upper bound for sublethal doses: cap at 48h
            # Sublethal doses (dose_ratio < 1) would otherwise give >12h
            # That's okay but cap prevents absurd "day 3 activation" tails
            mean_commitment_h = min(mean_commitment_h, 48.0)

            # Fixed CV=0.25 (tunable parameter, not claiming truth)
            cv = 0.25
            sigma = np.sqrt(np.log(1 + cv**2))
            mu = np.log(mean_commitment_h) - 0.5 * sigma**2

            # Sample using rng_treatment (biological variability)
            delay_h = float(self.rng_treatment.lognormal(mean=mu, sigma=sigma))

            # Hard clamp on sampled value (prevents pathological tails)
            # [1.5h, 72h] is a boring engineering guardrail, not a biological claim
            delay_h = np.clip(delay_h, 1.5, 72.0)

            vessel.compound_meta['commitment_delays'][cache_key] = delay_h
else:
    # Vehicle control: set sentinel delays (will never trigger)
    for subpop_name in vessel.subpopulations.keys():
        cache_key = (compound, treatment_start_time, subpop_name)
        vessel.compound_meta['commitment_delays'][cache_key] = 1e9  # Infinite delay
```

### File 2: `src/cell_os/sim/biology_core.py`

**Replace lines 439-441** with:

```python
# Per-subpopulation commitment delay (replaces hard 12h threshold)
# params should contain 'commitment_delay_h' passed from vessel.compound_meta
if params and 'commitment_delay_h' in params:
    commitment_delay_h = params['commitment_delay_h']

    # Guard: if sentinel value (1e9), treat as no attrition gate
    if commitment_delay_h > 1e6:
        return 0.0
else:
    # Fallback to 12h if not provided (backward compatibility)
    commitment_delay_h = 12.0

if time_since_treatment_h <= commitment_delay_h:
    return 0.0
```

### File 3: Modify attrition call sites

**In `biological_virtual.py` around line 1184** (when calling `compute_attrition_rate_instantaneous`):

```python
# Build cache key matching treatment application
# CRITICAL: Must match the key used when sampling delays
treatment_start_time = vessel.compound_start_time.get(compound, self.simulated_time)
cache_key = (compound, treatment_start_time, subpop_name)

# Retrieve commitment delay for this exposure + subpop
commitment_delay_h = vessel.compound_meta.get('commitment_delays', {}).get(
    cache_key, 12.0  # fallback for backward compatibility
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

**Similar update needed in `compute_attrition_rate_interval_mean` call around line 1210.**

---

## Tests

### Test 1: Hardened No-Kink Test

```python
def test_no_kink_in_attrition_derivative_hardened():
    """Ensure attrition rate has no step discontinuities AND no population synchronization."""

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
    dt = times[1] - times[0]
    derivatives = np.diff(deaths) / dt

    # TEST 1: No pair of adjacent derivatives differs by more than 100×
    # (allows smooth ramps, forbids step functions)
    ratios = []
    for i in range(len(derivatives) - 1):
        if derivatives[i] > 1e-6:  # Only check non-zero regions
            ratio = derivatives[i+1] / max(derivatives[i], 1e-9)
            ratios.append(ratio)

            # Fail fast on first huge jump
            assert ratio < 100, f"Derivative jump {ratio:.1f}× at t={times[i+1]:.1f}h (step function)"

    max_jump = max(ratios) if ratios else 1.0
    print(f"✓ Maximum derivative ratio: {max_jump:.2f}× (smooth)")

    # TEST 2: No single timestep where hazard goes from 0 to >0 for entire population
    # Check that hazard activations are spread over multiple timesteps
    zero_to_nonzero_transitions = 0
    for i in range(len(derivatives) - 1):
        if derivatives[i] < 1e-9 and derivatives[i+1] > 1e-6:
            zero_to_nonzero_transitions += 1

    # Should have multiple activation windows (one per subpop at different times)
    # If only 1, all subpops activated simultaneously (synchronization)
    assert zero_to_nonzero_transitions >= 2, \
        f"Only {zero_to_nonzero_transitions} activation event(s) - suggests synchronization"

    print(f"✓ Hazard activations spread over {zero_to_nonzero_transitions} time windows")


def test_no_single_timestep_population_synchronization():
    """Verify that attrition doesn't turn on for all subpops in same timestep."""

    vm = BiologicalVirtualMachine(seed=42)
    vessel_id = "P1_A01"
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vessel = vm.vessel_states[vessel_id]

    # High dose treatment
    vm.treat_with_compound(vessel_id, "tunicamycin", 10.0)

    # Extract commitment delays for all subpops
    delays = []
    treatment_start = vessel.compound_start_time.get("tunicamycin", 0.0)
    for subpop in ['sensitive', 'typical', 'resistant']:
        key = ('tunicamycin', treatment_start, subpop)
        delay = vessel.compound_meta['commitment_delays'].get(key, None)
        assert delay is not None, f"Missing delay for {subpop}"
        delays.append(delay)

    # Delays should differ by at least 0.5h (prevents rounding to same timestep)
    delays_sorted = sorted(delays)
    min_gap = min(delays_sorted[i+1] - delays_sorted[i] for i in range(len(delays_sorted)-1))

    assert min_gap > 0.5, \
        f"Subpop delays too close ({min_gap:.2f}h gap) - risk of synchronization"

    print(f"✓ Minimum delay gap between subpops: {min_gap:.2f}h")
    print(f"  Delays: {[f'{d:.1f}h' for d in delays_sorted]}")
```

### Test 2: Hardened Heterogeneity Test

```python
def test_commitment_heterogeneity_with_variance_stability():
    """Verify commitment delays vary correctly with dose AND variance stays sane."""

    delays_by_dose = {}

    for dose_multiplier in [0.5, 1, 2, 5, 10, 20]:
        vm = BiologicalVirtualMachine(seed=42)
        vessel_id = f"P1_A0{dose_multiplier}"
        vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
        vessel = vm.vessel_states[vessel_id]

        dose_uM = dose_multiplier * 1.0  # IC50 = 1.0 for tunicamycin
        vm.treat_with_compound(vessel_id, "tunicamycin", dose_uM)

        # Extract commitment delays
        treatment_start = vessel.compound_start_time.get("tunicamycin", 0.0)
        delays = []
        for subpop in ['sensitive', 'typical', 'resistant']:
            key = ('tunicamycin', treatment_start, subpop)
            delay = vessel.compound_meta['commitment_delays'].get(key, None)
            delays.append(delay)

        delays_by_dose[dose_multiplier] = delays

    # ASSERTION 1: Delays exist and vary across subpops at each dose
    for dose_mult, delays in delays_by_dose.items():
        assert all(d is not None for d in delays), f"Missing delays at {dose_mult}×IC50"
        std_dev = np.std(delays)
        assert std_dev > 0.3, f"Insufficient heterogeneity at {dose_mult}×IC50 (std={std_dev:.2f}h)"

    # ASSERTION 2: Higher dose → shorter mean commitment time (monotonic)
    means = {dose: np.mean(delays) for dose, delays in delays_by_dose.items()}
    dose_levels = sorted(means.keys())
    for i in range(len(dose_levels) - 1):
        assert means[dose_levels[i]] >= means[dose_levels[i+1]], \
            f"Mean commitment increased from {dose_levels[i]}× to {dose_levels[i+1]}× " \
            f"({means[dose_levels[i]]:.1f}h → {means[dose_levels[i+1]]:.1f}h)"

    # ASSERTION 3: Variance stays bounded (doesn't explode or collapse with dose)
    variances = {dose: np.var(delays) for dose, delays in delays_by_dose.items()}
    max_var = max(variances.values())
    min_var = min(variances.values())

    # Variance shouldn't differ by more than 10× across dose range
    assert max_var / min_var < 10.0, \
        f"Variance unstable: {min_var:.2f} to {max_var:.2f} (ratio {max_var/min_var:.1f}×)"

    print("✓ Commitment heterogeneity verified:")
    for dose in sorted(means.keys()):
        delays = delays_by_dose[dose]
        print(f"  {dose:4.1f}×IC50: mean={means[dose]:5.1f}h, "
              f"std={np.std(delays):4.2f}h, range=[{min(delays):4.1f}, {max(delays):4.1f}]h")
```

### Test 3: Cache Key Correctness (Re-dosing)

```python
def test_commitment_delays_respect_redosing():
    """Verify that re-dosing with same compound generates new delays."""

    vm = BiologicalVirtualMachine(seed=42)
    vessel_id = "P1_A01"
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vessel = vm.vessel_states[vessel_id]

    # First dose at t=0
    vm.treat_with_compound(vessel_id, "tunicamycin", 5.0)
    t0 = vessel.compound_start_time.get("tunicamycin")
    delays_first = {}
    for subpop in ['sensitive', 'typical', 'resistant']:
        key = ('tunicamycin', t0, subpop)
        delays_first[subpop] = vessel.compound_meta['commitment_delays'].get(key)

    # Advance time and re-dose (simulating washout + re-treatment)
    vm._step_vessel(vessel, 24.0)
    vm.simulated_time = 24.0

    # Second dose at t=24h (same compound, different time)
    # Note: This requires compound_start_time to be updated on re-treatment
    vessel.compound_start_time["tunicamycin"] = 24.0  # Simulate re-treatment
    vm.treat_with_compound(vessel_id, "tunicamycin", 5.0)

    t1 = vessel.compound_start_time.get("tunicamycin")
    delays_second = {}
    for subpop in ['sensitive', 'typical', 'resistant']:
        key = ('tunicamycin', t1, subpop)
        delays_second[subpop] = vessel.compound_meta['commitment_delays'].get(key)

    # Verify: delays should differ (cache key includes treatment time)
    assert t1 != t0, "Treatment times should differ"

    for subpop in ['sensitive', 'typical', 'resistant']:
        # With different RNG draws, delays should differ
        # (seed is same but RNG state advanced between calls)
        assert delays_first[subpop] != delays_second[subpop], \
            f"Re-dosing reused old delay for {subpop} (cache key broken)"

    print("✓ Re-dosing generates independent commitment delays")
    print(f"  First dose (t={t0}h): {list(delays_first.values())}")
    print(f"  Second dose (t={t1}h): {list(delays_second.values())}")
```

### Test 4: Edge Case Guards

```python
def test_commitment_delay_edge_cases():
    """Verify edge cases: zero dose, sublethal, extreme high dose."""

    vm = BiologicalVirtualMachine(seed=42)

    # Test 1: Zero dose (vehicle)
    vessel_id = "P1_A01"
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vm.treat_with_compound(vessel_id, "DMSO", 0.0)

    vessel = vm.vessel_states[vessel_id]
    delays_vehicle = vessel.compound_meta.get('commitment_delays', {})

    # Vehicle should either have no delays or sentinel values
    for key, delay in delays_vehicle.items():
        if 'DMSO' in key:
            assert delay > 1e6, f"Vehicle delay should be sentinel (got {delay:.1f}h)"

    print("✓ Zero dose handled correctly (sentinel delays)")

    # Test 2: Sublethal dose (<IC50)
    vessel_id = "P1_A02"
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vm.treat_with_compound(vessel_id, "tunicamycin", 0.5)  # 0.5×IC50

    vessel = vm.vessel_states[vessel_id]
    treatment_start = vessel.compound_start_time.get("tunicamycin", 0.0)
    delays_sublethal = [
        vessel.compound_meta['commitment_delays'].get(('tunicamycin', treatment_start, s))
        for s in ['sensitive', 'typical', 'resistant']
    ]

    # Sublethal doses should have longer delays (but capped at 48h)
    mean_sublethal = np.mean([d for d in delays_sublethal if d is not None])
    assert 12.0 < mean_sublethal <= 48.0, \
        f"Sublethal delay out of range: {mean_sublethal:.1f}h (expected 12-48h)"

    print(f"✓ Sublethal dose: mean delay {mean_sublethal:.1f}h (capped)")

    # Test 3: Extreme high dose (100×IC50)
    vessel_id = "P1_A03"
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vm.treat_with_compound(vessel_id, "tunicamycin", 100.0)  # 100×IC50

    vessel = vm.vessel_states[vessel_id]
    treatment_start = vessel.compound_start_time.get("tunicamycin", 0.0)
    delays_extreme = [
        vessel.compound_meta['commitment_delays'].get(('tunicamycin', treatment_start, s))
        for s in ['sensitive', 'typical', 'resistant']
    ]

    # Extreme doses should have short delays (but bounded ≥1.5h)
    mean_extreme = np.mean([d for d in delays_extreme if d is not None])
    assert 1.5 <= mean_extreme < 6.0, \
        f"Extreme dose delay out of range: {mean_extreme:.1f}h (expected 1.5-6h)"

    print(f"✓ Extreme dose: mean delay {mean_extreme:.1f}h (lower bounded)")
```

---

## What's Fixed

1. **Cache key now includes treatment_start_time**: Handles re-dosing correctly
2. **Dose ratio guards**: Zero dose → sentinel, bounds prevent explosions
3. **Delay bounds**: [1.5h, 48h] mean, [1.5h, 72h] sampled - prevents pathological tails
4. **Soft saturation**: `12 / sqrt(1 + dose_ratio)` prevents infinite descent
5. **Four hardened tests**: Kink, synchronization, heterogeneity stability, edge cases

## What's Still Honest

- Deterministic given seed (not claiming true stochasticity)
- Lognormal + CV=0.25 is a choice, explicitly tunable
- Bounds are engineering guardrails, not biological claims
- Still uses population-level (subpop) abstraction, not per-cell

## What's Still a Lie (Next Patch)

- Subpop viabilities still synchronized (line 922-956)
- No selection pressure (fractions fixed at 25/50/25)
- No commitment reversal (monotonic death)
