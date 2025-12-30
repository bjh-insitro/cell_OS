# Phase 2D.1: Contamination Events - Implementation Status

**Date:** 2025-12-29
**Status:** Steps 1-7 complete (VM integration + morphology signature)

---

## Completed Steps

### ✅ Step 1: RNG Helpers + `operational_events.py`

**File:** `src/cell_os/hardware/operational_events.py`

Implemented:
- `get_operational_rng()` - Order-independent RNG via FNV-1a hash + SeedSequence spawn
- `maybe_trigger_contamination()` - Poisson event sampling in continuous time
- `update_contamination_phase()` - Deterministic phase progression (latent → arrest → death)
- `get_contamination_growth_multiplier()` - Growth arrest effect during arrest/death phases
- `get_contamination_death_hazard()` - Death hazard proposal during death phase
- `get_contamination_morphology_shift()` - Morphology shift magnitude (severity-scaled)
- `CONTAMINATION_MORPHOLOGY_SIGNATURES` - Type-specific channel shifts (bacterial/fungal/mycoplasma)

### ✅ Step 2: VesselState Fields + Death Channel

**File:** `src/cell_os/hardware/biological_virtual.py` (lines 214-220)

Added fields to `VesselState.__init__()`:
- `contaminated: bool` - Event occurred flag
- `contamination_type: Optional[str]` - Type ("bacterial" | "fungal" | "mycoplasma")
- `contamination_onset_h: Optional[float]` - Onset time (hours)
- `contamination_phase: Optional[str]` - Phase ("latent" | "arrest" | "death")
- `contamination_severity: Optional[float]` - Severity multiplier (0.25-3.0, lognormal)
- `death_contamination: float` - Separate death channel (conservation-tracked)

### ✅ Step 3: Config Schema

**File:** `data/cell_thalamus_params.yaml` (lines 510-561)

Added `operational_events.contamination` config:
- Master switches: `operational_events.enabled` and `contamination.enabled` (both default `false`)
- Baseline rate: `baseline_rate_per_vessel_day = 0.005` (0.5% per day → ~3.5% over 7 days)
- Stress multipliers: `stress_multiplier_5x` and `stress_multiplier_10x` (for identifiability testing)
- Type mixture: `type_probs` (bacterial 50%, fungal 20%, mycoplasma 30%)
- Severity distribution: lognormal with CV=0.5, clipped to [0.25, 3.0]
- Phase params: Type-specific latent/arrest/death timing and death rates
- Growth arrest: `growth_arrest_multiplier = 0.05` (95% growth reduction)
- Morphology signature: `morphology_signature_strength = 1.0` (observer-side)

### ✅ Step 4: VM Integration (Trigger)

**File:** `src/cell_os/hardware/biological_virtual.py`

**Config loading** (lines 2696-2701):
- `_load_cell_thalamus_params()` loads contamination config if `operational_events.enabled`
- Stored in `self.contamination_config` (None if disabled)

**Event trigger** in `_step_vessel()` (lines 972-990):
- Calls `maybe_trigger_contamination()` with Poisson sampling
- Calls `update_contamination_phase()` for deterministic progression
- Only active if `contamination_config.enabled == True`

### ✅ Step 5: Growth Arrest Integration

**File:** `src/cell_os/hardware/biological_virtual.py` (lines 1105-1113)

Added growth arrest factor in `_update_vessel_growth()`:
- Calls `get_contamination_growth_multiplier(vessel, config)` during arrest/death phases
- Multiplier = 0.05 (95% growth reduction, effectively stops division)
- Applied after contact inhibition, before confluence saturation

### ✅ Step 6: Death Hazard Integration

**File:** `src/cell_os/hardware/biological_virtual.py`

**Hazard proposal** (lines 1017-1022):
- Calls `get_contamination_death_hazard(vessel, config)` during death proposal phase
- Proposes hazard via `_propose_hazard(vessel, hazard, 'death_contamination')`
- Only active during "death" phase, scaled by severity

**Conservation checks** (lines 877-898):
- Added `death_contamination` to `_assert_conservation()` tracked causes
- Included in ledger overflow diagnostic messages

**Death mode logic** (lines 1347-1454):
- Added `death_contamination` to `_update_death_mode()` tracked causes
- Added `contamination_death` threshold check and mode label
- Conservation enforcement includes `death_contamination` in all checks

### ✅ Step 7: Morphology Signature (Minimal, Deterministic)

**Files:**
- `src/cell_os/hardware/operational_events.py` (lines 222-274)
- `src/cell_os/hardware/assays/cell_painting.py` (lines 430-467)

**Signature definitions** (`operational_events.py`):
- Type-specific channel shifts (deterministic, no RNG)
- Bacterial: High RNA (+0.6), moderate ER/mito, disrupted actin (-0.4)
- Fungal: Strong actin (+0.8), moderate RNA, mild ER/mito
- Mycoplasma: Subtle shifts across all channels (cryptic)

