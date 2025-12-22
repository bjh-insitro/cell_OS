# Agent 2: Epistemic Contracts

**Mission**: Define contracts (invariants) for epistemic honesty.

These are NOT implementations. These are rules the system must satisfy to prevent lying to itself.

---

## Contract 3.1: Confidence Must Be Decreasable

### Invariant

**For any confidence claim C(t) at time t:**

1. **Contradictory evidence decreases confidence**
   - If observation O contradicts claim C, then C(t+1) < C(t)
   - Contradiction defined as: prediction error > 2σ

2. **Confidence decay over time**
   - If no supporting evidence for Δt > decay_threshold, then C(t+Δt) < C(t)
   - Prevents stale confidence from being treated as fresh knowledge

3. **Monotonic decrease under repeated failure**
   - If claim C fails validation N consecutive times, C(t+N) < C(t) * (1 - penalty)^N
   - Example: Expected gain consistently overestimated → expected gain estimate must decrease

### Current Violations

| Component | Violation | Evidence |
|-----------|-----------|----------|
| `estimate_expected_gain()` | ❌ No confidence decay | Heuristic rules never weaken based on past errors |
| `estimate_expected_gain()` | ❌ No contradiction penalty | Repeated overclaiming doesn't revise estimates |
| `nuisance_probability` | ⚠️ Partial decay | Only updates when nuisance model updates (rare) |
| `calibrated_confidence` | ✅ Decreasable (UNUSED) | Would change with retraining, but never called |

### Enforcement Mechanisms

#### Option A: Time-Based Decay

```python
# Pseudocode (not implementation)
class ConfidenceClaim:
    value: float
    created_at: float
    last_evidence_at: float
    decay_rate: float = 0.1  # 10% per time unit

    def get_current_value(self, current_time: float) -> float:
        time_since_evidence = current_time - self.last_evidence_at
        if time_since_evidence > STALE_THRESHOLD:
            decay = self.decay_rate * (time_since_evidence - STALE_THRESHOLD)
            return self.value * (1.0 - decay)
        return self.value
```

#### Option B: Contradiction-Based Penalty

```python
# Pseudocode (not implementation)
class ExpectedGainEstimator:
    historical_errors: List[Tuple[float, float]]  # (claimed, realized)

    def estimate_with_calibration(self, template: str) -> Tuple[float, float]:
        base_estimate = self._heuristic_estimate(template)

        # Compute historical bias
        if len(self.historical_errors) > 0:
            claimed = [c for c, _ in self.historical_errors]
            realized = [r for _, r in self.historical_errors]
            bias = mean(claimed) - mean(realized)

            # Penalize if systematically overconfident
            if bias > 0:
                calibrated_mean = base_estimate - bias
                calibrated_std = std(realized)  # Uncertainty from variance
                return (calibrated_mean, calibrated_std)

        return (base_estimate, None)  # No calibration data yet
```

#### Option C: Bayesian Confidence Update

```python
# Pseudocode (not implementation)
class BayesianConfidenceTracker:
    prior_correct: int = 1  # Beta distribution parameters
    prior_incorrect: int = 1

    def observe(self, claimed_confident: bool, was_correct: bool):
        if claimed_confident and was_correct:
            self.prior_correct += 1
        elif claimed_confident and not was_correct:
            self.prior_incorrect += 1

    def get_calibrated_confidence(self) -> float:
        # Beta distribution mean = α / (α + β)
        return self.prior_correct / (self.prior_correct + self.prior_incorrect)
```

### Acceptance Test

```python
def test_confidence_decreases_on_contradiction():
    estimator = ExpectedGainEstimator()

    # Initial estimate
    initial_gain, _ = estimator.estimate("baseline_replicates")

    # Claim and realize (3 consecutive overclaims)
    for i in range(3):
        estimator.claim(initial_gain)
        estimator.realize(initial_gain * 0.5)  # Realized only half

    # Estimate again
    updated_gain, _ = estimator.estimate("baseline_replicates")

    # Contract 3.1: Confidence MUST decrease after repeated failure
    assert updated_gain < initial_gain, \
        f"Expected gain must decrease after overclaiming: {initial_gain} → {updated_gain}"
```

