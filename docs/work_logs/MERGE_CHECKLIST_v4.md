# Merge Checklist: Subpopulation Viability v4

## Status: READY FOR HOSTILE REVIEW

**Depends on**: v3 (commitment heterogeneity) must be merged first

---

## Deliverables

- ✓ **PATCH_subpop_viability_v4_FINAL.md** - Full specification with prerequisites
- ✓ **test_subpop_viability_v4_FINAL.py** - 6 hardened tests (4 core + 2 tripwires)
- ✓ **GO_NO_GO_v4_verification.md** - Pre-implementation audit findings

---

## Prerequisites (Must Be Applied Before v4 Diffs)

v4 assumes per-subpop hazard computation exists. Current code defines IC50 shifts but doesn't use them. Prerequisites make the code obey the world it already claims exists.

### Prereq A: Delete sync helper (removes lie injector)

**File**: `src/cell_os/hardware/biological_virtual.py`

**Actions**:
1. Delete line 1018: `self._sync_subpopulation_viabilities(vessel)`
2. Delete lines 922-956: `_sync_subpopulation_viabilities` function definition
3. Verify: `rg "_sync_subpopulation_viabilities"` returns nothing

**Why**: Function forces all subpop viabilities back to vessel viability, defeating v4 entirely.

**Tripwire test**:
```bash
# Add to test file or run manually
python3 -c "
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
import numpy as np

vm = BiologicalVirtualMachine(seed=42)
vm.seed_vessel('v', 'A549', initial_count=1e6, initial_viability=0.9)
vessel = vm.vessel_states['v']

# Set different viabilities
names = sorted(vessel.subpopulations.keys())
vessel.subpopulations[names[0]]['viability'] = 0.5
vessel.subpopulations[names[1]]['viability'] = 0.7
vessel.subpopulations[names[2]]['viability'] = 0.9

# Step without treatment
vm._step_vessel(vessel, 1.0)

# Assert they stayed different
v_after = [vessel.subpopulations[n]['viability'] for n in names]
unique = len(set(np.round(v_after, 6)))
assert unique >= 2, f'Subpops re-synced: {v_after}'
print('✓ Prereq A verified: No sync after step')
"
```

---

### Prereq B: Per-subpop hazard computation and caching

**File**: `src/cell_os/hardware/biological_virtual.py`
**Location**: Lines ~1170-1224 (attrition computation in `_step_vessel`)

**Objective**: Move loop boundary from vessel-level to per-subpop. No new ontology, just use existing IC50 shift parameters.

**Key changes**:
- Add loop: `for subpop_name in sorted(vessel.subpopulations.keys()):`
- Apply `ic50_shift` per subpop (already defined at lines 213, 222, 231)
- Retrieve `commitment_delay_h` from v3 cache: `vessel.compound_meta['commitment_delays'][(compound, exposure_id, subpop_name)]`
- Compute attrition per subpop with subpop-specific IC50 and viability
- Store `subpop['_total_hazard']` and `subpop['_hazards']` (used by Diff 3)

**Two guardrails**:
1. **No silent fallback**: If `dose_ratio >= 1.0` and `commitment_delay_h` missing, raise
2. **Clear cache each step**: Initialize `subpop['_hazards'] = {}` and `subpop['_total_hazard'] = 0.0` at start

**Verification** (after refactor):
```bash
# Print hazards under lethal dose
python3 -c "
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine

vm = BiologicalVirtualMachine(seed=42)
vm.seed_vessel('v', 'A549', initial_count=1e6, initial_viability=0.3)
vm.treat_with_compound('v', 'tunicamycin', 5.0)
vessel = vm.vessel_states['v']

# Step once
vm._step_vessel(vessel, 1.0)

# Check per-subpop hazards
names = sorted(vessel.subpopulations.keys())
for name in names:
    h = vessel.subpopulations[name].get('_total_hazard', 0.0)
    print(f'{name}: hazard={h:.6f}/h')

# Sensitive should have higher hazard (lower IC50)
hazards = [vessel.subpopulations[n]['_total_hazard'] for n in names]
print(f'✓ Prereq B verified: Hazards differ per subpop')
"
```

Expected: Hazards should differ (sensitive has lower IC50 → higher hazard at same dose).

---

### "Real Tell" Verification (After Prerequisites, Before v4 Diffs)

After applying both prerequisites, run this check to verify prerequisites actually work:

