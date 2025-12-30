# Heavy-Tail Measurement Noise: Implementation Summary

## What Was Delivered

Added heavy-tail noise overlay to Cell Painting assays for realistic lab outliers (focus drift, contamination, bubbles).

---

## Files Modified

| File | Change | Justification |
|------|--------|---------------|
| `src/cell_os/hardware/_impl.py` | Added `heavy_tail_shock()` | Reusable statistical primitive (Student-t on log-scale, clipped) |
| `src/cell_os/hardware/assays/cell_painting.py` | Wired shock into `_add_biological_noise()` | Overlays shock on base lognormal: `morph[ch] *= base_i × shock` |
| `data/cell_thalamus_params.yaml` | Added 5 config params | Default: `heavy_tail_frequency=0.0` (dormant, preserves goldens) |
| `src/cell_os/hardware/biological_virtual.py` | (1) Added `heavy_tail_shock` to rng_assay whitelist<br>(2) Moved `well_biology` init to `seed_vessel()` | (1) RNG guard surgical change<br>(2) **Bug fix**: was violating measurement purity contract |
| `src/cell_os/hardware/rng_guard.py` | Added `standard_t()` method | Follows same pattern as `lognormal`, `normal`, etc. |

---

## Regression Tests: Biology Unchanged

**Test:** `test_regression_biology_unchanged.py`

**Verified:**
```
✅ Biology trajectories IDENTICAL with frequency=0.0 (to machine precision)
   - viability: 0.1833674752 == 0.1833674752 ✓
   - cell_count: 582505.7457 == 582505.7457 ✓
   - confluence: 0.0583106928 == 0.0583106928 ✓
   - er_stress: 0.4000000000 == 0.4000000000 ✓
   - mito_dysfunction: 1.0000000000 == 1.0000000000 ✓
   - transport_dysfunction: 0.0000256308 == 0.0000256308 ✓

✅ well_biology initialized deterministically at seeding
✅ well_biology does NOT affect biology state (measurement-only parameter)
✅ RNG guard is surgical (heavy_tail_shock in assay, NOT in growth)
```

**Conclusion:** With `frequency=0.0`, **ZERO biology changes**. The implementation is measurement-only.

---

## The `well_biology` Bug Fix

### What Was Happening (Before)

`_ensure_well_biology()` was called during `measure()` in `cell_painting.py:238`:

```python
def measure(self, vessel, **kwargs):
    self._ensure_well_biology(vessel)  # Called during measurement!
    # ...
```

Inside `_ensure_well_biology()` (line 334):

```python
vessel.well_biology = {  # MUTATION during measurement!
    "er_baseline_shift": float(rng.normal(0.0, 0.08)),
    # ...
}
```

**Problem:** Measurements were MUTATING vessel state. This violates the measurement purity contract.

### What Was Fixed

Moved the EXACT SAME initialization to `seed_vessel()` in `biological_virtual.py:1721`:

```python
def seed_vessel(self, vessel_id, cell_line, ...):
    # ... existing seeding code ...

    # Initialize per-well latent biology (persistent baseline shifts for Cell Painting)
    # This must be done HERE (during seeding) not during measurement (violates purity contract)
    state.well_biology = {
        "er_baseline_shift": float(state.rng_well.normal(0.0, 0.08)),
        "mito_baseline_shift": float(state.rng_well.normal(0.0, 0.10)),
        "rna_baseline_shift": float(state.rng_well.normal(0.0, 0.06)),
        "nucleus_baseline_shift": float(state.rng_well.normal(0.0, 0.04)),
        "actin_baseline_shift": float(state.rng_well.normal(0.0, 0.05)),
        "stress_susceptibility": float(state.rng_well.lognormal(mean=0.0, sigma=0.15)),
    }
```

**Key points:**
- Same RNG (`rng_well`)
- Same parameters
- Same logic
- **Just moved to seeding time, not measurement time**

**Impact on biology:** NONE. `well_biology` only affects measurement (morphology scaling), not biology state (viability, cell_count, stress).

---

## RNG Guard Change

**Added to `rng_assay` whitelist:**

```python
allowed_patterns={"...", "heavy_tail_shock", "..."}
```

**Verified surgical:**
- `heavy_tail_shock` in `rng_assay` ✅ (correct)
- `heavy_tail_shock` NOT in `rng_growth` ✅ (correct)
- Same pattern-matching as existing functions (`lognormal_multiplier`, etc.)

**Added to `ValidatedRNG`:**

```python
def standard_t(self, df, size=None):
    """Generate Student's t-distributed values."""
    self._check_caller()  # Enforces whitelist
    self.call_count += 1
    return self._rng.standard_t(df, size)
```

Follows exact same pattern as `lognormal()`, `normal()`, etc. No special cases, no backdoors.

---

## Contract Tests

### Fast Tests (`test_heavy_tail_fast.py`) - **4.5 seconds total**

| Test | What It Proves | Status |
|------|----------------|--------|
| `test_heavy_tail_shock_primitive()` | Dormant=1.0, always-on=clipped, variation present | ✅ PASS |
| `test_channel_correlation_tight()` | One shock per measurement affects all channels | ✅ PASS |
| `test_rng_draw_count_invariance()` | RNG advances identically regardless of p_heavy | ✅ PASS |
| `test_exceedance_rate_order_of_magnitude()` | Outlier rate ≈ p_heavy (binomial tolerance) | ✅ PASS |
| `test_clipping_enforced_tight()` | Clipping ALWAYS enforced, even extreme params | ✅ PASS |

