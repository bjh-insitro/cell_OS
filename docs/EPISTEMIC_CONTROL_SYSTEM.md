# Epistemic Control System: Making Uncertainty Conservation Physical

**Date**: 2025-12-20
**Status**: SHIPPED

## Philosophy

Uncertainty is conserved unless you earn the reduction. This is not a suggestion—it's a **conservation law** enforced by code, like mass conservation in death accounting.

The epistemic control system makes three things true:

1. **Epistemic debt accumulates** when agents overclaim information gain
2. **Posterior widening is penalized** (unforced increases in uncertainty hurt)
3. **Costs inflate with debt** (bad calibration makes future actions expensive)

This creates pressure toward calibrated justifications without hardcoding thresholds.

---

## Core Components

### 1. Epistemic Debt (`epistemic_debt.py`)

Tracks the gap between claimed and realized information gain.

```python
from cell_os.epistemic_debt import EpistemicDebtLedger

ledger = EpistemicDebtLedger()

# Agent claims scRNA will provide 0.8 bits
ledger.claim("scrna_001", "scrna_seq", expected_gain_bits=0.8)

# scRNA actually provides 0.2 bits
ledger.realize("scrna_001", actual_gain_bits=0.2)

# Debt accumulates: 0.8 - 0.2 = 0.6 bits
print(f"Debt: {ledger.total_debt:.2f} bits")  # → 0.60 bits

# Future costs inflate
inflated_cost = ledger.get_inflated_cost(base_cost=200.0)
print(f"Cost: ${inflated_cost:.2f}")  # → $212.00 (6% inflation)
```

**Key property: Asymmetry**
- Overclaiming (claim > realize) accumulates debt
- Underclaiming (claim < realize) does NOT reduce debt
- This rewards conservative estimates

---

### 2. Epistemic Penalties (`epistemic_penalty.py`)

Makes posterior widening hurt in two ways:

#### Immediate penalty (subtract from reward)
```python
from cell_os.epistemic_penalty import compute_entropy_penalty, EpistemicPenaltyConfig

config = EpistemicPenaltyConfig(entropy_penalty_weight=1.0)

# Posterior widened by 0.5 bits
penalty = compute_entropy_penalty(
    prior_entropy=2.0,
    posterior_entropy=2.5,  # Widened!
    action_type="scrna_seq",
    config=config
)

print(f"Penalty: {penalty:.2f}")  # → 0.50 (subtract from reward)
```

#### Planning horizon shrinkage
```python
from cell_os.epistemic_penalty import compute_planning_horizon_shrinkage

# High uncertainty shrinks planning horizon
multiplier = compute_planning_horizon_shrinkage(
    current_entropy=4.0,  # High uncertainty
    baseline_entropy=2.0,
    config=config
)

print(f"Horizon multiplier: {multiplier:.2f}")  # → 0.60 (40% reduction)
```

**Why this matters**: High entropy should make the agent cautious and short-sighted. Low entropy permits longer-horizon planning.

---

### 3. Integrated Controller (`epistemic_control.py`)

High-level interface that coordinates debt + penalties:

```python
from cell_os.epistemic_control import EpistemicController

controller = EpistemicController()

# Set baseline for horizon shrinkage
controller.set_baseline_entropy(2.0)

# Before action: claim expected gain
controller.claim_action("scrna_001", "scrna_seq", expected_gain_bits=0.8)

# After action: measure realized gain
realized_gain = controller.measure_information_gain(
    prior_entropy=2.0,
    posterior_entropy=1.2,  # Narrowed by 0.8 bits
)

# Resolve claim
controller.resolve_action("scrna_001", realized_gain, "scrna_seq")

# Compute penalty (zero if narrowed, positive if widened)
penalty_result = controller.compute_penalty()
print(f"Entropy penalty: {penalty_result.entropy_penalty:.2f}")
print(f"Horizon multiplier: {penalty_result.horizon_multiplier:.2f}")

# Get cost for next action
inflated_cost = controller.get_inflated_cost(base_cost=200.0)
```

---

## Integration with scRNA-seq Hardening

The epistemic control system completes the scRNA hardening from `SCRNA_SEQ_HARDENING.md`:

| Layer | Mechanism | Effect |
|-------|-----------|--------|
| **Cost model** | Time = 4h, cost = $200 | Makes scRNA expensive |
| **Cell cycle confounder** | Cycling suppresses stress markers | Makes scRNA misleading |
| **Justification gating** | Requires failed cheaper assays | Makes scRNA earned |
| **Epistemic debt** | Overclaiming accumulates | Makes poor justification expensive |
| **Entropy penalty** | Widening hurts reward | Makes disagreement painful |

Together, these force the agent to:
- Try cheaper assays first
- Justify info gain honestly
- Pay for overclaiming
- Suffer when scRNA widens posterior

---

## Example: Agent That Overpromises Gets Punished

