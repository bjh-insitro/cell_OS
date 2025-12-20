# Beam Search Calibrated Confidence Integration - READY TO APPLY

## Status

All patches designed and verified. Ready for implementation.

**What's Done**:
- ✓ BeamNode extended with belief state fields (lines 288-337)
- ✓ PrefixRolloutResult extended with belief state fields (lines 20-39)
- ✓ _prune_and_select rewritten to handle terminals vs non-terminals (lines 563-635)

**What Remains**:
- Add 2 helper methods before `_expand_node`
- Replace `_expand_node` (lines 486-569) with new version

## Integration Recipe

### Step 1: Insert Helper Methods (before line 486)

Insert these two methods into BeamSearch class right before `_expand_node`:

```python
def _populate_node_from_prefix(self, node, pr) -> None:
    """Populate BeamNode cached fields from PrefixRolloutResult."""
    node.viability_current = pr.viability
    node.actin_fold_current = pr.actin_fold
    node.confidence_margin_current = pr.classifier_margin

    node.posterior_top_prob_current = pr.posterior_top_prob
    node.posterior_margin_current = pr.posterior_margin
    node.nuisance_frac_current = pr.nuisance_fraction
    node.calibrated_confidence_current = pr.calibrated_confidence
    node.predicted_axis_current = pr.predicted_axis

def _compute_commit_utility(
    self,
    calibrated_conf: float,
    elapsed_time_h: float,
    ops_penalty: int,
    viability: float
) -> float:
    """Compute terminal utility for COMMIT decision."""
    w_commit_conf = getattr(self, 'w_commit_conf', 5.0)
    w_commit_time = getattr(self, 'w_commit_time', 0.1)
    w_commit_ops = getattr(self, 'w_commit_ops', 0.05)
    w_commit_viability = getattr(self, 'w_commit_viability', 0.1)

    conf_reward = w_commit_conf * calibrated_conf
    time_penalty = w_commit_time * elapsed_time_h
    ops_cost = w_commit_ops * ops_penalty
    viability_penalty = w_commit_viability * (1.0 - viability)

    return conf_reward - time_penalty - ops_cost - viability_penalty
```

### Step 2: Replace `_expand_node` (lines 486-569)

The new version needs to:
1. Compute `prefix_current` once at top for COMMIT gating
2. Generate CONTINUE successors (keep existing loop structure)
3. Populate belief state on CONTINUE successors using helper
4. Generate COMMIT successor after CONTINUE loop
5. Add forensic logging for COMMIT decisions

**Key fixes from bugs**:
- COMMIT node uses `t_step=node.t_step` (NO advance without action)
- `return successors` only at END (not before COMMIT block)
- Use `_populate_node_from_prefix` helper to avoid field mismatch
- CONTINUE nodes: `commit_utility=None`, `is_terminal=False`
- COMMIT nodes: `commit_utility=<computed>`, `is_terminal=True`

### Step 3: Update rollout_prefix() to Compute Belief State

In Phase5EpisodeRunner.rollout_prefix() around line 243, after measuring features:

