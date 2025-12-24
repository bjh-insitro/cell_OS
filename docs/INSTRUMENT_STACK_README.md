# Instrument Stack v1.0 - Documentation Index

**Status**: Frozen at v1.0 (commit 730aa74, tag: `instrument_stack_v1`)

**What this is**: A variance-first architecture for accounting instrument artifacts in cell biology experiments. Turns "why is this well weird?" into quantitative variance decomposition.

---

## Quick Start

### Run the visualization
```bash
python scripts/visualize_instrument_stack.py
```

**Output**: Three figures showing spatial gradients, variance decomposition, and sequence contamination.

### Run the demos
```bash
# Aspiration artifact
python scripts/demo_variance_ledger_polished.py

# Evaporation artifact
python scripts/demo_evaporation_variance.py

# Carryover artifact
python scripts/demo_carryover_variance.py
```

**Output**: Quantitative reports with modeled difference, aleatoric/epistemic split, z-scores, and actionable calibration guidance.

### Run the tests
```bash
# Unit tests (27 tests)
pytest tests/unit/test_variance_ledger.py -v
pytest tests/unit/test_evaporation_effects.py -v
pytest tests/unit/test_carryover_effects.py -v

# Integration test (15 tests - contract enforcement)
pytest tests/integration/test_artifact_contracts.py -v
```

**All 42 tests should pass.**

---

## Architecture Documentation

### 1. Core Concept
**File**: [`docs/INSTRUMENT_STACK_COMPLETE.md`](INSTRUMENT_STACK_COMPLETE.md)

**What it covers**:
- The 5-step variance-first pattern (physics → prior → ridge → calibration → ledger)
- Three artifacts: aspiration, evaporation, carryover
- Effect size comparison (0.08% to 20%)
- Correlation structure (spatial vs sequence)
- Files created, tests passing, total line count

**Read this first** to understand the overall system.

---

### 2. Contract (Anti-Rot Protection)
**File**: [`docs/INSTRUMENT_ARTIFACT_CONTRACT.md`](INSTRUMENT_ARTIFACT_CONTRACT.md)

**What it covers**:
- Required fields for every artifact (`ARTIFACT_SPEC`)
- Domain definitions (spatial, sequence, temporal, global)
- Anti-double-counting clause (forbidden dependencies)
- Integration test that enforces contract
- Anti-patterns to avoid

**Read this before adding a new artifact** to ensure contract compliance.

---

### 3. Individual Artifacts

#### Evaporation
**File**: [`docs/EVAPORATION_VARIANCE_COMPLETE.md`](EVAPORATION_VARIANCE_COMPLETE.md)

**What it covers**:
- Spatial exposure field (edge-center gradient)
- Volume loss → concentration drift (dose amplification)
- Ridge uncertainty (60% CV from rate prior)
- Gravimetric calibration hook
- Demo output showing +20% dose difference
- 9 unit tests

**Effect size**: +20% (human-scale, dominates variance)

#### Carryover
**File**: [`docs/CARRYOVER_VARIANCE_COMPLETE.md`](CARRYOVER_VARIANCE_COMPLETE.md)

**What it covers**:
- Sequence-dependent contamination (NOT spatial)
- Pipette residual transfer model
- Ridge uncertainty (80% CV from fraction prior)
- Blank-after-hot calibration hook
- Demo output showing "column 7 is cursed" pathology
- 12 unit tests

**Effect size**: +7.5% (medium, sequence-based)

#### Aspiration
**File**: Inline docstrings in `src/cell_os/hardware/aspiration_effects.py`

**What it covers**:
- Localized shear → cell detachment
- Left-right gradient from aspiration angle
- Ridge uncertainty (2% CV from gamma prior)
- Microscopy calibration hook

**Effect size**: +0.08% (tiny, below noise floor)

**Note**: No standalone docs yet, but fully implemented and tested.

---

## Code Structure

### Core Modules

```
src/cell_os/
├── uncertainty/
│   └── variance_ledger.py          # Variance tracking infrastructure
│                                    # VarianceLedger, explain_difference()
├── hardware/
│   ├── aspiration_effects.py       # Spatial (angle-dependent)
│   ├── evaporation_effects.py      # Spatial (geometry-dependent)
│   └── carryover_effects.py        # Sequence (tip-dependent)
```

### Demos

```
scripts/
├── demo_variance_ledger_polished.py   # Aspiration + reporting scale
├── demo_evaporation_variance.py       # Evaporation + ridge uncertainty
├── demo_carryover_variance.py         # Carryover + sequence contamination
└── visualize_instrument_stack.py      # 3×3 heatmaps + waterfall + trace
```

