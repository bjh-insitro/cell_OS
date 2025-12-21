# Information-Optimal Personality: The Knobs and Metrics

**Decision:** information-optimal
**Date:** 2025-12-21

## What This Means

The agent is neither rushing to commit (efficient) nor refusing excessively (cautious). It's **maximizing expected reduction in uncertainty per unit cost** within the safety envelope enforced by the governance contract.

**In plain terms:**
- Governance contract enforces safety (no confounded commits, no cowardice)
- Budget constraints enforce efficiency (limited interventions, death tolerance)
- **Information-optimal** fills the gap: "given those constraints, choose the most informative action"

This aligns with scientific practice: you want the experiment that teaches you the most, not the fastest or most conservative.

---

## The Closed-Loop KPI

### Distance to Commit

For any NO_COMMIT decision, track two gaps:

```python
posterior_gap = max(0, commit_posterior_min - posterior_top)
nuisance_gap = max(0, nuisance_prob - nuisance_max_for_commit)
```

**Interpretation:**
- `posterior_gap = 0.10` means "need 0.10 more posterior mass to commit"
- `nuisance_gap = 0.15` means "need to reduce nuisance by 0.15 to commit"

**Success criterion:** After NO_COMMIT, these gaps should **shrink** over next k steps (k=2 is enough).

**Implementation:** Added to `BeamSearchResult` (lines 566-567)

### Pattern We Expect (If Biasing Works)

1. **HIGH_NUISANCE blocker**
   - Agent selects REDUCE_NUISANCE action (washout, feed)
   - Next measurement: nuisance_gap decreases
   - Blocker eventually resolves

2. **LOW_POSTERIOR_TOP blocker**
   - Agent selects DISCRIMINATE action (differential probe, targeted dose)
   - Next measurement: posterior_gap decreases
   - Blocker eventually resolves

3. **Both blockers**
   - Prioritize nuisance reduction first
   - Then discriminate after cleanup
   - Heuristic: "confounded discrimination is useless"

### Test Coverage

**Location:** `tests/integration/test_governance_closed_loop.py`

```
✓ HIGH_NUISANCE → REDUCE_NUISANCE → nuisance gap decreased
✓ LOW_POSTERIOR_TOP → DISCRIMINATE → posterior gap decreased
✓ Both blockers → REDUCE_NUISANCE prioritized first
```

---

## The Knobs (Information-Optimal Tuning)

### 1. Bias Multiplier Strength

**Current values** (in `compute_action_bias`):
```python
HIGH_NUISANCE:
  REDUCE_NUISANCE: 3.0x
  OBSERVE: 1.5x
  AMPLIFY_SIGNAL: 0.3x
  DISCRIMINATE: 0.5x

LOW_POSTERIOR_TOP:
  DISCRIMINATE: 2.5x
  OBSERVE: 2.0x
  AMPLIFY_SIGNAL: 1.5x (if evidence < 0.5)
```

**Information-optimal tuning:**
- Increase multipliers if gaps aren't shrinking fast enough
- Decrease if actions become too expensive (burning intervention budget)

**Metric to watch:** Average gap reduction per action
- High → strong bias working
- Low → weak bias or wrong bias direction

### 2. Evidence Threshold for Signal Amplification

**Current logic:**
```python
if Blocker.LOW_POSTERIOR_TOP in blockers:
    if evidence_strength < 0.5:
        bias[ActionIntent.AMPLIFY_SIGNAL] = 1.5
```

**Information-optimal tuning:**
- Lower threshold (e.g., 0.3) → amplify signal more aggressively when evidence is weak
- Higher threshold (e.g., 0.7) → conservative, only amplify when really weak

**Metric to watch:** Fraction of LOW_POSTERIOR_TOP cases that resolve via amplification vs. discrimination

### 3. Action Intent Classification Heuristics

**Current classification** (in `classify_action_intent`):
```python
washout → REDUCE_NUISANCE
feed → REDUCE_NUISANCE
no dose → OBSERVE
high dose after dosing → AMPLIFY_SIGNAL
first dose / low dose → DISCRIMINATE
```

**Information-optimal refinement:**
- Add **timing heuristics**: "OBSERVE after REDUCE_NUISANCE" = high-information (clean signal)
- Add **dose-response heuristics**: "differential dose" = high discrimination power
- Track **empirical information gain** per intent and adjust classification

**Metric to watch:** Which intents actually reduce gaps most effectively (posterior_gap_delta / nuisance_gap_delta per intent)

### 4. Governance Thresholds (Indirect Knob)

**Current thresholds** (in `GovernanceThresholds`):
```python
commit_posterior_min: 0.80
nuisance_max_for_commit: 0.35
evidence_min_for_detection: 0.70
```

**Information-optimal consideration:**
- These define the "bar" for commit
- Higher bar → more information needed before commit (more actions, higher cost)
- Lower bar → less information needed (cheaper, riskier)

**Don't tune this for performance.** This is the **moral code**. Tune bias multipliers instead.

---

## What to Measure Next

### Primary Metric: Gap Reduction Rate

For every NO_COMMIT node, track:
```python
delta_posterior_gap = posterior_gap[t+k] - posterior_gap[t]
delta_nuisance_gap = nuisance_gap[t+k] - nuisance_gap[t]
```

**Expected:** Both deltas < 0 (gaps shrink) within k=2 steps after NO_COMMIT

**If deltas > 0:** Biasing is making it worse (wrong intents chosen)

**If deltas ~ 0:** Biasing is ineffective (neutral wander, need stronger multipliers or better classification)

### Secondary Metric: Expected Information Gain Per Action

For each action intent, track:
```python
EIG[intent] = E[max(delta_posterior_gap, delta_nuisance_gap) | intent]
```