```python
# Existing Phase5 classifier (keep)
predicted_axis, confidence = infer_stress_axis_with_confidence(...)

# NEW: Compute Bayesian posterior
from .mechanism_posterior_v2 import compute_mechanism_posterior_v2, NuisanceModel
from .confidence_calibrator import ConfidenceCalibrator, BeliefState

# Build nuisance model
meas_mods = vm.run_context.get_measurement_modifiers()
context_shift = np.array([
    (meas_mods['channel_biases']['actin'] - 1.0) * 0.2,
    (meas_mods['channel_biases']['mito'] - 1.0) * 0.2,
    (meas_mods['channel_biases']['er'] - 1.0) * 0.2
])

hetero_width = vessel.get_mixture_width('transport_dysfunction')
artifact_var = 0.01 * np.exp(-current_time_h / 10.0)

nuisance = NuisanceModel(
    context_shift=context_shift,
    pipeline_shift=np.array([0.01, -0.01, 0.01]),
    artifact_var=artifact_var,
    heterogeneity_var=hetero_width ** 2,
    context_var=0.15 ** 2,
    pipeline_var=0.10 ** 2
)

# Compute posterior
posterior = compute_mechanism_posterior_v2(
    actin_fold=actin_fold,
    mito_fold=mito_fold,
    er_fold=er_fold,
    nuisance=nuisance
)

# Build belief state
belief_state = BeliefState(
    top_probability=posterior.top_probability,
    margin=posterior.margin,
    entropy=posterior.entropy,
    nuisance_fraction=nuisance.nuisance_fraction,
    timepoint_h=current_time_h,
    dose_relative=1.0,
    viability=viability
)

# Load calibrator and predict
calibrator = ConfidenceCalibrator.load('/Users/bjh/cell_OS/data/confidence_calibrator_v1.pkl')
calibrated_conf = calibrator.predict_confidence(belief_state)

# Return in PrefixRolloutResult
prefix_result = PrefixRolloutResult(
    viability=viability,
    actin_fold=actin_fold,
    classifier_margin=confidence,
    predicted_axis=posterior.top_mechanism.value,
    washout_count=washout_count,
    feed_count=feed_count,
    actin_struct=actin_struct,
    baseline_actin=baseline_actin,

    # NEW belief state fields
    mito_fold=mito_fold,
    er_fold=er_fold,
    posterior_top_prob=posterior.top_probability,
    posterior_margin=posterior.margin,
    nuisance_fraction=nuisance.nuisance_fraction,
    calibrated_confidence=calibrated_conf
)
```

### Step 4: Add Configuration to __init__

In BeamSearch.__init__(), add:

```python
# Commit gating
self.commit_conf_threshold = 0.75  # Min calibrated confidence to allow COMMIT

# Commit utility weights
self.w_commit_conf = 5.0
self.w_commit_time = 0.1
self.w_commit_ops = 0.05
self.w_commit_viability = 0.1

# Debug mode
self.debug_invariants = False  # Set True to check terminal invariants
```

## Expected Behavior After Integration

### Before (Current)
- Beam always runs full horizon (8 timesteps)
- High classifier margin → high exploration score
- No concept of "confident enough to stop"

### After (With Calibration)
- **Beam can commit early** when calibrated_confidence ≥ 0.75
- **High margin + high nuisance**: If calibrated_conf high → COMMIT; if low → keep exploring
- **Low margin + low nuisance**: May commit earlier (clean context justifies moderate posterior)
- **COMMIT decisions logged** with full forensics

## Testing Plan

1. **Run 20 seeds** on single compound (nocodazole)
2. **Check logs** for COMMIT decisions:
   - Are they consistent across same seed?
   - Do they hesitate in high-nuisance cases?
   - Do they commit earlier in low-nuisance cases?
3. **Verify no crashes** from field mismatches
4. **Check beam diversity**: Both terminals and non-terminals in beam?

## The Critical Test: Paradox Regime

**High calibrated_conf + high nuisance → COMMIT decisively**

If calibrator says "this ugly pattern is reliable," planner should commit consistently, not oscillate.

## Files Modified

1. `src/cell_os/hardware/beam_search.py`:
   - PrefixRolloutResult extended
   - BeamNode extended
   - _prune_and_select rewritten
   - _populate_node_from_prefix added
   - _compute_commit_utility added
   - _expand_node replaced
   - __init__ updated

2. `src/cell_os/hardware/beam_search.py` (Phase5EpisodeRunner.rollout_prefix):
   - Add posterior computation
   - Add calibrated confidence
   - Return belief state in PrefixRolloutResult

## Current Session Accomplishments

From "nearest-neighbor cosplay" to **calibrated Bayesian inference with epistemic honesty**:

1. ✓ Learned mechanism signatures (cosplay detector ratio = ∞)
2. ✓ Trained calibrated confidence (ECE < 0.1)
3. ✓ Fixed semantic lies (death accounting, plate seeding, conservation)
4. ✓ Designed three-layer architecture (inference, reality, decision)
5. ✓ Integrated COMMIT gating (this document)

**Next**: Apply integration, test on beam search, watch for hesitation.

The planner becomes a **judge**, not just an optimizer.