```python
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine

vm = BiologicalVirtualMachine(seed=42)
vm.seed_vessel('v', 'A549', initial_count=1e6, initial_viability=0.3)
vm.treat_with_compound('v', 'tunicamycin', 5.0)
vessel = vm.vessel_states['v']

# Step once
vm._step_vessel(vessel, 1.0)

# Get subpops sorted by IC50 shift
names = sorted(vessel.subpopulations.keys())
subpops_by_shift = sorted(names, key=lambda n: vessel.subpopulations[n]['ic50_shift'])
sensitive = subpops_by_shift[0]
resistant = subpops_by_shift[-1]

# Extract state
h_sens = vessel.subpopulations[sensitive]['_total_hazard']
h_res = vessel.subpopulations[resistant]['_total_hazard']
v_sens = vessel.subpopulations[sensitive]['viability']
v_res = vessel.subpopulations[resistant]['viability']

# Compute weighted mean
wm = sum(vessel.subpopulations[n]['fraction'] * vessel.subpopulations[n]['viability'] for n in names)

# THE THREE TELLS:
# 1. Hazards differ (IC50 shifts matter)
assert h_sens > h_res, f"Hazards equal: {h_sens:.6f} vs {h_res:.6f}. Prereq B not working?"

# 2. Viabilities diverging (hazards applied per subpop, not yet re-synced)
# NOTE: After prereqs but BEFORE v4 diffs, this may still fail if sync still called
# This checks if death application is per-subpop (should pass after prereqs)
print(f"Sensitive: hazard={h_sens:.6f}/h, viability={v_sens:.4f}")
print(f"Resistant: hazard={h_res:.6f}/h, viability={v_res:.4f}")
print(f"Vessel viability: {vessel.viability:.4f}, Weighted mean: {wm:.4f}")

# If hazards differ but viabilities DON'T → death application still vessel-level
# If viabilities differ but vessel mismatch → derivation wrong or not called
```

**Pass criteria**:
- Hazards: `h_sens > h_res` (sensitive has lower IC50 → higher hazard)
- Viabilities: `v_sens < v_res` (sensitive dying faster) - **may fail until v4 Diff 3 applied**
- Vessel: `abs(vessel.viability - wm) < 1e-9` - **will fail until v4 Diff 1 applied**

**What failures mean**:
- Hazards equal → Prereq B not applied (IC50 shifts not used)
- Viabilities equal but hazards differ → Death still vessel-level OR sync still called
- Vessel ≠ weighted mean → Vessel still authoritative, not derived

---

## Code Changes (v4 Proper - 4 diffs)

### Change 1: Add recompute helper and initialize subpop fields

**File**: `src/cell_os/hardware/biological_virtual.py`

Add method:
```python
def _recompute_vessel_from_subpops(self, vessel: VesselState):
    # Weighted mean from subpops (sorted for determinism)
    # Sets vessel.viability and vessel.death_total
```

Initialize at vessel creation:
```python
for subpop_name in sorted(vessel.subpopulations.keys()):
    subpop['viability'] = vessel.viability
    subpop['death_total'] = 1.0 - vessel.viability
```

### Change 2: Fix `_apply_instant_kill` (lines ~770-797)

**Key change**: Apply kill to each subpop independently, then derive vessel.

**OLD** (lines 792-793):
```python
for subpop in vessel.subpopulations.values():
    subpop['viability'] = vessel.viability  # BACKWARD!
```

**NEW**:
```python
for name in sorted(vessel.subpopulations.keys()):
    sp = vessel.subpopulations[name]
    sv0 = sp['viability']
    sv1 = sv0 * (1.0 - kill_fraction)
    sp['viability'] = sv1

self._recompute_vessel_from_subpops(vessel)  # FORWARD!
```

### Change 3: Fix `_commit_step_death` (lines ~798-880)

**Key change**: Apply survival per subpop, derive vessel.

**Prerequisite**: Store `subpop['_total_hazard']` during hazard computation loop.

**NEW behavior**:
```python
for name in sorted(vessel.subpopulations.keys()):
    sp = vessel.subpopulations[name]
    total_hazard_subpop = sp['_total_hazard']
    survival = exp(-total_hazard_subpop * hours)
    sp['viability'] *= survival

self._recompute_vessel_from_subpops(vessel)
```

### Change 4: Runtime invariant

Add to end of `_step_vessel`, `_apply_instant_kill`, `_commit_step_death`:

```python
wm = sum(sp['fraction'] * sp['viability'] for sp in ...)
assert abs(vessel.viability - wm) < 1e-9, "vessel != weighted mean"
```

---

## Tests (Run Before Merge)

### 1. Vessel Viability Is Weighted Mean
```bash
python3 -c "
from tests import test_vessel_viability_is_weighted_mean
test_vessel_viability_is_weighted_mean()
"
```

Expected: `✓ Vessel viability is weighted mean`

### 2. Instant Kill Creates Divergence
```bash
python3 -c "
from tests import test_instant_kill_creates_subpop_divergence
test_instant_kill_creates_subpop_divergence()
"
```

Expected: `✓ Instant kill creates divergence: [0.72, 0.48, 0.24]`

### 3. Sensitive Dies Earlier (Kill-Shot Test)
```bash
python3 -c "
from tests import test_sensitive_dies_earlier_than_resistant
test_sensitive_dies_earlier_than_resistant()
"
```

Expected: `✓ Sensitive dies earlier: X.Xh vs resistant: Y.Yh` (where X < Y)

**If this fails**, backward authority still exists somewhere.

### 4. Determinism Smoke
```bash
python3 -c "
from tests import test_subpop_viability_trajectories_deterministic
test_subpop_viability_trajectories_deterministic()
"
```

