# Cell Line-Specific Passaging Architecture Analysis

**Date:** 2025-11-27  
**Repository:** `/Users/brighart/cell_OS/cell_OS`  
**Objective:** Evaluate current state and propose architecture for modular, cell-line-aware passaging workflows

**Status (Updated 2025-11-27):** ✅ **IMPLEMENTED** - Passaging, Thaw, and Feed operations are now fully data-driven via `data/cell_lines.yaml` and `ProtocolResolver`. The Cell Line Inspector dashboard tab provides visual validation of all resolved protocols.

---

## Current State

### A. Cell-Line-Specific Configuration

#### 1. **Primary Source: `src/cell_os/cell_line_database.py`**

**Format:** Python module with hardcoded `CellLineProfile` dataclass instances

**Schema:**
```python
@dataclass
class CellLineProfile:
    name: str
    cell_type: str  # "immortalized", "primary", "iPSC", "differentiated"
    
    # Dissociation
    dissociation_method: str  # "accutase", "tryple", "trypsin", "versene", "scraping"
    dissociation_notes: str
    
    # Transfection
    transfection_method: str
    transfection_efficiency: str
    transfection_notes: str
    
    # Transduction
    transduction_method: str
    transduction_notes: str
    
    # Freezing
    freezing_media: str  # "cryostor", "fbs_dmso", "bambanker", "mfresr"
    freezing_notes: str
    
    # Culture conditions
    coating: str  # "laminin_521", "matrigel", "plo", "none"
    media: str  # Primary media type
    
    # Cost profile
    cost_tier: str  # "budget", "standard", "premium"
```

**Example Entries:**
- **iPSC:**
  - `dissociation_method`: "versene"
  - `coating`: "laminin_521"
  - `media`: "mtesr_plus_kit"
  - `freezing_media`: "mfresr"
  - `cost_tier`: "premium"

- **HEK293:**
  - `dissociation_method`: "trypsin"
  - `coating`: "none"
  - `media`: "dmem_high_glucose"
  - `freezing_media`: "fbs_dmso"
  - `cost_tier`: "budget"

**Strengths:**
- ✅ Centralized cell line configuration
- ✅ Includes dissociation methods, media, coatings, freezing media
- ✅ Well-documented with notes
- ✅ Covers 15+ cell lines (HEK293, iPSC, hESC, A549, etc.)

**Limitations:**
- ❌ **No vessel-specific parameters** (e.g., T75 vs T25 volumes)
- ❌ **No volume specifications** (wash, detach, quench volumes)
- ❌ **No incubation parameters** (temperature, time)
- ❌ **No wash buffer specification** (assumes DPBS)
- ❌ **Hardcoded in Python** (not easily editable by non-programmers)

#### 2. **Vessel Specifications: `data/raw/vessels.yaml`**

**Format:** YAML

**Schema:**
```yaml
vessels:
  flask_t75:
    name: "T75 Flask"
    vendor: "THERMO SCI CELL CULT PLASTICS"
    catalog_number: "12565349"
    surface_area_cm2: 75.0
    working_volume_ml: 15.0
    coating_volume_ml: 8.0
    max_volume_ml: 250.0
    type: Flask
    well_count: 1
    footprint: T-Series_Flask
    volume_unit: mL
    consumable_id: t75_flask  # Links to pricing
```

**Strengths:**
- ✅ Comprehensive vessel library (6-well, 12-well, 24-well, 96-well, T25, T75, T175, T225)
- ✅ Includes working volumes and coating volumes
- ✅ Links to pricing via `consumable_id`

**Limitations:**
- ❌ **No cell-line-specific volumes** (working_volume_ml is vessel default, not cell-line-specific)
- ❌ **No passaging-specific parameters** (wash volume, detach volume, etc.)

#### 3. **Reagent Pricing: `data/raw/pricing.yaml`**

**Format:** YAML (1948 lines, comprehensive)

**Schema:**
```yaml
items:
  accutase:
    name: "StemPro Accutase"
    category: reagent
    vendor: "Thermo"
    catalog_number: "A1110501"
    pack_size: 100
    pack_unit: mL
    pack_price_usd: 74.65
    logical_unit: mL
    unit_price_usd: 0.7465
```

