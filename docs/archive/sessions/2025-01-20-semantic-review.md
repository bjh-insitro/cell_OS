# Semantic Review Fixes: 2025-01-20

## Hard-Nosed Semantic Review: Where It Can Still Lie

Based on detailed code review, these are the "quiet bugs" that don't throw errors but create semantic violations or confusion.

---

## Critical Fixes (Implemented)

### Fix #1: Threshold Shift Direction Was Inverted ⚠️ CRITICAL BUG

**Bug**: `theta_shifted = THETA / threshold_shift` inverted the semantics
- sensitive (shift=0.8) → theta = 0.7/0.8 = **0.875** (HIGHER, dies LATER) ❌
- resistant (shift=1.2) → theta = 0.7/1.2 = **0.583** (LOWER, dies EARLIER) ❌

This is **exactly backwards** from stated intent: "sensitive dies earlier"

**Fix** (biological_virtual.py:882, 985):
```python
# Old (WRONG):
theta_shifted = ER_STRESS_DEATH_THETA / threshold_shift
width_shifted = ER_STRESS_DEATH_WIDTH / threshold_shift

# New (CORRECT):
theta_shifted = ER_STRESS_DEATH_THETA * threshold_shift
width_shifted = ER_STRESS_DEATH_WIDTH * threshold_shift
```

Now:
- sensitive (shift=0.8) → theta = 0.7 * 0.8 = **0.56** (LOWER, dies EARLIER) ✓
- resistant (shift=1.2) → theta = 0.7 * 1.2 = **0.84** (HIGHER, dies LATER) ✓

**Verified by**: test_threshold_shift_direction.py (2/2 passing)

---

### Fix #2: passage_cells Dropped Attribution History

**Bug**: `passage_cells()` inherited viability deficits but wiped their attribution
- Old: `target.viability = source.viability * (1 - passage_stress)` (inherits deficit)
- Old: `target.death_unknown = passage_death` (only new stress, history lost)
- Result: Prior `death_compound`, `death_er_stress`, etc. vanish → lands in `death_unattributed` later

**Fix** (biological_virtual.py:1677-1709): **Stateful transfer**
```python
# Carry over ALL death buckets to preserve attribution history
target.death_compound = source.death_compound
target.death_starvation = source.death_starvation
target.death_mitotic_catastrophe = source.death_mitotic_catastrophe
target.death_er_stress = source.death_er_stress
target.death_mito_dysfunction = source.death_mito_dysfunction
target.death_confluence = source.death_confluence
target.death_unknown = source.death_unknown

# ADD new passage stress to death_unknown
passage_death = source.viability * passage_stress
if passage_death > DEATH_EPS:
    target.death_unknown += passage_death

# Also carry over:
# - Latent stress states (er_stress, mito_dysfunction, transport_dysfunction)
# - Compound exposure (compounds, compound_meta, compound_start_time)
# - Subpopulation states (viability, latent states per subpop)
```

Passaging is now a **population transfer operation**, not a reset. Attribution continuity maintained.

---

### Fix #3: Conservation Epsilon Inconsistency

**Bug**: Three different tolerances used across conservation checks
- `_commit_step_death`: `> total_dead + 1e-9`
- `_update_death_mode` (first check): `> total_dead + 1e-6`
- `_update_death_mode` (second check): `> total_dead + 1e-5`

This creates ambiguity about where numerical wiggle is acceptable.

**Fix** (biological_virtual.py:680, 1338, 1376): **Uniform DEATH_EPS**
```python
# All conservation checks now use DEATH_EPS (1e-9) consistently
if credited > total_dead + DEATH_EPS:
    raise ConservationViolationError(...)
```

Policy: **Hard errors everywhere with strict 1e-9 tolerance**. No wiggle room.

---

## Documented Semantic Choices (No Changes Needed)

### A) Instant Kill Sequential Semantics

