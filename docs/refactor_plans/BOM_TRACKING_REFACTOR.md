# Bill of Materials (BOM) Tracking Refactor Plan

## Problem Statement

Currently, `UnitOp` operations track aggregate costs (`material_cost_usd`, `instrument_cost_usd`) but do not maintain detailed itemized resource lists. This prevents the dashboard from displaying proper Bills of Materials for workflows, particularly for titration and other analytical workflows.

**Current Behavior:**
- Operations calculate total costs
- No tracking of *what* resources are consumed (specific reagents, consumables, etc.)
- `render_resources()` shows "No resources used" for most workflows
- Only MCB/WCB workflows (which use simulation wrappers) have partial resource tracking

**Desired Behavior:**
- All operations maintain a list of `BOMItem` objects in the `items` field
- Each `BOMItem` specifies `resource_id` and `quantity`
- Dashboard can display detailed, itemized BOMs for any workflow
- Costs are derived from item quantities × unit prices (single source of truth)

---

## Current Architecture

### Data Structures

```python
@dataclass
class UnitOp:
    # ... other fields ...
    material_cost_usd: float = 0.0
    instrument_cost_usd: float = 0.0
    items: List = field(default_factory=list)  # Recently added, not populated
```

### Operation Creation Pattern

Operations are created in specialized classes:
- `CellCultureOps` (thaw, passage, feed, seed)
- `HarvestFreezeOps` (harvest, freeze)
- `TransfectionOps` (transfect, transduce)
- `VesselOps` (coat, centrifuge)
- `ImagingOps` (fix, stain, image)
- `AnalysisOps` (flow cytometry, NGS, compute)
- `QCOps` (mycoplasma, sterility, karyotype)

**Current Implementation:** Operations hardcode costs rather than calculating from items.

```python
# Example from op_flow_cytometry
def op_flow_cytometry(self, vessel_id: str, num_samples: int = 96, name: str = None) -> UnitOp:
    return UnitOp(
        # ...
        material_cost_usd=0.5 * num_samples,  # Hardcoded cost
        instrument_cost_usd=20.0,
        sub_steps=[]
        # items=[]  # Empty!
    )
```

---

## Proposed Solution

### Define BOMItem Structure

```python
@dataclass
class BOMItem:
    resource_id: str
    quantity: float
    unit: str = "unit"  # mL, unit, well, etc.
    
    # Optional metadata
    category: str = "material"  # material, instrument_usage, service
```

### Update Base UnitOp

Already done - `items: List[BOMItem]` field exists.

### Refactor Operation Creation Methods

Each operation method should:

1. **Identify Resources**: Determine what materials/consumables are used
2. **Calculate Quantities**: Based on operation parameters
3. **Create BOMItems**: One for each resource
4. **Populate `items` field**: Add all BOMItems to the operation
5. **Calculate Costs**: Derive from `sum(item.quantity * pricing.get_price(item.resource_id))`

**Example Refactored Method:**

```python
def op_flow_cytometry(self, vessel_id: str, num_samples: int = 96, name: str = None) -> UnitOp:
    items = []
    
    # 1. Sheath fluid
    sheath_volume_per_sample = 0.5  # mL
    items.append(BOMItem(
        resource_id="flow_sheath_fluid",
        quantity=sheath_volume_per_sample * num_samples,
        unit="mL",
        category="material"
    ))
    
    # 2. Sample tubes or plate
    if num_samples <= 96:
        items.append(BOMItem(
            resource_id="plate_96well_u",
            quantity=1,
            unit="unit",
            category="material"
        ))
    else:
        num_tubes = num_samples
        items.append(BOMItem(
            resource_id="flow_tube_5ml",
            quantity=num_tubes,
            unit="unit",
            category="material"
        ))
    
    # 3. Instrument usage
    items.append(BOMItem(
        resource_id="flow_cytometer_usage",
        quantity=num_samples,
        unit="sample",
        category="instrument_usage"
    ))
    
    # Calculate costs from items
    material_cost = sum(
        item.quantity * self.inv.get_price(item.resource_id) 
        for item in items if item.category == "material"
    )
    instrument_cost = sum(
        item.quantity * self.inv.get_price(item.resource_id) 
        for item in items if item.category == "instrument_usage"
    )
    
    return UnitOp(
        uo_id=f"FlowCytometry_{vessel_id}",
        name=name if name else f"Flow Cytometry ({num_samples} samples)",
        layer="analysis",
        category="readout",
        time_score=60,
        cost_score=2,
        automation_fit=1,
        failure_risk=1,
        staff_attention=2,
        instrument="Flow Cytometer",
        material_cost_usd=material_cost,
        instrument_cost_usd=instrument_cost,
        items=items,
        sub_steps=[]
    )
```