**Strengths:**
- ✅ Comprehensive reagent database (media, enzymes, coatings, consumables)
- ✅ Includes all dissociation reagents: `accutase`, `tryple_express`, `trypsin_edta`, `versene_edta`
- ✅ Includes all media types: `mtesr_plus_kit`, `dmem_high_glucose`, `neurobasal`, etc.
- ✅ Includes coatings: `laminin_521`, `matrigel`, `plo`, `pdl`
- ✅ Includes freezing media: `cryostor`, `bambanker`, `mfresr`, `dmso`
- ✅ Unit pricing for cost accounting

**Limitations:**
- ❌ **No logical role mapping** (e.g., which reagent is "growth_media" for which cell line)

#### 4. **LabWorldModel Integration**

**File:** `src/cell_os/lab_world_model/__init__.py`

**Current Structure:**
```python
@dataclass
class LabWorldModel:
    cell_registry: CellRegistry
    resource_costs: ResourceCosts
    workflow_index: WorkflowIndex
    experiment_history: ExperimentHistory
    resource_accounting: ResourceAccounting
    posteriors: Dict[CampaignId, DoseResponsePosterior]
```

**Strengths:**
- ✅ Modular architecture with clear separation of concerns
- ✅ `ResourceCosts` component for pricing
- ✅ `ResourceAccounting` for cost calculations
- ✅ `CellRegistry` for cell line information

**Limitations:**
- ❌ **No protocol/workflow resolver** component
- ❌ **CellRegistry doesn't currently use `cell_line_database.py`**
- ❌ **No integration between cell lines and passaging workflows**

---

### B. Unit Operations / Protocols

#### 1. **UnitOp Base Class: `src/cell_os/unit_ops/base.py`**

**Definition:**
```python
@dataclass
class UnitOp:
    uo_id: str = ""
    name: str = "Generic Op"
    layer: str = "base"
    category: str = "handling"
    time_score: int = 1
    cost_score: int = 1
    automation_fit: int = 1
    failure_risk: int = 1
    staff_attention: int = 1
    instrument: Optional[str] = None
    material_cost_usd: float = 0.0
    instrument_cost_usd: float = 0.0
    sub_steps: List['UnitOp'] = field(default_factory=list)
```

**Strengths:**
- ✅ Well-defined dataclass with cost tracking
- ✅ Supports hierarchical operations via `sub_steps`
- ✅ Includes automation metrics

**Limitations:**
- ❌ **No parameter/kwargs field** for storing operation-specific parameters
- ❌ **No reagent role abstraction**

#### 2. **Parametric Operations: `src/cell_os/unit_ops/parametric.py`**

**Current Passaging Implementation:**
```python
def op_passage(self, vessel_id: str, ratio: int = 1, dissociation_method: str = "accutase"):
    v = self.vessels.get(vessel_id)
    steps = []
    
    # 1. Aspirate old media
    steps.append(self.op_aspirate(vessel_id, v.working_volume_ml, ...))
    
    # 2. Wash with DPBS (hardcoded)
    steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dpbs", ...))
    steps.append(self.op_aspirate(vessel_id, v.working_volume_ml, ...))
    
    # 3. Enzymatic detach (conditional on method)
    if dissociation_method == "scraping":
        # ...
    elif dissociation_method == "versene":
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml * 0.2, "versene_edta", ...))
        steps.append(self.op_incubate(vessel_id, 10))
    else:  # accutase, tryple, trypsin
        enzyme = "accutase"
        if dissociation_method == "tryple": enzyme = "tryple_express"
        elif dissociation_method == "trypsin": enzyme = "trypsin_edta"
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml * 0.2, enzyme, ...))
        steps.append(self.op_incubate(vessel_id, 5))
    
    # 4. Quench, centrifuge, resuspend, count, re-plate
    # ...
```

**Strengths:**
- ✅ Implements complete passaging workflow
- ✅ Supports multiple dissociation methods
- ✅ Calculates costs via sub-steps
- ✅ Uses vessel library for volumes

