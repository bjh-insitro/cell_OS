# Epistemic System Improvements: Tier 1 Complete

**Date**: 2025-12-20
**Status**: SHIPPED

## What Was Improved

Three critical loopholes were closed to prevent gaming and enable proper credit assignment:

### 1. Entropy Source Tracking
**Problem**: System couldn't distinguish exploration uncertainty (good) from measurement-induced confusion (bad).

**Solution**: Added `EntropySource` enum to track where uncertainty comes from:
- `PRIOR`: Haven't measured yet (exploration - NOT penalized)
- `MEASUREMENT_NARROWING`: Measurement reduced entropy (good)
- `MEASUREMENT_AMBIGUOUS`: Measurement gave ambiguous signal (penalized)
- `MEASUREMENT_CONTRADICTORY`: Measurement contradicted prior (heavily penalized)

**Result**: Agents can now explore appropriately without being punished for not having measured yet.

```python
# Before: all high entropy was penalized
penalty = compute_penalty(prior=2.0, post=2.0)  # Penalized even if exploration

# After: only measurement-induced confusion is penalized
penalty = compute_penalty(
    prior=2.0,
    post=2.0,
    entropy_source=EntropySource.PRIOR  # NOT penalized
)
```

---

### 2. Marginal Information Gain
**Problem**: Agents could spam redundant assays without accounting for overlap with previous measurements.

**Solution**: Claims now support `prior_modalities` and `claimed_marginal_gain`:

```python
# Imaging measured first
controller.claim_action("imaging_001", "cell_painting", expected_gain_bits=0.8)
controller.resolve_action("imaging_001", 0.8)

# scRNA must account for overlap
controller.claim_action(
    "scrna_001",
    "scrna_seq",
    expected_gain_bits=0.5,  # Total if alone
    prior_modalities=("cell_painting",),
    claimed_marginal_gain=0.2,  # After accounting for imaging
)
```

**Result**: Agents must think about *redundancy* when justifying expensive assays.

---

### 3. Provisional Penalties (Multi-Step Credit Assignment)
**Problem**: Some experiments widen entropy temporarily but enable decisive follow-ups. Immediate penalty makes these look like failures.

**Solution**: `ProvisionalPenaltyTracker` allows delayed settlement:

```python
# scRNA widens entropy (reveals subpopulations)
penalty = controller.compute_penalty()  # 0.5 bits

# Make it provisional
controller.add_provisional_penalty(
    action_id="scrna_001",
    penalty_amount=penalty.entropy_penalty,
    settlement_horizon=3  # Re-evaluate after 3 steps
)

# 3 steps later: if entropy collapsed, refund penalty
controller.step_provisional_penalties()
# Else: finalize penalty
```

**Result**: Productive uncertainty is distinguishable from self-harm.

---

## Implementation Details

### Files Modified

**epistemic_penalty.py** (~80 lines changed)
- Added `EntropySource` enum
- Modified `compute_entropy_penalty()` to respect source
- Contradiction penalties 1.5× higher than ambiguity
- Prior uncertainty never penalized

**epistemic_debt.py** (~30 lines changed)
- Added `prior_modalities` and `claimed_marginal_gain` to `EpistemicClaim`
- Logging now shows marginal vs total gain

**epistemic_control.py** (~50 lines changed)
- Added `entropy_source` parameter throughout
- Integrated `ProvisionalPenaltyTracker`
- Auto-infers source from gain if not provided
- Added `step_provisional_penalties()` method

**epistemic_provisional.py** (NEW, ~200 lines)
- Complete provisional penalty system
- Tracks penalties with settlement horizons
- Auto-settles based on entropy trajectory
- Manual refund/finalize if needed

---

## Test Coverage

### New Tests (`test_epistemic_improvements.py`)
- ✓ Entropy source distinguishes exploration vs confusion
- ✓ Prior uncertainty is not penalized
- ✓ Measurement-induced confusion is penalized (1.5× for contradiction)
- ✓ Marginal info gain tracking prevents redundancy claims
- ✓ Provisional penalties enable productive uncertainty
- ✓ Provisional penalties finalize if entropy stays high
- ✓ Full integrated workflow (imaging → scRNA → follow-up)

### Backward Compatibility
- ✓ All original tests pass (`test_epistemic_control.py`)
- ✓ Existing code works without changes (source auto-inferred)
- ✓ Save/load preserves all state

---

## Usage Examples

### Basic: Entropy source tracking
```python
controller = EpistemicController()

# Before first measurement (exploration - no penalty)
controller.measure_information_gain(
    prior_entropy=2.5,  # High (haven't measured)
    posterior_entropy=2.5,
    entropy_source=EntropySource.PRIOR
)
penalty = controller.compute_penalty()
assert penalty.entropy_penalty == 0.0  # No penalty for exploration

# After measurement worsens things (penalty)
controller.measure_information_gain(
    prior_entropy=1.0,  # Low (was confident)
    posterior_entropy=2.0,  # High (now confused!)
    entropy_source=EntropySource.MEASUREMENT_CONTRADICTORY
)
penalty = controller.compute_penalty()
assert penalty.entropy_penalty > 0.5  # Penalized
```

