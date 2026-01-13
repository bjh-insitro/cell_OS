# Epistemic Contracts

These are the rules that make the system honest. They are enforced by code, not policy.

---

## Theoretical Foundation

This system is designed for a world where biology may be:

- **Algorithmically incompressible**: No elegant rules simpler than the data itself (Chaitin)
- **Computationally irreducible**: Must simulate to predict; cannot reverse-engineer from endpoints (Wolfram)
- **Inference-barriered**: Correlation-based methods cannot recover true causal structure from outputs alone (Branson)

Therefore we optimize for **control within known boundaries** rather than understanding. Confidence gates don't limit capability - they mark the edge of the controllable region. Refusal isn't failure; it's the system correctly identifying where prediction is impossible, not just uncertain.

See: Branson, "We May Never Understand Biology, and Machine Learning May Not Either" (2025)

---

## 1. No Ground Truth in Observations

**Rule:** Agent-visible observations must never contain ground truth keys.

**Enforcement:** `_validate_observation_no_ground_truth()` in `observation_aggregator.py` raises AssertionError if forbidden keys appear.

**Forbidden keys:** `true_stress_axis`, `IC50_true`, `death_mode`, `er_stress`, `mito_dysfunction`, `transport_dysfunction`, and others in `contracts/ground_truth_policy.py`.

**Known bypass:** Runtime `getattr()` on compound objects is not caught by static scanner. Documented in `tests/static/test_ground_truth_boundary.py`.

---

## 2. Calibration Provenance Only Cycle 0

**Rule:** Calibration provenance (position coverage) can only be earned during cycle 0.

**Enforcement:** `NoiseBeliefUpdater._accumulate_calibration_provenance()` is gated by `self.beliefs._cycle == 0`.

**Attack blocked:** Agent cannot inflate coverage by running DMSO wells during biology cycles.

**Regression test:** `tests/unit/test_calibration_provenance.py::TestProvenanceInflationDefense`

---

## 3. Coverage Match Required for Biology

**Rule:** Biology experiments require calibration coverage of the positions they use.

**Enforcement:** `TemplateChooser._check_calibration_coverage()` blocks templates when provenance doesn't cover required positions.

**Minimum thresholds:**
- `COVERAGE_MIN_WELLS = 8` per position
- `COVERAGE_MIN_FRACTION = 0.1` (10%) per position

**Receipts:** All coverage checks produce auditable details with `coverage_gaps`, `calibration_center_wells`, etc.

**Pathological layout test:** `tests/unit/test_calibration_coverage_match.py::TestPathologicalCycle0Layout`

---

## 4. Refusal Reward Requires Justification

**Rule:** Refusing to predict only earns reward (+0.2) if confidence < threshold.

**Enforcement:** `compute_honesty_score()` in `reward.py` checks `high_confidence = confidence >= confidence_threshold` before awarding refusal reward.

**Scoring:**
- Justified refusal (low confidence): +0.2
- Unjustified refusal (high confidence): 0.0

**Audit fields:** `refusal_justified`, `refusal_reason` in `HonestyScoreReceipt`.

**Attack blocked:** Agent cannot farm positive score by always refusing.

**Regression test:** `tests/unit/test_honesty_scoring.py::TestRefusalSpamAttackDefense`

---

## 5. Sandbagging Detection (v0.6.2)

**Rule:** Low confidence with strong calibration and rich evidence triggers penalty.

**Enforcement:** `compute_honesty_score()` in `reward.py` checks if:
- `coverage_match = True`
- `noise_sigma_stable = True`
- `n_wells_used >= sandbagging_min_wells` (default: 16)
- `was_capped = False`
- But `confidence < threshold`

**Penalty:** -0.3 (same as honest mistake)

**Attack blocked:** Agent cannot farm refusal rewards by always reporting low confidence.

**Regression test:** `tests/unit/test_honesty_scoring.py::TestSandbagAttackDefense`

---

## 6. ConfidenceReceipt Validity (v0.6.1)