**Limitations:**
- ❌ **Hardcoded reagent IDs** ("dpbs", "versene_edta", "accutase")
- ❌ **Hardcoded volumes** (e.g., `v.working_volume_ml * 0.2` for enzyme)
- ❌ **Hardcoded incubation times** (10 min for versene, 5 min for enzymes)
- ❌ **Hardcoded quench media** ("mtesr_plus_kit" regardless of cell line)
- ❌ **No cell-line parameter** (dissociation method must be passed explicitly)
- ❌ **No integration with `cell_line_database.py`**

#### 3. **Thaw Operation: `src/cell_os/unit_ops/parametric.py`**

```python
def op_thaw(self, vessel_id: str, cell_line: str = None):
    # ...
    # Conditional coating check
    coating_needed = False
    if cell_line and CELL_LINE_DB_AVAILABLE:
        profile = get_cell_line_profile(cell_line)
        if profile and profile.get('coating_required', False):
            coating_needed = True
    
    if coating_needed:
        steps.append(self.op_dispense(vessel_id, v.coating_volume_ml, "laminin_521"))
        # ...
```

**Strengths:**
- ✅ **Already uses `cell_line_database.py`!**
- ✅ Conditional coating based on cell line profile
- ✅ Detailed sub-step breakdown

**Limitations:**
- ❌ **Hardcoded coating reagent** ("laminin_521" instead of using profile.coating)
- ❌ **Hardcoded media** ("mtesr_plus_kit")
- ❌ **Partial integration** (only checks coating, not other parameters)

---

### C. LabWorldModel & Inventory Integration

#### 1. **Inventory System: `src/cell_os/inventory.py`**

**Key Class:**
```python
class Inventory:
    def __init__(self, pricing_yaml: str = "data/raw/pricing.yaml"):
        self.pricing = self._load_pricing(pricing_yaml)
    
    def get_price(self, item_id: str) -> float:
        # Returns unit_price_usd for an item
    
    def consume(self, item_id: str, quantity: float, unit: str):
        # Tracks consumption (if tracking enabled)
```

**Strengths:**
- ✅ Loads pricing from YAML
- ✅ Provides `get_price()` for cost calculation
- ✅ Supports consumption tracking

**Usage in UnitOps:**
```python
class ParametricOps:
    def __init__(self, vessels: VesselLibrary, inv: Inventory):
        self.vessels = vessels
        self.inv = inv
    
    def op_dispense(self, vessel_id, volume_ml, liquid_name, ...):
        unit_price = self.inv.get_price(liquid_name)
        mat_cost = unit_price * volume_ml
        # ...
```

**Strengths:**
- ✅ **Already integrated** with unit ops for cost calculation
- ✅ Uses reagent IDs from pricing.yaml

**Limitations:**
- ❌ **No role-based reagent lookup** (must pass exact reagent ID)

#### 2. **ResourceAccounting: `src/cell_os/lab_world_model/resource_accounting.py`**

**Purpose:** Aggregate costs from usage logs

**Integration:**
- LabWorldModel delegates cost computation to ResourceAccounting
- ResourceAccounting uses ResourceCosts (pricing data)

**Strengths:**
- ✅ Clean separation of cost accounting logic
- ✅ Can aggregate costs from workflow execution

