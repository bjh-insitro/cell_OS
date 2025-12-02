# Parametric Operations Refactoring - Implementation Guide

## Overview

This guide shows how to refactor `src/cell_os/unit_ops/parametric.py` (1,344 lines) into a modular, maintainable structure.

---

## Current Structure (Problems)

```python
# parametric.py - 1,344 lines! 😱
class ParametricOps:
    def __init__(self, vessel_lib, pricing_inv):
        # ... setup
    
    def op_centrifuge(self, ...):      # Lines 45-66
        # ... 22 lines
    
    def op_thaw(self, ...):            # Lines 70-265
        # ... 196 lines! 😱
    
    def op_passage(self, ...):         # Lines 267-390
        # ... 124 lines
    
    def op_feed(self, ...):            # Lines 392-472
        # ... 81 lines
    
    # ... 16 more operations
```

**Problems**:
- ❌ Single file with 1,344 lines
- ❌ 20+ operations in one class
- ❌ Hard to test individual operations
- ❌ Difficult to extend
- ❌ Violates Single Responsibility Principle

---

## Proposed Structure (Solution)

```
src/cell_os/unit_ops/
├── __init__.py
├── base.py                    # Base classes and utilities
├── parametric.py              # Main facade (~100 lines)
├── operations/
│   ├── __init__.py
│   ├── base_operation.py      # Base operation class
│   ├── cell_culture.py        # thaw, passage, feed, seed
│   ├── transfection.py        # transduce, transfect
│   ├── vessel_ops.py          # centrifuge, coat
│   ├── harvest_freeze.py      # harvest, freeze
│   └── quality_control.py     # mycoplasma, sterility, karyotype
└── liquid_handling.py
```

---

## Step-by-Step Implementation

### Step 1: Create Base Operation Class

```python
# operations/base_operation.py
from typing import Dict, Any, Optional
from dataclasses import dataclass
from ..base import VesselLibrary

@dataclass
class OperationResult:
    """Result of an operation execution."""
    success: bool
    cost_usd: float
    duration_min: float
    metadata: Dict[str, Any]
    error: Optional[str] = None


class BaseOperation:
    """Base class for all parametric operations."""
    
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv):
        self.vessels = vessel_lib
        self.pricing = pricing_inv
    
    def get_cost(self, item_id: str) -> float:
        """Get cost of a single item from pricing."""
        try:
            return self.pricing["items"][item_id]["unit_price_usd"]
        except (KeyError, TypeError):
            return 0.0
    
    def get_cell_line_defaults(self, cell_line: str) -> Dict[str, Any]:
        """Get default parameters for a cell line."""
        # Implementation from original
        pass
    
    def execute(self, *args, **kwargs) -> OperationResult:
        """Execute the operation. Override in subclasses."""
        raise NotImplementedError
```

---

### Step 2: Create Cell Culture Operations

```python
# operations/cell_culture.py
from typing import Optional, List
from .base_operation import BaseOperation, OperationResult

class CellCultureOps(BaseOperation):
    """Operations for cell culture: thaw, passage, feed, seed."""
    
    def thaw(
        self,
        vessel_id: str,
        cell_line: Optional[str] = None,
        skip_coating: bool = False
    ) -> OperationResult:
        """
        Thaw cells from cryovial into culture vessel.
        
        Args:
            vessel_id: Target vessel ID
            cell_line: Cell line name (for defaults)
            skip_coating: Skip coating step if True
            
        Returns:
            OperationResult with cost, duration, and metadata
        """
        # Move implementation from original op_thaw
        # ... (196 lines from original)
        
        return OperationResult(
            success=True,
            cost_usd=total_cost,
            duration_min=total_duration,
            metadata={"vessel_id": vessel_id, "cell_line": cell_line}
        )
    
    def passage(
        self,
        vessel_id: str,
        ratio: int = 1,
        dissociation_method: str = "accutase",
        cell_line: Optional[str] = None
    ) -> OperationResult:
        """
        Passage cells (dissociate, split, re-plate).
        
        Args:
            vessel_id: Vessel to passage
            ratio: Split ratio (1:ratio)
            dissociation_method: Method to use
            cell_line: Cell line name
            
        Returns:
            OperationResult
        """
        # Move implementation from original op_passage
        # ... (124 lines from original)
        
        return OperationResult(
            success=True,
            cost_usd=total_cost,
            duration_min=total_duration,
            metadata={"ratio": ratio, "method": dissociation_method}
        )
    
    def feed(
        self,
        vessel_id: str,
        media: Optional[str] = None,
        cell_line: Optional[str] = None,
        supplements: Optional[List[str]] = None,
        name: Optional[str] = None
    ) -> OperationResult:
        """Feed cells (media change)."""
        # Move implementation from original op_feed
        # ... (81 lines from original)
        
        return OperationResult(
            success=True,
            cost_usd=total_cost,
            duration_min=total_duration,
            metadata={"media": media, "supplements": supplements}
        )
    
    def seed(
        self,
        vessel_id: str,
        num_cells: int,
        cell_line: Optional[str] = None,
        name: Optional[str] = None
    ) -> OperationResult:
        """Seed cells into a vessel."""
        # Move implementation from original op_seed
        # ...
        
        return OperationResult(
            success=True,
            cost_usd=total_cost,
            duration_min=total_duration,
            metadata={"num_cells": num_cells}
        )
```