```python
controller = EpistemicController()
base_cost = 200.0

# Episode 1: Agent claims 0.8 bits, gets 0.2 bits
controller.claim_action("ep1", "scrna_seq", 0.8)
controller.resolve_action("ep1", 0.2)
# Debt = 0.6 bits

cost_ep2 = controller.get_inflated_cost(base_cost)
print(f"Episode 2 cost: ${cost_ep2:.2f}")  # → $212.00 (6% inflation)

# Episode 2: Agent claims 0.7 bits, gets 0.1 bits
controller.claim_action("ep2", "scrna_seq", 0.7)
controller.resolve_action("ep2", 0.1)
# Debt = 1.2 bits (0.6 + 0.6)

cost_ep3 = controller.get_inflated_cost(base_cost)
print(f"Episode 3 cost: ${cost_ep3:.2f}")  # → $224.00 (12% inflation)

# Episode 3: Agent claims 0.5 bits, gets -0.2 bits (WIDENED!)
controller.claim_action("ep3", "scrna_seq", 0.5)
controller.resolve_action("ep3", -0.2, "scrna_seq")
# Debt = 1.9 bits (1.2 + 0.7)

# Entropy penalty for widening
penalty = controller.compute_penalty()
print(f"Widening penalty: {penalty.entropy_penalty:.2f}")  # → 0.20

final_cost = controller.get_inflated_cost(base_cost)
print(f"Final cost: ${final_cost:.2f}")  # → $238.00 (19% inflation)
```

**Result**: Agent that consistently overpromises faces escalating costs and penalties.

---

## Integration Checklist

### Already implemented ✓
- [x] Epistemic debt ledger with asymmetric accumulation
- [x] Entropy penalty computation
- [x] Planning horizon shrinkage
- [x] Integrated controller
- [x] Test coverage (8 tests, all passing)
- [x] Save/load persistence

### Next integration steps
- [ ] Wire controller into `BiologicalVirtualMachine.scrna_seq_assay`
- [ ] Pass `prior_entropy` and `posterior_entropy` from mechanism posterior
- [ ] Apply cost inflation to scRNA requests
- [ ] Apply entropy penalty to reward function
- [ ] Add epistemic debt to run statistics/logging
- [ ] Create adversarial stress tests (agents that game the system)

---

## Usage Pattern for Planners

### Step 1: Initialize at experiment start
```python
epistemic = EpistemicController()
epistemic.set_baseline_entropy(initial_posterior.entropy)
```

### Step 2: Before expensive action
```python
# Estimate expected info gain
expected_gain = estimate_info_gain(
    current_uncertainty=belief.entropy,
    mechanism_ambiguity=count_plausible_mechanisms(belief),
    viability=vessel.viability
)

# Claim
epistemic.claim_action(
    action_id=f"scrna_{step}",
    action_type="scrna_seq",
    expected_gain_bits=expected_gain
)

# Check inflated cost
cost = epistemic.get_inflated_cost(base_cost=200.0)
```

### Step 3: After action
```python
# Measure realized gain
realized_gain = epistemic.measure_information_gain(
    prior_entropy=belief_before.entropy,
    posterior_entropy=belief_after.entropy
)

# Resolve claim
epistemic.resolve_action(action_id, realized_gain, "scrna_seq")

# Apply penalty
penalty = epistemic.compute_penalty()
reward -= penalty.entropy_penalty

# Shrink horizon if uncertain
if penalty.horizon_multiplier < 0.8:
    planning_horizon *= penalty.horizon_multiplier
```

---

## Test Results

All tests pass (`tests/phase6a/test_epistemic_control.py`):

```
✓ Information gain computation works
✓ Epistemic debt accumulates: 1.100 bits
✓ Underclaiming does not accumulate debt (asymmetry works)
✓ Cost inflation from debt: 3.0 bits → 1.30× multiplier
✓ Entropy penalty works: widening hurts, narrowing doesn't
✓ Horizon shrinkage: 2× entropy → 0.60× horizon
✓ Integration with MechanismPosterior works
✓ Full workflow demonstrates epistemic control
✓ Save/load preserves epistemic debt
```

### Key empirical results:
- Overclaiming accumulates debt (0.6 bits for claiming 0.8, getting 0.2)
- Debt inflates costs (1.9 bits debt → 19% cost increase)
- Widening is penalized (0.5 bit widening → 0.5 penalty)
- High entropy shrinks horizon (4.0 vs 2.0 baseline → 0.6× multiplier)

---

## Design Decisions

### Why asymmetric debt (overclaim hurts, underclaim doesn't help)?

- Encourages conservative estimates
- Punishes overconfidence more than underconfidence
- Matches how real science works: false promises damage credibility

### Why entropy penalty weight = 1.0 by default?

- 1 bit of widening → 1 unit of reward penalty
- Calibrate to your reward scale
- Higher weight = more caution, lower weight = more exploration

### Why 10% cost inflation per bit of debt?

- Makes debt meaningful but not catastrophic
- 2 bits debt → 20% cost increase
- Enough to change strategy, not enough to make scRNA impossible

### Why only penalize agent-caused widening?

- World drift and batch effects are not agent's fault
- Only penalize widening from expensive, confounded assays
- Prevents unfair punishment for stochastic environment

---

## Philosophy Summary

This system enforces three conservation laws:

1. **Mass conservation**: cells don't appear (death accounting)
2. **Time conservation**: observation takes time (injection B)
3. **Uncertainty conservation**: data doesn't sharpen belief without cost (this)

Together, these define a **contract** about allowed operations. The agent cannot:
- Launder death into growth
- Launder time into simultaneity
- Launder confusion into confidence

When something breaks, it breaks **loudly** by violating a conservation law.

---

## References

- **scRNA hardening**: `docs/SCRNA_SEQ_HARDENING.md`
- **Assay governance**: `src/cell_os/hardware/assay_governance.py`
- **Mechanism posterior**: `src/cell_os/hardware/mechanism_posterior_v2.py`
- **Test coverage**: `tests/phase6a/test_epistemic_control.py`

---

**Shipped**: 2025-12-20

The system now knows that **more data can make you stupider** if you don't respect it. That lesson transfers to every future modality.
