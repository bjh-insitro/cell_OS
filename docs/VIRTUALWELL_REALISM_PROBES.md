# VirtualWell Realism Probes

**Purpose:** Make simulator realism claims falsifiable through auditable tests

**Not a feature spree.** This is a probe suite to verify epistemic honesty, not add "more realism."

## Three Probe Pillars

### P1: Observer Independence (Backaction = 0)

**Claim:** Measuring a well does not alter future biology trajectory

**Tests:**
- **P1.1: Measure vs no-measure equivalence** (`test_p1_1_measure_vs_no_measure_equivalence`)
  - Setup: Run with/without intermediate measurement at T1, compare state at T2
  - Assert: Viability, stress states, death accounting identical (< 1e-9 difference)
  - **Failure mode:** `observer_backaction_max > 1e-6` → measurement leaked into biology

- **P1.2: Repeated measurement idempotence** (`test_p1_2_repeated_measurement_idempotence`)
  - Setup: Measure same well twice at same timepoint
  - Assert: Biology unchanged, measurement noise may differ (RNG advances)
  - **Failure mode:** Viability drifts between measurements

**Diagnostic fields:**
- `p1_observer_backaction_max`: Max delta across viability/stress/death (float)
- `p1_observer_backaction_violation`: True if delta > 1e-6 (bool)
- `p1_repeated_viability_drift`: Viability change between repeated measures (float)

---

### P2: Noise Model Fidelity

**Claim:** Lognormal noise → nonnegative, multiplicative scaling, realistic outliers

**Tests:**
- **P2.1: Nonnegativity enforcement** (`test_p2_1_nonnegativity_enforcement`)
  - Setup: Generate 16 replicates, check all channels >= 0
  - Assert: No negative signals (Cell Painting, LDH)
  - **Failure mode:** `nonnegativity_violations > 0` → noise model broken

- **P2.2: CV scaling (heteroscedasticity)** (`test_p2_2_cv_scaling_heteroscedasticity`)
  - Setup: Low-signal (high dose) vs high-signal (low dose) conditions
  - Assert: CV similar (multiplicative) or differs (heteroscedastic)
  - **Failure mode:** Unexpected CV pattern contradicts noise assumptions

- **P2.3: Outlier accounting** (`test_p2_3_outlier_accounting`)
  - Setup: 50 replicates, check for |z| > 3 outliers
  - Assert: Outliers rare but exist (~1-5%)
  - **Failure mode:** No outliers (truncated distribution) or too many (bad noise)

**Diagnostic fields:**
- `p2_nonnegativity_violations`: Count of negative signals (int)
- `p2_noise_cv_low`: CV at low signal (float)
- `p2_noise_cv_high`: CV at high signal (float)
- `p2_noise_model`: "multiplicative" or "heteroscedastic" (string)
- `p2_outlier_rate`: Fraction with |z| > 3 (float)
- `p2_max_z_score`: Largest observed z-score (float)

---

### P3: Batch Effects Separability

**Claim:** Batch creates systematic shift, but biology ground truth unchanged

**Tests:**
- **P3.1: Batch creates systematic shift** (`test_p3_1_batch_creates_systematic_shift`)
  - Setup: Same biology, different batch contexts
  - Assert: Measurement shifts but viability identical (< 1e-6)
  - **Failure mode:** Viability changes → batch leaked into biology

- **P3.2: Within vs across batch correlation** (`test_p3_2_within_vs_across_batch_correlation`)
  - Setup: Wells in batch A vs batch B
  - Assert: `corr_within > corr_across` (positive gap)
  - **Failure mode:** No correlation structure → batch effects not implemented

- **P3.3: Batch does not flip mechanism** (`test_p3_3_batch_does_not_flip_mechanism`)
  - Setup: Same compound/dose, two batches
  - Assert: Mechanism signature (ER elevation) consistent
  - **Failure mode:** **DIAGNOSTIC ONLY** - if mechanism flips, document limitation

**Diagnostic fields:**
- `p3_batch_effect_magnitude`: ||shift|| across channels (float)
- `p3_corr_gap`: within_corr - across_corr (float)
- `p3_mechanism_consistent`: True if signature stable (bool)

---

## Running Tests

```bash
# All probes (takes ~30 seconds)
python3 -m pytest tests/integration/test_virtualwell_realism_probes.py -v

# Or standalone
PYTHONPATH=. python3 tests/integration/test_virtualwell_realism_probes.py
```