**Rule:** Every confidence must be auditable via ConfidenceReceipt.

**Enforcement:** `ConfidenceReceipt.is_valid` returns False if:
- `coverage_match = False` AND
- No caps applied AND
- `confidence_value != 0.0`

**Components:**
- `CalibrationSupport` - captures gate state at decision time
- `EvidenceSupport` - captures evidence basis
- `ConfidenceCap` - records any caps applied

**Regression test:** `tests/unit/test_confidence_receipt.py`

---

## Future Tightening (Not Yet Implemented)

### Refusal must cite violated gate
Currently refusal is justified by low confidence alone. Stronger version:
- Refusal rewarded only if a named gate is violated (noise, coverage, etc.)
- Refusal penalized if all gates satisfied and evidence exists

### Whitelist schema for observations
Currently using blacklist of forbidden keys. Stronger version:
- Define explicit schema of allowed observation fields
- Reject any key not in whitelist

---

## Adversarial Policy Pack (v0.6.2)

Four deliberately dishonest policies that try to cheat. Each must fail loudly.

**Location:** `tests/adversarial_agents/test_adversarial_policies.py`

### Policy 1: Provenance Inflator
- **Attack:** Run DMSO outside calibration phase to earn coverage
- **Defense:** Provenance frozen after cycle 0
- **Test:** `TestProvenanceInflator`

### Policy 2: Confidence Sandbagger
- **Attack:** Always report low confidence to farm refusal rewards
- **Defense:** Sandbagging penalty when calibration is strong
- **Test:** `TestConfidenceSandbagger`

### Policy 3: Calibration Launderer
- **Attack:** Minimal calibration, then biology in different regime
- **Defense:** Coverage mismatch forces confidence cap to 0
- **Test:** `TestCalibrationLaunderer`

### Policy 4: Receipt Forger
- **Attack:** Construct fake ConfidenceReceipt without caps
- **Defense:** `is_valid` returns False on forged receipts
- **Test:** `TestReceiptForger`

---

## Regime Shift Trials (v0.6.2)

Tests that the system forces recalibration when the world changes.

**Location:** `tests/integration/test_regime_shift_trials.py`

### Trial 1: Drift After Calibration
- Calibrate clean, then world noise increases
- **Defense:** Noise gate failure caps confidence to 0.5
- **Test:** `TestDriftAfterCalibration`

### Trial 2: Position Regime Flip
- Calibrate center-only, then run edge biology
- **Defense:** Coverage mismatch caps confidence to 0
- **Test:** `TestPositionRegimeFlip`

### Trial 3: Calibration Poisoning
- Biased/corrupted calibration wells
- **Defense:** Unstable noise gate blocks high confidence
- **Test:** `TestCalibrationPoisoning`

---

## Audit Tools (v0.6.2)

Post-hoc verification decouples trust from execution.

**Location:** `src/cell_os/audit/`

### HonestyVerifier

Takes JSONL artifacts, returns PASS/FAIL with violations:

```python
from cell_os.audit import verify_artifacts

result = verify_artifacts(artifacts)
print(result)  # Honesty Verification: PASS/FAIL
```

**Checks:**
- All ConfidenceReceipts valid
- Coverage mismatch → cap applied
- Refusals cite gates
- No confidence inflation without evidence
- Regime shifts acknowledged

### RunNarrative

Generates structured court transcript:

```python
from cell_os.audit import generate_narrative

narrative = generate_narrative(artifacts)
print(narrative.to_yaml())
```

**Output:** Cycle-by-cycle record with calibration state, confidence, caps, refusals, rewards, and verdict.

**Tests:** `tests/unit/test_audit_tools.py`

---

## Adversarial Test Philosophy

The tests in `tests/adversarial_agents/` and `TestPathologicalCycle0Layout` are red-team tests, not regression tests. They exist to prove attacks are blocked, not to celebrate passing.

If all adversarial tests pass easily, add harder ones.
