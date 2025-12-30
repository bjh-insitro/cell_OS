# Cell_OS Import Dependency Analysis - Comprehensive Report

**Date:** 2025-12-29
**Analyzed:** 347 Python modules in `src/cell_os/`

---

## Executive Summary

The cell_OS codebase is a large-scale biological simulation platform with:
- **347 modules** with **576 dependency edges**
- **6 circular dependency cycles** detected
- **17 modules** with excessive imports (>20)
- **111 modules** mixing relative and absolute import styles
- **74 potentially unused imports** across 46 files

### Severity Assessment
- **Critical Issues:** 6 circular dependencies (though some are mitigated with lazy imports)
- **High Priority:** 1 module with coupling score of 47 (biological_virtual.py)
- **Medium Priority:** Standardization of import styles, cleanup of unused imports
- **Low Priority:** Long dependency chains (acceptable in a complex domain model)

---

## 1. Top 10 Dependency Hotspots

These modules are most frequently imported and represent critical infrastructure:

| Imports | Module | Imported By | Depends On | Notes |
|---------|--------|-------------|------------|-------|
| 51 | `cell_os.hardware.constants` | 8 | 0 | **Pure constant definitions - good design** |
| 43 | `cell_os.hardware.injections.base` | 15 | 0 | **Base classes - good design** |
| 35 | `cell_os.posh_lv_moi` | 9 | 3 | Domain-specific logic |
| 31 | `cell_os.unit_ops.base` | 24 | 1 | **Core abstraction - critical** |
| 30 | `cell_os.hardware.biological_virtual` | 29 | 18 | **⚠️ HIGH COUPLING (47 total)** |
| 25 | `cell_os.epistemic_agent.schemas` | 12 | 0 | Schema definitions |
| 23 | `cell_os.inventory` | 20 | 0 | Resource management |
| 19 | `cell_os.hardware._impl` | 8 | 0 | Implementation utilities |
| 17 | `cell_os.unit_ops` | 6 | 0 | Unit operations |
| 16 | `cell_os.workflows` | 11 | 0 | Workflow definitions |

### Key Insights:
- **Constants and base classes** at the top is healthy architecture
- **biological_virtual.py** is a concerning outlier with high coupling
- Most hotspots have **0 outgoing dependencies**, indicating good abstraction

---

## 2. Circular Dependencies (Detailed Analysis)

### Cycle 1: **titration_loop ↔ titration_lab ↔ budget_manager**
```
titration_loop → titration_lab → budget_manager → titration_loop
```

**Status:** ✅ **Partially Mitigated**
**Location:**
- `/src/cell_os/titration_loop.py` (line 26)
- `/src/cell_os/titration_lab.py` (line 16)

**Mitigation Already in Place:**
```python
# In titration_loop.py
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cell_os.budget_manager import BudgetConfig
```

**Recommendation:** ✅ **No action needed** - TYPE_CHECKING pattern correctly applied

---

### Cycle 2: **upstream ↔ guide_design_v2**
```
upstream → guide_design_v2 → upstream
```

**Status:** ⚠️ **Partially Mitigated (Lazy Import)**
**Location:**
- `/src/cell_os/upstream.py` (line 60 - lazy import inside method)
- `/src/cell_os/guide_design_v2.py` (line 15)

**Current Mitigation:**
```python
# In upstream.py (inside _generate_with_solver method)
from cell_os.guide_design_v2 import GuideLibraryAdapter, GuideDesignConfig
```

**Problem:** While lazy import avoids runtime errors, it's still architectural coupling.

**Recommendation:** 🔧 **Extract Common Types**
```python
# Create: src/cell_os/guide_types.py
@dataclass
class GuideRNA:
    sequence: str
    target_gene: str
    # ... fields

@dataclass
class GeneTarget:
    symbol: str
    entrez_id: Optional[str] = None
    # ... fields

# Then both upstream.py and guide_design_v2.py import from guide_types
```

---

### Cycle 3: **biological_virtual ↔ detector_stack**
```
biological_virtual → detector_stack → biological_virtual
```

**Status:** ✅ **Correctly Mitigated**
**Location:**
- `/src/cell_os/hardware/biological_virtual.py` (line 2992)
- `/src/cell_os/hardware/detector_stack.py` (line 22)

