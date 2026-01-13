# v4 Ship Sequence - Exact Order

**Date**: 2025-12-25
**Status**: Ready to execute

---

## Ship Sequence (Boring, Falsifiable, Hard to Lie)

Execute in exact order. Do not skip steps. Do not "continue anyway" if a check fails.

---

### Step 1: Run prereq tripwires first

**BEFORE touching any code**, establish baseline.

```bash
cd /Users/bjh/cell_OS
PYTHONPATH=.:$PYTHONPATH python3 tests/statistical_audit/test_v4_prereq_verification.py
```

**Expected result**: FAIL (prereqs not applied yet)

**Pass criteria** (for reference, after prereqs applied):
- After a step, subpops you manually separated stay separated
- No remaining call site to deleted sync helper
- Per-subpop hazard cache exists and populated for lethal exposure

**If these pass BEFORE applying prereqs**: Something is wrong with baseline test.

**Current status**: ✅ Baseline established (test fails as expected)

---

### Step 2: Apply Prereq A (Delete sync helper)

**File**: `src/cell_os/hardware/biological_virtual.py`

**Actions**:
1. Delete line 1018: `self._sync_subpopulation_viabilities(vessel)`
2. Delete lines 922-956: `_sync_subpopulation_viabilities` function definition

**Then do the dumb but necessary check**:

```bash
rg "_sync_subpopulation_viabilities" src/cell_os/hardware/biological_virtual.py
```

**Expected**: No results (function deleted everywhere)

**If results found**: Missed a call site or partial deletion. Fix before continuing.

---

### Step 3: Apply Prereq B (Per-subpop hazard computation)

**File**: `src/cell_os/hardware/biological_virtual.py`
**Location**: Replace lines ~1170-1224 (attrition computation in `_step_vessel`)

**Code**: See `PATCH_subpop_viability_v4_FINAL.md` Prerequisites section B (lines 77-173)

**Two runtime invariants to assert immediately in code** (not just tests):

#### Invariant 1: Reset hazards every step

```python
# At start of per-subpop loop in _step_vessel
for subpop_name in sorted(vessel.subpopulations.keys()):
    subpop = vessel.subpopulations[subpop_name]
    # Clear cache (prevents stale hazards on early return)
    if '_hazards' not in subpop:
        subpop['_hazards'] = {}
    if '_total_hazard' not in subpop:
        subpop['_total_hazard'] = 0.0
```

#### Invariant 2: No silent fallback for lethal doses

```python
# After computing dose_ratio with shifted IC50
dose_ratio = dose_uM / ic50_uM if ic50_uM > 0 else 0.0
if dose_ratio >= 1.0 and commitment_delay_h is None:
    raise ValueError(
        f"Missing commitment_delay_h for {subpop_name} at lethal dose "
        f"(dose_ratio={dose_ratio:.2f}). v3 sampling skipped?"
    )
```

**Why these matter**:
- Invariant 1: Prevents using stale hazards when step early-returns (e.g., viability = 0)
- Invariant 2: Turns missing delays from "silently wrong" to "loudly broken" (v3 contract enforcement)

---

### Step 4: Run the "real tell" check

After applying both prerequisites, verify they actually work:

```bash
python3 -c "
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
print(f'1. Hazards differ? {h_sens:.6f} > {h_res:.6f}: {h_sens > h_res}')
print(f'2. Viabilities diverging? {v_sens:.4f} < {v_res:.4f}: {v_sens < v_res}')
print(f'3. Vessel = weighted mean? |{vessel.viability:.4f} - {wm:.4f}| < 1e-9: {abs(vessel.viability - wm) < 1e-9}')

# Critical: Tell 1 MUST pass (Prereq B working)
assert h_sens > h_res, f'Hazards equal: {h_sens:.6f} vs {h_res:.6f}. Prereq B not working!'
print('✓ Real tell check 1 passed: Hazards differ (Prereq B works)')
"
```