---

### Step 3: Create Other Operation Classes

```python
# operations/transfection.py
class TransfectionOps(BaseOperation):
    """Transfection and transduction operations."""
    
    def transduce(self, vessel_id: str, virus_vol_ul: float = 10.0, 
                  method: str = "passive") -> OperationResult:
        """Transduce cells with viral vector."""
        # Implementation
        pass
    
    def transfect(self, vessel_id: str, method: str = "pei") -> OperationResult:
        """Transfect cells with plasmid DNA."""
        # Implementation
        pass


# operations/vessel_ops.py
class VesselOps(BaseOperation):
    """Vessel-related operations."""
    
    def centrifuge(self, vessel_id: str, duration_min: float, 
                   speed_rpm: float = 1000, **kwargs) -> OperationResult:
        """Centrifuge a vessel."""
        # Implementation
        pass
    
    def coat(self, vessel_id: str, agents: List[str] = None, 
             num_vessels: int = 1) -> OperationResult:
        """Coat vessel(s) with ECM proteins."""
        # Implementation
        pass


# operations/harvest_freeze.py
class HarvestFreezeOps(BaseOperation):
    """Harvest and freeze operations."""
    
    def harvest(self, vessel_id: str, dissociation_method: str = None,
                **kwargs) -> OperationResult:
        """Harvest cells for freezing or analysis."""
        # Implementation
        pass
    
    def freeze(self, num_vials: int = 10, freezing_media: str = "cryostor_cs10",
               **kwargs) -> OperationResult:
        """Freeze cells into cryovials."""
        # Implementation
        pass


# operations/quality_control.py
class QualityControlOps(BaseOperation):
    """Quality control and testing operations."""
    
    def mycoplasma_test(self, sample_id: str, method: str = "pcr") -> OperationResult:
        """Test for mycoplasma contamination."""
        # Implementation
        pass
    
    def sterility_test(self, sample_id: str, duration_days: int = 7) -> OperationResult:
        """Test for bacterial/fungal contamination."""
        # Implementation
        pass
    
    def karyotype(self, sample_id: str, method: str = "g_banding") -> OperationResult:
        """Karyotype analysis for chromosomal abnormalities."""
        # Implementation
        pass
```

---

### Step 4: Create Facade (Backward Compatible)

```python
# parametric.py - Main facade (~100 lines)
from typing import List, Optional
from .base import VesselLibrary
from .operations.cell_culture import CellCultureOps
from .operations.transfection import TransfectionOps
from .operations.vessel_ops import VesselOps
from .operations.harvest_freeze import HarvestFreezeOps
from .operations.quality_control import QualityControlOps

class ParametricOps:
    """
    Unified interface for all parametric operations.
    
    This is a facade that delegates to specialized operation classes.
    Maintains backward compatibility with the original API.
    """
    
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv):
        self.vessels = vessel_lib
        self.pricing = pricing_inv
        
        # Create specialized operation handlers
        self.cell_culture = CellCultureOps(vessel_lib, pricing_inv)
        self.transfection = TransfectionOps(vessel_lib, pricing_inv)
        self.vessel = VesselOps(vessel_lib, pricing_inv)
        self.harvest = HarvestFreezeOps(vessel_lib, pricing_inv)
        self.qc = QualityControlOps(vessel_lib, pricing_inv)
    
    # Backward-compatible delegation methods
    # These maintain the original API: op_*()
    
    def op_thaw(self, *args, **kwargs):
        """Thaw cells from cryovial. Delegates to CellCultureOps."""
        return self.cell_culture.thaw(*args, **kwargs)
    
    def op_passage(self, *args, **kwargs):
        """Passage cells. Delegates to CellCultureOps."""
        return self.cell_culture.passage(*args, **kwargs)
    
    def op_feed(self, *args, **kwargs):
        """Feed cells. Delegates to CellCultureOps."""
        return self.cell_culture.feed(*args, **kwargs)
    
    def op_seed(self, *args, **kwargs):
        """Seed cells. Delegates to CellCultureOps."""
        return self.cell_culture.seed(*args, **kwargs)
    
    def op_transduce(self, *args, **kwargs):
        """Transduce cells. Delegates to TransfectionOps."""
        return self.transfection.transduce(*args, **kwargs)
    
    def op_transfect(self, *args, **kwargs):
        """Transfect cells. Delegates to TransfectionOps."""
        return self.transfection.transfect(*args, **kwargs)
    
    def op_centrifuge(self, *args, **kwargs):
        """Centrifuge vessel. Delegates to VesselOps."""
        return self.vessel.centrifuge(*args, **kwargs)
    
    def op_coat(self, *args, **kwargs):
        """Coat vessel. Delegates to VesselOps."""
        return self.vessel.coat(*args, **kwargs)
    
    def op_harvest(self, *args, **kwargs):
        """Harvest cells. Delegates to HarvestFreezeOps."""
        return self.harvest.harvest(*args, **kwargs)
    
    def op_freeze(self, *args, **kwargs):
        """Freeze cells. Delegates to HarvestFreezeOps."""
        return self.harvest.freeze(*args, **kwargs)
    
    def op_mycoplasma_test(self, *args, **kwargs):
        """Mycoplasma test. Delegates to QualityControlOps."""
        return self.qc.mycoplasma_test(*args, **kwargs)
    
    def op_sterility_test(self, *args, **kwargs):
        """Sterility test. Delegates to QualityControlOps."""
        return self.qc.sterility_test(*args, **kwargs)
    
    def op_karyotype(self, *args, **kwargs):
        """Karyotype analysis. Delegates to QualityControlOps."""
        return self.qc.karyotype(*args, **kwargs)
```