---

## Contract 3.2: Ambiguity Must Be Representable

### Invariant

**The system must be able to say "I don't know" when:**

1. **Multiple explanations are near-equivalent**
   - If top-2 mechanism probabilities differ by < threshold (e.g., 0.15)
   - System must represent ambiguity explicitly

2. **Modalities disagree**
   - If morphology says mechanism A, but transcriptomics says mechanism B
   - System must not collapse to single answer

3. **Evidence supports multiple hypotheses**
   - If likelihood ratio < clear_threshold
   - System must express uncertainty

### Current Violations

| Component | Violation | Evidence |
|-----------|-----------|----------|
| `GovernanceInputs` | ❌ No ambiguity field | Cannot access `is_ambiguous` from Agent 2 posterior |
| `decide_governance()` | ❌ Ignores ambiguity | Can commit even if mechanisms are indistinguishable |
| `top_mechanism` property | ⚠️ Lossy collapse | argmax destroys margin information |

### Enforcement Mechanisms

#### Option A: Add Ambiguity to Governance Contract

```python
# Pseudocode (not implementation)
@dataclass(frozen=True)
class GovernanceInputs:
    posterior: Dict[str, float]
    nuisance_prob: float
    evidence_strength: float
    is_ambiguous: bool  # NEW: From Agent 2 posterior
    likelihood_gap: float  # NEW: Separation metric

def decide_governance(x: GovernanceInputs, t: GovernanceThresholds) -> GovernanceDecision:
    # Existing logic...

    # NEW: Block commit if ambiguous
    if x.is_ambiguous:
        return GovernanceDecision(
            action=GovernanceAction.NO_COMMIT,
            mechanism=None,
            reason=f"no_commit: ambiguous classification (gap={x.likelihood_gap:.3f})",
            blockers={Blocker.AMBIGUOUS_MECHANISMS}
        )

    # Existing commit logic...
```

#### Option B: Hysteresis for Commitment

```python
# Pseudocode (not implementation)
@dataclass
class GovernanceThresholds:
    commit_posterior_enter: float = 0.80  # Must reach 0.80 to commit
    commit_posterior_exit: float = 0.75   # Must drop below 0.75 to revoke

    # NEW: Gap threshold
    min_likelihood_gap: float = 0.15  # Mechanisms must be this separated

class StatefulGovernance:
    committed_mechanism: Optional[str] = None

    def decide(self, x: GovernanceInputs, t: GovernanceThresholds) -> GovernanceDecision:
        top_mech, top_p = _top_mechanism(x.posterior)

        # Check gap requirement
        if x.likelihood_gap < t.min_likelihood_gap:
            # Too ambiguous - cannot commit (or must revoke if already committed)
            if self.committed_mechanism is not None:
                self.committed_mechanism = None
            return GovernanceDecision(
                action=GovernanceAction.NO_COMMIT,
                mechanism=None,
                reason=f"ambiguous: gap={x.likelihood_gap:.3f} < {t.min_likelihood_gap}",
                blockers={Blocker.AMBIGUOUS_MECHANISMS}
            )

        # Hysteresis: different thresholds for entering vs exiting
        if self.committed_mechanism is None:
            # Not yet committed - use enter threshold
            if top_p >= t.commit_posterior_enter:
                self.committed_mechanism = top_mech
                return GovernanceDecision(action=GovernanceAction.COMMIT, ...)
        else:
            # Already committed - use exit threshold (lower)
            if top_p < t.commit_posterior_exit:
                self.committed_mechanism = None
                return GovernanceDecision(action=GovernanceAction.NO_COMMIT, ...)
            else:
                # Stay committed
                return GovernanceDecision(action=GovernanceAction.COMMIT, ...)

        return GovernanceDecision(action=GovernanceAction.NO_COMMIT, ...)
```

