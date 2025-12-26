# v4 Implementation Notes

**Date**: 2025-12-25
**Status**: Ready to implement

---

## Key Insight: Prerequisites vs. Diffs

Initial go/no-go audit revealed current code **defines but doesn't use** IC50 shifts and commitment delays. This created a false sense of model richness.

**Reframe**: Instead of treating this as "extra work" for v4, treat it as **making the code honest about what world it already claims to implement**.

---

## Structure

### Prerequisites (unglamorous honesty work)
1. **Delete lie injector**: `_sync_subpopulation_viabilities` forces backward authority
2. **Make hazards per-subpop**: Move loop boundary to actually use existing parameters

### v4 Proper (4 surgical diffs)
1. Add `_recompute_vessel_from_subpops` helper
2. Fix `_apply_instant_kill` (reverse authority)
3. Fix `_commit_step_death` (use per-subpop hazards)
4. Add runtime invariants (vessel = weighted mean)

---

## Why This Matters

**Before prerequisites**:
- IC50 shifts defined at lines 213, 222, 231
- Never actually applied to attrition computation
- Attrition computed once at vessel level
- All subpops get same hazard despite different IC50s

**After prerequisites**:
- Same IC50 shifts, now USED in attrition loop
- Hazard computed per subpop with shifted IC50
- Subpops have different hazards (sensitive > resistant)
- v4 diffs can make these hazards affect viability divergence

**Before v4 diffs**:
- Different hazards per subpop (after prereqs)
- But `_commit_step_death` applies vessel-level survival
- Then `_sync_subpopulation_viabilities` re-syncs everything
- Net result: subpops synchronized despite different hazards

**After v4 diffs**:
- Different hazards per subpop (prereqs)
- `_commit_step_death` applies per-subpop survival
- No sync function to undo divergence
- Net result: sensitive dies earlier than resistant

---

## The Real Tell

After prerequisites + v4, under lethal dose:

```python
# Step once
vm._step_vessel(vessel, 1.0)

# Print hazards (should differ)
for name in sorted(vessel.subpopulations.keys()):
    h = vessel.subpopulations[name]['_total_hazard']
    v = vessel.subpopulations[name]['viability']
    print(f"{name}: hazard={h:.6f}/h, viability={v:.4f}")
```

**Expected**:
- Hazards differ (sensitive highest, resistant lowest)
- Viabilities diverging (sensitive dropping faster)

**If hazards all equal**: Prereq B not applied (IC50 shifts not used)
**If viabilities all equal**: v4 Diff 3 not applied OR sync still being called

---

## Two Guardrails from Prerequisites

### Guardrail 1: No silent fallback

```python
# In per-subpop hazard loop
dose_ratio = dose_uM / ic50_uM if ic50_uM > 0 else 0.0
if dose_ratio >= 1.0 and commitment_delay_h is None:
    raise ValueError(
        f"Missing commitment_delay_h for {subpop_name} at lethal dose. "
        f"v3 sampling skipped?"
    )
```

**Why**: Turns missing delays from "silently wrong" to "loudly broken". v3 contract enforcement.

### Guardrail 2: Clear cache each step

```python
# At start of per-subpop loop
if '_hazards' not in subpop:
    subpop['_hazards'] = {}
if '_total_hazard' not in subpop:
    subpop['_total_hazard'] = 0.0
```

**Why**: Prevents using stale hazards when step early-returns (e.g., viability already 0).

---

## Tripwire Tests

### Prereq A tripwire
```python
# Set different viabilities manually
# Step once
# Assert they stayed different
# Catches: sync function still being called
```

### Prereq B tripwire
```python
# Treat with lethal dose
# Step once
# Assert subpop['_total_hazard'] exists
# Assert hazards differ (sensitive > resistant)
# Catches: attrition still vessel-level
```

### v4 Test 3 (kill-shot)
```python
# Treat with lethal dose
# Step over 24h
# Assert sensitive crosses threshold BEFORE resistant
# Catches: viabilities still synchronized
```

### v4 Test 5 (one-step divergence)
```python
# Treat with lethal dose
# Step ONCE to 18h
# Assert viabilities diverged (not all equal)
# Catches: vessel-level survival disguised as per-subpop
```