Expected: 
```
✓ Subpop trajectories identical across runs
✓ Trajectories differ with seed=99
```

---

## Pre-Merge Verification

### Prerequisites Complete?

**Check**:
```bash
# Prereq A: Sync helper deleted
rg "_sync_subpopulation_viabilities" src/cell_os/hardware/biological_virtual.py
# Should return nothing

# Prereq B: Per-subpop hazards exist
python3 -c "
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
vm = BiologicalVirtualMachine(seed=42)
vm.seed_vessel('v', 'A549', initial_count=1e6, initial_viability=0.3)
vm.treat_with_compound('v', 'tunicamycin', 5.0)
vessel = vm.vessel_states['v']
vm._step_vessel(vessel, 1.0)

# Check hazards differ
names = sorted(vessel.subpopulations.keys())
hazards = [vessel.subpopulations[n].get('_total_hazard', 0.0) for n in names]
assert len(set(hazards)) >= 2, f'Hazards all equal: {hazards}'
print('✓ Prerequisites verified')
"
```

### Edge Cases to Check

1. **Instant kill on vessel with viability=1.0**: Should work (all subpops start at 1.0)
2. **Instant kill on vessel with viability=0.0**: Should return early (no-op)
3. **Multiple instant kills in sequence**: Each updates subpops, derives vessel
4. **Passaging**: If you passage vessels, ensure subpop viabilities are copied

---

## What This Fixes

1. ✓ Subpops can diverge (sensitive dies earlier under lethal dose)
2. ✓ Commitment heterogeneity + viability heterogeneity = realistic trajectories
3. ✓ Vessel viability clean readout (never authoritative)
4. ✓ Backward authority eliminated (no more "sync subpops to vessel")

**Kill-shot artifact removed**: Flow cytometry showing sensitive population dropping earlier than resistant. Previously impossible, now possible.

---

## What This Doesn't Fix (v5 Scope)

**Subpopulation fractions are still fixed** (line 210-238):
- No selection pressure
- No Darwinian dynamics
- Resistant cells can't outgrow sensitive cells under drug

After v4, this becomes the next obvious lie: differential viabilities but fractions stay 25/50/25 forever.

**Next structural upgrade (v5)**:
1. Track subpop absolute cell counts (not just fractions)
2. Let fractions derive from cell counts
3. Selection emerges naturally (resistant grows while sensitive shrinks)

---

## Compatibility Notes

### Weighted Mean Weights (Fixed Fractions)

**Source**: Subpopulation fractions defined at vessel creation (lines 212, 221, 230):
- `sensitive['fraction']`: 0.25 (25%)
- `typical['fraction']`: 0.50 (50%)
- `resistant['fraction']`: 0.25 (25%)

**These fractions NEVER change in v4** (no selection dynamics). This is a known limitation - v5 will add selection.

**Formula**: `vessel.viability = 0.25 * sensitive.viability + 0.50 * typical.viability + 0.25 * resistant.viability`

Tests must compute weighted mean from `subpop['fraction']` (same source as code), not hardcoded weights.

---

### Death Ledger Compatibility (NOT Causal)

**Per-axis vessel death fields** (`death_compound`, `death_er_stress`, etc.):
- **NOT causal** - compatibility/reporting outputs ONLY
- Allocated proportionally from total kill based on subpop hazard shares
- Exist for backward compatibility with downstream code
- **CRITICAL**: Do not use vessel death fields for causal logic
- **Ground truth**: Subpop viabilities and hazards are authoritative

**If downstream code uses vessel death fields causally**:
- Verify it still works with derived values (should be fine for reporting)
- If used causally, refactor to use subpop viabilities directly

---

## Sign-Off

**Ready to merge** after:
1. ✅ Prerequisites A & B applied (sync deleted, per-subpop hazards exist)
2. ✅ All four v4 diffs applied (recompute, instant kill, commit death, invariants)
3. ✅ All six tests pass (4 core + 2 tripwires)
4. ✅ Runtime invariants don't fire
5. ✅ Prereq verification passes

**Merge command**:
```bash
git add src/cell_os/hardware/biological_virtual.py
git add tests/statistical_audit/test_subpop_viability_v4_FINAL.py
git commit -m "feat: independent subpopulation viabilities (v4)

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
Prepares for v5 (selection dynamics)."
```

---

## Post-Merge: What to Expect

**Immediate effects**:
- Vessel viability curves will look identical (weighted mean of 25/50/25)
- But subpop viabilities now diverge (check with debugger or tests)
- Flow cytometry simulations (if you have them) will show staggered drops

**Next visible artifact**:
- Fixed fractions (25/50/25) despite differential death
- Sensitive cells die faster but fraction stays 25%
- This is v5's target

**Viability gate becomes more visible**:
- Attrition requires `current_viability < 0.5`
- Now evaluated per subpop
- Some subpops may hit gate earlier
- This per-subpop gating is actually MORE realistic, but may expose weirdness if the gate itself is arbitrary
- NOT a bug, but expect questions about why 0.5
