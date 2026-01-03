# Phase 2 Completion Checklist

## Status: 3 of 5 functions complete

### ✅ Completed

1. **VesselState.__init__** - Added vessel-level fields:
   - `death_total`
   - `_hazards` (dict)
   - `_total_hazard` (float)
   - `er_stress`, `mito_dysfunction`, `transport_dysfunction` (vessel-level stress axes)

2. **_apply_instant_kill** (lines 746-763) - ✅ **DONE**
   ```python
   # Phase 2: Apply kill to vessel-level viability (authoritative)
   v_before = v0
   v_after = float(np.clip(v0 * (1.0 - kill_fraction), 0.0, 1.0))
   vessel.viability = v_after
   vessel.death_total = float(np.clip(1.0 - v_after, 0.0, 1.0))
   # Scale cell count, update ledger, update confluence
   ```

3. **_commit_step_death** (lines 800-838) - ✅ **DONE**
   ```python
   # Phase 2: Apply survival at vessel level using total hazard
   h_total = float(max(0.0, getattr(vessel, '_total_hazard', 0.0)))
   survival = float(np.exp(-h_total * hours))
   v_after = float(np.clip(v_before * survival, 0.0, 1.0))
   vessel.viability = v_after
   vessel.death_total = float(np.clip(1.0 - v_after, 0.0, 1.0))
   # ... allocate death to fields proportionally
   ```

4. **_apply_stress_recovery** (lines 919-923) - ✅ **DONE**
   ```python
   # Phase 2: Decay vessel-level stress axes
   for axis in ['er_stress', 'mito_dysfunction', 'transport_dysfunction']:
       current = float(getattr(vessel, axis, 0.0) or 0.0)
       if current > 0.0:
           setattr(vessel, axis, float(current * decay_factor))
   ```

### ⏳ TODO

5. **_apply_compound_attrition** (lines 1182-1296) - **IN PROGRESS**
   - Replace subpop loop (lines 1183-1296)
   - Compute IC50 once (no subpop shift)
   - Store hazards in `vessel._hazards` and `vessel._total_hazard`
   - Use vessel.viability (not subpop.viability)

   **Exact replacement pattern**:
   ```python
   # Phase 2: VESSEL-LEVEL HAZARD COMPUTATION (no subpops)
   if not hasattr(vessel, '_hazards') or vessel._hazards is None:
       vessel._hazards = {}
   if not hasattr(vessel, '_total_hazard'):
       vessel._total_hazard = 0.0

   # Compute IC50 once (no subpop shift)
   ic50_uM = biology_core.compute_adjusted_ic50(...)
   ic50_uM *= bio_mods['ec50_multiplier']

   # Get vessel-level commitment delay (not per-subpop)
   cache_key = (compound, exposure_id, vessel.vessel_id)  # NOT subpop_name
   commitment_delay_h = vessel.compound_meta.get('commitment_delays', {}).get(cache_key)

   # Compute attrition at vessel level
   attrition_rate = biology_core.compute_attrition_rate_interval_mean(
       ...,
       current_viability=vessel.viability,  # NOT subpop['viability']
       ...
   )

   # Store in vessel._hazards (not subpop['_hazards'])
   if attrition_rate > 0:
       vessel._hazards['death_compound'] = vessel._hazards.get('death_compound', 0.0) + attrition_rate
       vessel._total_hazard += attrition_rate
   ```

6. **_sample_commitment_delays_for_treatment** (lines 2163-2182) - **TODO**
   - Replace per-subpop loop
   - Sample single delay per vessel
   - Cache with key `(compound, exposure_id, vessel.uid)` NOT `(..., subpop_name)`

   **Exact replacement pattern**:
   ```python
   # Sample commitment delay for vessel (not per subpop)
   vessel_uid = getattr(vessel, "uid", vessel.vessel_id)
   cache_key = (compound, exposure_id, vessel_uid)

   if cache_key in self._commitment_delay_cache:
       return self._commitment_delay_cache[cache_key]

   # Dose-dependent mean: 12 / sqrt(1 + dose_ratio)
   mean_commitment_h = 12.0 / np.sqrt(1.0 + dose_ratio)
   mean_commitment_h = float(np.clip(mean_commitment_h, 1.5, 48.0))

   # Sample once for vessel
   cv = 0.25
   sigma = np.sqrt(np.log(1.0 + cv**2))
   mu = np.log(mean_commitment_h) - 0.5 * sigma**2
   delay_h = float(self.rng_treatment.lognormal(mean=mu, sigma=sigma))
   delay_h = float(np.clip(delay_h, 1.5, 48.0))

   self._commitment_delay_cache[cache_key] = delay_h
   return delay_h
   ```

## Bridge Test Required

Before running Attack 3, add this test to verify VM is functional:

```python
def test_vm_runs_without_subpops():
    """Phase 2 bridge test: VM completes a run end-to-end."""
    rc = RunContext.sample(seed=42)
    vm = BiologicalVirtualMachine(seed=42, run_context=rc)
    vm._load_cell_thalamus_params()

    # Seed vessel
    vm.seed_vessel("A1", "A549", initial_count=2000, vessel_type="96-well")

    # Apply compound
    vm.treat_with_compound("A1", "tBHQ", 30.0)

    # Step 48h in increments
    for _ in range(8):
        vm.advance_time(6.0)

    # Measure
    vessel = vm.vessel_states["A1"]
    obs = vm.cell_painting_assay("A1")

    # Assert sanity
    assert 0.0 <= vessel.viability <= 1.0, f"Bad viability: {vessel.viability}"
    assert vessel.cell_count >= 0.0, f"Negative cell count: {vessel.cell_count}"
    assert all(np.isfinite(v) for v in obs['morphology'].values()), "Non-finite morphology"

    print(f"✅ Bridge test passed: viability={vessel.viability:.3f}")
```

## AST Guardrail (Optional)

Prevent regressions by asserting `"subpopulations"` doesn't appear in code:

```python
def test_no_subpopulations_in_code():
    """AST test: ensure 'subpopulations' string doesn't appear."""
    with open("src/cell_os/hardware/biological_virtual.py") as f:
        code = f.read()

    # Count occurrences (allow in comments)
    lines = code.split('\n')
    code_refs = [i for i, line in enumerate(lines)
                 if 'subpopulations' in line and not line.strip().startswith('#')]

    assert len(code_refs) == 0, \
        f"Found {len(code_refs)} references to 'subpopulations' at lines: {code_refs}"
```

## Once Complete

1. Run bridge test
2. Run Phase 1 contract tests (should still pass)
3. Run Attack 3 confound matrix
4. Interpret results with confidence

## Files Modified

- `src/cell_os/hardware/biological_virtual.py` (5 functions + VesselState.__init__)
- `tests/contracts/test_vm_bridge.py` (new - bridge test)

## Expected Behavior After Phase 2

- VM runs without errors
- No `AttributeError: 'VesselState' object has no attribute 'subpopulations'`
- Death dynamics work at vessel level
- Hazards accumulate in `vessel._hazards` and `vessel._total_hazard`
- Stress axes decay at vessel level
- Commitment delays sampled once per vessel (not per subpop)