**Limitations:**
- ❌ **No workflow-to-usage-log bridge** (workflows don't automatically generate usage logs)

---

## Gap Analysis

### What Exists ✅

1. **Cell Line Configuration**
   - ✅ Centralized database (`cell_line_database.py`) with dissociation methods, media, coatings
   - ✅ 15+ cell lines defined with method recommendations

2. **Vessel Specifications**
   - ✅ Comprehensive vessel library (`vessels.yaml`)
   - ✅ Working volumes, coating volumes, pricing links

3. **Reagent Pricing**
   - ✅ Complete reagent database (`pricing.yaml`)
   - ✅ All necessary reagents (enzymes, media, coatings, buffers)

4. **Unit Operations**
   - ✅ Well-defined `UnitOp` dataclass with cost tracking
   - ✅ Parametric operations (`op_passage`, `op_thaw`, etc.)
   - ✅ Hierarchical sub-steps for granular cost accounting

5. **Inventory Integration**
   - ✅ `Inventory` class for pricing lookup
   - ✅ Cost calculation in unit ops
   - ✅ `ResourceAccounting` for cost aggregation

6. **Partial Cell-Line Integration**
   - ✅ `op_thaw` already uses `cell_line_database.py` for coating decisions

### What's Missing ❌

1. **Cell-Line-Specific Passaging Parameters**
   - ❌ No vessel-specific volumes per cell line (e.g., T75 wash volume for iPSC vs HEK293)
   - ❌ No incubation parameters (temperature, time) per cell line/method
   - ❌ No wash buffer specification per cell line
   - ❌ No quench media specification per cell line

2. **Reagent Role Abstraction**
   - ❌ Operations use hardcoded reagent IDs ("dpbs", "mtesr_plus_kit")
   - ❌ No mapping from logical roles (growth_media, wash_buffer, detach_reagent) to concrete reagents
   - ❌ No way to say "use this cell line's growth media" without hardcoding

3. **Protocol Templates**
   - ❌ No abstract protocol definitions (YAML or otherwise)
   - ❌ Passaging logic is hardcoded in Python
   - ❌ No separation between protocol structure and cell-line-specific parameters

4. **Protocol Resolver**
   - ❌ No component to bind abstract protocols to cell-line-specific parameters
   - ❌ No API like `resolve_passage_protocol(cell_line, vessel_type) -> List[UnitOp]`

5. **LabWorldModel Integration**
   - ❌ `CellRegistry` doesn't use `cell_line_database.py`
   - ❌ No protocol/workflow resolver component in LabWorldModel
   - ❌ No bridge from cell line + vessel → concrete passaging workflow

6. **Data Format**
   - ❌ Cell line config is Python code (not easily editable)
   - ❌ No YAML/JSON config for cell-line-specific passaging parameters

---

## Proposed Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                     LabWorldModel                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │CellRegistry  │  │ResourceCosts │  │ProtocolResolver  │  │
│  │              │  │              │  │   (NEW)          │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐
│ cell_lines.yaml  │  │ pricing.yaml │  │ protocols/       │
│  (NEW)           │  │ (EXISTS)     │  │  passaging/      │
│                  │  │              │  │   pass_T75.yaml  │
│ - iPSC:          │  │ - accutase   │  │   (NEW)          │
│   media: mtesr   │  │ - dpbs       │  │                  │
│   detach: versene│  │ - ...        │  │ - steps:         │
│   coating: lam521│  │              │  │   - wash         │
│   passage:       │  │              │  │   - detach       │
│     T75:         │  │              │  │   - quench       │
│       wash: 15mL │  │              │  │   - ...          │
│       detach: 3mL│  │              │  │                  │
└──────────────────┘  └──────────────┘  └──────────────────┘
```

### Component Breakdown

#### 1. **Cell Line Configuration: `data/cell_lines.yaml`** (NEW)

**Purpose:** Centralized, editable cell line configuration with passaging parameters

**Schema:**
```yaml
cell_lines:
  iPSC:
    display_name: "Induced Pluripotent Stem Cells"
    cell_type: "iPSC"
    
    # Reagent roles
    growth_media: mtesr_plus_kit
    wash_buffer: dpbs
    detach_reagent: versene_edta
    coating:
      reagent: laminin_521
      dilution: "1:100"
      volume_per_cm2_uL: 0.5
    freezing_media: mfresr
    
    # Passaging parameters by vessel type
    passage:
      T75:
        volumes_mL:
          wash: 15.0
          detach: 3.0
          quench: 15.0  # Only if enzymatic
          collect: 18.0
          resuspend: 15.0
        incubation:
          detach:
            temp_C: 37
            minutes: 10
      T25:
        volumes_mL:
          wash: 5.0
          detach: 1.0
          quench: 5.0
          collect: 6.0
          resuspend: 5.0
        incubation:
          detach:
            temp_C: 37
            minutes: 10
    
    # Method preferences
    dissociation_method: versene  # Default
    transfection_method: nucleofection
    transduction_method: spinoculation
    
    # Cost tier
    cost_tier: premium

  HEK293:
    display_name: "HEK293 (Human Embryonic Kidney)"
    cell_type: "immortalized"
    
    growth_media: dmem_high_glucose
    wash_buffer: dpbs
    detach_reagent: trypsin_edta
    coating: null  # No coating needed
    freezing_media: fbs_dmso
    
    passage:
      T75:
        volumes_mL:
          wash: 10.0
          detach: 2.0
          quench: 10.0
          collect: 12.0
          resuspend: 10.0
        incubation:
          detach:
            temp_C: 37
            minutes: 5
      T25:
        volumes_mL:
          wash: 3.0
          detach: 0.5
          quench: 3.0
          collect: 3.5
          resuspend: 3.0
        incubation:
          detach:
            temp_C: 37
            minutes: 5
    
    dissociation_method: trypsin
    transfection_method: pei
    transduction_method: spinoculation
    cost_tier: budget
```

**Migration Strategy:**
- Convert `cell_line_database.py` entries to YAML
- Add vessel-specific passaging parameters
- Keep `cell_line_database.py` as deprecated fallback for 1-2 releases

#### 2. **Protocol Templates: `protocols/passaging/pass_T75_generic.yaml`** (NEW)

**Purpose:** Abstract passaging workflow with logical reagent roles

**Schema:**
```yaml
name: pass_T75_generic
description: "Generic T75 flask passaging protocol"
vessel_type: T75
category: passaging

steps:
  - step_id: aspirate_old_media
    uo_type: aspirate
    volume_key: working_volume  # From vessel spec
    
  - step_id: wash_1
    uo_type: dispense
    reagent_role: wash_buffer
    volume_key: wash
    
  - step_id: aspirate_wash_1
    uo_type: aspirate
    volume_key: wash
    
  - step_id: enzymatic_detach
    uo_type: dispense
    reagent_role: detach_reagent
    volume_key: detach
    
  - step_id: incubate_detach
    uo_type: incubate
    incubation_key: detach
    
  - step_id: quench_detach
    uo_type: dispense
    reagent_role: growth_media
    volume_key: quench
    condition: enzymatic  # Only if detach_reagent is enzymatic
    
  - step_id: collect_cells
    uo_type: aspirate
    volume_key: collect
    
  - step_id: centrifuge
    uo_type: centrifuge
    speed_g: 300
    minutes: 5
    
  - step_id: aspirate_supernatant
    uo_type: aspirate
    volume_key: collect
    
  - step_id: resuspend
    uo_type: dispense
    reagent_role: growth_media
    volume_key: resuspend
    
  - step_id: cell_count
    uo_type: count
    method: manual
    
  - step_id: replate
    uo_type: dispense
    reagent_role: growth_media
    volume_key: working_volume
    vessel_id: target  # New vessel
```

**Alternative:** Could also be defined in Python as a dataclass if YAML is too complex.

#### 3. **Protocol Resolver: `src/cell_os/protocol_resolver.py`** (NEW)

**Purpose:** Bind abstract protocols to concrete cell-line-specific parameters

**API:**
```python
class ProtocolResolver:
    def __init__(
        self, 
        cell_lines_config: str = "data/cell_lines.yaml",
        protocols_dir: str = "protocols/passaging",
        vessels: VesselLibrary = None,
        inventory: Inventory = None
    ):
        self.cell_lines = self._load_cell_lines(cell_lines_config)
        self.protocols = self._load_protocols(protocols_dir)
        self.vessels = vessels or VesselLibrary()
        self.inventory = inventory or Inventory()
    
    def resolve_passage_protocol(
        self, 
        cell_line_name: str, 
        vessel_type: str
    ) -> List[UnitOp]:
        """
        Resolve a passaging protocol for a specific cell line and vessel.
        
        Args:
            cell_line_name: e.g., "iPSC", "HEK293"
            vessel_type: e.g., "T75", "T25"
        
        Returns:
            List of concrete UnitOp instances with:
            - Reagent roles resolved to actual reagent IDs
            - Volume keys resolved to actual volumes
            - Incubation keys resolved to temp/time
        """
        # 1. Load cell line config
        cell_config = self.cell_lines[cell_line_name]
        
        # 2. Load protocol template
        protocol = self.protocols[f"pass_{vessel_type}_generic"]
        
        # 3. Get vessel spec
        vessel = self.vessels.get(f"flask_{vessel_type.lower()}")
        
        # 4. Get passaging params for this vessel
        passage_params = cell_config["passage"][vessel_type]
        
        # 5. Resolve each step
        unit_ops = []
        for step in protocol["steps"]:
            # Resolve reagent role
            if "reagent_role" in step:
                reagent_id = cell_config[step["reagent_role"]]
            else:
                reagent_id = None
            
            # Resolve volume
            if "volume_key" in step:
                if step["volume_key"] == "working_volume":
                    volume = vessel.working_volume_ml
                else:
                    volume = passage_params["volumes_mL"][step["volume_key"]]
            else:
                volume = None
            
            # Resolve incubation
            if "incubation_key" in step:
                incubation = passage_params["incubation"][step["incubation_key"]]
                temp = incubation["temp_C"]
                minutes = incubation["minutes"]
            else:
                temp, minutes = None, None
            
            # Create UnitOp
            uo = self._create_unit_op(
                step_type=step["uo_type"],
                reagent_id=reagent_id,
                volume=volume,
                temp=temp,
                minutes=minutes,
                vessel=vessel
            )
            unit_ops.append(uo)
        
        return unit_ops
    
    def _create_unit_op(self, step_type, reagent_id, volume, temp, minutes, vessel):
        # Delegate to existing ParametricOps methods
        # or create UnitOp directly with cost calculation
        pass
```

**Integration with LabWorldModel:**
```python
@dataclass
class LabWorldModel:
    # ... existing fields ...
    protocol_resolver: ProtocolResolver = field(init=False)
    
    def __post_init__(self):
        self.resource_accounting = ResourceAccounting(resource_costs=self.resource_costs)
        self.protocol_resolver = ProtocolResolver(
            vessels=VesselLibrary(),
            inventory=Inventory()
        )
    
    def get_passage_protocol(self, cell_line: str, vessel_type: str) -> List[UnitOp]:
        """Get a concrete passaging protocol for a cell line and vessel."""
        return self.protocol_resolver.resolve_passage_protocol(cell_line, vessel_type)
```

#### 4. **Enhanced CellRegistry: `src/cell_os/lab_world_model/cell_registry.py`**

**Current:** Stores cell_lines and assays DataFrames

**Proposed Enhancement:**
```python
class CellRegistry:
    def __init__(
        self, 
        cell_lines: pd.DataFrame = None,
        assays: pd.DataFrame = None,
        cell_lines_yaml: str = "data/cell_lines.yaml"
    ):
        self.cell_lines = cell_lines if cell_lines is not None else pd.DataFrame()
        self.assays = assays if assays is not None else pd.DataFrame()
        
        # NEW: Load cell line configs
        self.cell_line_configs = self._load_cell_line_configs(cell_lines_yaml)
    
    def get_cell_line_config(self, cell_line: str) -> Dict[str, Any]:
        """Get full configuration for a cell line."""
        return self.cell_line_configs.get(cell_line)
    
    def get_reagent_for_role(self, cell_line: str, role: str) -> str:
        """
        Get the reagent ID for a logical role.
        
        Args:
            cell_line: e.g., "iPSC"
            role: e.g., "growth_media", "wash_buffer", "detach_reagent"
        
        Returns:
            Reagent ID from pricing.yaml
        """
        config = self.get_cell_line_config(cell_line)
        return config.get(role)
```

---

## Concrete Next Steps

### Step 1: Create Cell Line Configuration YAML

**Goal:** Establish canonical cell line config with passaging parameters

**Files to Create:**
- `data/cell_lines.yaml`

**Content:**
- Migrate all entries from `cell_line_database.py` to YAML
- Add vessel-specific passaging parameters (T75, T25 at minimum)
- Include volumes, incubation parameters, reagent roles

**Constraints:**
- Do not delete `cell_line_database.py` yet (keep as deprecated fallback)
- Start with 3-5 cell lines (iPSC, HEK293, HEK293T, A549, HeLa)
- Ensure all reagent IDs match `pricing.yaml`

**Example Entry:**
```yaml
cell_lines:
  iPSC:
    display_name: "Induced Pluripotent Stem Cells"
    growth_media: mtesr_plus_kit
    wash_buffer: dpbs
    detach_reagent: versene_edta
    coating:
      reagent: laminin_521
    passage:
      T75:
        volumes_mL:
          wash: 15.0
          detach: 3.0
          quench: 0.0  # No quench for versene
          resuspend: 15.0
        incubation:
          detach:
            temp_C: 37
            minutes: 10
```

### Step 2: Create Protocol Template (Optional - Can Start with Python)

**Goal:** Define abstract passaging protocol structure

**Option A: YAML Template**
- Create `protocols/passaging/pass_T75_generic.yaml`
- Define steps with reagent roles and volume keys

**Option B: Python Dataclass** (Simpler for MVP)
- Create `src/cell_os/protocol_templates.py`
- Define protocol as a list of step dictionaries

**Recommendation:** Start with **Option B** (Python) for faster iteration

**Example:**
```python
# src/cell_os/protocol_templates.py
PASSAGE_T75_TEMPLATE = [
    {"uo": "aspirate", "volume_key": "working_volume"},
    {"uo": "dispense", "reagent_role": "wash_buffer", "volume_key": "wash"},
    {"uo": "aspirate", "volume_key": "wash"},
    {"uo": "dispense", "reagent_role": "detach_reagent", "volume_key": "detach"},
    {"uo": "incubate", "incubation_key": "detach"},
    {"uo": "dispense", "reagent_role": "growth_media", "volume_key": "quench", "condition": "enzymatic"},
    {"uo": "aspirate", "volume_key": "collect"},
    {"uo": "centrifuge", "speed_g": 300, "minutes": 5},
    {"uo": "aspirate", "volume_key": "collect"},
    {"uo": "dispense", "reagent_role": "growth_media", "volume_key": "resuspend"},
    {"uo": "count", "method": "manual"},
]
```

### Step 3: Implement Protocol Resolver

**Goal:** Create resolver to bind templates to cell-line-specific parameters

**Files to Create:**
- `src/cell_os/protocol_resolver.py`

**API:**
```python
class ProtocolResolver:
    def __init__(self, cell_lines_yaml, vessels, inventory):
        # Load cell line configs
        # Load protocol templates
        
    def resolve_passage_protocol(self, cell_line: str, vessel_type: str) -> List[UnitOp]:
        # 1. Get cell line config
        # 2. Get protocol template
        # 3. Get vessel spec
        # 4. Resolve each step
        # 5. Return list of UnitOps
```

**Implementation Notes:**
- Reuse existing `ParametricOps` methods where possible
- Calculate costs using `Inventory.get_price()`
- Handle conditional steps (e.g., quench only if enzymatic)

**Constraints:**
- Must be backwards compatible (don't break existing `op_passage`)
- Should work with existing `VesselLibrary` and `Inventory`

### Step 4: Integrate with LabWorldModel

**Goal:** Add protocol resolver to LabWorldModel

**Files to Edit:**
- `src/cell_os/lab_world_model/__init__.py`

**Changes:**
```python
@dataclass
class LabWorldModel:
    # ... existing fields ...
    protocol_resolver: ProtocolResolver = field(init=False)
    
    def __post_init__(self):
        # ... existing init ...
        self.protocol_resolver = ProtocolResolver(
            cell_lines_yaml="data/cell_lines.yaml",
            vessels=VesselLibrary(),
            inventory=Inventory()
        )
    
    def get_passage_protocol(self, cell_line: str, vessel_type: str) -> List[UnitOp]:
        return self.protocol_resolver.resolve_passage_protocol(cell_line, vessel_type)
```

**Constraints:**
- Do not break existing LabWorldModel constructors
- Make protocol_resolver optional (lazy init if needed)

### Step 5: Enhance CellRegistry (Optional)

**Goal:** Make CellRegistry aware of cell_lines.yaml

**Files to Edit:**
- `src/cell_os/lab_world_model/cell_registry.py`

**Changes:**
```python
class CellRegistry:
    def __init__(self, ..., cell_lines_yaml="data/cell_lines.yaml"):
        # ... existing init ...
        self.cell_line_configs = self._load_yaml(cell_lines_yaml)
    
    def get_cell_line_config(self, cell_line: str) -> Dict:
        return self.cell_line_configs.get(cell_line, {})
    
    def get_reagent_for_role(self, cell_line: str, role: str) -> str:
        config = self.get_cell_line_config(cell_line)
        return config.get(role)
```

**Constraints:**
- Backwards compatible (don't break existing CellRegistry usage)
- YAML loading should be optional (graceful fallback)

### Step 6: Update Existing op_passage (Refactor)

**Goal:** Make existing `op_passage` use the new resolver (optional)

**Files to Edit:**
- `src/cell_os/unit_ops/parametric.py`

**Changes:**
```python
def op_passage(self, vessel_id: str, cell_line: str = None, ratio: int = 1, dissociation_method: str = None):
    """
    Passage cells with optional cell-line-aware parameter resolution.
    
    If cell_line is provided, uses cell_lines.yaml for parameters.
    Otherwise, falls back to legacy hardcoded behavior.
    """
    if cell_line:
        # NEW: Use protocol resolver
        from cell_os.protocol_resolver import ProtocolResolver
        resolver = ProtocolResolver(vessels=self.vessels, inventory=self.inv)
        return resolver.resolve_passage_protocol(cell_line, vessel_type)
    else:
        # LEGACY: Existing hardcoded logic
        # ... (keep existing code) ...
```

**Constraints:**
- **Backwards compatible** (existing calls without cell_line still work)
- **Optional refactor** (can be done later)

### Step 7: Add Tests

**Goal:** Ensure protocol resolver works correctly

**Files to Create:**
- `tests/unit/test_protocol_resolver.py`

**Test Cases:**
```python
def test_resolve_passage_ipsc_t75():
    resolver = ProtocolResolver()
    ops = resolver.resolve_passage_protocol("iPSC", "T75")
    
    assert len(ops) > 0
    assert any("versene" in op.name.lower() for op in ops)
    assert any("mtesr" in op.name.lower() for op in ops)

def test_resolve_passage_hek293_t75():
    resolver = ProtocolResolver()
    ops = resolver.resolve_passage_protocol("HEK293", "T75")
    
    assert any("trypsin" in op.name.lower() for op in ops)
    assert any("dmem" in op.name.lower() for op in ops)

def test_cost_calculation():
    resolver = ProtocolResolver()
    ops = resolver.resolve_passage_protocol("iPSC", "T75")
    
    total_cost = sum(op.material_cost_usd + op.instrument_cost_usd for op in ops)
    assert total_cost > 0
```

**Constraints:**
- Do not break existing tests
- Use pytest fixtures for setup

### Step 8: Documentation

**Goal:** Document the new architecture

**Files to Create/Edit:**
- `docs/protocols/passaging_architecture.md`
- Update `README.md` with new features

**Content:**
- Architecture diagram
- Example usage
- Migration guide from hardcoded to config-based

---

## Summary

### Current State
- ✅ Cell line database exists (`cell_line_database.py`) but lacks passaging parameters
- ✅ Vessel library exists (`vessels.yaml`) with volumes
- ✅ Pricing database exists (`pricing.yaml`) with all reagents
- ✅ Unit ops exist (`parametric.py`) but use hardcoded reagents/volumes
- ✅ Inventory integration exists for cost calculation
- ✅ Partial cell-line integration in `op_thaw`

### Gaps
- ❌ No vessel-specific passaging parameters per cell line
- ❌ No reagent role abstraction
- ❌ No protocol resolver component
- ❌ Passaging logic is hardcoded in Python

### Proposed Solution
1. **Cell Line Config YAML** - Centralized, editable config with passaging parameters
2. **Protocol Templates** - Abstract protocol structure (start with Python, migrate to YAML later)
3. **Protocol Resolver** - Binds templates to cell-line-specific parameters
4. **LabWorldModel Integration** - Add resolver as component

### Implementation Path
1. Create `data/cell_lines.yaml` (migrate from `cell_line_database.py`)
2. Create `src/cell_os/protocol_resolver.py` with resolver logic
3. Integrate resolver into `LabWorldModel`
4. (Optional) Refactor existing `op_passage` to use resolver
5. Add tests and documentation

### Key Design Decisions
- **Start with Python templates** (not YAML) for faster iteration
- **Backwards compatible** (don't break existing code)
- **Modular** (resolver is separate component)
- **Reuse existing infrastructure** (VesselLibrary, Inventory, UnitOp)
- **Deprecate gradually** (keep `cell_line_database.py` for 1-2 releases)
