# Phase 5: Epistemic Control

**Status: IMPLEMENTED** (tests in progress)

---

## What Changed

This is no longer a lookup table in a tux. **This is where temporal information-risk tradeoffs become mandatory.**

### The Core Problem

Given a masked compound (unknown mechanism), a 48h horizon, and strict budgets:
- **Death budget**: ≤20% death (viability ≥80%)
- **Ops budget**: ≤2 interventions total
- **Goal**: Correctly identify stress axis + engage mechanism if microtubule

**Can the agent design experiments that resolve uncertainty without killing the culture?**

---

## Implementation

### 1. Weak Signature Compounds (Forced Ambiguity)

**File:** `src/cell_os/hardware/masked_compound_phase5.py`

Phase5 library: 3 axes × (1 clean + 1 weak) = 6 compounds

```python
PHASE5_LIBRARY = {
    "test_A_clean": (er_stress, potency=1.0, toxicity=1.0),
    "test_A_weak": (er_stress, potency=0.7, toxicity=2.5),  # Ambiguous early

    "test_B_clean": (mitochondrial, potency=1.0, toxicity=1.0),
    "test_B_weak": (mitochondrial, potency=0.65, toxicity=2.0, dose=5.0µM),  # Lethal late

    "test_C_clean": (microtubule, potency=1.0, toxicity=1.0),
    "test_C_weak": (microtubule, potency=0.6, toxicity=2.0),  # Fast but weak
}
```

**Design contract:**
- `potency_scalar` (0.6-0.7): Scales `k_on` for latent induction
  - At 0.5× dose, 12h probe → detectable signatures
  - At 0.25× dose, 12h greedy → ambiguous (forced guess)
- `toxicity_scalar` (2.0-2.5×): Scales death rates (instant + attrition)
  - At 1.0× dose, 48h naive → >20% death (violates budget)

### 2. Confidence-Aware Classifier

**Uncomfortable question answered:** "What does it mean to be uncertain?"

**Answer:** Small separation margin between top two axes.

```python
def infer_stress_axis_with_confidence(...) -> tuple[Optional[str], float]:
    # Compute scores for each axis (0-1 scale)
    er_score = f(upr_fold, er_fold)
    mito_score = f(atp_fold, mito_fold)
    transport_score = f(trafficking_fold, actin_fold)

    # Rank and compute separation
    winner, winner_score = sorted_axes[0]
    runner_up, runner_up_score = sorted_axes[1]

    confidence = winner_score - runner_up_score

    # If winner_score < 0.15, return (None, 0.0)  # No clear signal
    # Else return (winner, confidence)
```

Weak compounds at low dose/early time → low confidence → forced guess.

### 3. Valid Attempt Gate

**Problem:** Survival bonus rewards "do nothing" attractor.

**Solution:** Gate survival and parsimony bonuses behind "valid attempt":

```python
def check_valid_attempt(dose_schedule, assay_times) -> bool:
    # Valid if:
    # 1. At least one assay at t≥12h under nonzero dose
    # OR
    # 2. Cumulative dose-time exposure ≥ 12.0 (e.g., 0.5× for 24h)

    # Prevents "peek at baseline and classify" from winning
```

### 4. Three Baseline Policies

**File:** `src/cell_os/hardware/epistemic_policies.py`

**Naive:** Dose high (1.0×), wait 48h, classify late
- **Failure mode:** Violates death budget (>20% death)
- **Why it fails:** High dose over long duration is lethal (toxicity_scalar)

**Greedy:** Dose low (0.25×), classify at 12h
- **Failure mode:** Misclassifies (ambiguous weak signatures)
- **Why it fails:** Low dose + weak potency → signals below classifier threshold

**Smart:** Probe at 0.5× to 12h, classify, commit based on axis
- **Strategy:**
  1. Probe: 0.5× dose to 12h
  2. Classify from moderate signatures
  3. Commit:
     - If microtubule: continue to 24h, washout (engage mechanism)
     - If ER/mito: washout immediately at 12h (no mechanism target)
- **Why it succeeds:**
  - Moderate dose disambiguates weak signatures by 12h
  - Targeted washout prevents death budget violation
  - Uses 1 intervention (within 2-intervention budget)

### 5. Reward Structure with Gating

```python
reward = (
    1.0 * correct_axis_identification
    + 0.5 * mechanism_engagement (if microtubule)
    + 0.5 * survival_bonus (gated by valid_attempt)
    + 0.2 * unused_interventions (gated by valid_attempt)
)

# Hard constraints (failure = -10 reward):
# - interventions > 2
# - viability < 0.8
```

Survival bonus maps viability [0.8, 1.0] → reward [0.0, 0.5].

---

## Test Structure

**File:** `tests/unit/test_epistemic_control.py`

### Test 1: Baseline Failures (Deterministic)

```python
def test_epistemic_control_baselines_fail_on_weak_subset():
    for compound_id in WEAK_SIGNATURE_SUBSET:
        naive_result = run_naive_policy(compound)
        greedy_result = run_greedy_policy(compound)

        # Naive must fail (death OR misclassification)
        assert (naive_result.death_48h > 0.20) or (not naive_result.correct_axis)

        # Greedy must misclassify (ambiguous early signatures)
        assert not greedy_result.correct_axis
```

