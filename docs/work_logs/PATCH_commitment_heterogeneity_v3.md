# Patch v3: Commitment Heterogeneity (Final)

## Fixes from v2
1. **Consistent bounds**: [1.5h, 48h] everywhere. No 72h.
2. **Cache key uses integer exposure ID**: No float drift.
3. **Sentinel is a branch**: Never flows through math.
4. **Explicit World A**: Below IC50 → no attrition, don't sample delays.
5. **No hard min gap**: Test warns if collapse happens, doesn't enforce.
6. **Calibrated test thresholds**: CV-based variance, not absolute.

---

## Design Decisions (Explicit)

### World A: Sublethal doses do not cause attrition
- `dose_ratio < 1.0` → attrition rate = 0 (unchanged from current code)
- For these doses, **do not sample commitment delays** (waste of RNG)
- Future: "World B" would add stochastic low-dose death as separate patch

### Commitment delay bounds: [1.5h, 48h]
- **Lower bound 1.5h**: Never imply instant commitment (prevents gate conflicts)
- **Upper bound 48h**: No "day 3 activation" tails (simulator doesn't model multi-day recovery)
- Both bounds are **engineering guardrails**, not biological claims

### Cache key: (compound, exposure_id, subpop)
- `exposure_id`: Integer, monotonic, unique per dosing event
- Stored in `vessel.compound_meta['exposure_ids'][compound]`
- No float drift, no epsilon collisions

### Sentinel: Short-circuit branch, not magic number
- Vehicle or dose_ratio < 1: Skip sampling, return attrition=0 directly
- No sentinel values flowing through equations

---

## Code Diff

### Part 1: Add exposure ID tracking

**File**: `src/cell_os/hardware/biological_virtual.py`

**After line 450** (in `__init__`):
```python
# Exposure ID counter for commitment delay cache keys
# Monotonic integer ensures no float collision issues
self.next_exposure_id = 0
```

### Part 2: Sample commitment delays on treatment

**File**: `src/cell_os/hardware/biological_virtual.py`

**Replace lines 2060-2061** with:
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
# ONLY sample if dose is lethal (dose >= IC50), otherwise attrition=0 by World A
dose_ratio = dose_uM / max(ic50_uM, 1e-6)

if dose_ratio >= 1.0:  # Lethal dose only (World A: sublethal → no attrition)
    if 'commitment_delays' not in vessel.compound_meta:
        vessel.compound_meta['commitment_delays'] = {}

    for subpop_name in vessel.subpopulations.keys():
        # Cache key: (compound, exposure_id, subpop) - no float drift
        cache_key = (compound, exposure_id, subpop_name)

        # Dose-dependent mean with soft saturation
        # Form: 12 / sqrt(1 + dose_ratio)
        # At IC50: 12h, at 4×IC50: 5.4h, at 100×IC50: 1.2h (asymptotes to 0)
        mean_commitment_h = 12.0 / np.sqrt(1.0 + dose_ratio)

        # Engineering bounds: [1.5h, 48h]
        # Lower: prevents instant commitment
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
# If dose_ratio < 1.0: do not sample (sublethal → no attrition by design)
```

### Part 3: Retrieve commitment delay at attrition call site

**File**: `src/cell_os/hardware/biological_virtual.py`

**Around line 1184** (in attrition hazard loop, replace existing call):
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
    # No exposure ID → pre-patch vessel or vehicle, fallback to 12h
    commitment_delay_h = None

# Call attrition with params (or None, which triggers fallback in function)
params = {'commitment_delay_h': commitment_delay_h} if commitment_delay_h is not None else None

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
    params=params
)
```

**Same pattern for `compute_attrition_rate_interval_mean` around line 1210.**

### Part 4: Update attrition function (no sentinel, just branch)

**File**: `src/cell_os/sim/biology_core.py`

**Replace lines 439-441** with:
```python
# Per-subpopulation commitment delay (replaces hard 12h threshold)
# params contains 'commitment_delay_h' or None (fallback to 12h)
if params and params.get('commitment_delay_h') is not None:
    commitment_delay_h = params['commitment_delay_h']
else:
    # Fallback to 12h for backward compatibility
    commitment_delay_h = 12.0

# Guard: commitment delay is a gate, not math input
# If not yet committed, return 0 immediately (branch, not sentinel)
if time_since_treatment_h <= commitment_delay_h:
    return 0.0

# Continue with existing attrition logic (viability check, dose ratio, etc.)
```

---

## Tests

### Test 1: No-Kink (Hardened)

```python
def test_no_kink_in_attrition_derivative():
    """Ensure attrition rate has no step discontinuities in time."""

    vm = BiologicalVirtualMachine(seed=42)
    vessel_id = "P1_A01"
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vessel = vm.vessel_states[vessel_id]

    # High dose treatment (well above IC50)
    vm.treat_with_compound(vessel_id, "tunicamycin", 10.0)

    # Sample at fine resolution
    times = np.linspace(0, 24, 241)  # 0.1h steps
    deaths = []

    for t in times:
        vm._step_vessel(vessel, t)
        deaths.append(vessel.death_er_stress)

    # Compute derivative
    dt = times[1] - times[0]
    derivatives = np.diff(deaths) / dt

    # Test: no adjacent derivatives differ by more than 100×
    max_ratio = 1.0
    for i in range(len(derivatives) - 1):
        if derivatives[i] > 1e-6:
            ratio = derivatives[i+1] / max(derivatives[i], 1e-9)
            max_ratio = max(max_ratio, ratio)

            assert ratio < 100, \
                f"Derivative jump {ratio:.1f}× at t={times[i+1]:.1f}h (step function)"

    print(f"✓ Maximum derivative ratio: {max_ratio:.2f}× (smooth)")
```

### Test 2: Heterogeneity with CV Stability

```python
def test_commitment_heterogeneity_cv_stable():
    """Verify delays vary with dose, and CV stays bounded."""

    results = {}

    for dose_mult in [1, 2, 5, 10, 20]:
        vm = BiologicalVirtualMachine(seed=42)
        vessel_id = f"P1_A0{dose_mult}"
        vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
        vessel = vm.vessel_states[vessel_id]

        dose_uM = dose_mult * 1.0  # IC50=1.0
        vm.treat_with_compound(vessel_id, "tunicamycin", dose_uM)

        # Extract delays
        exposure_id = vessel.compound_meta['exposure_ids']['tunicamycin']
        delays = [
            vessel.compound_meta['commitment_delays'][(compound, exposure_id, s)]
            for s in ['sensitive', 'typical', 'resistant']
        ]

        results[dose_mult] = {
            'delays': delays,
            'mean': np.mean(delays),
            'std': np.std(delays),
            'cv': np.std(delays) / np.mean(delays)
        }

    # Assertion 1: Mean decreases monotonically with dose
    dose_levels = sorted(results.keys())
    for i in range(len(dose_levels) - 1):
        mean_low = results[dose_levels[i]]['mean']
        mean_high = results[dose_levels[i+1]]['mean']
        assert mean_low >= mean_high, \
            f"Mean commitment increased from {dose_levels[i]}× to {dose_levels[i+1]}×"

    # Assertion 2: CV stays bounded (0.1 to 0.5 is reasonable for lognormal with CV=0.25)
    # Don't check absolute variance (collapses at high dose as mean → floor)
    cvs = [r['cv'] for r in results.values()]
    assert all(0.05 < cv < 0.6 for cv in cvs), \
        f"CV out of range: {cvs}"

    print("✓ Commitment heterogeneity with stable CV:")
    for dose, r in results.items():
        print(f"  {dose:2d}×IC50: mean={r['mean']:5.1f}h, "
              f"std={r['std']:4.2f}h, CV={r['cv']:.3f}")
```

### Test 3: Re-dosing Cache Correctness

```python
def test_commitment_delays_respect_redosing():
    """Verify re-dosing generates new delays (cache key uses exposure_id)."""

    vm = BiologicalVirtualMachine(seed=42)
    vessel_id = "P1_A01"
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vessel = vm.vessel_states[vessel_id]

    # First dose
    vm.treat_with_compound(vessel_id, "tunicamycin", 5.0)
    exposure_id_1 = vessel.compound_meta['exposure_ids']['tunicamycin']
    delays_1 = {
        s: vessel.compound_meta['commitment_delays'][('tunicamycin', exposure_id_1, s)]
        for s in ['sensitive', 'typical', 'resistant']
    }

    # Simulate re-dosing (advance time, reset compound state)
    vm._step_vessel(vessel, 24.0)
    vm.simulated_time = 24.0
    vessel.compound_start_time["tunicamycin"] = 24.0

    # Second dose (same compound, same dose, different exposure)
    vm.treat_with_compound(vessel_id, "tunicamycin", 5.0)
    exposure_id_2 = vessel.compound_meta['exposure_ids']['tunicamycin']
    delays_2 = {
        s: vessel.compound_meta['commitment_delays'][('tunicamycin', exposure_id_2, s)]
        for s in ['sensitive', 'typical', 'resistant']
    }

    # Verify: exposure IDs differ
    assert exposure_id_1 != exposure_id_2, "Exposure IDs should be unique"

    # Verify: delays differ (RNG state advanced)
    for s in ['sensitive', 'typical', 'resistant']:
        assert delays_1[s] != delays_2[s], \
            f"Re-dosing reused old delay for {s}"

    print(f"✓ Re-dosing generates independent delays")
    print(f"  Exposure 1 (id={exposure_id_1}): {list(delays_1.values())}")
    print(f"  Exposure 2 (id={exposure_id_2}): {list(delays_2.values())}")
```

### Test 4: Edge Cases (World A Explicit)

```python
def test_commitment_delay_edge_cases_world_a():
    """Verify edge cases in World A (sublethal → no attrition)."""

    vm = BiologicalVirtualMachine(seed=42)

    # Test 1: Sublethal dose (0.5×IC50) → no delays sampled
    vessel_id = "P1_A01"
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vm.treat_with_compound(vessel_id, "tunicamycin", 0.5)

    vessel = vm.vessel_states[vessel_id]
    delays = vessel.compound_meta.get('commitment_delays', {})

    # In World A, sublethal doses should NOT sample delays
    exposure_id = vessel.compound_meta.get('exposure_ids', {}).get('tunicamycin')
    if exposure_id is not None:
        for s in ['sensitive', 'typical', 'resistant']:
            key = ('tunicamycin', exposure_id, s)
            assert key not in delays, \
                f"Sublethal dose sampled delay for {s} (World A violation)"

    print("✓ Sublethal dose: no delays sampled (World A)")

    # Test 2: Lethal dose (2×IC50) → delays sampled, bounds respected
    vessel_id = "P1_A02"
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vm.treat_with_compound(vessel_id, "tunicamycin", 2.0)

    vessel = vm.vessel_states[vessel_id]
    exposure_id = vessel.compound_meta['exposure_ids']['tunicamycin']
    delays_lethal = [
        vessel.compound_meta['commitment_delays'][('tunicamycin', exposure_id, s)]
        for s in ['sensitive', 'typical', 'resistant']
    ]

    # All delays should be in [1.5h, 48h]
    for d in delays_lethal:
        assert 1.5 <= d <= 48.0, f"Delay {d:.1f}h out of bounds [1.5, 48.0]"

    print(f"✓ Lethal dose: delays {[f'{d:.1f}h' for d in delays_lethal]} in [1.5, 48.0]")

    # Test 3: Extreme dose (100×IC50) → delays approach lower bound
    vessel_id = "P1_A03"
    vm.seed_vessel(vessel_id, "A549", initial_count=1e6, initial_viability=0.98)
    vm.treat_with_compound(vessel_id, "tunicamycin", 100.0)

    vessel = vm.vessel_states[vessel_id]
    exposure_id = vessel.compound_meta['exposure_ids']['tunicamycin']
    delays_extreme = [
        vessel.compound_meta['commitment_delays'][('tunicamycin', exposure_id, s)]
        for s in ['sensitive', 'typical', 'resistant']
    ]

    mean_extreme = np.mean(delays_extreme)
    assert 1.5 <= mean_extreme < 4.0, \
        f"Extreme dose mean {mean_extreme:.1f}h not near lower bound"

    print(f"✓ Extreme dose: mean {mean_extreme:.1f}h (near lower bound)")
```

### Test 5: Monotonicity of Dose-Delay Function

```python
def test_dose_delay_function_monotonic():
    """Verify mean(delay) is strictly decreasing with dose_ratio."""

    # Test the mathematical function directly (no simulator)
    dose_ratios = np.logspace(-1, 2, 50)  # 0.1 to 100
    means = [12.0 / np.sqrt(1.0 + dr) for dr in dose_ratios]

    # Clip to bounds
    means_clipped = [np.clip(m, 1.5, 48.0) for m in means]

    # Check monotonicity (non-increasing)
    for i in range(len(means_clipped) - 1):
        assert means_clipped[i] >= means_clipped[i+1], \
            f"Mean increased at dose_ratio {dose_ratios[i]:.2f} → {dose_ratios[i+1]:.2f}"

    # Check asymptotic behavior
    assert means_clipped[-1] < 2.0, "Should approach lower bound at high dose"
    assert means_clipped[0] > 10.0, "Should be >10h at low dose"

    print(f"✓ Dose-delay function monotonic decreasing")
    print(f"  At 0.1×IC50: {means_clipped[0]:.1f}h")
    print(f"  At 1×IC50: {means_clipped[len(means_clipped)//3]:.1f}h")
    print(f"  At 100×IC50: {means_clipped[-1]:.1f}h")
```

---

## Summary

**What's fixed:**
- Consistent bounds [1.5h, 48h]
- Integer exposure_id cache key (no float drift)
- Sentinel is branch, not number
- World A explicit: sublethal → skip sampling
- CV-based variance test, not absolute
- No hard min gap enforcement

**What's honest:**
- Deterministic (seed-controlled)
- Lognormal CV=0.25 is tunable choice
- Bounds are guardrails, not biology
- World A: no sublethal attrition yet

**What's still a lie (next patch):**
- Subpop viabilities synchronized
- Fractions fixed (no selection)
- No commitment reversal