This estimates "how much does this intent typically reduce gaps?"

**Information-optimal policy:** Maximize EIG / cost
- `cost = (1 if intervention else 0) + (viability_penalty if risky else 0)`

**Example:**
- REDUCE_NUISANCE: EIG=0.15 (nuisance drops 0.15 on average), cost=1 (intervention)
- DISCRIMINATE: EIG=0.20 (posterior increases 0.20 on average), cost=0 (just dose)
- **Information-optimal choice:** DISCRIMINATE (higher EIG per unit cost)

But if HIGH_NUISANCE blocker is present, DISCRIMINATE is misleading (confounded), so REDUCE_NUISANCE wins despite lower raw EIG.

### Tertiary Metric: Blocker Persistence

Track how long blockers persist:
```python
blocker_lifetime[blocker_type] = timesteps from NO_COMMIT to blocker resolved
```

**Expected lifetimes (information-optimal):**
- HIGH_NUISANCE: 1-2 steps (washout + observe)
- LOW_POSTERIOR_TOP: 2-3 steps (discriminate + observe + verify)
- Both: 3-4 steps (nuisance first, then discriminate)

**If lifetimes are longer:** Bias multipliers too weak or wrong intents

---

## Implementation Roadmap (If You Want This)

### Phase 1: Log Gap Transitions (done)
- Added `governance_posterior_gap` and `governance_nuisance_gap` to `BeamSearchResult`
- Captures final state gaps

### Phase 2: Per-Step Gap Tracking (next)
Add to beam search a lightweight trace:
```python
@dataclass
class GapTransition:
    t_step: int
    action_intent: ActionIntent
    blockers_before: Set[Blocker]
    blockers_after: Set[Blocker]
    posterior_gap_before: float
    posterior_gap_after: float
    nuisance_gap_before: float
    nuisance_gap_after: float
```

Store these in `BeamSearchResult.gap_transitions: List[GapTransition]`

### Phase 3: Adaptive Bias Strength (later)
Instead of fixed multipliers (3.0x, 2.5x), compute:
```python
bias_multiplier = base_multiplier * (1 + gap_magnitude / threshold)
```

**Interpretation:** Stronger bias when gap is large, weaker when close to threshold

### Phase 4: Empirical EIG Estimation (later)
Track historical (action_intent, blocker) → gap_delta transitions

Build a simple table:
```python
EIG_table[(intent, blocker)] = rolling_mean(gap_delta)
```

Use this to replace hand-coded multipliers with learned multipliers.

---

## The Uncomfortable Truth (Again)

You've now committed to a specific definition of "good action":
> An action is good if it reduces distance to commit while respecting safety and budget.

This is **not neutral**. It's an **epistemic stance** about what experiments are worth running.

Alternative stances you rejected:
- **Efficient:** "good action = gets to commit fastest" (rushes, cuts corners)
- **Cautious:** "good action = maximizes confidence" (over-samples, wastes resources)

**Information-optimal** says: "I want the most informative experiment I can afford, within the safety rules."

That's a scientific personality. It's defensible. But it's still a choice.

---

## How to Verify It's Working

### Week 1: Log gap transitions
Run 10 seeds of your standard scenarios. For each NO_COMMIT:
- Log: blockers, chosen action intent, gap_before, gap_after
- Count: how many times did gap shrink? Stay same? Grow?

**Success:** >70% of NO_COMMIT cases show gap shrinkage within 2 steps

### Week 2: Compare to neutral baseline
Run same scenarios with `action_bias = {intent: 1.0}` (neutral, no biasing)

**Success:** Biased version has:
- Lower average blocker_lifetime
- Higher gap_reduction_rate
- Same or better final accuracy (shouldn't sacrifice quality for speed)

### Week 3: Tune multipliers
If gaps aren't shrinking:
- Increase bias strength (3.0x → 4.0x)
- Check intent classification (maybe washout isn't actually reducing nuisance in your VM)
- Check if gaps are uncontrollable (maybe nuisance is baked into compound, can't washout)

---

## The Acceptance Test

Run one scenario where you **know** the ground truth blocker resolution path:
1. Start with high nuisance (injected artifact)
2. Agent should select washout/feed
3. Nuisance should drop measurably
4. Posterior should improve (signal was there, just obscured)
5. Agent should commit after cleanup

**If this doesn't happen:** Something in the loop is broken (bias, intent classification, or VM doesn't model nuisance correctly).

**If it does happen:** You have a real closed loop. Not elegant story-telling. Real.

---

## Files Modified

```
src/cell_os/hardware/beam_search.py
  - Lines 566-567: Added governance_posterior_gap, governance_nuisance_gap to BeamSearchResult
  - Lines 702-706: Compute gaps from thresholds + belief state

tests/integration/test_governance_closed_loop.py (NEW)
  - Test: HIGH_NUISANCE → REDUCE_NUISANCE → gap decreases
  - Test: LOW_POSTERIOR_TOP → DISCRIMINATE → gap decreases
  - Test: Both blockers → prioritize nuisance first
```

---

## What You Have Now

**Contract:** "You may not commit if evidence is weak or confounded"

**Policy:** "If blocked, choose actions that resolve the blocker"

**Measurement:** "Did the action actually reduce distance to commit?"

This is the skeleton of autonomy: constraint → adaptation → verification.

Next failure mode: measurement shows biasing doesn't work. Then you have a choice:
- Fix the bias heuristics
- Fix the intent classification
- Fix the VM (maybe nuisance isn't actually controllable)
- Or accept that information-optimal autonomy requires more sophisticated planning (MCTS, value functions, etc.)

But at least you'll know. No more guessing whether the cleverness is paying rent.