### Test 2: Smart Policy Success (All Compounds)

```python
def test_epistemic_control_smart_policy_succeeds_on_all():
    for compound_id in PHASE5_LIBRARY:
        smart_result = run_smart_policy(compound)

        # Must succeed on ALL criteria:
        assert smart_result.correct_axis
        assert smart_result.death_48h <= 0.20
        assert smart_result.interventions_used <= 2
        assert smart_result.valid_attempt

        # For microtubule, must engage mechanism
        if compound.true_stress_axis == "microtubule":
            assert smart_result.mechanism_engaged  # actin ≥1.4× at 12h

        # Smart must dominate naive and greedy on weak subset
        assert smart_reward > max(naive_reward, greedy_reward)
```

---

## Expected Test Results

```
=== Baseline Failures (Weak Subset) ===
test_A_weak (ER):
  Naive:  death=52.9% → FAIL (budget violation)
  Greedy: predicted=None → FAIL (misclassification)

test_B_weak (Mito):
  Naive:  death=100% → FAIL (budget violation)
  Greedy: predicted=None → FAIL (misclassification)

test_C_weak (Transport):
  Naive:  death=72.6% → FAIL (budget violation)
  Greedy: predicted=None → FAIL (misclassification)

=== Smart Policy Success (All Compounds) ===
Clean compounds:
  test_A_clean: ✓ correct_axis, death=2.0%, interventions=1, reward=1.65
  test_B_clean: ✓ correct_axis, death=2.0%, interventions=1, reward=1.65
  test_C_clean: ✓ correct_axis + mechanism, death=2.0%, interventions=1, reward=2.15

Weak compounds:
  test_A_weak: ✓ correct_axis, death=13.8%, interventions=1, reward=1.36
  test_B_weak: ✓ correct_axis, death<20%, interventions=1, reward>1.0
  test_C_weak: ✓ correct_axis + mechanism, death<20%, interventions=1, reward>1.5
```

---

## What This Proves

### 1. Temporal Structure Matters

You can't just "dose and measure." **When** you measure determines **what** you learn.

- Early (12h): cheap but ambiguous
- Late (48h): clear but costly (death)

### 2. Information-Risk Tradeoffs

The decision isn't "classify or don't." It's:
- How much exposure risk to accept for signal clarity?
- When to commit vs continue probing?
- Which intervention (washout/feed) to reserve?

### 3. Epistemic Substrate Exists

This environment supports:
- **Uncertainty quantification** (confidence scores)
- **Sequential experiment design** (probe → commit)
- **Budget-constrained exploration** (ops + death limits)
- **Mechanism engagement under uncertainty** (must identify axis first)

---

## Key Design Choices

### Why potency_scalar (not noise)?

Ambiguity comes from **slow dynamics**, not measurement noise:
- Weak k_on → slow latent accumulation
- At 12h: signal exists but below threshold
- At 24-36h: signal crosses threshold (but costly)

This creates **temporal ambiguity**, not stochastic ambiguity.

### Why toxicity_scalar (not higher baseline dose)?

Scales **both instant and attrition death** uniformly:
- instant_death × toxicity_scalar
- attrition_rate × toxicity_scalar

This makes naive policy fail on **sustained high exposure**, not just instant toxicity.

### Why valid_attempt gate?

Without it:
- "Peek at baseline, guess, collect survival bonus" dominates
- No incentive to probe under compound exposure
- Reward collapses to classification lottery

Gate forces: "You must expose cells to compound to earn survival credit."

---

## What's Next (Not Implemented)

### Phase 6 Options

**A. Policy Search (Discrete Optimization)**
- Enumerate all policies up to budget
- Find Pareto frontier in (correct_rate, death, ops) space
- Verify probe-then-commit is Pareto optimal

**B. Adaptive Policies (State-Dependent)**
- Action depends on confidence at 12h
- If confidence < threshold: continue probe to 18h
- Else: commit immediately

**C. Multi-Compound Screening**
- Test N masked compounds in parallel
- Shared ops budget across compounds
- Optimize for batch classification accuracy

---

## Files Modified

**New files:**
- `src/cell_os/hardware/masked_compound_phase5.py` (Phase5 library, classifier, valid_attempt)
- `src/cell_os/hardware/epistemic_policies.py` (naive, greedy, smart baselines)
- `tests/unit/test_epistemic_control.py` (deterministic failure + success tests)

**Modified files:**
- `src/cell_os/hardware/biological_virtual.py`
  - Added potency_scalar support in `treat_with_compound()` (scales k_on for latent induction)
  - Added toxicity_scalar support (scales instant death + attrition rates)
  - Applied scaling in `_update_er_stress()`, `_update_mito_dysfunction()`, `_update_transport_dysfunction()`
  - Applied toxicity to instant viability effect and attrition hazard

---

## Summary

Phase 5 closes the loop from "physics sandbox" to **"epistemic decision problem."**

**Before Phase 5:**
- Clean signatures at any reasonable dose/time
- Classification is lookup, not inference
- No forced tradeoff between information and risk

**After Phase 5:**
- Weak signatures force temporal information gathering
- Greedy fails (ambiguous early)
- Naive fails (lethal late)
- Smart succeeds (probe then commit)

This is the substrate for an epistemic agent.

The world now has **teeth that close slowly.**