**Current behavior**: Multiple instant kills in same operation operate sequentially
- First kill: `v1 = v0 * (1 - kill1)`, credit `death_field1 = v0 - v1`
- Second kill: `v2 = v1 * (1 - kill2)`, credit `death_field2 = v1 - v2`
- Both causes credited, conservation holds

**Semantic**: Order matters for instant events. They are sequential, not competing.

**Alternatives**:
- Could implement "instant competing-risks aggregator" like `_commit_step_death`
- Current approach is simpler and correct if order is intentional

**Decision**: Keep current (sequential instant events). Document in code if needed.

---

### B) Operator Time Costs Don't Advance Simulated Time

**Current behavior**: `feed_vessel()` and `washout_compound()` return `time_cost_h` but don't advance `self.simulated_time`

**Design**: Intentional separation
- Physics time advances only via `incubate()` / `advance_time()`
- Policy layer must account for operation time in schedule externally

**Risk**: If policy doesn't pay time costs, creates free lunch

**Recommendation**: Enforce at bridge layer (policy integration), not in VM

---

### C) Nutrient Depletion Anchor Unused

**Current state**: `last_feed_time` is set but not used for aging effects beyond glucose/glutamine depletion

**Status**: "Unfinished promise" - not a bug, just incomplete feature

---

### D) Epistemic vs Physical Mixture (Architectural)

**Current**: Subpops generate physical hazards (weighted sum), then viabilities synced to vessel

This **mixes** "physical mixture" and "epistemic parameter uncertainty" interpretations.

**Not wrong**, but makes Phase 6 "proper projections" harder.

**Decision**: Keep current (physical mixture for hazards, sync viabilities). Will refactor in Phase 6.

---

## Test Results

All semantic honesty test suites passing:
- ✓ test_instant_kill_semantics.py: 3/3
- ✓ test_threshold_shift_direction.py: 2/2
- ✓ test_death_accounting_honesty.py: 3/3
- ✓ test_adversarial_honesty.py: 3/3
- ✓ test_semantic_invariants.py: 2/2
- ✓ test_stress_axis_determinism.py: 2/2

---

## Outstanding Questions for Review

### 1) atp_viability_assay Missing Run Context Transforms

In `cell_painting_assay`, you apply:
- Run context measurement modifiers (`illumination_bias`, `channel_biases`)
- Pipeline transform (batch-dependent feature extraction)

In `atp_viability_assay`, you apply:
- plate/day/operator/well/edge factors only
- **NO** run context measurement modifiers
- **NO** pipeline transform

**Question**: Is this intentional (scalar assays unaffected by lot/instrument drift)? Or should LDH/ATP/UPR/trafficking signals also get run context transforms?

Currently LDH/ATP/UPR/trafficking would be **identical across different run contexts**, which might not match real-world batch effects on biochemical assays.

---

### 2) Technical Noise Application Order

Need to verify in `cell_painting_assay`:
- Whether batch/plate/day/operator effects are correlated correctly
- Whether failure modes interact with viability and washout artifacts in sane order
- Whether you accidentally double-apply lognormal noise layers (bio CV + plating CV + well CV)

**Action**: Paste rest of `cell_painting_assay` for detailed audit

---

## Key Invariants Now Enforced

1. **Threshold shift semantics**: `theta_shifted = THETA * shift`
   - sensitive (shift < 1) → lower threshold → dies earlier
   - resistant (shift > 1) → higher threshold → dies later

2. **Passage stateful transfer**: Death attribution history preserved through passage
   - All death buckets carried over
   - Latent states, compound exposure, subpop states carried over
   - New passage stress added to existing `death_unknown`

3. **Conservation epsilon uniform**: All checks use DEATH_EPS (1e-9)
   - Hard errors everywhere with strict tolerance
   - No ambiguity about where wiggle is acceptable

4. **Comments match code**: All semantic inversions fixed, docstrings accurate