---

## Benefits of This Refactoring

### Before
- ❌ 1,344 lines in one file
- ❌ 20+ methods in one class
- ❌ Hard to test individual operations
- ❌ Difficult to extend
- ❌ Poor organization

### After
- ✅ ~200-300 lines per file (manageable)
- ✅ Focused classes with single responsibility
- ✅ Easy to test each operation class independently
- ✅ Easy to add new operations (just add to appropriate class)
- ✅ Clear organization by operation type
- ✅ **100% backward compatible** via facade pattern

---

## Testing Strategy

```python
# tests/unit/test_cell_culture_ops.py
import pytest
from cell_os.unit_ops.operations.cell_culture import CellCultureOps
from cell_os.unit_ops.base import VesselLibrary

@pytest.fixture
def cell_culture_ops():
    vessel_lib = VesselLibrary()
    pricing = {"items": {...}}
    return CellCultureOps(vessel_lib, pricing)

def test_thaw_operation(cell_culture_ops):
    result = cell_culture_ops.thaw(
        vessel_id="T25_001",
        cell_line="HEK293T"
    )
    
    assert result.success
    assert result.cost_usd > 0
    assert result.duration_min > 0
    assert "vessel_id" in result.metadata

def test_passage_operation(cell_culture_ops):
    result = cell_culture_ops.passage(
        vessel_id="T25_001",
        ratio=3
    )
    
    assert result.success
    assert result.metadata["ratio"] == 3
```

---

## Migration Path

### Phase 1: Create New Structure (No Breaking Changes)
1. Create `operations/` directory
2. Create base operation class
3. Create specialized operation classes
4. Keep original `parametric.py` unchanged

### Phase 2: Add Facade (Backward Compatible)
1. Create new facade in `parametric.py`
2. Delegate to specialized classes
3. Run all existing tests - should pass!

### Phase 3: Deprecate Old Methods (Optional)
1. Add deprecation warnings to old methods
2. Update documentation
3. Migrate codebase to use new API

### Phase 4: Remove Old Code (Future)
1. After migration period, remove old implementation
2. Keep facade for backward compatibility

---

## File Size Comparison

| File | Before | After |
|------|--------|-------|
| parametric.py | 1,344 lines | ~100 lines (facade) |
| cell_culture.py | - | ~300 lines |
| transfection.py | - | ~150 lines |
| vessel_ops.py | - | ~200 lines |
| harvest_freeze.py | - | ~250 lines |
| quality_control.py | - | ~300 lines |
| **Total** | **1,344 lines** | **~1,300 lines** |

Same functionality, much better organized! 🎉

---

## Next Steps

1. Create `operations/` directory
2. Implement `base_operation.py`
3. Start with one operation class (e.g., `cell_culture.py`)
4. Test thoroughly
5. Repeat for other operation classes
6. Create facade
7. Run full test suite
8. Update documentation

---

**Estimated Time**: 8-12 hours  
**Risk**: Low (backward compatible)  
**Impact**: High (much more maintainable)
