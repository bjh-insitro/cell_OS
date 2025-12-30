# Meta-Test Hardening: Adversarial Review Response

## What Was Challenged

**Claim**: "syntactically impossible to write hardcoded death lists"

**Reality**: AST meta-test could be trivially bypassed with:
1. Binary ops: `TRACKED_DEATH_FIELDS | {"death_new"}`
2. Function calls: `sorted(["death_compound", "death_er"])`
3. Comprehensions: `["death_" + x for x in ["compound", "er"]]`
4. Dynamic building elsewhere and importing

## Hardening Applied

### 1. AST Meta-Test Enhanced (`test_no_hardcoded_death_lists.py`)

**Added Bypass Detection**:

```python
class DeathFieldListScanner(ast.NodeVisitor):
    def visit_List/Set/Tuple(self, node):
        # Original: catch literal collections

    def visit_BinOp(self, node):
        # NEW: catch TRACKED_DEATH_FIELDS | {...} or + (...)

    def visit_Call(self, node):
        # NEW: catch sorted([...death...]), sum([...death...])

    def visit_ListComp(self, node):
        # NEW: catch ["death_" + x for x in ...]
```

**Coverage Now Includes**:
- ✅ Literal List/Set/Tuple with `"death_"` strings (original)
- ✅ Binary ops (`|`, `+`) with death string collections
- ✅ Function calls wrapping death string collections
- ✅ Comprehensions dynamically building `"death_"` strings

**Still Bypassable** (but annoying enough):
- ❌ Building list in another module and importing (requires multi-file conspiracy)
- ❌ Using `dir(vessel)` + `.startswith("death_")` filter (AST can't catch this pattern reliably)

**Philosophy**: Don't need perfect static analysis. Just make bypassing annoying enough that nobody does it **by accident**.

### 2. Authority Contract Expanded (`test_tracked_fields_authority.py`)

**Added Invariants**:

```python
def test_tracked_fields_initialized_to_zero_at_seed():
    """All TRACKED_DEATH_FIELDS must be exactly 0.0 at seed time."""
    # Catches:
    # - Forgot to initialize (None)
    # - Wrong type (np.float32 instead of float)
    # - Non-zero initial value (leak from previous vessel)

    # Exception: death_unknown can be > 0 (seeding stress)

def test_tracked_fields_monotone_across_steps():
    """Death fields must be monotone non-decreasing."""
    # Catches:
    # - Accidental reset during stepping
    # - Negative hazard proposals
    # - Conservation violations that decrease fields

    # Allow DEATH_EPS tolerance for numerical noise
```

**Result**: Authority contract now stands alone - initialization and lifecycle invariants don't depend on Phase 6a tests.

### 3. Rhetoric Fixed

**Before**: "The code **refuses to compile**..."

**After**: "CI **refuses to merge**..." (Python compiles fine, meta-test fails in CI)

More honest about what "impossible" means in a dynamic language.

---

## Test Results

### ✅ 12/12 Meta-Tests Passing

**AST Hardening** (2):
- No hardcoded lists in `biological_virtual.py`
- No duplicates in `constants.py`

**Authority Contract** (10):
- Exclusion rules (unattributed, transport stub)
- Proposal validation
- Field matching
- **NEW**: Initialization to exactly 0.0
- **NEW**: Monotonicity across steps

**Integration**:
- Still passes 24h staurosporine simulation
- Still passes all Phase 6a physics tests

---

## Adversarial Test: Can You Bypass It?

### Easy Bypasses (Now Blocked)

```python
# 1. Binary op bypass (NOW CAUGHT)
credited = sum(TRACKED_DEATH_FIELDS | {"death_new"})
# → Fails: visit_BinOp detects literal set with "death_new"

# 2. Function call bypass (NOW CAUGHT)
for field in sorted(["death_compound", "death_er"]):
    ...
# → Fails: visit_Call detects literal list in sorted()

# 3. Comprehension bypass (NOW CAUGHT)
fields = ["death_" + x for x in ["compound", "er"]]
# → Fails: visit_ListComp detects dynamic "death_" construction
```

### Hard Bypasses (Still Possible, But Annoying)

```python
# 4. Multi-file conspiracy (HARD TO CATCH)
# my_constants.py
DEATH_SUBSET = ["death_compound", "death_er"]

# biological_virtual.py
from .my_constants import DEATH_SUBSET
for field in DEATH_SUBSET:  # Meta-test can't see this
    ...
# → Meta-test only scans biological_virtual.py AST
# → Would need import resolution to catch this

# 5. Runtime filter (VERY HARD TO CATCH)
fields = [f for f in dir(vessel) if f.startswith("death_")]
# → This is actually FINE if you then filter by TRACKED_DEATH_FIELDS
# → Only bad if you hardcode exclusions
```

**Decision**: Don't try to catch these. The multi-file conspiracy requires **intentional** bypass (not accident). The runtime filter is actually a reasonable pattern if done right.

---

## Philosophy: Good Tyranny

**Goal**: Make the bad pattern annoying enough that:
- ✅ Nobody does it **by accident**
- ✅ Intentional bypass requires obvious conspiracy (code review catches it)
- ❌ Don't need perfect static analysis (diminishing returns)

**Test Coverage**:
- Literal collections: ✅ Caught
- Binary ops: ✅ Caught
- Function calls: ✅ Caught
- Comprehensions: ✅ Caught
- Multi-file import: ❌ Not caught (but requires intent)
- Runtime filters: ❌ Not caught (but can be correct pattern)

**Correctness Hierarchy**:
1. **Structural** (meta-tests): Make bad pattern annoying
2. **Operational** (authority tests): Validate invariants hold in real flows
3. **Physics** (Phase 6a tests): Ensure scaling/conservation correct

All three layers pass. The tyranny is good enough.

---

## Remaining Vulnerabilities (Acceptable)

### 1. Multi-File Import Conspiracy

**Pattern**:
```python
# death_fields.py (new file)
LEGACY_FIELDS = ["death_compound", "death_er"]

# biological_virtual.py
from .death_fields import LEGACY_FIELDS
for f in LEGACY_FIELDS: ...  # Meta-test doesn't catch imports
```

**Why Accept**: Requires **two files** + **import statement** + **intentional bypass**. Code review will catch this. Not an accident.

**Mitigation**: Code review checklist: "New imports of death field lists?"

### 2. Runtime Filter with Hardcoded Exclusions

**Pattern**:
```python
# Get all death fields dynamically
all_death = [f for f in dir(vessel) if f.startswith("death_")]

# But then hardcode exclusions (BAD)
excluded = {"death_unattributed", "death_mode"}  # Forgot death_transport_dysfunction
active = [f for f in all_death if f not in excluded]
```

**Why Accept**: This is a **reasonable pattern** if exclusions come from a canonical set. Only bad if hardcoded. AST can't distinguish intent reliably.

**Mitigation**: Authority test `test_tracked_fields_matches_vessel_state_death_fields` catches drift between VesselState and TRACKED_DEATH_FIELDS. So this pattern only breaks if the excluded set diverges.

---

## Summary

**Before**: AST test caught literal List/Set/Tuple only (easy bypasses)

**After**: AST test catches literals + binops + calls + comprehensions (hard bypasses remain)

**Philosophy**: "Annoying enough that nobody does it by accident" > "perfect static analysis"

**Test Coverage**: 12 meta-tests (2 AST + 10 authority) all passing

**Deliverable**: The tyranny is good - not perfect, but good enough to prevent regression while staying pragmatic about Python's dynamic nature.