### Tests

```
tests/
├── unit/
│   ├── test_variance_ledger.py        # 6 tests (ledger operations)
│   ├── test_evaporation_effects.py    # 9 tests (edge > center, ridge boundary)
│   └── test_carryover_effects.py      # 12 tests (sequence dependence, wash)
└── integration/
    └── test_artifact_contracts.py     # 15 tests (contract enforcement)
```

---

## Key Concepts

### Variance Kinds
- **MODELED**: Deterministic effect in this run (given sampled parameters)
- **ALEATORIC**: Irreducible randomness (technical noise)
- **EPISTEMIC**: Calibration uncertainty (parameter priors)

### Effect Types
- **DELTA**: Additive contribution (e.g., +0.05 µM carryover)
- **MULTIPLIER**: Multiplicative contribution (e.g., 1.2× dose from evaporation)
- **CV**: Coefficient of variation (uncertainty)

### Correlation Groups
- **Spatial**: `aspiration_position`, `evaporation_geometry` (wells near each other)
- **Sequence**: `carryover_tip_{tip_id}` (wells dispensed by same tip)
- **Ridge**: `aspiration_ridge`, `evaporation_ridge`, `carryover_ridge` (epistemic shared across plate)
- **Independent**: `independent` (aleatoric noise, uncorrelated)

### The 5-Step Pattern

Every artifact follows this architecture:

1. **Physics**: Deterministic model with saturation (e.g., volume can't go below 30%)
2. **Epistemic Prior**: Non-identifiable parameter encoded as Lognormal distribution
3. **Ridge Uncertainty**: Two-point bracket (5th/95th percentiles) propagates prior CV
4. **Calibration Hook**: Bayesian update from external evidence (microscopy, gravimetry, dye)
5. **Variance Ledger**: Record MODELED + EPISTEMIC + ALEATORIC with correlation groups

---

## Usage Examples

### Example 1: Explain Well-to-Well Difference

```python
from cell_os.uncertainty.variance_ledger import VarianceLedger, explain_difference

ledger = VarianceLedger()

# ... simulate wells A1 and H12 with artifacts ...
# (see demo scripts for full example)

explanation = explain_difference(
    ledger=ledger,
    well_a='A1',
    well_b='H12',
    metric='effective_dose',
    baseline_value=1.0,  # 1 µM
    expected_aleatoric_sd=0.03  # 3% CV
)

print(explanation['summary'])
# Output:
# Modeled difference: +0.200 µM
#   That's +20.0% relative to baseline
#   That's +6.67× the expected aleatoric SD
# Primary drivers:
#   - VAR_INSTRUMENT_EVAPORATION_GEOMETRY: +0.200 (100% of delta)
```

### Example 2: Check Artifact Contract Compliance

```python
from cell_os.hardware import aspiration_effects, evaporation_effects, carryover_effects

# All three expose ARTIFACT_SPEC
assert hasattr(aspiration_effects, 'ARTIFACT_SPEC')
assert aspiration_effects.ARTIFACT_SPEC['domain'] == 'spatial'
assert 'dispense_sequence' in aspiration_effects.ARTIFACT_SPEC['forbidden_dependencies']

# Contract test enforces this automatically
# pytest tests/integration/test_artifact_contracts.py
```

### Example 3: Calibrate Evaporation Rate

```python
from cell_os.hardware.evaporation_effects import (
    EvaporationRatePrior,
    update_evaporation_rate_prior_from_gravimetry
)

# Start with default prior
prior = EvaporationRatePrior()  # mean=0.5 µL/h, CV=0.30

# Measure edge vs center volume loss (gravimetry)
edge_loss_ul = 21.6  # Edge well lost 21.6 µL
center_loss_ul = 14.4  # Center well lost 14.4 µL
time_hours = 24.0

# Update prior
updated_prior, report = update_evaporation_rate_prior_from_gravimetry(
    prior=prior,
    edge_loss_ul=edge_loss_ul,
    center_loss_ul=center_loss_ul,
    time_hours=time_hours,
    edge_exposure=1.5,
    center_exposure=1.0,
    plate_id="CALIB_001"
)

print(f"Prior:     mean={prior.mean:.3f}, CV={prior.cv:.3f}")
print(f"Posterior: mean={updated_prior.mean:.3f}, CV={updated_prior.cv:.3f}")
print(f"Sigma reduction: {report['sigma_reduction']:.1%}")

# Output:
# Prior:     mean=0.500, CV=0.300
# Posterior: mean=0.590, CV=0.070
# Sigma reduction: 76.0%
```

---

## Visualization Output

### Figure 1: 3×3 Heatmaps
**File**: `validation_frontend/public/demo_results/instrument_stack_heatmaps.png`

**Shows**:
- Row 1: Aspiration (left-right gradient, tiny effect)
- Row 2: Evaporation (edge-center gradient, large effect)
- Row 3: Carryover (column stripes, sequence-dependent)
- Columns: Modeled effect | Aleatoric CV | Epistemic ridge CV

**Key insight**: Carryover shows vertical stripes (sequence), not spatial gradient.

### Figure 2: Explain Difference Waterfall
**File**: `validation_frontend/public/demo_results/explain_difference_waterfall.png`

**Shows**:
- Bar chart: Contributions to A1 vs D6 difference
- Uncertainty breakdown: Aleatoric vs epistemic

**Key insight**: Evaporation dominates, epistemic >> aleatoric (calibration will help).

### Figure 3: Carryover Sequence Trace
**File**: `validation_frontend/public/demo_results/carryover_sequence_trace.png`

**Shows**:
- Blank wells vs dispense sequence
- Red = contaminated after hot well
- Gray = clean after blank well

**Key insight**: "Column 7 is cursed" because it's always dispensed after column 6 (hot).

---

## FAQs

### Q: Why are some artifacts documented more than others?

**A**: Evaporation and carryover have standalone docs because they were developed during the documentation push. Aspiration was implemented earlier. All three have 100% inline docstring coverage and full test suites.

### Q: Can I add a new artifact?

**A**: Yes. Follow the 5-step pattern and declare `ARTIFACT_SPEC` at module level. The contract integration test (`tests/integration/test_artifact_contracts.py`) will enforce compliance.

**See**: `docs/INSTRUMENT_ARTIFACT_CONTRACT.md` section "Adding New Artifacts"

### Q: Why is the stack "frozen"?

**A**: To prevent scope creep. The three artifacts prove the pattern works. New artifacts should come from necessity (questions the system can't answer), not from "completing the taxonomy."

**Tag**: `instrument_stack_v1` (commit 730aa74)

### Q: What's the difference between aleatoric and epistemic uncertainty?

**A**:
- **Aleatoric**: Irreducible randomness (e.g., pipetting variation, well-to-well noise). Can't be reduced by calibration.
- **Epistemic**: Parameter uncertainty (e.g., evaporation rate prior CV=30%). Can be reduced by calibration (e.g., gravimetry → CV=7%).

**Actionable**: If epistemic dominates, run calibration. If aleatoric dominates, add replicates.

### Q: Why do some artifacts have huge epistemic CV (60-80%)?

**A**: Because those parameters (evaporation rate, carryover fraction) are **not uniquely identifiable** from dose-response curves alone. They need external evidence (gravimetry, dye traces) to narrow the posterior.

**This is a feature, not a bug**: The system is honest about what it doesn't know.

### Q: How do I know if an effect is "real" vs artifact?

**A**: Use `explain_difference()` with reporting scale:
- Check z-score: Effect >> aleatoric SD? (e.g., 6× → strong signal)
- Check variance decomposition: Is modeled delta larger than epistemic+aleatoric uncertainty?
- Check correlation warnings: Are you mixing spatial and sequence groups?

**Example**:
- Evaporation A1 vs H12: +0.2 µM, z=6.67× → Real, resolvable
- Aspiration A1 vs A12: +0.0008 µM, z=0.04× → Tiny, below noise

---

## Next Steps (Not Implemented Yet)

### Plate-Level Variance Attribution
Not well-to-well. Whole-plate.

"Top 5 variance contributors for this plate" with:
- Percent contribution
- Z-scale impact
- Calibration leverage (what would reduce it)

**Turns the microscope into a planning tool.**

### Experiment Design Under Uncertainty
Given a hypothesis and a budget:
- Where do I place controls?
- Which rows/columns do I avoid?
- Is it cheaper to recalibrate or to add replicates?

**Thalamus becomes infrastructure, not metaphor.**

### Letting Artifacts Argue with Biology
When the variance ledger says:
> "You can't resolve this effect without calibrating evaporation"

That's not a warning. That's a **design constraint**.

**Makes bad experiments obvious.**

---

## Citation

If you use this instrument stack, cite:

```
Instrument Stack v1.0: Variance-First Architecture for Cell Biology Artifacts
Repository: https://github.com/[your-org]/cell_OS
Tag: instrument_stack_v1
Date: 2025-12-23
```

---

## License

[Your license here]

---

## Contact

[Your contact info here]

---

**Document Version**: 1.0
**Last Updated**: 2025-12-23
**Stack Version**: instrument_stack_v1 (commit 730aa74)