### Acceptance Test

```python
def test_ambiguous_classification_refuses_commit():
    """Test that ambiguous posteriors cannot commit."""

    # Create ambiguous posterior (mechanisms similar)
    posterior = {
        "er_stress": 0.42,
        "microtubule": 0.38,
        "mitochondrial": 0.15,
        "unknown": 0.05,
    }

    gov_inputs = GovernanceInputs(
        posterior=posterior,
        nuisance_prob=0.1,
        evidence_strength=0.8,
        is_ambiguous=True,  # Marked as ambiguous by Agent 2
        likelihood_gap=0.08,  # Gap < 0.15 threshold
    )

    decision = decide_governance(gov_inputs)

    # Contract 3.2: Ambiguous classification MUST NOT commit
    assert decision.action != GovernanceAction.COMMIT, \
        f"Ambiguous posterior (gap={gov_inputs.likelihood_gap:.3f}) " \
        f"must not commit, got {decision.action}"

    assert Blocker.AMBIGUOUS_MECHANISMS in decision.blockers, \
        f"Ambiguity blocker must be reported, got {decision.blockers}"
```

---

## Contract 3.3: Debt Must Be Repayable

### Invariant

**Epistemic debt must NEVER create permanent deadlock:**

1. **Calibration must always be affordable**
   - Even at maximum debt, agent can execute calibration
   - Calibration inflation is capped (Agent 3: 1.5× max)

2. **Debt repayment must be monotonic**
   - Calibration reduces debt (repayment > 0)
   - Successive calibrations decrease debt toward zero

3. **Deadlock must be explicitly detected**
   - If calibration becomes unaffordable, system flags `is_deadlocked=True`
   - Terminal abort with clear error message (not silent failure)

4. **Budget reserve for recovery**
   - Non-calibration actions must leave MIN_CALIBRATION_COST_WELLS available
   - Prevents epistemic bankruptcy

### Current Implementation (Agent 3)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Capped calibration inflation | ✅ ENFORCED | `get_inflated_cost(is_calibration=True)` caps at 1.5× |
| Monotonic repayment | ✅ ENFORCED | `compute_repayment()` always returns ≥ 0 |
| Explicit deadlock detection | ✅ ENFORCED | `should_refuse_action()` checks `is_deadlocked` |
| Budget reserve | ✅ ENFORCED | Non-calibration blocked if budget_after < MIN_CALIBRATION_COST_WELLS |

### Invariants to Assert

#### Invariant 3.3.1: Calibration Inflation Cap

```python
def invariant_calibration_inflation_capped(controller, max_debt=100.0):
    """Calibration inflation must be capped at 1.5× even with extreme debt."""

    # Set up controller with extreme debt
    for i in range(int(max_debt)):
        controller.claim_action(f"overclaim_{i}", "biology", 1.0)
        controller.resolve_action(f"overclaim_{i}", 0.0)

    debt = controller.get_total_debt()
    assert debt >= max_debt, f"Setup failed: debt={debt} < {max_debt}"

    # Check calibration inflation
    base_cost = 12.0
    inflated_cost = controller.get_inflated_cost(
        base_cost=base_cost,
        is_calibration=True
    )

    multiplier = inflated_cost / base_cost

    # CONTRACT 3.3: Calibration inflation MUST be capped
    assert multiplier <= 1.5, \
        f"Calibration inflation exceeds 1.5× cap: {multiplier:.2f}× (debt={debt:.1f})"

    return True
```

#### Invariant 3.3.2: Debt Decreases Monotonically