### Add Helper Method for Cost Calculation

Add to `BaseOperation` class:

```python
def calculate_costs_from_items(self, items: List[BOMItem]) -> Tuple[float, float]:
    """Calculate material and instrument costs from BOMItems."""
    material_cost = sum(
        item.quantity * self.get_price(item.resource_id) 
        for item in items if item.category == "material"
    )
    instrument_cost = sum(
        item.quantity * self.get_price(item.resource_id) 
        for item in items if item.category == "instrument_usage"
    )
    return material_cost, instrument_cost
```

---

## Implementation Plan

### Phase 1: Foundation (2-3 hours)

**1.1 Define BOMItem Structure**
- [ ] Create `BOMItem` dataclass in `src/cell_os/unit_ops/base.py`
- [ ] Add proper type hints to `UnitOp.items` field
- [ ] Add `calculate_costs_from_items()` helper to `BaseOperation`

**Files:** `src/cell_os/unit_ops/base.py`, `src/cell_os/unit_ops/operations/base_operation.py`

**1.2 Populate Pricing Database**
- [ ] Audit existing resource IDs in `data/inventory.db`
- [ ] Add missing resource IDs needed for operations:
  - `flow_sheath_fluid`
  - `flow_tube_5ml`
  - `flow_cytometer_usage`
  - `ngs_reagent_kit`
  - `pcr_reagents`
  - `cell_counter_slides`
  - etc.
- [ ] Ensure all resources have `unit_price_usd` values

**Files:** `data/inventory.db` (via migration script)

### Phase 2: Core Operations (4-6 hours)

Refactor operations in priority order:

**2.1 Analysis Operations** (High Priority - affects Titration)
- [ ] `op_flow_cytometry` 
- [ ] `op_count`
- [ ] `op_compute_analysis`
- [ ] `op_ngs_verification`

**Files:** `src/cell_os/unit_ops/analysis.py`

**2.2 Cell Culture Operations** (High Priority - affects MCB/WCB)
- [ ] `op_thaw`
- [ ] `op_feed`
- [ ] `op_passage`
- [ ] `op_seed`
- [ ] `op_seed_plate`

**Files:** `src/cell_os/unit_ops/operations/cell_culture.py`

**2.3 Harvest & Freeze Operations**
- [ ] `op_harvest`
- [ ] `op_freeze`

**Files:** `src/cell_os/unit_ops/operations/harvest_freeze.py`

**2.4 Vessel Operations**
- [ ] `op_coat`
- [ ] `op_centrifuge`

**Files:** `src/cell_os/unit_ops/operations/vessel_ops.py`

### Phase 3: Specialized Operations (3-4 hours)

**3.1 Transfection/Transduction**
- [ ] `op_transfect`
- [ ] `op_transduce`

**Files:** `src/cell_os/unit_ops/operations/transfection.py`

**3.2 Imaging Operations**
- [ ] `op_fix_cells`
- [ ] `op_cell_painting`
- [ ] `op_imaging`

**Files:** `src/cell_os/unit_ops/imaging.py`

**3.3 QC Operations**
- [ ] `op_mycoplasma_test`
- [ ] `op_sterility_test`
- [ ] `op_karyotype`

**Files:** `src/cell_os/unit_ops/operations/qc_ops.py`

**3.4 Liquid Handling (Atomic)**
- [ ] `op_aspirate`
- [ ] `op_dispense`
- [ ] `op_incubate`

