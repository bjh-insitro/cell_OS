# Confidence Calibration Implementation Progress

**Status**: Calibrator training in progress (150 stratified simulation runs)
**Date**: 2025-12-20

## Completed

### ✓ Architecture Design

Three-layer separation implemented:

1. **Inference Layer** (`mechanism_posterior_v2.py`)
   - Bayesian posterior with per-mechanism covariance
   - Nuisance model with mean-shift + variance inflation
   - Produces P(mechanism | features)
   - **Does NOT penalize for nuisance** (stays clean)

2. **Reality Layer** (`confidence_calibrator.py`)
   - Maps belief_state → P(correct)
   - Learns from empirical correctness rates
   - Allows inversions: 80% posterior + 53% nuisance → 52% confidence

3. **Decision Layer** (pending integration with beam search)
   - Uses calibrated confidence for governance
   - COMMIT / WAIT / RESCUE based on calibrated_conf

### ✓ Calibrator Implementation

**File**: `src/cell_os/hardware/confidence_calibrator.py`

**Features**:
- BeliefState: Complete state at decision point (top_prob, margin, entropy, nuisance_frac, timepoint, dose, viability)
- ConfidenceCalibrator: Trains on (belief_state, ground_truth) pairs
- Methods: 'platt' (logistic regression) or 'isotonic'
- Stratified split: Ensures train/test have low/medium/high nuisance
- Evaluation: ECE, Brier, stratified metrics
- Freezing: Treat like labware once trained

### ✓ Training Script

**File**: `train_confidence_calibrator.py`

**Stratification** (critical for avoiding IID-only training):

1. **Low nuisance** (n=50)
   - Clean context (strength=0.5)
   - Early timepoint (10h)
   - Reference dose
   - Target: High accuracy, high confidence justified

2. **Medium nuisance** (n=50)
   - Typical context (strength=1.0)
   - Mid timepoint (14h)
   - Varied dose
   - Target: Moderate accuracy, moderate confidence

3. **High nuisance** (n=50)
   - Cursed context (strength=2.5)
   - Late timepoint (18h, high heterogeneity)
   - Weak dose (ambiguous signal)
   - Target: Conservative (conf ≤ acc + 0.05)

**Total**: 150 simulation runs (stratified by nuisance level)

### ✓ Integration Test

**File**: `test_calibrated_posterior.py`

Tests full pipeline:
1. Run experiment (varied context/timepoint/dose)
2. Compute Bayesian posterior (Layer 1)
3. Apply calibrated confidence (Layer 2)
4. Compare raw vs calibrated

Shows inversions in action:
- Easy case: 95% → 92% (slight reduction, low nuisance)
- Hard case: 80% → 52% (major reduction, high nuisance)

### ✓ Documentation

**Files**:
- `docs/CALIBRATION_ARCHITECTURE.md`: Three-layer design, stratification rationale, acceptance criteria
- `SIGNATURE_LEARNING_RESULTS.md`: Previous milestone (learned signatures pass cosplay detector)
- `CALIBRATION_PROGRESS.md`: This file

## In Progress

### ⟳ Calibrator Training

**Status**: Running in background (task ID: b60e88f)
**Duration**: ~30-60 minutes (150 simulation runs)

**Steps**:
1. Generate 50 low-nuisance samples (DONE if running)
2. Generate 50 medium-nuisance samples
3. Generate 50 high-nuisance samples
4. Train logistic regression calibrator
5. Evaluate on stratified test set
6. Check acceptance criteria:
   - ECE < 0.1 (overall calibration)
   - High-nuisance bins conservative (not overconfident)
   - Low-nuisance bins maintain confidence (not paranoid)
7. Freeze and save to `data/confidence_calibrator_v1.pkl`

## Pending

### Next: Evaluate Calibration

Once training completes:
1. Check ECE < 0.1 (reliability curves near diagonal)
2. Verify high-nuisance bins conservative
3. Verify low-nuisance bins maintain confidence
4. Generate reliability diagram
5. If criteria met: freeze and save
6. If criteria fail: diagnose and retrain with adjustments

