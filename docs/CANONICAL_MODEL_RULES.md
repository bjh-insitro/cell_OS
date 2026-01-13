# Canonical Model Rules: The Constitution

**Status:** ACTIVE
**Last Updated:** 2025-12-21
**Authority:** Architecture constraints that prevent translation proliferation

---

## Purpose

This document defines the rules for maintaining canonical types in cell_OS.
When Claude (or humans) go feral and start creating new ambiguous fields,
point at this constitution.

---

## Core Principles

### 1. **Canonical types live in `src/cell_os/core/`**

All types that define experimental semantics must live here:
- `experiment.py` - Well, Treatment, SpatialLocation
- `assay.py` - AssayType enum
- (future) `channel.py` - CellPaintingChannel enum

**NOT in:**
- `epistemic_agent/schemas.py` (legacy WellSpec)
- `hardware/` (simulator-specific types)
- `simulation/` (execution types)

### 2. **Legacy types may not be imported into `core/`**

Canonical types must not depend on legacy types. The dependency flows ONE WAY:

```
legacy types → core/legacy_adapters.py → core/experiment.py
     ↓                                        ↑
  (adapts to)                           (canonical)
```

**Forbidden:**
```python
# In core/experiment.py
from epistemic_agent.schemas import WellSpec  # ❌ NO
```

**Allowed:**
```python
# In core/legacy_adapters.py
from epistemic_agent.schemas import WellSpec  # ✓ OK (adapters only)
```

### 3. **All translations live in `core/legacy_adapters.py`**

Translation code lives in EXACTLY ONE FILE. Not scattered across:
- design_bridge.py
- world.py
- validators
- random helper functions

**Pattern:**
```python
def {source}_to_{dest}(input) -> OutputType:
    """Convert {source} -> {dest}.

    Expects input to have: [document fields]
    Maps: [document mappings]
    Does NOT map: [document exclusions]
    """
    return OutputType(...)
```

### 4. **No invented fields in adapters**

Adapters translate existing data, they do NOT invent values.

**Forbidden:**
```python
def adapter(input):
    return Well(
        assay="cell_painting",  # ❌ INVENTED
        operator="default",     # ❌ INVENTED
    )
```

**Allowed:**
```python
def adapter(input, *, assay: AssayType):  # ✓ Caller provides
    return Well(assay=assay)

def adapter(input):
    return Well(
        assay=AssayType.from_string(input.assay),  # ✓ Normalized, not invented
    )
```

### 5. **World executes physics only**

