# Epistemic System Integration Guide

**Quick Start**: How to wire epistemic control into your planner in 30 minutes.

---

## Overview

The epistemic system enforces three conservation laws:
1. **Mass**: Cells don't appear from nothing (death accounting)
2. **Time**: Observation takes time, drift accumulates (injection B)
3. **Uncertainty**: Data doesn't sharpen belief without cost (epistemic control)

This guide shows how to integrate #3 into your planning loop.

---

## Step 1: Initialize Controller (5 min)

```python
from cell_os.epistemic_control import EpistemicController, EntropySource

# At experiment start
controller = EpistemicController()

# Set baseline entropy (your typical uncertainty level)
initial_posterior = your_mechanism_posterior()
controller.set_baseline_entropy(initial_posterior.entropy)
```

**Why**: Baseline defines "normal" uncertainty. High entropy shrinks planning horizon relative to baseline.

---

## Step 2: Before Expensive Action (10 min)

```python
# Estimate expected info gain
from cell_os.hardware.assay_governance import estimate_scRNA_info_gain

expected_gain = estimate_scRNA_info_gain(
    current_uncertainty=belief.entropy,
    mechanism_ambiguity=count_plausible_mechanisms(belief),
    viability=vessel.viability
)

# Claim (with marginal gain if prior measurements exist)
controller.claim_action(
    action_id=f"scrna_{episode}",
    action_type="scrna_seq",
    expected_gain_bits=expected_gain,
    prior_modalities=tuple(already_measured),  # e.g., ("cell_painting", "atp")
    claimed_marginal_gain=expected_gain * 0.5  # Adjust for overlap
)

# Get inflated cost (debt makes it more expensive)
base_cost = 200.0
actual_cost = controller.get_inflated_cost(base_cost)

# Use actual_cost in your budget/planning
if actual_cost > budget:
    return choose_cheaper_alternative()
```

**Why**:
- Claiming creates accountability (will be compared to realized gain later)
- Marginal gain forces you to account for redundancy with prior measurements
- Cost inflation makes bad calibration expensive

---

## Step 3: After Action (10 min)

```python
# Get entropy before and after
prior_entropy = belief_before.entropy
posterior_entropy = belief_after.entropy

# Determine entropy source
if not_measured_yet:
    source = EntropySource.PRIOR  # Exploration (not penalized)
elif posterior_entropy < prior_entropy:
    source = EntropySource.MEASUREMENT_NARROWING  # Good
elif measurement_contradicted_prior:
    source = EntropySource.MEASUREMENT_CONTRADICTORY  # Bad (1.5× penalty)
else:
    source = EntropySource.MEASUREMENT_AMBIGUOUS  # Mediocre

# Measure realized gain
realized_gain = controller.measure_information_gain(
    prior_entropy=prior_entropy,
    posterior_entropy=posterior_entropy,
    entropy_source=source
)

# Resolve claim (accumulates debt if overclaimed)
controller.resolve_action(
    action_id=f"scrna_{episode}",
    actual_gain_bits=realized_gain,
    action_type="scrna_seq"
)
```

**Why**:
- `entropy_source` ensures exploration isn't penalized
- Realized gain compared to claimed gain → debt if overclaimed
- Debt accumulates and inflates future costs

---

## Step 4: Apply Penalties (5 min)

```python
# Compute penalty
penalty = controller.compute_penalty(action_type="scrna_seq")

# Apply to reward
reward -= penalty.entropy_penalty

# Shrink planning horizon if uncertain
planning_horizon *= penalty.horizon_multiplier

# Log for analysis
log_metrics({
    "entropy_penalty": penalty.entropy_penalty,
    "horizon_multiplier": penalty.horizon_multiplier,
    "did_widen": penalty.did_widen,
    "epistemic_debt": controller.get_total_debt()
})
```

**Why**:
- Entropy penalty makes widening hurt immediately
- Horizon shrinkage makes agent cautious when confused
- Debt persists across episodes (long-term memory)

---

## Optional: Provisional Penalties (Advanced)

Use when an action might widen entropy temporarily but enable later resolution:

```python
# After scRNA widens entropy
penalty = controller.compute_penalty()

if might_be_productive(action):  # Your heuristic
    # Make penalty provisional (held in escrow)
    controller.add_provisional_penalty(
        action_id=f"scrna_{episode}_provisional",
        penalty_amount=penalty.entropy_penalty,
        settlement_horizon=3  # Re-evaluate after 3 steps
    )
    # Penalty not applied immediately
else:
    # Apply penalty immediately
    reward -= penalty.entropy_penalty

# Each step, settle expired provisional penalties
finalized = controller.step_provisional_penalties()
reward -= finalized  # Apply finalized penalties
```

**When to use**:
- scRNA reveals subpopulations (temporary widening, but clarifying)
- Multi-condition screen (initial confusion, later decisive)
- Exploratory experiments where uncertainty is expected

**When NOT to use**:
- Routine measurements
- Actions that shouldn't widen entropy at all
- When you're not sure (default to immediate penalty)

---

## Complete Integration Example

```python
class EpistemicPlanner:
    def __init__(self):
        self.controller = EpistemicController()
        self.episode = 0

    def plan_experiment(self, belief_state, budget):
        # Get current state
        current_entropy = belief_state.entropy
        already_measured = belief_state.modalities_used

        # Consider scRNA
        if current_entropy > 1.0 and "cell_painting" in already_measured:
            # High entropy, already tried imaging → scRNA might help

            # Estimate gain
            expected_gain = self._estimate_gain(belief_state)

            # Account for overlap
            marginal_gain = expected_gain * 0.6  # 60% is new info

            # Claim
            self.controller.claim_action(
                f"scrna_{self.episode}",
                "scrna_seq",
                expected_gain,
                prior_modalities=tuple(already_measured),
                claimed_marginal_gain=marginal_gain
            )

            # Check cost
            cost = self.controller.get_inflated_cost(200.0)
            if cost > budget:
                return self._choose_alternative()

            # Run action
            result = self._run_scrna()

            # Measure gain
            realized = self.controller.measure_information_gain(
                prior_entropy=current_entropy,
                posterior_entropy=result.entropy,
                entropy_source=self._infer_source(result)
            )

            # Resolve
            self.controller.resolve_action(
                f"scrna_{self.episode}",
                realized,
                "scrna_seq"
            )

            # Apply penalty
            penalty = self.controller.compute_penalty()
            self.reward -= penalty.entropy_penalty

            return result

    def _infer_source(self, result):
        """Infer entropy source from result."""
        if result.entropy < result.prior_entropy:
            return EntropySource.MEASUREMENT_NARROWING
        elif result.contradicted_prior:
            return EntropySource.MEASUREMENT_CONTRADICTORY
        else:
            return EntropySource.MEASUREMENT_AMBIGUOUS
```

---

## What to Monitor

### Per-episode metrics
```python
{
    "epistemic_debt": controller.get_total_debt(),
    "cost_multiplier": controller.get_cost_multiplier(),
    "entropy_penalty": penalty.entropy_penalty,
    "horizon_multiplier": penalty.horizon_multiplier,
    "info_gain": realized_gain,
    "overclaim": claimed - realized
}
```

### Aggregate statistics
```python
stats = controller.get_statistics()
{
    "total_debt": stats["total_debt"],
    "mean_overclaim": stats["mean_overclaim"],
    "overclaim_rate": stats["overclaim_rate"],
    "cost_multiplier": stats["cost_multiplier"],
    "provisional_refund_rate": stats.get("provisional_refund_rate", 0)
}
```

### Red flags
- `total_debt > 5.0`: Agent is badly calibrated
- `overclaim_rate > 0.8`: Agent consistently overpromises
- `cost_multiplier > 1.5`: Future scRNA prohibitively expensive
- `provisional_refund_rate < 0.2`: Agent avoiding risk inappropriately

---

## Common Patterns

### Pattern 1: Imaging first, scRNA second
```python
# Step 1: Cheap imaging
controller.claim_action("img", "cell_painting", 0.4)
# ... run imaging
controller.resolve_action("img", realized_gain)

# Step 2: scRNA with marginal gain
controller.claim_action(
    "scrna",
    "scrna_seq",
    expected_gain_bits=0.6,  # Total
    prior_modalities=("cell_painting",),
    claimed_marginal_gain=0.3  # Marginal after imaging
)
```