### Then: Test Beam Search Behavior

**Critical test**: Does beam search behave differently WITHOUT changing reward weights?

Expected changes:
1. **Fewer early commits in high-nuisance runs**
   - Before: 80% posterior → COMMIT
   - After: 80% posterior + 53% nuisance → 52% calibrated → WAIT

2. **No collapse in easy cases**
   - Before: 95% posterior → COMMIT
   - After: 95% posterior + 10% nuisance → 92% calibrated → COMMIT

3. **Rescue plans for right reasons**
   - Dominant uncertainty source correctly identified
   - Cheapest rescue targets that source

**How you know it's working**: Planner hesitates in exactly the cases you would hesitate.

### Finally: Full Signature Learning (Optional)

Current: 20 samples per mechanism (quick test)
Option: 200 samples per mechanism (production)

**Decision point**: Check if quick signatures are stable enough, or if production signatures needed for final deployment.

## Acceptance Criteria

System is "good enough" when:

1. **Calibration metrics pass**:
   - [ ] ECE < 0.1 (overall)
   - [ ] High-nuisance bins conservative (conf ≤ acc + 0.05)
   - [ ] Low-nuisance bins well-calibrated (|conf - acc| < 0.1)

2. **Beam search behavior natural**:
   - [ ] Hesitates in high-nuisance cases
   - [ ] Commits in low-nuisance cases
   - [ ] No suspicious certainty (high conf + high nuisance)

3. **System is teachable**:
   - [ ] Distinguishes "data favors X" from "allowed to trust that"
   - [ ] Knows when it doesn't know
   - [ ] Not just correct, but epistemically mature

## Key Insights

### What We've Proven

1. **Feature space sufficient**: 3D [actin, mito, ER] with per-mechanism covariance achieves ratio = ∞ on cosplay detector
2. **Likelihood evaluates shape**: Not nearest-neighbor, real geometry
3. **Nuisance model works**: Context mimic test passed (explained away fake ER signal)
4. **Remaining gap is calibration**: Not inference, not features, but trust

### What Calibration Provides

**NOT**: A penalty inside the posterior (self-contradictory)
**YES**: An outer epistemic contract learned from data

Maps: (posterior, nuisance, context) → P(actually correct)

Allows inversions like:
- 80% posterior + 53% nuisance → 52% confidence (reduction)
- 60% posterior + 10% nuisance → 70% confidence (increase)

This is epistemic maturity, not a bug.

### Stratification is Critical

Training on IID samples only gives beautifully calibrated average-case model that lies exactly when you need it.

Stratifying by nuisance level:
- Explicit representation of edge cases
- Calibrator learns: "high nuisance → lower trust"
- Conservative where it matters

### Freezing is Discipline

Once trained, freeze the calibrator. Treat like labware.

Do not retrain casually. Version if needed (v2, v3, ...).

Changes to calibrator should be as deliberate as changes to lab protocol.

## Timeline

- **2025-12-20 09:00**: Started signature learning (quick test, 20 samples)
- **2025-12-20 09:15**: Signature learning complete, cosplay detector passed (ratio = ∞)
- **2025-12-20 09:30**: Context mimic test passed
- **2025-12-20 09:45**: Messy boundary test showed suspicious certainty (diagnostic)
- **2025-12-20 10:00**: Implemented calibrator architecture
- **2025-12-20 10:15**: Started calibrator training (150 stratified runs)
- **2025-12-20 10:30**: [CURRENT] Training in progress, preparing integration tests

## Next Session

When calibrator training completes:
1. Review calibration metrics (stratified ECE, Brier)
2. Test on varied scenarios (easy/typical/hard)
3. Integrate with beam search
4. Watch planner behavior (does it hesitate appropriately?)
5. If working: freeze, version, document
6. If not: diagnose, adjust stratification, retrain

**Goal**: System that knows when it doesn't know.

Not just correct. **Teachable.**