**Mitigation:**
```python
# In detector_stack.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .biological_virtual import BiologicalVirtualMachine
```

**Recommendation:** ✅ **No action needed** - Best practice TYPE_CHECKING pattern

---

### Cycles 4-6: **Self-referential / False Positives**
- `hardware.beam_search`
- `core.experiment ↔ core.temporal_causality`
- `cell_thalamus.boundary_detection`

**Recommendation:** Requires manual inspection to determine if these are:
- False positives from analysis
- Legitimate lazy imports
- Actual issues needing refactoring

---

## 3. Modules with Excessive Imports

Modules with >20 imports suggest god objects or insufficient decomposition:

| Module | Total Imports | Cell_OS Deps | Severity |
|--------|--------------|--------------|----------|
| `hardware.biological_virtual` | **63** | 18 | 🔴 Critical |
| `epistemic_agent.loop` | **49** | 17 | 🔴 Critical |
| `hardware.assays.cell_painting` | **45** | 9 | 🟡 High |
| `epistemic_agent.observation_aggregator` | **30** | 8 | 🟡 High |
| `hardware.beam_search.search` | **29** | 6 | 🟡 High |
| `autonomous_executor` | **26** | 4 | 🟢 Medium |
| `lab_world_model` | **26** | 10 | 🟢 Medium |
| `api.routes.analysis` | **26** | 5 | 🟢 Medium |

### Critical Analysis: **biological_virtual.py**

**File:** `/src/cell_os/hardware/biological_virtual.py`

**Import Categories:**
```python
# Standard library (5)
import logging, numpy, yaml, pathlib, datetime

# Internal hardware modules (10)
from .virtual import VirtualMachine
from ..sim import biology_core
from .run_context import RunContext, ...
from .injection_manager import InjectionManager
from .operation_scheduler import OperationScheduler
from .assays import CellPaintingAssay, LDHViabilityAssay, ScRNASeqAssay
from .stress_mechanisms import (5 classes)
from .constants import (many constants)
from ._impl import utilities

# Other (18 total cell_os dependencies)
```

**Why so many imports?**
This is the **core VM** that integrates:
- Time advancement & scheduling
- Vessel operations
- Growth dynamics
- Death accounting
- Assay subsystems (3 types)
- Stress mechanisms (5 types)
- RNG management
- Parameter loading

**Verdict:** ⚠️ **Borderline Acceptable**
- This is genuinely a complex integration point
- Represents a clear architectural boundary (the VM)
- Could potentially split into smaller components, but may not improve clarity

**Refactoring Options:**
1. **Extract VM subsystems** into separate classes (injected via constructor)
   - `AssayManager` (manages all assay types)
   - `StressMechanismManager` (manages all stress mechanisms)
   - `SchedulingEngine` (time + operations)
2. **Create a facade** to hide internal complexity from callers
3. **Accept as-is** if this truly is the integration point for the biological VM

---

## 4. High Coupling Analysis

**Top 5 by Total Coupling** (imports + imported by):

| Module | Outgoing | Incoming | Total | Assessment |
|--------|----------|----------|-------|------------|
| `hardware.biological_virtual` | 18 | 29 | **47** | 🔴 Critical hub |
| `unit_ops.base` | 1 | 24 | **25** | ✅ Good (base class) |
| `unit_ops.parametric` | 11 | 12 | **23** | 🟡 Moderate |
| `epistemic_agent.loop` | 17 | 0 | **17** | 🟢 Leaf node |
| `lab_world_model` | 10 | 5 | **15** | 🟢 Acceptable |

### Critical: biological_virtual.py
- **47 coupling points** (highest in codebase)
- **29 modules depend on it** (single point of failure)
- **Depends on 18 modules** (tight integration)

**Risk Assessment:**
- Changes to this module can break 29 other modules
- Tight coupling makes testing difficult
- Represents architectural bottleneck

**Recommendations:**
1. **Introduce interfaces** for assays and stress mechanisms
2. **Dependency injection** instead of direct imports
3. **Extract subsystems** as mentioned above
4. **Comprehensive testing** given its criticality

---

## 5. Import Style Inconsistencies

**111 modules** mix relative and absolute imports, including:

```python
# Example from database/base.py
from cell_os.config import settings  # Absolute
from .cache import CacheManager        # Relative
```