**Design:** No slow statistical estimation, no 1000+ draw loops. Sharp, deterministic, fast.

---

## Configuration

### Default (Dormant)

```yaml
technical_noise:
  heavy_tail_frequency: 0.0      # DORMANT (preserves golden files)
  heavy_tail_nu: 4.0             # Student-t df (if enabled)
  heavy_tail_log_scale: 0.35     # Shock magnitude (if enabled)
  heavy_tail_min_multiplier: 0.2 # Hard floor (5× attenuation max)
  heavy_tail_max_multiplier: 5.0 # Hard ceiling (5× amplification max)
```

### Enable for Realism

```yaml
heavy_tail_frequency: 0.01  # 1% of measurements get shocks
```

Or programmatically:

```python
vm = BiologicalVirtualMachine(seed=42)
tech_noise = vm.thalamus_params['technical_noise']
tech_noise['heavy_tail_frequency'] = 0.01  # Enable
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Clipping [0.2, 5.0]** | Student-t exp(t) has no finite mean; clipping prevents numeric explosion |
| **No mean correction** | Cannot guarantee E[exp(T)]=1 for Student-t; clipping is the safety rail |
| **Dormant default (p=0.0)** | Preserves golden files, existing tests, gradual rollout |
| **Overlay on base lognormal** | Preserves existing CV calibration, adds rare shocks |
| **Channel correlation** | One shock per measurement (realistic: focus drift hits all channels) |
| **Draw-count invariance** | Always draws u and t, uses conditional assignment (no RNG control flow) |

---

## What Changed in Biology?

**Answer: NOTHING.**

With `frequency=0.0`:
- Viability trajectories: IDENTICAL
- Cell counts: IDENTICAL
- Stress states: IDENTICAL
- Compound effects: IDENTICAL

The only change was **moving `well_biology` initialization from measurement to seeding** to fix a contract violation. This does NOT affect biology - `well_biology` is a measurement-layer parameter.

---

## What Remains Impossible

Heavy-tail noise is **measurement-only**. It CANNOT:
- Alter biology (viability, cell_count, stress states)
- Depend on future measurements (causality enforced)
- Remember across measurements (transient, not persistent per-well)
- Violate clipping bounds (always in [clip_min, clip_max])
- Leak into biology RNG (uses only rng_assay, not rng_growth)

---

## Performance

| Test Suite | Time | Notes |
|------------|------|-------|
| Fast contract tests | **4.5s** | Sharp, deterministic, n=500 max |
| Regression tests | **3.2s** | Full biology trajectories, viability, stress |
| Full existing test suite | **Unchanged** | All pass, frequency=0.0 is no-op |

---

## Next Steps

1. ✅ **Verify no regressions:** Run existing test suite → all pass
2. ✅ **Prove biology unchanged:** Deterministic equality tests → all pass
3. ✅ **Fast, sharp tests:** Replace slow statistical tests → 4.5s total
4. ⏭️ **Enable for realism runs:** Set `frequency=0.01` in experiments
5. ⏭️ **Monitor epistemic agent:** Does it learn outlier handling vs outlier worship?

---

## Diffs

### `biological_virtual.py` (2 changes)

```diff
@@ -495,7 +495,7 @@ class BiologicalVirtualMachine(VirtualMachine):
         self.rng_assay = ValidatedRNG(
             np.random.default_rng(seed + 3),
             stream_name="assay",
-            allowed_patterns={"measure", "count_cells", ..., "lognormal_multiplier", ...},
+            allowed_patterns={"measure", "count_cells", ..., "lognormal_multiplier", "heavy_tail_shock", ...},
             enforce=True
         )

@@ -1716,6 +1716,17 @@ class BiologicalVirtualMachine(VirtualMachine):
         well_seed = stable_u32(f"well_biology_{well_position}_{cell_line}")
         state.rng_well = np.random.default_rng(well_seed)

+        # Initialize per-well latent biology (persistent baseline shifts for Cell Painting)
+        # This must be done HERE (during seeding) not during measurement (violates purity contract)
+        state.well_biology = {
+            "er_baseline_shift": float(state.rng_well.normal(0.0, 0.08)),
+            "mito_baseline_shift": float(state.rng_well.normal(0.0, 0.10)),
+            "rna_baseline_shift": float(state.rng_well.normal(0.0, 0.06)),
+            "nucleus_baseline_shift": float(state.rng_well.normal(0.0, 0.04)),
+            "actin_baseline_shift": float(state.rng_well.normal(0.0, 0.05)),
+            "stress_susceptibility": float(state.rng_well.lognormal(mean=0.0, sigma=0.15)),
+        }
+
         # Injection A+B: seed event establishes initial exposure state
```

### `rng_guard.py` (1 change)

```diff
@@ -200,6 +200,12 @@ class ValidatedRNG:
         self.call_count += 1
         return self._rng.exponential(scale, size)

+    def standard_t(self, df, size=None):
+        """Generate Student's t-distributed values."""
+        self._check_caller()
+        self.call_count += 1
+        return self._rng.standard_t(df, size)
+
     def get_state(self):
         """Get current RNG state (for diagnostics only)."""
```

---

## Conclusion

Implementation is **complete, tested, and verified regression-free.**

- Heavy tails are dormant by default (frequency=0.0)
- Biology trajectories unchanged (deterministic equality proven)
- RNG guard is surgical (measurement-only, no biology leakage)
- Fast tests run in <5 seconds
- One bug fixed: `well_biology` moved from measurement to seeding (contract violation fix)

**Ready for realism runs when you enable frequency > 0.**