**Files:** `src/cell_os/unit_ops/liquid_handling.py`

### Phase 4: Testing & Validation (2-3 hours)

**4.1 Unit Tests**
- [ ] Test BOMItem creation
- [ ] Test cost calculation from items
- [ ] Test each refactored operation for correct item population
- [ ] Verify backward compatibility (costs match previous hardcoded values)

**Files:** `tests/unit/test_unit_ops_bom.py` (new)

**4.2 Integration Tests**
- [ ] Build workflows and verify `all_ops` have populated `items`
- [ ] Test MCB/WCB workflows
- [ ] Test Titration workflow
- [ ] Test Library Banking workflow

**Files:** `tests/integration/test_workflow_bom.py` (new)

**4.3 Dashboard Validation**
- [ ] Verify BOM rendering for Titration
- [ ] Verify BOM rendering for MCB/WCB
- [ ] Check cost breakdown charts
- [ ] Ensure no regressions in existing views

### Phase 5: Documentation & Cleanup (1-2 hours)

**5.1 Update Documentation**
- [ ] Document BOMItem structure
- [ ] Add examples of creating operations with items
- [ ] Update architecture diagrams

**Files:** `docs/architecture/unit_operations.md`

**5.2 Remove Fallback**
- [ ] Remove temporary fallback in `render_resources()`
- [ ] Clean up any debug logging

**Files:** `dashboard_app/components/campaign_visualizers.py`

---

## Migration Strategy

### Backward Compatibility

1. **Dual Mode Operation**: During transition, operations should:
   - Calculate costs from `items` if populated
   - Fall back to hardcoded costs if `items` is empty
   - Log warnings for operations missing items (dev mode only)

2. **Gradual Rollout**: Refactor operations in phases
   - Phase 2 (Core) can be done first
   - Other phases can follow incrementally
   - Dashboard falls back gracefully for un-refactored operations

### Data Validation

Add validation helpers:

```python
def validate_operation_bom(op: UnitOp) -> List[str]:
    """Validate that operation has proper BOM tracking."""
    issues = []
    
    if not op.items:
        issues.append(f"{op.uo_id}: No items populated")
    
    # Verify costs match items
    calc_mat, calc_inst = calculate_costs_from_items(op.items)
    if abs(calc_mat - op.material_cost_usd) > 0.01:
        issues.append(f"{op.uo_id}: Material cost mismatch")
    
    return issues
```

---

## Resource ID Naming Convention

Standardize resource IDs across the inventory:

### Categories

- **Consumables**: `{item_type}_{size}` (e.g., `tube_15ml`, `pipette_10ml`)
- **Media/Reagents**: `{reagent_name}` (e.g., `dmem_10fbs`, `cryostor_cs10`)
- **Instruments**: `{instrument}_usage` (e.g., `flow_cytometer_usage`, `bsc_usage`)
- **Services**: `{service_name}` (e.g., `cloud_compute_analysis`)

### Examples

```yaml
# Consumables
flask_t75: T75 Flask (unit)
tube_15ml: 15mL Conical Tube (unit)
pipette_10ml: 10mL Serological Pipette (unit)
tip_1000ul_lr: 1000µL Low Retention Tips (unit)
micronic_tube: Micronic 0.75mL Tube (unit)
plate_96well_u: 96-Well U-Bottom Plate (unit)

# Media & Reagents
dmem_10fbs: DMEM + 10% FBS (mL)
mtesr_plus_kit: mTeSR Plus Kit (mL)
cryostor_cs10: CryoStor CS10 (mL)
pbs: PBS (mL)
trypsin_edta: Trypsin-EDTA (mL)
accutase: Accutase (mL)
matrigel: Matrigel (unit)
vitronectin: Vitronectin (µL)

# Analysis Reagents
flow_sheath_fluid: Flow Cytometry Sheath Fluid (mL)
ngs_library_prep_kit: NGS Library Prep Kit (reaction)
pcr_master_mix: PCR Master Mix (µL)

# Instrument Usage
flow_cytometer_usage: Flow Cytometer Usage (sample)
bsc_usage: Biosafety Cabinet Usage (hour)
incubator_usage: Incubator Usage (hour)
centrifuge_usage: Centrifuge Usage (run)
sequencer_usage: NGS Sequencer Usage (lane)

# Services
cloud_compute_analysis: Cloud Compute Analysis (sample)
```