### Intermediate: Marginal gain
```python
# First measurement
controller.claim_action("img", "cell_painting", 0.8)
controller.resolve_action("img", 0.8)

# Second measurement must account for first
controller.claim_action(
    "rna",
    "scrna_seq",
    expected_gain_bits=0.5,  # Total gain
    prior_modalities=("cell_painting",),
    claimed_marginal_gain=0.2,  # Marginal after imaging
)
# Debt computed on claimed=0.5 vs realized
# But logged as "marginal: 0.2 after imaging"
```

### Advanced: Provisional penalties
```python
# Measurement widens entropy
penalty = controller.compute_penalty()

# If you think widening will be productive, make it provisional
if might_be_productive:
    controller.add_provisional_penalty(
        action_id="scrna_001",
        penalty_amount=penalty.entropy_penalty,
        settlement_horizon=3  # Wait 3 steps
    )
    # Penalty held in escrow, not applied yet

# Each step, advance provisional tracker
for step in range(3):
    # ... do work
    controller.posterior_entropy = new_entropy
    finalized = controller.step_provisional_penalties()
    # If entropy collapsed: penalty refunded
    # If entropy stayed high: penalty finalized
```

---

## Key Behavioral Changes

### What's Now Possible

1. **Exploration without penalty**
   - High prior entropy (haven't measured) → no penalty
   - Enables curious exploration before committing to expensive assays

2. **Honest redundancy accounting**
   - Must declare prior modalities when claiming gain
   - Forces agents to think about marginal contribution

3. **Delayed judgment**
   - Temporary entropy increase can be forgiven if later resolved
   - Enables multi-step strategies where initial confusion is productive

### What's Still Enforced

1. **Overclaiming accumulates debt** (unchanged)
2. **Cost inflation from debt** (unchanged)
3. **Measurement-induced confusion penalized** (strengthened with source tracking)
4. **Horizon shrinkage from high entropy** (unchanged)

---

## Failure Modes Closed

| Failure Mode | Before | After |
|--------------|--------|-------|
| **Exploration penalty** | Penalized for not having measured | Only penalizes measurement-induced confusion |
| **Redundancy spam** | Could claim scRNA after imaging without accounting for overlap | Must declare marginal gain vs total gain |
| **Productive uncertainty** | All widening penalized immediately | Can be provisional if leads to resolution |

---

## Integration Checklist

### Already working ✓
- [x] Entropy source auto-inferred from gain if not provided
- [x] Backward compatible (existing code works)
- [x] All original tests pass
- [x] New tests demonstrate all three improvements
- [x] Documentation complete

### Next steps
- [ ] Wire into planner: pass `entropy_source` explicitly based on prior beliefs
- [ ] Add heuristics for when to use provisional penalties
- [ ] Log provisional penalty refund rate (calibration metric)
- [ ] Add "marginal info gain quality" to auditing dashboard

---

## Statistics to Monitor

```python
stats = controller.get_statistics()

# Existing metrics
stats["total_debt"]  # Cumulative overclaim
stats["cost_multiplier"]  # Debt inflation factor

# New metrics
stats["provisional_total_escrowed"]  # Currently held in escrow
stats["provisional_total_refunded"]  # Successfully refunded (productive)
stats["provisional_total_finalized"]  # Finalized as penalties (not productive)
stats["provisional_refund_rate"]  # Fraction of provisional penalties refunded
```

**Good calibration**: `refund_rate` ~30-50%
- Too low: agent avoids risk, never uses provisional
- Too high: agent uses provisional to avoid all penalties (gaming)

---

## Philosophical Implications

### Entropy source tracking teaches:
**"Being uncertain before you measure is wise. Getting more uncertain after measuring is bad."**

This is how real science works: ignorance is acceptable, confusion after investigation is a sign something went wrong.

### Marginal gain teaches:
**"Information has context. Value depends on what you already know."**

Forces agents to think about the *shape* of their belief state and how new information fits.

### Provisional penalties teach:
**"Temporary uncertainty can be strategic. The key is whether it resolves."**

Enables risky but principled exploration. The system learns to distinguish investigation from thrashing.

---

## What This Unlocks

With these three improvements, the epistemic system can now handle:

1. **Curious agents**: Explore appropriately without penalty
2. **Strategic agents**: Plan multi-step investigations where initial confusion is acceptable
3. **Efficient agents**: Avoid redundant measurements by accounting for overlap

Before: agents optimized for "never be uncertain"
After: agents can optimize for "be uncertain when appropriate, resolve when possible"

That's a fundamentally different learning problem. And it's closer to real science.

---

## References

- **Base system**: `docs/EPISTEMIC_CONTROL_SYSTEM.md`
- **scRNA hardening**: `docs/SCRNA_SEQ_HARDENING.md`
- **Entropy penalty**: `src/cell_os/epistemic_agent/penalty.py`
- **Provisional penalties**: `src/cell_os/epistemic_provisional.py`
- **Test coverage**: `tests/phase6a/test_epistemic_improvements.py`

---

**Shipped**: 2025-12-20

The system now distinguishes **exploration from confusion**, **marginal from total information**, and **productive from destructive uncertainty**.

These are not incremental improvements. They're structural fixes that close loopholes agents would inevitably discover.