**Affected Areas:**
- `database/*` (most modules)
- `workflow_execution/*`
- `hardware/*` (extensive)
- `core/*`

**Recommendation:** 🔧 **Standardize to Absolute Imports**

**Rationale:**
- More explicit and clear
- Better IDE support
- Easier refactoring
- PEP 8 recommendation for clarity

**Migration Strategy:**
```python
# Before (mixed)
from .cache import CacheManager
from cell_os.config import settings

# After (consistent absolute)
from cell_os.database.cache import CacheManager
from cell_os.config import settings
```

**Exceptions:**
- Within hardware/* package, relative imports may be acceptable for cohesion
- But should be consistent within each package

---

## 6. Potentially Unused Imports

**46 files** with **74 unused imports** detected (heuristic analysis).

### Top Offenders:

**wcb_crash.py** - 7 unused:
```python
# Line 9
import base64  # ❌ Unused

# Lines 18-22
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine  # ❌
from cell_os.workflow_executor import WorkflowExecutor  # ❌
from cell_os.unit_ops.parametric import ParametricOps  # ❌
from cell_os.unit_ops.base import VesselLibrary  # ❌
from cell_os.simulation.failure_modes import FailureModeSimulator  # ❌
```

**mcb_crash.py** - 5 unused (similar pattern)

**Common Patterns:**
- Type hints that were removed but imports remain
- Refactored code that removed usage
- Defensive imports "just in case"

**Recommendation:** 🧹 **Cleanup Pass**
- Use automated tools (e.g., `autoflake`, `pycln`)
- Manual review for false positives
- Estimated effort: 2-3 hours

---

## 7. Long Dependency Chains

**2,095 chains** of 5+ levels detected.

**Example Chain:**
```
titration_loop
  → titration_lab
    → budget_manager
      → recipe_optimizer
        → unit_ops.base
```

**Assessment:** 🟢 **Acceptable**
- This is a complex domain (biological simulation)
- Long chains reflect legitimate hierarchical dependencies
- Most chains follow logical layering

**No action needed** - this is expected in a large codebase with proper layering.

---

## 8. Refactoring Recommendations (Prioritized)

### Priority 1: CRITICAL (This Sprint)

#### 1.1 Resolve upstream ↔ guide_design_v2 Circular Dependency
- **Effort:** 2 hours
- **Strategy:** Extract common types to `guide_types.py`
- **Files affected:** 2

#### 1.2 Reduce biological_virtual.py Coupling
- **Effort:** 2-3 days
- **Strategy:**
  - Extract `AssayManager` class
  - Extract `StressMechanismManager` class
  - Inject dependencies instead of importing
- **Files affected:** 1 primary, ~10 callers to refactor

---

### Priority 2: HIGH (Next Sprint)

#### 2.1 Standardize Import Style
- **Effort:** 1 day (mostly automated)
- **Strategy:**
  - Run automated conversion tool
  - Manual review of hardware/* package
- **Files affected:** 111 modules

#### 2.2 Investigate False-Positive Cycles
- **Effort:** 4 hours
- **Files:** beam_search, core.experiment, boundary_detection
- **Strategy:** Manual inspection → apply TYPE_CHECKING pattern

---

### Priority 3: MEDIUM (Technical Debt)

#### 3.1 Cleanup Unused Imports
- **Effort:** 2-3 hours
- **Strategy:**
  ```bash
  pip install autoflake
  autoflake --remove-all-unused-imports --in-place --recursive src/cell_os/
  ```
- **Files affected:** 46 modules

#### 3.2 Split Large Modules
- **Candidates:**
  - `epistemic_agent.loop` (49 imports)
  - `hardware.assays.cell_painting` (45 imports)
- **Effort:** 1-2 days per module

---

### Priority 4: LOW (Future Consideration)

#### 4.1 Introduce Interface Abstractions
- Create ABCs for major extension points (assays, stress mechanisms)
- Use dependency injection throughout

#### 4.2 Dependency Inversion
- Higher-level modules should depend on abstractions
- Particularly for hardware subsystems

---

## 9. Positive Findings ✅

The codebase shows several **good architectural practices**:

1. **Proper use of TYPE_CHECKING** for breaking circular deps (detector_stack)
2. **Lazy imports** where needed (upstream.py)
3. **Clean base classes** (constants, injections.base) with 0 dependencies
4. **Clear layering** in most areas (reflected in dependency chains)
5. **No excessive fan-out** from most modules

---

## 10. Dependency Hotspot Monitoring

### Modules to Watch Closely:

| Module | Why Critical | Monitoring Strategy |
|--------|--------------|---------------------|
| `biological_virtual.py` | 47 coupling, 29 importers | Freeze API, comprehensive tests |
| `unit_ops.base` | 24 importers | Stable interface, no breaking changes |
| `hardware.constants` | 51 imports | Version constants carefully |
| `epistemic_agent.loop` | 49 imports | Consider splitting |

---

## 11. Tooling Recommendations

### Continuous Monitoring:
```bash
# Add to CI/CD pipeline
pip install pydeps
pydeps src/cell_os --max-bacon 3 --cluster

# Import linting
pip install flake8-import-order
flake8 src/cell_os --select=I

# Unused import detection
pip install autoflake
autoflake --check --remove-all-unused-imports src/cell_os
```

### Pre-commit Hooks:
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/PyCQA/autoflake
    hooks:
      - id: autoflake
        args: ['--remove-all-unused-imports', '--in-place']

  - repo: https://github.com/PyCQA/isort
    hooks:
      - id: isort
        args: ['--profile', 'black']
```

---

## 12. Architectural Insights

### What the Dependencies Reveal:

1. **Hardware Layer is Core:** The `hardware.*` modules are foundational
2. **Clear Separation:** Epistemic agent, unit ops, and simulation are well-separated
3. **Central VM Pattern:** biological_virtual.py is intentionally a central coordinator
4. **Domain Complexity:** Long chains reflect genuine domain modeling needs

### Suggested Layering (if not already enforced):

```
┌─────────────────────────────────────┐
│   Dashboard / API / CLI             │  ← User interfaces
├─────────────────────────────────────┤
│   Autonomous Executor / Loops       │  ← Orchestration
├─────────────────────────────────────┤
│   Epistemic Agent / Decision        │  ← Intelligence
├─────────────────────────────────────┤
│   Workflows / Unit Ops / Simulation │  ← Operations
├─────────────────────────────────────┤
│   Hardware VM / Biological Virtual  │  ← Core simulation
├─────────────────────────────────────┤
│   Database / Config / Schemas       │  ← Infrastructure
└─────────────────────────────────────┘
```

Dependencies should flow **downward only**. Any upward dependency is a candidate for:
- Interface extraction
- Dependency injection
- Event-based decoupling

---

## 13. Summary Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Total Modules | 347 | - | - |
| Circular Dependencies | 6 | 0 | 🔴 |
| Avg Imports/Module | 5.8 | <10 | ✅ |
| Modules >20 imports | 17 | <10 | 🟡 |
| Max Coupling Score | 47 | <30 | 🔴 |
| Mixed Import Styles | 111 | 0 | 🟡 |
| Unused Imports | 74 | 0 | 🟡 |

---

## 14. Next Steps

### Immediate (This Week):
- [ ] Fix `upstream ↔ guide_design_v2` circular dependency
- [ ] Investigate 3 false-positive cycles
- [ ] Document architectural boundaries

### Short Term (This Month):
- [ ] Refactor `biological_virtual.py` for lower coupling
- [ ] Standardize import styles (automated pass)
- [ ] Cleanup unused imports (automated pass)
- [ ] Add import monitoring to CI/CD

### Long Term (Next Quarter):
- [ ] Introduce interface abstractions for extensibility
- [ ] Comprehensive dependency inversion for testability
- [ ] Architectural documentation of layers
- [ ] Dependency budget enforcement in CI

---

## Appendix: Analysis Scripts

All analysis scripts are available in the repository root:

1. **analyze_imports.py** - Main dependency analysis
2. **analyze_unused_imports.py** - Unused import detection
3. **circular_dependency_analysis.py** - Detailed cycle analysis

### Running the Analysis:

```bash
# Full dependency analysis
python analyze_imports.py

# Unused imports
python analyze_unused_imports.py

# Detailed circular dependency report
python circular_dependency_analysis.py
```

---

**Analysis Complete:** 2025-12-29
**Analyst:** Claude Code (Automated Import Dependency Analysis)
**Next Review:** Recommended in 1 month