---

## Testing Checklist

### Unit Test Coverage

- [ ] `BOMItem` dataclass creation
- [ ] Cost calculation from items matches expected values
- [ ] Each operation method populates `items` correctly
- [ ] Quantities scale with parameters (e.g., `num_samples`)
- [ ] Edge cases (zero quantities, missing resources)

### Integration Test Coverage

- [ ] Full MCB workflow has complete BOM
- [ ] Full WCB workflow has complete BOM
- [ ] Titration workflow has complete BOM
- [ ] Library Banking workflow has complete BOM
- [ ] Costs from BOM match previous hardcoded costs (±$0.50)

### Dashboard Test Coverage

- [ ] Titration BOM displays correctly
- [ ] MCB BOM displays correctly
- [ ] WCB BOM displays correctly
- [ ] Cost breakdown pie chart renders
- [ ] Export to CSV/Excel works
- [ ] No performance regression

---

## Success Criteria

1. **All workflows display detailed BOMs** with itemized resources
2. **No "No resources used" messages** in dashboard
3. **Cost calculations are accurate** (match or improve upon hardcoded values)
4. **No breaking changes** to existing workflows
5. **Test coverage ≥ 90%** for BOM-related code
6. **Documentation complete** with examples

---

## Estimated Timeline

- **Phase 1 (Foundation)**: 2-3 hours
- **Phase 2 (Core Operations)**: 4-6 hours
- **Phase 3 (Specialized Operations)**: 3-4 hours
- **Phase 4 (Testing)**: 2-3 hours
- **Phase 5 (Documentation)**: 1-2 hours

**Total: 12-18 hours** (1.5 - 2.5 days)

**Recommended Approach**: Implement in phases over 1 week, allowing for testing and validation between phases.

---

## Risk Mitigation

### Risk: Breaking Existing Workflows

**Mitigation**: 
- Maintain backward compatibility during transition
- Comprehensive integration tests before each phase
- Feature flag to toggle between old/new BOM calculation

### Risk: Incomplete Resource Database

**Mitigation**:
- Audit all operation methods first to catalog resources
- Bulk-populate inventory before refactoring operations
- Add fallback for missing resource prices (log warning, use $1.00 default)

### Risk: Performance Impact

**Mitigation**:
- Profile BOM aggregation for large workflows
- Consider caching calculated costs
- Optimize database queries for batch price lookups

### Risk: Cost Discrepancies

**Mitigation**:
- Run parallel calculations (old vs. new) during transition
- Alert if differences exceed threshold
- Document and justify any intentional cost changes

---

## Open Questions

1. **Should `items` be flattened from `sub_steps`?**
   - If an operation has sub-steps, should parent aggregate all child items?
   - Current: Each operation tracks its own items independently
   
2. **How to handle variable pricing?**
   - Lot-specific pricing vs. catalog pricing
   - Should operations snapshot prices at creation time?
   
3. **Instrument usage units?**
   - Per-hour? Per-run? Per-sample?
   - Need standardization across all instrument resources

4. **Export format for BOM?**
   - CSV, Excel, PDF?
   - Should include metadata (workflow name, date, operator)?

---

## Future Enhancements

Beyond initial refactor:

1. **Real-time Inventory Depletion**: Operations consume from inventory when executed
2. **BOM Optimization**: Suggest workflow modifications to reduce costs
3. **Vendor Comparison**: Show cost differences across vendors
4. **Batch Ordering**: Aggregate BOMs across multiple workflows for bulk purchasing
5. **BOM Templates**: Save/load BOMs for recurring workflows
6. **What-If Analysis**: Compare costs of alternative protocols

---

**Status**: 🟡 **PLANNING** - Ready for implementation

**Owner**: TBD

**Reviewers**: TBD

**Last Updated**: 2025-12-01
