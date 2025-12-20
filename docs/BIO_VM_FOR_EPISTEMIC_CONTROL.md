# BiologicalVirtualMachine for Epistemic Control

**Purpose**: Frame BiologicalVM capabilities and limitations for Phase 5/6A epistemic control and beam search.

**Date**: 2024-12-19

---

## What It Does (High Level)

BiologicalVM is a **stateful lab simulator** that:
- Tracks **biological state** per vessel (latent stresses, nutrients, compounds)
- **Advances time** with competing-risks death model
- Produces **synthetic assay readouts** with realistic noise and artifacts
- **Physics runs whether you observe or not** (assays are measurement layers)

---

## Current Use Case: Epistemic Control Under Budgets

### Phase 5 (Current)
Generate weak/clean compound signatures for temporal information-risk tradeoffs:

```python
# Apply Phase 5 scalars
vm.treat_with_compound(
    vessel_id="test",
    compound="paclitaxel",
    dose_uM=0.005,
    potency_scalar=0.7,    # Weak induction (70% of normal k_on)
    toxicity_scalar=2.5    # High death (250% of normal attrition)
)
```

**Result**: Compound is ambiguous at 12h (probe), clear at 48h (deadly).

**Smart policy**: Probe 0.5× @ 12h → classify axis → commit (washout immediately for ER/mito, continue to 24h for microtubule).

**Hard constraints**: death ≤20%, interventions ≤2

### Phase 6A.1 (Current)
Real prefix rollouts for beam search planning:

```python
# Beam search candidate schedule
schedule = [dose_1.0, dose_0.5, washout, ...]

# Evaluate using ACTUAL physics (not heuristics)
prefix_result = runner.rollout_prefix(schedule[:2])  # Run VM to step 2
if prefix_result.viability < 0.80:
    prune()  # ACTUAL death check, not estimate
```

**The fix**: "You can't plan around a crocodile using a children's drawing."

### Next: Multi-Axis Epistemic Reward
- Classify stress axis from observations (ER/mito/microtubule)
- Reward correct classification + mechanism engagement
- Test: beam ≥ smart on full Phase5 library (6 compounds)

---

## What Works for This Use Case

### ✅ Latent Stress Dynamics
```python
vessel.er_stress        # 0-1, ER stress level
vessel.mito_dysfunction # 0-1, mito dysfunction level
vessel.transport_dysfunction  # 0-1, transport dysfunction (actin proxy)
```

These provide:
- **Temporal coupling**: Induction at rate `k_on * potency_scalar`, decay at rate `k_off`
- **Axis-specific signatures**: Different readout patterns per stress axis
- **Weak signatures**: Low potency_scalar → slow induction → ambiguous early readouts

**Critical for**: Classifier needs clear separation between axes at 12h vs 48h.

### ✅ Competing-Risks Death Model
```python
# Multiple death sources propose hazards
_propose_hazard(vessel, starvation_rate, "death_starvation")
_propose_hazard(vessel, hazard_er, "death_er_stress")
_propose_hazard(vessel, hazard_mito, "death_mito_dysfunction")
_propose_hazard(vessel, attrition_rate, "death_compound")

# Commit death once, allocate to causes
_commit_step_death(vessel, hours)
```

**Critical for**: Beam search needs accurate death trajectories to respect 20% budget.

### ✅ Phase 5 Scalar Integration
Applied in 5 locations:
1. `_update_er_stress`: `potency_scalar` scales k_on
2. `_update_mito_dysfunction`: `potency_scalar` scales k_on
3. `_update_transport_dysfunction`: `potency_scalar` scales k_on
4. `_apply_compound_attrition`: `toxicity_scalar` scales death rate
5. `treat_with_compound`: `toxicity_scalar` scales instant death

**Status**: Complete and consistent ✓

### ✅ Washout Mechanics
```python
vm.washout_compound(vessel_id, compound)
# - Removes compound from vessel.compounds
# - Records washout count (for ops budget)
# - Applies measurement artifact (intensity penalty ~12h)
```

**Critical for**: Smart policy washout timing (immediate for ER/mito, delayed for microtubule).

---

## Known Limitations (Affect Planning)

### ⚠️ 1. Death = Disappearance (Semantic Mismatch)

**Current behavior**:
```python
# Death immediately reduces BOTH viability AND cell_count
survival = ...
vessel.viability *= survival
vessel.cell_count *= survival
```

**Problem**: Assays can't distinguish "recently dead" from "vanished".

**Impact on epistemic control**:
- Classifier sees intensity drop (dead cells dim) but not structure changes
- LDH reconstruction has to divide by viability (hacky)
- Temporal signatures merge (death at 12h vs 24h looks similar)

**Workaround**: Classifier uses fold-changes (relative to baseline), not absolute values.

**Fix priority**: MEDIUM (affects classifier quality, not search correctness)

### ⚠️ 2. Timestamps Break Determinism

**Current behavior**:
```python
result = {
    'timestamp': datetime.now().isoformat(),  # Wall time, not simulated time!
    ...
}
```

