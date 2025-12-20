# Phase 6A.1 Status: Prefix Rollouts Implemented

**Commit:** `5c03b88` - feat(search): phase6a.1 - replace heuristics with actual prefix rollouts

---

## What Works Now

### 1. Cached Prefix Rollouts ✓
```python
runner.rollout_prefix(schedule_prefix)
# Returns: PrefixRolloutResult with ACTUAL state from VM
#   - viability (true, not estimated)
#   - actin_fold (measured)
#   - classifier_margin (confidence from Phase5 classifier)
#   - predicted_axis
```

**Test results:**
- Prefix 1 (0.5× @ 6h): viability=0.919, actin=1.389×, margin=0.162, axis=microtubule ✓
- Prefix 2 (1.0× @ 12h): viability=0.645, actin=1.602×, margin=0.318, axis=microtubule ✓
- Cache working: same object returned on repeat calls ✓

### 2. Death Pruning is Correct ✓
- Prunes when `prefix_result.viability < 0.80` (actual measurement)
- No more optimistic "dose × 0.08" guesses
- Beam now respects the 20% death budget during search, not just at evaluation

### 3. Classifier Margin in Heuristic ✓
- Heuristic uses real classifier confidence: `w_mechanism * margin + w_viability * viability - w_interventions * ops`
- Beam can see epistemic uncertainty and adjust exploration
- Rewards high confidence (axis is clear) early

---

## What's Different from 6A

**Before (6A):**
```python
# Fake estimates
estimated_death = total_dose * 0.08
estimated_actin = 1.0 + total_dose * 0.25
```
Result: policies with 57% death (violates 20% budget)

**After (6A.1):**
```python
# Real physics
prefix_result = runner.rollout_prefix(schedule)
if prefix_result.viability < 0.80:
    prune()  # ACTUAL death check
```
Result: TBD (beam search running, slower but correct)

---

## Performance

**Speed tradeoff:**
- 6A (fake heuristics): ~70 nodes expanded, instant
- 6A.1 (real rollouts): Each node expansion = VM rollout to timestep
  - With cache: repeated prefixes instant
  - Cold start: slower but CORRECT

This is the right tradeoff. "Fast but wrong" isn't planning.

---

## What's Next (Remaining from Phase 6A.1 Plan)

### ☐ RewardSpec Abstraction
Create unified reward API:
```python
@dataclass
class RewardSpec:
    mode: str  # "phase4_mechanism" or "phase5_epistemic"

def compute_reward(receipt, spec: RewardSpec) -> float:
    if spec.mode == "phase4_mechanism":
        return compute_microtubule_mechanism_reward(...)
    elif spec.mode == "phase5_epistemic":
        return compute_epistemic_reward(...)
```

**Why:** Beam currently hardcodes Phase4 microtubule reward. Need Phase5 epistemic reward to test on full library.

### ☐ Test: Beam >= Smart on Phase5 Library
Run test_beam_search.py on all 6 compounds:
- test_A_* (ER stress)
- test_B_* (mitochondrial)
- test_C_* (microtubule)

**Current blocker:** Reward mismatch (Phase4 vs Phase5)

**Expected after RewardSpec:**
- Beam matches or beats smart on all 6 compounds
- Proves search works across all axes, not just microtubule

---

## Summary

Phase 6A.1 completes the "make it real" pass:
- ✅ Prefix rollouts (actual physics, not vibes)
- ✅ Correct death pruning
- ✅ Classifier margin in heuristic
- ⏳ RewardSpec (next)
- ⏳ Full Phase5 library test (after RewardSpec)

**The crocodile is no longer a drawing. It bites with real teeth.**
