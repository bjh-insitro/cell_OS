# Phase 6A Validation Tests

**Phase 6A: Epistemic Control** - December 2025

This directory contains validation tests for the Phase 6A epistemic control implementation, including calibrated confidence, semantic honesty enforcement, and mechanism inference.

---

## Test Categories

### Calibrated Confidence & Inference
Tests for the three-layer architecture (inference, reality, decision):

- **test_calibrated_posterior.py** - Full pipeline integration test (posterior → calibrated confidence)
- **test_context_mimic.py** - Context shift robustness ("teeth check" - can it handle fake signals?)
- **test_messy_boundary.py** - Ambiguous case handling (high nuisance, weak signals)
- **test_real_posterior.py** - Real posterior computation validation
- **test_beam_commit_integration.py** - Beam search COMMIT gating integration

### Semantic Honesty Enforcement
Tests ensuring the simulator has "no quiet lies":

- **test_death_accounting_honesty.py** - Death attribution tracking (no silent laundering)
- **test_conservation_violations.py** - Conservation law enforcement (crashes on violations)
- **test_adversarial_honesty.py** - Adversarial test cases for honesty
- **test_semantic_invariants.py** - Semantic integrity invariants
- **test_instant_kill_semantics.py** - Instant kill vs. gradual death semantics
- **test_threshold_shift_direction.py** - Subpopulation threshold shift correctness
- **test_microtubule_double_counting.py** - Prevent double-counting in death ledgers
- **test_mixed_mechanisms_conservation.py** - Conservation across mixed mechanisms

### RunContext & Realism Layer
Tests for Phase 5B realism injections:

- **test_run_context_variability.py** - RunContext effects on biology and measurement
- **test_scalar_assay_run_context.py** - Scalar assay context integration (LDH/ATP not oracles)
- **test_volume_evaporation_injection.py** - Volume/evaporation dynamics
- **test_evap_drift_affects_attrition.py** - Evaporation → concentration drift → attrition
- **test_injection_manager_schema.py** - Injection system schema validation

### Statistical Robustness
Tests for noise models and distributional assumptions:

- **test_lognormal_integration.py** - Lognormal noise integration
- **test_multiplicative_noise.py** - Multiplicative noise handling
- **test_stress_axis_determinism.py** - Stress axis determinism across runs

### Diagnostic Tests
Exploratory tests for understanding system behavior:

- **test_refusal_diagnostic.py** - Refusal behavior diagnostics

---

## Running Tests

### Run all Phase 6A tests
```bash
pytest tests/phase6a/
```

### Run specific test category
```bash
# Calibrated confidence tests
pytest tests/phase6a/test_calibrated_posterior.py tests/phase6a/test_context_mimic.py

# Semantic honesty tests
pytest tests/phase6a/test_death_accounting_honesty.py tests/phase6a/test_conservation_violations.py

# RunContext tests
pytest tests/phase6a/test_run_context_variability.py tests/phase6a/test_scalar_assay_run_context.py
```

### Run with verbose output
```bash
pytest tests/phase6a/ -v
```

---

## Test Design Principles

### 1. Honesty Over Correctness
Tests verify the simulator is **epistemically honest** (knows what it doesn't know) rather than just producing correct answers.

### 2. Invariant Enforcement
Tests ensure critical invariants hold:
- Conservation laws (death accounting sums correctly)
- Observer independence (measurements don't perturb physics)
- Determinism (same seed → same results)
- No silent fixes (errors crash, not quietly renormalized)

### 3. Adversarial Testing
Tests include adversarial cases designed to expose:
- Silent laundering (contamination → unattributed)
- Double counting (same death in multiple ledgers)
- Context tells (simulator-specific quirks agents could exploit)

### 4. Calibration Validation
Tests verify calibrated confidence behaves correctly:
- High posterior + high nuisance → reduced confidence
- Context mimic attacks detected and explained away
- Inversions allowed (empirically learned trust adjustments)

---

## Key Test Results

### Calibration Metrics
- **ECE** (Expected Calibration Error): 0.0626 < 0.1 ✓
- **High-nuisance bins**: Conservative (conf 0.899 vs acc 0.958) ✓
- **Cosplay detector**: Ratio = ∞ (perfect separation) ✓

### Semantic Honesty
- **No silent renormalization**: Conservation violations crash ✓
- **No laundering**: death_unknown tracked separately ✓
- **Plate seeding**: Context-dependent (cursed day varies per run) ✓

### RunContext Effects
- **Biology affected**: 2.5% viability difference between clean/cursed ✓
- **Measurement affected**: 73-155% channel intensity differences ✓
- **Scalars not oracles**: LDH/ATP also have context drift ✓

---

## Documentation

For more details on Phase 6A:
- [Phase 6A Session Summary](../../docs/milestones/PHASE_6A_EPISTEMIC_CONTROL_SESSION.md)
- [Calibration Architecture](../../docs/architecture/CALIBRATION_ARCHITECTURE.md)
- [Epistemic Honesty Philosophy](../../docs/designs/EPISTEMIC_HONESTY_PHILOSOPHY.md)
- [Semantic Fixes Status](../../docs/archive/sessions/2025-12-20-semantic-fixes.md)

---

**Last updated:** December 20, 2025