**Problem**: Identical schedules produce different outputs (timestamp varies).

**Impact on epistemic control**:
- Prefix rollout cache keys include schedules but not timestamps
- Design artifact hashes ignore timestamps (correct)
- Not a blocker, but messy for debugging

**Fix priority**: LOW (doesn't break beam search)

### ⚠️ 3. Nutrient Depletion Not Time-Aware

**Current behavior**:
```python
# Depletion doesn't reference last_feed_time
# Consumption is instantaneous per advance_time() call
```

**Problem**: Two 6h steps vs one 12h step produce different nutrient states.

**Impact on epistemic control**:
- Beam search uses 6h steps (fixed)
- As long as consistent, not a blocker
- Would break if comparing different step sizes

**Fix priority**: LOW (use fixed 6h steps)

### ⚠️ 4. Contamination as Instant Hit

**Current behavior**:
```python
if ENABLE_FEEDING_COSTS and random.random() < FEEDING_CONTAMINATION_RISK:
    vessel.viability *= 0.95  # Instant 5% death
    vessel.death_unknown += 0.05
```

**Problem**: Contamination is instantaneous, not a latent process.

**Impact on epistemic control**:
- Feeding interventions have stochastic death (breaks determinism with fixed seed)
- Beam search doesn't use feeding (interventions ≤2 budget mostly for washout)
- Not a blocker for current use case

**Fix priority**: LOW (not using feeds in Phase 5/6A)

---

## Blockers vs Nice-to-Haves

### 🚫 Blockers (Must Fix for Phase 6)

**None currently.**

Phase 5/6A work around the limitations:
- Use fold-changes (death=disappearance is fine)
- Fixed 6h steps (nutrient depletion consistent)
- Don't use feeding (contamination irrelevant)
- Cache by schedules (timestamps ignored)

### 📊 Nice-to-Haves (Improve Classifier Quality)

1. **Split viable/dead cell populations**
   - Would make LDH naturally correct
   - Would improve temporal signatures
   - Classifier could learn "timing of death" patterns

2. **Time-aware nutrient depletion**
   - Would enable comparing different step sizes
   - Would make step size a tunable parameter

3. **Latent contamination process**
   - Would make feeding interventions more realistic
   - Not needed for current Phase 5/6A work

### 🔧 Technical Debt (Clean Up Eventually)

From user feedback:

1. **`logger` used before definition** (line ~26)
   - Easy fix: move `logger = logging.getLogger(__name__)` before try/except

2. **Duplicate `transport_dysfunction`** (FIXED ✓)
   - Was on line 136 + 160, removed duplicate

3. **Global feature flags**
   - Replace with `MechanismConfig` dataclass
   - Snapshot into artifacts for reproducibility

4. **`VesselState` as dataclass**
   - Add validation method
   - Formalize invariants (viability bounds, ledger conservation)

5. **Parameter schema validation**
   - Use pydantic for YAML loading
   - Version parameter schema

6. **Teeth tests**
   - Observer independence (assays don't mutate physics)
   - Ledger conservation
   - Washout penalty (measurement only)
   - No-compound monotonicity (latent decay)
   - Seed determinism

---

## Verdict for Epistemic Control

**Status**: Production-ready for Phase 5/6A with known limitations.

✅ **Works**:
- Phase 5 scalars correct and consistent
- Competing-risks death model accurate enough for 20% budget
- Latent stress dynamics enable temporal information-risk tradeoffs
- Prefix rollouts give real viability trajectories (not heuristics)

⚠️ **Limitations** (not blockers):
- Death = disappearance (affects classifier quality, not search)
- Timestamps non-deterministic (ignored in cache keys)
- Nutrient depletion step-size dependent (use fixed 6h)

🚫 **Blockers**: None.

---

## Example: Why This Matters for Beam Search

### Without Real Rollouts (Phase 6A - Broken)

```python
# Heuristic death estimate
estimated_death = total_dose_exposure * 0.08  # Wrong!

# Result: Beam finds policies with 57% death (3× over budget)
```

### With Real Rollouts (Phase 6A.1 - Fixed)

```python
# Actual physics
prefix_result = runner.rollout_prefix(schedule)
actual_viability = prefix_result.viability  # From VM

if actual_viability < 0.80:
    prune()  # Real death check
```

**Result**: Beam respects 20% death budget during search, not just at evaluation.

**The VM's competing-risks model is what makes this work.**

---

## Recommendations

### For Phase 6 (Next)

1. **Keep limitations documented** (this file)
2. **Add teeth tests** when time permits (observer independence, ledger conservation)
3. **Monitor classifier quality** - if fold-change separation degrades, revisit death=disappearance

### For Phase 7+ (Future)

1. **Split viable/dead populations** (biggest quality improvement)
2. **Parameter schema validation** (reproducibility)
3. **Time-aware nutrient depletion** (enable step size tuning)

---

## Credit

Analysis and improvement suggestions from user feedback (2024-12-19).