**Pass criteria**:
- ✅ **Tell 1** (MUST pass): `h_sens > h_res` - Hazards differ (IC50 shifts used)
- ⚠️ **Tell 2** (may fail): `v_sens < v_res` - Viabilities diverging
- ⚠️ **Tell 3** (may fail): `abs(vessel - wm) < 1e-9` - Vessel is weighted mean

**What failures mean**:
- **Tell 1 fails**: Prereq B not applied correctly. IC50 shifts still unused. STOP.
- **Tell 2 fails**: Death application still vessel-level OR sync still called somewhere. Expected until v4 Diff 3.
- **Tell 3 fails**: Vessel still authoritative, not derived. Expected until v4 Diff 1.

**If Tell 1 fails**: Do NOT continue. Debug Prereq B. Print IC50 values per subpop to verify shifts applied.

**If Tell 1 passes**: Prerequisites work. Proceed to v4 diffs.

---

### Step 5: Apply the v4 four diffs

Only now. Do NOT skip straight to this step.

**File**: `src/cell_os/hardware/biological_virtual.py`

See `PATCH_subpop_viability_v4_FINAL.md` for exact code (lines 187-377).

#### Diff 1: Add recompute helper and initialize subpop fields

```python
def _recompute_vessel_from_subpops(self, vessel: VesselState):
    """
    Derive vessel viability and death_total from subpopulations.
    Subpop viability is authoritative. Vessel viability is readout.
    """
    total_v = 0.0
    for name in sorted(vessel.subpopulations.keys()):
        sp = vessel.subpopulations[name]
        frac = float(sp.get('fraction', 0.0))
        v = float(np.clip(sp.get('viability', 1.0), 0.0, 1.0))
        total_v += frac * v
    vessel.viability = float(np.clip(total_v, 0.0, 1.0))
    vessel.death_total = float(np.clip(1.0 - vessel.viability, 0.0, 1.0))
```

Also initialize `subpop['viability']` at vessel creation.

#### Diff 2: Fix `_apply_instant_kill` (lines 770-797)

Replace entire function. Key change: apply kill to each subpop, then call `_recompute_vessel_from_subpops`.

#### Diff 3: Fix `_commit_step_death` (lines ~798-880)

Replace entire function. Key change: apply survival per subpop using `subpop['_total_hazard']`, then call `_recompute_vessel_from_subpops`.

#### Diff 4: Add runtime invariants

Add at end of:
- `_apply_instant_kill`
- `_commit_step_death`
- `_step_vessel` (after viability clip at line ~1282)

```python
# INVARIANT: vessel.viability must equal weighted mean of subpops
wm = 0.0
for name in sorted(vessel.subpopulations.keys()):
    sp = vessel.subpopulations[name]
    wm += float(sp.get('fraction', 0.0)) * float(np.clip(sp.get('viability', 1.0), 0.0, 1.0))

assert abs(vessel.viability - wm) < 1e-9, \
    f"INVARIANT VIOLATION: vessel.viability ({vessel.viability:.10f}) != " \
    f"weighted mean ({wm:.10f}). Subpop viabilities are authoritative."
```

---

### Step 6: Run the full v4 test suite

```bash
# Prereq verification (should pass now)
PYTHONPATH=.:$PYTHONPATH python3 tests/statistical_audit/test_v4_prereq_verification.py

# v4 proper tests (6 tests: 4 core + 2 tripwires)
PYTHONPATH=.:$PYTHONPATH python3 tests/statistical_audit/test_subpop_viability_v4_FINAL.py
```

**Expected output**:
```
✓ Prereq A: No sync after step
✓ Prereq B: Per-subpop hazards exist and differ
✓ Prereq B: Commitment delays exist (v3 merged)
✓ All prerequisites verified - Ready for v4 diffs

✓ Vessel viability is weighted mean
✓ Instant kill creates divergence
✓ Sensitive dies earlier
✓ Subpop trajectories identical across runs (seed=42)
✓ One-step divergence verified
✓ No re-sync: viabilities remain distinct
✓ All v4 tests passed - READY TO SHIP
```