```python
def invariant_debt_decreases_with_calibration(controller):
    """Debt must strictly decrease after calibration."""

    # Accumulate debt
    for i in range(5):
        controller.claim_action(f"overclaim_{i}", "biology", 1.0)
        controller.resolve_action(f"overclaim_{i}", 0.0)

    debt_before = controller.get_total_debt()

    # Execute calibration
    repayment = controller.compute_repayment(
        action_id="calib",
        action_type="baseline_replicates",
        is_calibration=True,
        noise_improvement=0.1
    )

    debt_after = controller.get_total_debt()

    # CONTRACT 3.3: Debt MUST decrease after calibration
    assert repayment > 0, f"Calibration must earn repayment, got {repayment}"
    assert debt_after < debt_before, \
        f"Debt must decrease: {debt_before:.3f} → {debt_after:.3f}"

    return True
```

#### Invariant 3.3.3: Deadlock Detection is Explicit

```python
def invariant_deadlock_explicitly_detected(controller):
    """When deadlock occurs, is_deadlocked flag must be True."""

    # Create deadlock condition: high debt + low budget
    for i in range(10):
        controller.claim_action(f"overclaim_{i}", "biology", 1.0)
        controller.resolve_action(f"overclaim_{i}", 0.0)

    debt = controller.get_total_debt()
    budget = 10  # Insufficient for calibration (needs ~18 with inflation)

    should_refuse, refusal_reason, context = controller.should_refuse_action(
        template_name="dose_response",
        base_cost_wells=20,
        budget_remaining=budget,
        debt_hard_threshold=2.0
    )

    # If calibration is unaffordable, deadlock MUST be detected
    min_calib_cost = controller.get_inflated_cost(
        base_cost=MIN_CALIBRATION_COST_WELLS,
        is_calibration=True
    )

    if min_calib_cost > budget and debt > 2.0:
        # This is a deadlock condition
        # CONTRACT 3.3: Deadlock MUST be explicitly flagged
        assert context.get('is_deadlocked', False), \
            f"Deadlock condition exists but not detected: " \
            f"debt={debt:.1f}, budget={budget}, calib_cost={min_calib_cost:.0f}"

        assert refusal_reason == "epistemic_deadlock_detected", \
            f"Deadlock must have specific refusal reason, got '{refusal_reason}'"

    return True
```

### Agent 3 Verification

All invariants are currently ENFORCED by Agent 3's implementation:
- ✅ Calibration inflation capped at 1.5×
- ✅ Debt decreases with calibration repayment
- ✅ Deadlock explicitly detected when it occurs
- ✅ Budget reserve prevents epistemic bankruptcy

**Contract 3.3 is satisfied by existing implementation.**

---

## Summary: Which Contracts Need Work?

| Contract | Status | Priority | Intervention Needed |
|----------|--------|----------|---------------------|
| 3.1: Confidence Must Be Decreasable | ❌ VIOLATED | **HIGH** | Add contradiction penalty, time decay |
| 3.2: Ambiguity Must Be Representable | ❌ VIOLATED | **HIGH** | Integrate ambiguity into governance |
| 3.3: Debt Must Be Repayable | ✅ SATISFIED | N/A | Verify with tests (already done) |

---

## Phase 4 Recommendation

Choose **≤2 minimal interventions** (≤300 LOC):

**Option A: Ambiguity-Aware Governance** (Priority 1, ~100 LOC)
- Add `is_ambiguous` and `likelihood_gap` to GovernanceInputs
- Block COMMIT if ambiguous (gap < 0.15)
- Add `Blocker.AMBIGUOUS_MECHANISMS`
- Add hysteresis to commit decision (enter=0.80, exit=0.75)

**Option C: Confidence Decay for Expected Gain** (Priority 2, ~150 LOC)
- Add historical error tracking to BeliefState
- Calibrate expected gain estimates based on past (claimed, realized) pairs
- Penalize systematic overclaiming
- Return (mean, std) instead of scalar

Total: ~250 LOC (within 300 LOC budget)

**Do NOT implement Option B (Debt Repayment)** - Agent 3 already completed this.
