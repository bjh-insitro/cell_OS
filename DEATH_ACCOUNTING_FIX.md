# Death Accounting Fix - Complete ✓

## Problem

Death accounting was only tracking attrition deltas, not instant viability drops.

**Before:**
```python
# treat_with_compound:
vessel.viability *= viability_effect  # Instant death (95% → 3%)
# BUT: death_compound not updated!

# _apply_compound_attrition:
vessel.death_compound += killed_fraction  # Only tracks attrition
```

**Result:**
- High dose (10 µM): instant 95% death → viability 3%
- `death_compound = 0.0%` at 12h (wrong!)
- Death mode = "unknown" (had to use heuristic band-aid)

## Solution

Track instant compound death in `treat_with_compound`:

```python
# Apply instant effect to vessel state and track death accounting
prev_viability = vessel.viability
vessel.viability *= viability_effect
vessel.cell_count *= viability_effect

# Track instant compound death (not just attrition!)
instant_killed = prev_viability - vessel.viability
vessel.death_compound += instant_killed
vessel.death_compound = min(1.0, max(0.0, vessel.death_compound))
```

**Now:**
- Instant death tracked immediately
- Attrition continues to accumulate
- Death mode uses clean threshold logic (no heuristics)

## Validation

### High Dose (10 µM nocodazole)

**After fix:**
```
4h:  After compound - viability=3.1%
12h: death_compound=94.9%, death_mode='compound' ✓
96h: death_compound=96.4%, death_mode='compound' ✓
```

**Interpretation:**
- Instant: 98% → 3.1% (94.9% killed instantly)
- Tracked: death_compound = 94.9% at 12h ✓
- Attrition: 94.9% → 96.4% (additional 1.5% over 96h)
- Death mode: "compound" (correct label from instant death)

### Mid Dose (2.0 µM nocodazole)

**Observer independence test:**
```
No Painting (A):     viability=33.6%, death_compound=64.4%
With Painting (B):   viability=33.6%, death_compound=64.4%
Match: ✓
```

**Interpretation:**
- Instant: ~50% viability drop
- Attrition: continues to 33.6%
- Accounting: 64.4% compound death tracked correctly
- Observer independence preserved ✓

## Death Mode Simplification

### Before (heuristic band-aid):

```python
compound_death = death_compound > threshold or (viability < 0.5 and has_compounds)
```

Problem: Needed heuristic because instant death wasn't tracked.

### After (clean threshold):

```python
compound_death = vessel.death_compound > threshold
```

**Why it works now:** `death_compound` includes both instant and attrition death.

## Architecture

```
treat_with_compound()
  ↓
Apply instant viability effect
  ↓
Track instant_killed → death_compound  [NEW!]
  ↓
advance_time()
  ↓
_apply_compound_attrition()
  ↓
Track attrition_killed → death_compound
  ↓
_update_death_mode()
  ↓
Clean threshold-based labeling
```

## What This Fixes

❌ **Before:**
- Instant death invisible to accounting
- Death mode required heuristic band-aids
- Tests couldn't distinguish instant vs attrition death

✅ **After:**
- All compound death tracked (instant + attrition)
- Death mode uses clean threshold logic
- Death accounting accurate for all scenarios

## Files Modified

1. **src/cell_os/hardware/biological_virtual.py:**
   - `treat_with_compound()`: Track instant death
   - `_update_death_mode()`: Simplified to clean threshold logic

2. **test_observer_independence.py:**
   - Updated to 2.0 µM dose (where attrition matters)
   - Validates death accounting accuracy

## Validation Summary

| Metric | Expected | Actual | Status |
|--------|----------|--------|--------|
| Instant death tracked | Yes | 94.9% at 12h | ✓ |
| Attrition accumulates | Yes | 94.9% → 96.4% | ✓ |
| Death mode labeled | "compound" | "compound" | ✓ |
| Observer independence | Match | Match | ✓ |
| Accounting capped | [0, 1] | 96.4% (valid) | ✓ |

## Bottom Line

Death accounting now tells the truth:
- **Instant death:** Tracked when it happens (treat_with_compound)
- **Attrition death:** Accumulated over time (_apply_compound_attrition)
- **Total death:** `death_compound` = instant + attrition
- **Death mode:** Clean threshold-based logic (no heuristics)

No more "significant death but death_compound = 0%" lies.