**Morphology application** (`cell_painting.py`):
- `_apply_contamination_morphology()` applies shifts after latent stress effects
- Magnitude scales with severity (zero during latent phase)
- Deterministic (detectable pattern for diagnosis without labels)

---

## Testing

**Smoke test:** `tests/smoke/test_phase2d1_smoke.py`
- ✅ Contamination disabled by default (backward compat)
- ✅ Contamination can be enabled manually
- ✅ All VesselState fields initialized correctly
- ✅ Conservation includes `death_contamination`

**Integration test:**
```bash
PYTHONPATH=/Users/bjh/cell_OS:$PYTHONPATH python3 -c "
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
vm = BiologicalVirtualMachine(seed=42)
vm.seed_vessel('well_A1', 'A549', vessel_type='96-well', initial_count=5000)
vm.advance_time(24.0)
# ✅ No crashes, contamination_config=None, vessel.contaminated=False
"
```

---

## Remaining Steps (Phase 2D.1)

**Step 8: Contract Tests**
- [ ] `test_contamination_default_off.py` - Disabled → zero events, golden unchanged
- [ ] `test_contamination_determinism.py` - Same seed → identical outcomes
- [ ] `test_contamination_order_invariance.py` - Different vessel creation order → identical per-vessel outcomes
- [ ] `test_contamination_rng_isolation.py` - Change assay/biology config → contamination unchanged
- [ ] `test_contamination_rarity.py` - Baseline rate → Poisson expectation with wide tolerance
- [ ] `test_contamination_no_hallucination.py` - Detector flags ≤1% false positives when disabled

**Step 9: Identifiability Suite (3-Regime Design)**
- [ ] Create `configs/calibration/identifiability_2d1.yaml`
  - Regime A: Contamination-free (control, rate=0 or 0.1×)
  - Regime B: Contamination-enriched (stress test, rate=10×)
  - Regime C: Held-out validation (rate=5×)
- [ ] Implement `scripts/run_identifiability_2d1.py`
- [ ] Implement `scripts/render_identifiability_report_2d1.py`
- [ ] Create contamination detector (no labels) in `src/cell_os/calibration/contamination_detector.py`
  - Signature 1: Growth rate anomaly (change-point detection)
  - Signature 2: Morphology anomaly (outlier detection)
  - Signature 3: Viability time course (bimodal plateau → drop)

---

## Design Invariants (Enforced)

1. **Order Independence:**
   - RNG keyed by `lineage_id + domain`, not creation order
   - Vessel A contamination independent of whether vessel B exists

2. **RNG Isolation:**
   - Operational events use separate seed space (`run_seed` not VM RNG streams)
   - Disabling contamination doesn't perturb biology or assay RNG

3. **Death Channel Separation:**
   - `death_contamination` separate from `death_unknown`
   - `death_unknown` = seeding stress + misc operational failures
   - `death_contamination` = contamination-specific progressive kill

4. **Detectable Without Labels:**
   - Growth arrest: sudden drop in dN/dt
   - Morphology shift: type-specific deterministic signature
   - Viability time course: plateau → sudden drop (bimodal)

5. **Backward Compatibility:**
   - Config defaults: `operational_events.enabled = false`
   - No contamination events → identical behavior to before
   - Golden files unchanged when disabled

---

## Known Limitations

1. **Stress mechanism subpopulation shim:**
   - Added `self.subpopulations = {}` to VesselState for backward compat
   - Stress mechanisms (er_stress.py, mito_dysfunction.py) still use old subpop code
   - TODO: Refactor stress mechanisms to Phase 2 vessel-level semantics

2. **Morphology signature is minimal:**
   - Deterministic shifts only (no spatial structure, no stochastic variation)
   - Sufficient for diagnosis but not high-fidelity
   - Can be extended later with more complex patterns

---

## Files Modified

**New:**
- `src/cell_os/hardware/operational_events.py` (Phase 2D.1 infrastructure)
- `tests/smoke/test_phase2d1_smoke.py` (Smoke tests)
- `docs/phase2d1_implementation_status.md` (This file)

**Modified:**
- `src/cell_os/hardware/biological_virtual.py`
  - VesselState fields (lines 214-220, 234)
  - Config loading (lines 2696-2701)
  - VM integration (lines 972-990, 1017-1022, 1105-1113)
  - Conservation checks (lines 877-898, 1347-1454)
- `src/cell_os/hardware/assays/cell_painting.py`
  - Morphology application (lines 245-246, 430-467)
- `data/cell_thalamus_params.yaml`
  - Config schema (lines 510-561)

---

## Next Action

**User decision:** Proceed to Step 8 (contract tests) or defer to later?

**Recommended:** Implement contract tests next (especially `test_contamination_default_off.py`) to lock in backward compatibility before moving to identifiability suite.