### Pattern 2: Replicate when drift is high
```python
if drift_score > 0.7:
    # Don't use scRNA (time cost increases drift)
    # Use cheap replicates instead
    for rep in range(3):
        run_imaging(replicate=rep)
```

### Pattern 3: Provisional penalty for risky exploration
```python
if exploring_new_mechanism:
    penalty = controller.compute_penalty()
    controller.add_provisional_penalty(
        action_id,
        penalty.entropy_penalty,
        settlement_horizon=3
    )
    # Will be refunded if entropy collapses in 3 steps
```

---

## Troubleshooting

### "My agent never uses scRNA"
- Check: Is debt too high? (cost_multiplier > 1.3)
- Check: Is agent overclaiming consistently?
- Fix: Improve gain estimation, or reset debt

### "My agent spams scRNA"
- Check: Are penalties disabled?
- Check: Is marginal gain being claimed?
- Fix: Enable penalties, require marginal gain accounting

### "Debt keeps growing"
- Check: mean_overclaim > 0.3
- Root cause: Agent's gain estimator is miscalibrated
- Fix: Recalibrate estimator, or increase debt decay rate

### "Provisional penalties never refund"
- Check: Is entropy actually collapsing after widening?
- Root cause: Actions that widen aren't productive
- Fix: Tighten heuristic for when to use provisional

---

## Migration from Existing Code

### If you have no epistemic control:
1. Add `EpistemicController` to your planner (Step 1)
2. Wrap expensive actions with claim/resolve (Steps 2-3)
3. Start with penalties disabled to baseline behavior
4. Enable penalties gradually (first entropy, then debt)

### If you have simple penalties:
1. Replace with `EpistemicController`
2. Add `entropy_source` to distinguish exploration
3. Add marginal gain accounting if you use multiple modalities
4. Consider provisional penalties for multi-step experiments

### If you have custom debt tracking:
1. Migrate to `EpistemicDebtLedger` format
2. Use `controller.load()` to import history
3. Ensure asymmetry (overclaim hurts, underclaim doesn't help)
4. Add cost inflation if not already present

---

## FAQ

**Q: Do I need to use all three improvements (source, marginal, provisional)?**
A: No. Start with entropy source tracking (critical). Add marginal gain if you use multiple modalities. Add provisional only for advanced multi-step experiments.

**Q: How do I set baseline_entropy?**
A: Use your typical posterior entropy at experiment start, before any measurements. Often ~1.0-2.0 bits for 3-4 plausible mechanisms.

**Q: What if I don't have a mechanism posterior?**
A: You can still use the system with a proxy for uncertainty (e.g., prediction variance, ensemble disagreement). Just ensure it's comparable across time.

**Q: Should I use provisional penalties by default?**
A: No. Only use when you have a principled reason to expect temporary widening. Default to immediate penalties.

**Q: How do I calibrate the penalty weights?**
A: Start with defaults (entropy_penalty_weight=1.0). Increase if agent is too aggressive, decrease if too conservative. Tune against your reward scale.

---

## Summary

**Minimum viable integration** (Steps 1-4):
1. Initialize controller at experiment start
2. Claim before expensive action
3. Measure and resolve after action
4. Apply penalty to reward

**With this**, you get:
- Cost inflation from debt (makes overclaiming expensive)
- Entropy penalties (makes widening hurt)
- Entropy source tracking (doesn't penalize exploration)

**Advanced features** (optional):
- Marginal gain accounting (prevents redundancy)
- Provisional penalties (enables productive uncertainty)
- Multi-step credit assignment

**Total integration time**: ~30 minutes for basics, ~1 hour for advanced.

The system is designed to be incrementally adoptable. Start simple, add features as needed.

---

## See Also

- **Full demo**: `scripts/demos/full_epistemic_system_demo.py`
- **Test coverage**: `tests/phase6a/test_epistemic_*.py`
- **Architecture**: `docs/EPISTEMIC_CONTROL_SYSTEM.md`
- **Improvements**: `docs/EPISTEMIC_IMPROVEMENTS_SHIPPED.md`
- **scRNA hardening**: `docs/SCRNA_SEQ_HARDENING.md`
