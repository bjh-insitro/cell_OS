# Beam Search Integration Plan: Calibrated Confidence

**Goal**: Integrate calibrated confidence as a **judge** (gates decisions), not a **force** (doesn't distort beliefs)

## Design Principles

### ✓ DO

1. **Keep existing exploration heuristic clean** - measures trajectory quality
2. **Add explicit COMMIT and RESCUE actions** - beam can now decide when to stop
3. **Gate COMMIT with confidence threshold** - high margin alone insufficient
4. **Add terminal utility for COMMIT** - separate from exploration heuristic
5. **Carry belief state explicitly** - posterior, nuisance, calibrated_conf

### ✗ DO NOT

1. **Replace classifier_margin with calibrated_confidence in heuristic** - would poison inference
2. **Add nuisance penalties to heuristic** - calibration already knows about nuisance
3. **Let COMMIT trigger from death or margin spikes** - must be justified confidence
4. **Change posterior behavior** - three-layer separation stays intact

## Implementation Steps

### Step 1: Extend PrefixRolloutResult

**Add fields**:
```python
@dataclass
class PrefixRolloutResult:
    # Existing fields (keep)
    viability: float
    actin_fold: float
    classifier_margin: float  # Phase5 classifier (keep for transition)
    predicted_axis: Optional[str]
    washout_count: int
    feed_count: int
    actin_struct: float
    baseline_actin: float

    # NEW: Belief state (Bayesian posterior + calibration)
    mito_fold: float = 1.0
    er_fold: float = 1.0

    # Posterior outputs
    posterior_top_mechanism: Optional[str] = None
    posterior_top_prob: float = 0.0
    posterior_margin: float = 0.0  # top - second
    posterior_entropy: float = 0.0

    # Nuisance
    nuisance_fraction: float = 0.0

    # Calibrated confidence (the judge)
    calibrated_confidence: float = 0.0
```

### Step 2: Compute Belief State in rollout_prefix()

**After measuring features** (around line 243):

```python
# Existing Phase5 classifier (keep for comparison)
predicted_axis, classifier_confidence = infer_stress_axis_with_confidence(...)

# NEW: Compute Bayesian posterior + calibrated confidence
from .mechanism_posterior_v2 import (
    compute_mechanism_posterior_v2,
    NuisanceModel,
    Mechanism
)
from .confidence_calibrator import ConfidenceCalibrator, BeliefState

# Build nuisance model
meas_mods = vm.run_context.get_measurement_modifiers()
context_shift = np.array([
    (meas_mods['channel_biases']['actin'] - 1.0) * 0.2,
    (meas_mods['channel_biases']['mito'] - 1.0) * 0.2,
    (meas_mods['channel_biases']['er'] - 1.0) * 0.2
])

hetero_width = vessel.get_mixture_width('transport_dysfunction')  # Use dominant axis
artifact_var = 0.01 * np.exp(-(current_time_h) / 10.0)  # Decay with time

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
    dose_relative=1.0,  # TODO: track actual dose
    viability=viability
)

# Load calibrator and predict confidence
calibrator = ConfidenceCalibrator.load('/Users/bjh/cell_OS/data/confidence_calibrator_v1.pkl')
calibrated_conf = calibrator.predict_confidence(belief_state)

# Return in PrefixRolloutResult
prefix_result = PrefixRolloutResult(
    # ... existing fields ...
    posterior_top_mechanism=posterior.top_mechanism.value,
    posterior_top_prob=posterior.top_probability,
    posterior_margin=posterior.margin,
    posterior_entropy=posterior.entropy,
    nuisance_fraction=nuisance.nuisance_fraction,
    calibrated_confidence=calibrated_conf,
    mito_fold=mito_fold,
    er_fold=er_fold
)
```

### Step 3: Add Explicit Action Types

**Extend Action dataclass**:

```python
@dataclass
class Action:
    dose_fraction: float = 0.0
    washout: bool = False
    feed: bool = False

    # NEW: Explicit terminal actions
    action_type: str = "CONTINUE"  # "CONTINUE", "COMMIT", "RESCUE_TIME", "RESCUE_WELLS"

    # For COMMIT
    commit_mechanism: Optional[str] = None

    # For RESCUE
    rescue_target: Optional[str] = None  # "timepoint", "calibration", "dose_contrast"
```

### Step 4: Extend BeamNode

**Add belief state tracking**:

```python
@dataclass
class BeamNode:
    t_step: int
    schedule: List[Action]

    # Constraints
    washout_count: int = 0
    feed_count: int = 0

    # Observations (keep Phase5 for transition)
    viability_current: float = 1.0
    actin_fold_current: float = 1.0
    classifier_margin_current: float = 0.0  # Phase5 classifier

    # NEW: Belief state
    posterior_top_prob: float = 0.0
    posterior_margin: float = 0.0
    nuisance_fraction: float = 0.0
    calibrated_confidence: float = 0.0

    # Heuristic for exploration (NOT terminal utility)
    heuristic_score: float = 0.0

    # Terminal utility (only for COMMIT nodes)
    commit_utility: Optional[float] = None

    # Terminal reward (full rollout)
    terminal_reward: Optional[float] = None

    # Flags
    is_terminal: bool = False  # True for COMMIT nodes
    dominated: bool = False
```

### Step 5: Modify _expand_node() to Generate COMMIT/RESCUE

**After generating CONTINUE actions** (lines 477-541):

```python
# Existing CONTINUE actions (dose/washout/feed combinations)
for dose_level in self.dose_levels:
    for washout in [False, True]:
        for feed in [False, True]:
            action = Action(
                dose_fraction=dose_level,
                washout=washout,
                feed=feed,
                action_type="CONTINUE"
            )
            # ... create successor, rollout prefix, compute heuristic ...
            successors.append(successor)

# NEW: Add COMMIT action (if confident enough)
prefix_result = self.runner.rollout_prefix(node.schedule)
if prefix_result.calibrated_confidence >= self.commit_threshold:
    commit_action = Action(
        action_type="COMMIT",
        commit_mechanism=prefix_result.posterior_top_mechanism
    )

    commit_node = BeamNode(
        t_step=node.t_step + 1,  # Formally advance, but terminal
        schedule=node.schedule + [commit_action],
        washout_count=node.washout_count,
        feed_count=node.feed_count,
        viability_current=prefix_result.viability,
        calibrated_confidence=prefix_result.calibrated_confidence,
        is_terminal=True,
        commit_utility=self._compute_commit_utility(prefix_result, node.t_step)
    )
    successors.append(commit_node)

# NEW: Add RESCUE actions (if interventions remain)
if node.washout_count + node.feed_count < self.max_interventions:
    # RESCUE_TIME: extend measurement timepoint
    rescue_time_action = Action(
        action_type="RESCUE_TIME",
        feed=False,  # Just wait longer
        rescue_target="timepoint"
    )
    # ... create successor, estimate confidence gain ...

    # RESCUE_WELLS: add calibration wells (counts as intervention)
    rescue_wells_action = Action(
        action_type="RESCUE_WELLS",
        feed=True,  # Use feed as proxy for adding wells
        rescue_target="calibration"
    )
    # ... create successor, estimate confidence gain ...
```

### Step 6: Add Commit Utility Function

**New method in BeamSearch**:

```python
def _compute_commit_utility(self, prefix_result: PrefixRolloutResult, t_step: int) -> float:
    """
    Compute terminal utility for COMMIT decision.

    Separate from exploration heuristic. Answers:
    "Should we commit now, or keep exploring?"

    Args:
        prefix_result: Current belief state
        t_step: Current timestep

    Returns:
        Commit utility (higher = better to commit now)
    """
    elapsed_time = t_step * self.runner.step_h

    # Core: calibrated confidence
    conf_reward = self.w_commit_conf * prefix_result.calibrated_confidence

    # Time cost: earlier commits better (if confident)
    time_penalty = self.w_commit_time * elapsed_time

    # Risk cost: failure if wrong (higher nuisance = higher risk)
    expected_failure_cost = (1.0 - prefix_result.calibrated_confidence) * self.w_commit_risk

    commit_utility = conf_reward - time_penalty - expected_failure_cost

    return commit_utility
```

### Step 7: Modify Beam Pruning to Handle Terminal Nodes

**In _prune_and_select()** (lines 545-563):

```python
def _prune_and_select(self, nodes: List[BeamNode]) -> List[BeamNode]:
    """
    Select top-k nodes by heuristic score.

    Terminal nodes (COMMIT) ranked by commit_utility.
    Non-terminal nodes ranked by exploration heuristic.
    """
    if not nodes:
        return []

    # Separate terminal and non-terminal
    terminal_nodes = [n for n in nodes if n.is_terminal]
    non_terminal_nodes = [n for n in nodes if not n.is_terminal]

    # Rank terminals by commit_utility
    terminal_nodes.sort(key=lambda n: n.commit_utility, reverse=True)

    # Rank non-terminals by heuristic
    non_terminal_nodes.sort(key=lambda n: n.heuristic_score, reverse=True)

    # Keep best terminals (up to beam_width // 2)
    max_terminals = max(1, self.beam_width // 2)
    kept_terminals = terminal_nodes[:max_terminals]

    # Fill rest with non-terminals
    remaining_budget = self.beam_width - len(kept_terminals)
    kept_non_terminals = non_terminal_nodes[:remaining_budget]

    beam = kept_terminals + kept_non_terminals

    return beam
```

### Step 8: Add Decision Receipt Logging

**For every COMMIT node**:

```python
def _log_commit_decision(self, node: BeamNode):
    """
    Log commit decision for forensics.

    Critical for debugging "why did it commit here?"
    """
    logger.info(
        f"COMMIT at t={node.t_step} "
        f"posterior_top_prob={node.posterior_top_prob:.3f} "
        f"margin={node.posterior_margin:.3f} "
        f"nuisance={node.nuisance_fraction:.3f} "
        f"calibrated_conf={node.calibrated_confidence:.3f} "
        f"commit_utility={node.commit_utility:.3f} "
        f"commit_threshold={self.commit_threshold:.3f}"
    )
```

## Configuration Parameters

**Add to BeamSearch.__init__()**:

```python
# Commit gating
commit_threshold: float = 0.75  # Min calibrated confidence to allow COMMIT
w_commit_conf: float = 5.0      # Reward confident commits
w_commit_time: float = 0.1      # Penalize late commits
w_commit_risk: float = 2.0      # Penalize expected failure cost

# Rescue value
w_rescue_gain: float = 1.0      # Reward confidence gain per intervention
```

## Expected Behavior Changes

### Before (Current)

1. Beam always runs full horizon (8 timesteps)
2. High classifier margin → high exploration score
3. No concept of "confident enough to stop"
4. Death penalty only affects viability bonus

### After (With Calibration)

1. **Beam can commit early** if calibrated_confidence ≥ threshold
2. **High margin + high nuisance**:
   - If calibrated_conf high → COMMIT allowed, decisive
   - If calibrated_conf low → Keep exploring or RESCUE
3. **Low margin + low nuisance**:
   - May commit earlier than before (clean context justifies moderate posterior)
4. **Rescue becomes strategic**:
   - Add timepoint when artifacts high
   - Add calibration wells when context effects high

## Acceptance Criteria

### The Paradox Regime Test

**High calibrated_conf + high nuisance → COMMIT decisively**

If calibrator says "this ugly pattern is reliable," planner should commit consistently, not oscillate.

### Clean Moderate Posterior Test

**Moderate posterior + low nuisance → COMMIT earlier**

Clean context means posterior uncertainty is meaningful. Don't wait unnecessarily.

### Cursed Context Test

**High margin + high nuisance + low calibrated_conf → RESCUE or WAIT**

Don't commit just because margin looks good. Calibrator knows context is cursed.

### No Confidence Whiplash

**Commits should be consistent across repeats** (same seed, same compound)

No arbitrary decisions or oscillation.

### Decision Forensics

**Every COMMIT logs belief state**

Can answer "why did it commit here?" with receipts.

## Migration Path

### Phase 1 (This Session)

1. ✓ Extend PrefixRolloutResult with belief state
2. ✓ Compute posterior + calibrated confidence in rollout_prefix()
3. ✓ Add COMMIT action type
4. ✓ Gate COMMIT with confidence threshold
5. ✓ Add commit_utility separate from exploration heuristic

### Phase 2 (Next Session)

6. Add RESCUE actions (timepoint, wells, dose contrast)
7. Estimate confidence gain for rescue selection
8. Test on varied compounds and contexts

### Phase 3 (Validation)

9. Run acceptance tests (paradox, clean moderate, cursed context)
10. Check decision consistency across repeats
11. Verify no confidence whiplash
12. Audit decision receipts

## Critical Invariants

1. **Calibration never affects posterior**: Three-layer separation preserved
2. **Exploration heuristic stays clean**: Measures trajectory quality, not epistemic sufficiency
3. **COMMIT gated by threshold**: High margin alone insufficient
4. **Decisions are forensic**: Every commit has receipts
5. **Consistency over optimization**: Same conditions → same decisions

## The Judge, Not A Force

**Before**: Optimizer chasing signals (classifier margin)

**After**: Judge demanding reasons (calibrated confidence)

The beam search becomes **teachable** - it knows when it doesn't know, and stops when it does.