The world (simulation layer) enforces ONLY physical constraints:
- Budget exhausted (can't create wells out of nothing)
- Time travel (can't observe at negative time)
- Conservation of mass (cells don't appear/disappear)

**World does NOT enforce:**
- Scientific quality (confounding, power, replication)
- Policy constraints (calibration requirements)
- Design preferences (template choices)

**Rule:** If it's not a law of physics, it's not the world's job.

### 6. **Quality checks warn, policy refuses**

Scientific quality issues are WARNINGS from `DesignQualityChecker`.

Policy decisions (refuse/allow) belong to:
- EpistemicLoop (strict_mode parameter)
- Agent policy (RuleBasedPolicy, future learned policies)

**Forbidden:**
```python
# In world.py
if confounded:
    raise InvalidDesignError  # ❌ World shouldn't judge
```

**Allowed:**
```python
# In design_quality.py
if confounded:
    return QualityWarning(...)  # ✓ Warn, don't block

# In loop.py
if quality_report.blocks_execution:
    continue  # ✓ Policy decision
```

### 7. **Any new ambiguity requires an enum or canonical type**

If you're about to add a field that could be interpreted multiple ways, STOP.

Create a canonical type first:
- Time → `observation_time_h` with explicit semantics
- Assay → `AssayType` enum with normalization
- Channel → `CellPaintingChannel` enum (future)

**Forbidden:**
```python
@dataclass
class Foo:
    time: float  # ❌ What does this mean?
    assay: str   # ❌ What variants are valid?
```

**Allowed:**
```python
@dataclass
class Foo:
    observation_time_h: float  # ✓ Explicit semantics
    assay: AssayType           # ✓ Enum with normalization
```

### 8. **Semantic teeth prevent backsliding**

Every canonical type gets a test file that enforces:
1. Old names don't exist (`time_h`, `timepoint_h` banned)
2. Normalization works (all variants mapped)
3. Types are immutable (frozen=True)
4. Semantics are documented (docstrings checked)

**Pattern:**
```python
# tests/unit/test_{concept}_semantics.py
def test_well_has_no_ambiguous_time_fields():
    well_fields = {f.name for f in fields(Well)}
    assert "time_h" not in well_fields  # Old name banned
```

---

## Vocabulary Rules

### Time
- **Canonical:** `observation_time_h`
- **Meaning:** Hours since treatment start when assay readout is taken
- **Banned:** `time_h`, `timepoint_h`, `duration`, `time`

### Assay
- **Canonical:** `AssayType` enum
- **Variants:** Normalized via `AssayType.from_string()`
- **Banned:** Raw strings (`'cell_painting'`, etc.) in canonical types

### Channel Identity
- **Canonical:** `CellPaintingChannel` enum for channel identity
- **Meaning:** Channel is an identity (NUCLEUS, ER, MITO), NOT a feature name
- **Features:** Derived FROM channels (e.g., `f"{channel.short_name}_intensity"`)
- **Variants:** Normalized via `CellPaintingChannel.from_string()`
- **Banned:** Raw strings (`'nucleus'`, `'DNA'`, etc.) in canonical types
- **Banned:** Feature names in enum (e.g., `NUCLEUS_INTENSITY` - mixes layers)

### Treatment
- **Canonical:** `Treatment(compound, dose_uM)` composite object
- **Banned:** Flat `compound` and `dose_uM` fields on Well

### Location
- **Canonical:** `SpatialLocation(plate_id, well_id)` composite object
- **Banned:** `position_tag` field (too abstract), flat `plate_id`/`well_id` on Well

### Position
- **Canonical:** `SpatialLocation.position_class` property (derived, not stored)
- **Meaning:** Position classification derived FROM physical location (edge/center)
- **Pattern:** Property (computed), not field (stored)
- **Banned:** Storing position_tag separately from location
- **Banned:** Reverse inference (well_id → position_tag during aggregation)
- **Rule:** Abstraction may be derived from physical location, never stored independently

---

## Migration Pattern

When killing a translation:

1. **Define canonical type** with explicit semantics (docstring)
2. **Create adapters** in `core/legacy_adapters.py`
3. **Add semantic teeth tests** to prevent backsliding
4. **Update new code** to use canonical types
5. **Leave old code alone** (adapters bridge the gap)
6. **Eventually delete adapters** when all code migrated

**Do NOT:**
- Big-bang rewrites
- Update all call sites at once
- Break existing tests
- Force migration before ready

**DO:**
- Incremental changes
- Test at each step
- Document what changed
- Let old and new coexist temporarily

---

## Architecture Layers

```
┌─────────────────────────────────────────┐
│  Planning (epistemic_agent/agent/)      │ ← Action selection
├─────────────────────────────────────────┤
│  Quality (epistemic_agent/design_*)     │ ← Scientific warnings
├─────────────────────────────────────────┤
│  World Interface (epistemic_agent/world)│ ← Observable readouts
├─────────────────────────────────────────┤
│  Simulation (hardware/, biology/)           │ ← Pure physics
└─────────────────────────────────────────┘

         Adapters (core/legacy_adapters.py)
                      ↕
         Canonical Types (core/)
```

**Boundaries:**
- Planning → Quality: Proposals checked, warnings returned
- Quality → World: World ignores quality (executes anything physical)
- World → Simulation: World calls simulator, aggregates observations
- Canonical ← Legacy: Adapters convert, but never invent

---

## Common Violations (and How to Fix)

### ❌ **Violation:** New time field without explicit semantics
```python
@dataclass
class Experiment:
    time: float  # What does this mean?
```

**Fix:** Use canonical field with documented semantics
```python
@dataclass
class Experiment:
    observation_time_h: float  # Hours since treatment when measured
```

---

### ❌ **Violation:** String assay in canonical type
```python
@dataclass
class Well:
    assay: str  # Allows arbitrary strings
```

**Fix:** Use AssayType enum
```python
@dataclass
class Well:
    assay: AssayType  # Only valid assays allowed
```

---

### ❌ **Violation:** Adapter invents data
```python
def adapter(spec):
    return Well(
        assay="cell_painting",  # Invented!
    )
```

**Fix:** Make caller provide
```python
def adapter(spec, *, assay: AssayType):  # Caller must provide
    return Well(assay=assay)
```

---

### ❌ **Violation:** World validates design quality
```python
# In world.py
if confounded:
    raise InvalidDesignError("Design confounded")
```

**Fix:** Move to quality checker
```python
# In design_quality.py
if confounded:
    return QualityWarning(category='observation_time_mismatch', ...)
```

---

### ❌ **Violation:** Translation in multiple files
```python
# In design_bridge.py
timepoint_h = spec.time_h

# In world.py
time_h = assignment.timepoint_h

# In validator.py
observation_time = well.time_h
```

**Fix:** One adapter file
```python
# In core/legacy_adapters.py
def well_spec_to_well(spec):
    return Well(observation_time_h=spec.time_h)
```

---

## Enforcement

### Code Review Checklist

Before merging:
- [ ] New types in `core/` have explicit docstring semantics
- [ ] Adapters live in `core/legacy_adapters.py` (not scattered)
- [ ] No invented fields in adapters (caller provides or normalize)
- [ ] World doesn't validate quality (only physics)
- [ ] Quality checks return warnings (don't raise)
- [ ] Semantic teeth tests added for new canonical types
- [ ] No raw strings for assays/channels in canonical types

### When to Point at This Document

- Someone adds `time` without semantics → Point at Rule 7
- Someone invents default values in adapter → Point at Rule 4
- World starts refusing confounded designs → Point at Rules 5-6
- Translation code scattered across files → Point at Rule 3
- New code imports WellSpec into core/ → Point at Rule 2

---

## Examples of Good Architecture

### ✓ Canonical type with explicit semantics
```python
@dataclass(frozen=True)
class Well:
    """
    observation_time_h:
        Hours since treatment start when the assay readout is taken.
        This is the ONLY time field allowed in the canonical well model.
    """
    observation_time_h: float
```

### ✓ Adapter with forced honesty
```python
def well_assignment_to_well(assignment, *, assay: AssayType):
    """
    Requires:
    - assay: Must be provided by caller (WellAssignment doesn't specify)
    """
    return Well(assay=assay)  # Caller provides, we don't invent
```

### ✓ Quality checker that warns
```python
class DesignQualityChecker:
    def check(self, proposal) -> QualityReport:
        """Returns warnings, never raises."""
        warnings = []
        if confounded:
            warnings.append(QualityWarning(...))
        return QualityReport(warnings=warnings)
```

### ✓ World that's dumb
```python
def run_experiment(self, proposal) -> Observation:
    """Executes any physically valid proposal. No quality validation."""
    if budget_exceeded:
        raise ValueError  # Physics constraint
    # Just execute and return observations
```

---

## Version History

- **2025-12-21:** Initial constitution after `observation_time_h` and `AssayType` refactors
- **2025-12-21:** Added `CellPaintingChannel` enum for channel identity
- **2025-12-21:** Added `SpatialLocation.position_class` property for position semantics
- Future updates should be rare - these are foundational rules

---

*"Canonical types are the constitution. Legacy types are the old laws we're phasing out. Adapters are the bridge. This document is the judge."*