**Expected output:** 8/8 tests pass, diagnostic JSON with all fields populated

---

## Diagnostic Integration

**Event type:** `virtualwell_realism_probe`

**Emission:** End of run (optional, not per-cycle)

**Schema:**
```json
{
  "event_type": "virtualwell_realism_probe",
  "timestamp": "2025-12-22T17:10:00",
  "p1_observer_backaction_max": 1.23e-10,
  "p1_observer_backaction_violation": false,
  "p1_repeated_viability_drift": 5.67e-11,
  "p2_nonnegativity_violations": 0,
  "p2_noise_cv_low": 0.182,
  "p2_noise_cv_high": 0.175,
  "p2_noise_model": "multiplicative",
  "p2_outlier_rate": 0.02,
  "p2_max_z_score": 3.41,
  "p3_batch_effect_magnitude": 12.45,
  "p3_corr_gap": 0.31,
  "p3_mechanism_consistent": true
}
```

**Location:** `diagnostics.jsonl` (appended at end of run if probes enabled)

**Integration point:** `EpistemicLoop._save_json()` or post-run analysis script

---

## Failure Interpretation

### Observer Backaction Violation
- **Signal:** `p1_observer_backaction_max > 1e-6`
- **Cause:** Measurement mutated biology state (RNG leak, viability update, death ledger corruption)
- **Action:** File bug report, check RNG separation (`rng_assay` vs `rng_biology`)

### Nonnegativity Violation
- **Signal:** `p2_nonnegativity_violations > 0`
- **Cause:** Additive noise or negative floor allowed
- **Action:** Verify `lognormal_multiplier` used everywhere, check signal clipping

### Batch Leaks Into Biology
- **Signal:** `p3_1` test fails with viability_diff > 1e-6
- **Cause:** RunContext biology modifiers not constant (FIX #5 may have reverted)
- **Action:** Check `RunContext.get_biology_modifiers()` returns constants

### No Batch Effects
- **Signal:** `p3_corr_gap ≈ 0`
- **Cause:** Batch effects disabled or too weak
- **Action:** Check `context_strength` parameter, verify RunContext applied

---

## Design Philosophy

**This is NOT:**
- Parameter tuning to "look more real"
- Adding features users didn't ask for
- Fitting to real lab data

**This IS:**
- Making existing claims testable
- Detecting silent bugs (observer backaction, negative signals)
- Documenting limitations (mechanism flip under batch)
- Providing audit trail for epistemic honesty

**If a test fails:** Fix the bug or document the limitation. Do not weaken the test.

---

## Test Inventory

| Test | Probe | Runtime | Deterministic | Critical |
|------|-------|---------|---------------|----------|
| P1.1 | Observer independence | ~2s | Yes (seed=42) | ✅ Yes |
| P1.2 | Repeated measurement | ~1s | Yes (seed=123) | ✅ Yes |
| P2.1 | Nonnegativity | ~3s | Yes (seed=456) | ✅ Yes |
| P2.2 | CV scaling | ~4s | Yes (seed=789) | No |
| P2.3 | Outliers | ~5s | Yes (seed=999) | No |
| P3.1 | Batch shift | ~2s | Yes (seeds 1000,2000) | ✅ Yes |
| P3.2 | Batch correlation | ~3s | Yes (seeds 3000,4000) | No |
| P3.3 | Mechanism stability | ~2s | Yes (seeds 5000,6000) | No (diagnostic) |

**Total runtime:** ~22 seconds

**Critical tests** (P1.1, P1.2, P2.1, P3.1) must pass or CI fails.

---

## Integration with Existing Tests

**Complements:**
- `test_washout_measurement_separation.py` - Washout-specific observer independence
- `test_conservation_violations.py` - Death accounting conservation
- `test_step_size_consistency.py` - Temporal integration fidelity

**Does NOT replace:** Phase6a integration tests (those test full agent loop)

**Runs in:** `tests/integration/` (standalone, no agent dependencies)

---

## Future Extensions (NOT in scope)

- [ ] P4: Spatial correlation structure (edge effects, positional artifacts)
- [ ] P5: Temporal causality probes (future states don't affect past)
- [ ] P6: Subpopulation heterogeneity realism (3-bucket vs continuous)

**Keep focused.** Three pillars are sufficient for epistemic honesty audit.
