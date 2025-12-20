# Phase 6A: Beam Search (Proof-of-Concept)

**Status: PROOF-OF-CONCEPT** (works in principle, needs iteration)

---

## What Works

Beam search over action sequences with:
- Beam width 10, horizon 8 steps (48h @ 6h)
- Action space: dose levels {0, 0.25, 0.5, 1.0}, washout, feed
- Pruning by intervention budget (≤2) and death estimates
- Heuristic scoring for beam ordering
- Terminal evaluation for best policy selection

**Demonstrated capability:**
- Finds mechanism-engaging policies on microtubule compounds
- Explores ~70 nodes, prunes ~600+ for death/interventions
- Cache makes repeated evaluations instant

**Example result (test_C_clean, paclitaxel):**
- Reward: 0.341
- Mechanism hit: TRUE (actin >1.4× at 12h)
- Schedule: dose 1.0× → 0.5× → 0.25× over first 18h
- Death: 57.4% (over budget, but proof search works)

---

## Known Limitations

### 1. Death Estimation Too Optimistic

Heuristic estimates:
```python
estimated_death = min(0.3, total_dose_exposure * 0.08)
```

But actual death depends on:
- Compound toxicity (not captured)
- Temporal dynamics (attrition over time)
- Washout timing

**Result:** Beam finds policies that violate 20% death budget.

**Fix:** Use partial rollouts for accurate death trajectory, or calibrate heuristic per-compound.

### 2. Reward Function Mismatch

- Beam search uses: `compute_microtubule_mechanism_reward` (Phase 4)
- Phase 5 smart policy uses: `compute_epistemic_reward` (multi-axis)

**Result:** Beam only works for microtubule compounds (test_C_*).
- ER compounds (test_A_*): wrong reward signal
- Mito compounds (test_B_*): wrong reward signal

**Fix:** Implement Phase5-aware reward that:
1. Classifies stress axis from observations
2. Rewards correct classification
3. Rewards mechanism engagement (if microtubule)
4. Applies survival/parsimony bonuses with valid_attempt gate

### 3. No Confidence-Based Heuristic

Current heuristic uses mechanism potential (actin fold-change estimate).
Doesn't use classifier confidence margin for epistemic control.

**Fix:** Add `infer_stress_axis_with_confidence` to heuristic scoring.

---

## What Phase 6A Proves

**The search infrastructure works:**
1. Beam expansion explores action space
2. Pruning reduces combinatorial explosion (577 death, 156 interventions)
3. Heuristic guides search toward mechanism-engaging policies
4. Cache makes evaluation tractable

**The landscape is navigable:**
- Beam finds policies that engage mechanism (actin >1.4×)
- Not just random - search converges to dosing schedules
- Proves reward surface has structure beyond hand-coded heuristics

**What's missing:**
- Accurate death modeling (for budget compliance)
- Multi-axis reward (for Phase 5 integration)
- Adaptive heuristics (use observations, not just dose sums)

---

## Next Steps (Phase 6B or iteration)

### Option 1: Fix Death Estimation
- Implement true prefix rollouts (run VM to current timestep only)
- Cache prefix states for reuse
- Prune accurately based on trajectory

### Option 2: Implement Phase5 Epistemic Reward
- Add classifier to beam search observations
- Reward axis identification + mechanism engagement
- Test on full Phase5 library (all 6 compounds)

### Option 3: Adaptive Heuristics
- Use classifier confidence margin in heuristic
- Penalize high uncertainty at decision points
- Bonus for probe-then-commit patterns

### Option 4: Multi-Compound Screening (Phase 6C)
- Extend beam search to batch of compounds
- Shared intervention budget
- Optimize for batch classification accuracy

---

## Test Status

**Current test (`test_beam_search.py`):**
- Tests beam on Phase5 library
- Compares to smart policy
- **EXPECTED TO FAIL** due to reward mismatch

**To make test pass:**
1. Restrict to microtubule compounds only, OR
2. Implement Phase5 epistemic reward in beam search

---

## Files

**Implementation:**
- `src/cell_os/hardware/beam_search.py`
  - BeamSearch class
  - Phase5EpisodeRunner (applies potency/toxicity scalars)
  - BeamNode, BeamSearchResult dataclasses

**Tests:**
- `tests/unit/test_beam_search.py`
  - test_beam_search_matches_or_beats_smart_policy_phase5_library()
  - Currently fails on ER/mito compounds (reward mismatch)

**Documentation:**
- `docs/PHASE_6A_BEAM_SEARCH.md` (this file)

---

## Summary

Phase 6A beam search is a **working proof-of-concept** that demonstrates:
- Search infrastructure is sound
- Landscape has structure (search finds mechanism-engaging policies)
- Cache + pruning makes search tractable

Known issues (death estimation, reward mismatch) are tractable and well-understood.
This is a clean foundation for iteration.

**The world has teeth. Beam search is learning to navigate without getting bitten.**