**If any test fails**:
- Test 3 fails (sensitive doesn't die earlier): Death application still vessel-level. Check Diff 3.
- Test 5 fails (viabilities don't diverge after 1 step): Vessel-level survival disguised as per-subpop.
- Test 6 fails (viabilities re-sync after treatment): Hidden sync call somewhere.
- Any invariant fires: Some code path still mutates vessel.viability directly.

---

### Step 7: Run "real tell" check again (all three tells should pass)

```bash
python3 -c "
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

# ALL THREE TELLS MUST PASS:
assert h_sens > h_res, f'Hazards equal: {h_sens:.6f} vs {h_res:.6f}'
assert v_sens < v_res, f'Viabilities not diverging: {v_sens:.4f} vs {v_res:.4f}'
assert abs(vessel.viability - wm) < 1e-9, f'Vessel != weighted mean: {vessel.viability:.10f} vs {wm:.10f}'

print('✓ All three tells pass:')
print(f'  1. Hazards differ: {h_sens:.6f} > {h_res:.6f}')
print(f'  2. Viabilities diverging: {v_sens:.4f} < {v_res:.4f}')
print(f'  3. Vessel = weighted mean: {vessel.viability:.6f} = {wm:.6f}')
print()
print('v4 ready to trust and ship.')
"
```

**Expected**: All three assertions pass.

---

## Sanity Checks Verified

### 1. Weighted mean weights specification

**Source**: Fixed subpopulation fractions defined at vessel creation:
- `sensitive['fraction']`: 0.25 (25%)
- `typical['fraction']`: 0.50 (50%)
- `resistant['fraction']`: 0.25 (25%)

**These fractions NEVER change in v4** (no selection dynamics).

**Tests compute weights from same source**: `subpop['fraction']` (not hardcoded).

**See**: `PATCH_subpop_viability_v4_FINAL.md` lines 25-34, `MERGE_CHECKLIST_v4.md` lines 294-305

### 2. Death ledgers are NOT causal

**Vessel-level death fields** (`death_compound`, `death_er_stress`, etc.):
- **NOT causal** - compatibility/reporting outputs ONLY
- Allocated proportionally from total kill based on subpop hazard shares
- Exist for backward compatibility with downstream code
- **Ground truth**: Subpop viabilities and hazards are authoritative

**See**: `PATCH_subpop_viability_v4_FINAL.md` lines 36-42, `MERGE_CHECKLIST_v4.md` lines 309-320

---

## What to Commit

After all steps pass:

```bash
git add src/cell_os/hardware/biological_virtual.py
git add tests/statistical_audit/test_subpop_viability_v4_FINAL.py
git add tests/statistical_audit/test_v4_prereq_verification.py
git commit -m "feat: independent subpopulation viabilities (v4)

Prerequisites:
- Delete _sync_subpopulation_viabilities (lie injector)
- Refactor attrition to per-subpop hazard computation
- IC50 shifts now actually used (not just defined)

Core changes:
- Make subpop viability authoritative (not vessel)
- Vessel viability derived as weighted mean (0.25, 0.50, 0.25)
- Instant kill and hazard death update subpops independently
- Enables sensitive subpops to die earlier than resistant

Death ledgers (death_compound, etc.) are now compatibility outputs,
NOT causal. Subpop viabilities are ground truth.

Enables falsification: flow cytometry time courses showing
differential survival curves per subpopulation.

Depends on v3 (commitment heterogeneity).
Prepares for v5 (selection dynamics)."
```

---

## Current Status

- ✅ Prereq tripwires written (`test_v4_prereq_verification.py`)
- ✅ v4 tests written (6 tests in `test_subpop_viability_v4_FINAL.py`)
- ✅ Baseline established (prereq test fails as expected)
- ✅ Documentation complete with sanity checks
- ✅ "Real tell" check specified with exact assertions
- ✅ Ship sequence documented (this file)

**Next**: Execute Steps 2-7 in order. Do not skip. Do not continue if checks fail.