### v4 Test 6 (no-resync invariant)
```python
# Manually set different viabilities
# Treat (triggers instant kill)
# Assert viabilities still differ after treatment
# Catches: cleanup step that re-syncs
```

---

## What Changes in Behavior

### Immediate (after prereqs)
- Attrition computation happens per subpop (3× more calls to `compute_attrition_rate`)
- Subpops have different `_total_hazard` values (new fields)
- But viability still synchronized (sync function still active)

### After v4 proper
- Subpop viabilities diverge under stress
- Sensitive dies faster than resistant (observable in debugger)
- Vessel viability = weighted mean of subpop viabilities
- Flow cytometry simulations show staggered drops

### What DOESN'T change
- Vessel-level death fields (`death_compound`, etc.) still exist
- Now derived/allocated from subpop hazards, not authoritative
- Compatibility maintained for downstream code

---

## Common Failure Modes

### Mode 1: Prerequisites skipped, v4 diffs applied
**Symptom**: Test 3 fails (sensitive doesn't die earlier)
**Cause**: Attrition still vessel-level, all subpops get same hazard
**Fix**: Apply Prereq B (per-subpop hazard loop)

### Mode 2: Prereq A skipped, sync still called
**Symptom**: All tests pass but subpops stay synchronized
**Cause**: Line 1018 still calls `_sync_subpopulation_viabilities`
**Fix**: Delete line 1018 and function definition

### Mode 3: Prereq B partially applied
**Symptom**: `_total_hazard` exists but hazards all equal
**Cause**: IC50 shift not applied, or commitment delay not retrieved
**Fix**: Verify `ic50_uM *= ic50_shift` and commitment delay cache key

### Mode 4: v4 Diff 3 uses vessel-level hazards
**Symptom**: Test 3 fails, subpops diverge slightly then converge
**Cause**: `_commit_step_death` uses `vessel._step_total_hazard` not `subpop['_total_hazard']`
**Fix**: Verify loop uses `subpop['_total_hazard']` per subpop

---

## Timeline Estimate

- Prereq A (delete sync): 5 minutes
- Prereq B (per-subpop hazards): 30-45 minutes
- Verify prerequisites: 10 minutes
- Apply v4 Diffs 1-4: 15 minutes
- Run tests and debug: 15-30 minutes
- **Total**: 1-2 hours

---

## Success Criteria

After all work complete:

1. ✅ `rg "_sync_subpopulation_viabilities"` returns nothing
2. ✅ Prereq verification test passes
3. ✅ All 6 v4 tests pass (4 core + 2 tripwires)
4. ✅ Under lethal dose, print shows:
   - Different hazards per subpop (sensitive highest)
   - Different viabilities per subpop (sensitive lowest)
   - Vessel viability = weighted mean (within 1e-9)

---

## What v4 Enables (Falsification Target)

**Real experimental setup**:
- Flow cytometry time course
- Fluorescent marker for sensitive population
- Treat with lethal dose of compound
- Measure % viable in each population every 2h for 24h

**Before v4**: Simulator cannot generate staggered drops (all populations synchronized)

**After v4**: Simulator generates realistic trajectories (sensitive drops earlier)

**Next visible artifact** (v5 target):
- Sensitive dies faster but fraction stays 25%
- No selection pressure (fractions fixed)
- Resistant should outgrow sensitive, but doesn't

---

## Commit Message Structure

```
feat: independent subpopulation viabilities (v4)

Prerequisites:
- Delete _sync_subpopulation_viabilities (lie injector)
- Refactor attrition to per-subpop hazard computation
- IC50 shifts now actually used (not just defined)

Core changes:
- Make subpop viability authoritative (not vessel)
- Vessel viability derived as weighted mean
- Instant kill and hazard death update subpops independently
- Enables sensitive subpops to die earlier than resistant

Enables falsification: flow cytometry time courses showing
differential survival curves per subpopulation.

Depends on v3 (commitment heterogeneity).
Prepares for v5 (selection dynamics).
```

---

## Key Design Principle

**Minimal honesty**: Don't add features. Make existing parameters actually matter.

IC50 shifts and commitment delays were already defined. Prerequisites make them real. v4 makes their effects observable.

No new ontology. No new parameters. Just honest use of what's already there.
