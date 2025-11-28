# Simulation and Synthetic Data Generation in cell_OS

**Status**: Phase 1 Complete ✅ | Last Updated: 2025-11-28

## Executive Summary

cell_OS now has a **production-ready biological simulation system** via `BiologicalVirtualMachine`. This enables:
- Realistic synthetic data generation for ML training and benchmarking
- Stateful biological modeling (cell growth, passage tracking, dose-response)
- Multi-vessel experiment simulation with realistic noise profiles

**Quick Start**: See `examples/generate_synthetic_data.py` for ready-to-use data generation scripts.

---

## Current State Analysis

### 1. **Existing Simulation Capabilities**

#### A. **SimulationEngine** (`src/cell_os/simulation.py`)
- **Purpose**: Generates synthetic plate-based viability assay data
- **Features**:
  - Dose-response curves using 4-parameter logistic model
  - Batch effects (5% CV)
  - Pipetting noise (2% CV)
  - Measurement noise (5% SD)
  - Hardcoded IC50 values for specific cell line/compound pairs
  - Plate normalization against DMSO controls

**Strengths**:
- ✅ Realistic noise modeling (batch, pipetting, measurement)
- ✅ Well-structured for dose-response experiments
- ✅ Integrates with optimization loop (`scripts/run_loop.py`)

**Limitations**:
- ❌ Limited to viability assays only
- ❌ Hardcoded ground truth parameters (only 6 cell/compound pairs)
- ❌ No temporal dynamics (cell growth, passage effects)
- ❌ No spatial/plate effects (edge effects, gradients)
- ❌ No workflow-level simulation (doesn't simulate individual UnitOps)

#### B. **VirtualMachine** (`src/cell_os/hardware/virtual.py`)
- **Purpose**: HAL implementation for development/testing
- **Features**:
  - Simulates timing delays for operations
  - Returns mock success responses
  - Hardcoded cell count (1.5e6 cells, 98% viability)

**Strengths**:
- ✅ Fast execution (configurable speed multiplier)
- ✅ Clean abstraction for hardware operations

**Limitations**:
- ❌ No biological simulation (just timing)
- ❌ Returns constant values (no variability)
- ❌ Doesn't track state (e.g., cell growth over time)
- ❌ No resource consumption modeling

#### C. **SimulatedImagingExecutor** (`src/cell_os/simulated_executor.py`)
- **Purpose**: Imaging-specific simulation
- **Features**:
  - Viability and stress dose-response curves
  - Cell count and field quality metrics
  - Configurable noise

**Strengths**:
- ✅ Multi-readout simulation (viability + stress)
- ✅ Image quality metrics

**Limitations**:
- ❌ Isolated from main workflow system
- ❌ Hardcoded EC50 values

#### D. **MockSimulator** (`src/core/hardware_interface.py`)
- **Purpose**: Legacy HAL for older code
- **Features**:
  - Fluorescence measurement with Poisson MOI model
  - Generic protocol execution

**Strengths**:
- ✅ Includes transduction efficiency model

**Limitations**:
- ❌ Separate from new HAL architecture
- ❌ Not integrated with WorkflowExecutor

---

## 2. **Gaps and Improvement Opportunities**

### **Critical Gaps**

1. **No Workflow-Level Simulation**
   - Current: `VirtualMachine` just logs operations
   - Need: Simulate biological outcomes of each UnitOp
   - Example: `op_passage` should update cell count, viability, passage number

2. **No State Tracking**
   - Current: Each operation is stateless
   - Need: Track vessel contents, cell state, reagent usage over time
   - Example: Cells grow during incubation, die during trypsinization

3. **Limited Biological Diversity**
   - Current: 6 hardcoded cell/compound pairs
   - Need: Parameterized models for all cell lines in `cell_lines.yaml`

4. **No Temporal Dynamics**
   - Current: Static dose-response
   - Need: Cell growth curves, passage effects, senescence

5. **Disconnected Systems**
   - Current: 3+ separate simulation systems
   - Need: Unified simulation framework

---

## 3. **Recommended Improvements**

### **Phase 1: Enhanced VirtualMachine** ✅ **COMPLETE**

**Status**: Implemented in `src/cell_os/hardware/biological_virtual.py`

Created a **stateful, biologically-aware** `BiologicalVirtualMachine`:

**Implementation Highlights**:
- ✅ Cell growth modeling with exponential growth + confluence saturation
- ✅ Passage tracking with passage stress effects
- ✅ Dose-response simulation using 4-parameter logistic model
- ✅ Multi-vessel state management
- ✅ Realistic noise injection (10% CV cell counting, 2% CV viability, 5% biological)
- ✅ Time progression with incubation effects
- ✅ Comprehensive test suite (8 tests, all passing)

**Key Classes**:
```python
class VesselState:
    """Tracks biological state of a single vessel."""
    vessel_id: str
    cell_line: str
    cell_count: float
    viability: float
    passage_number: int
    confluence: float
    compounds: Dict[str, float]

class BiologicalVirtualMachine(VirtualMachine):
    """Enhanced HAL with biological simulation."""
    
    # Key methods:
    def seed_vessel(vessel_id, cell_line, initial_count, capacity)
    def count_cells(sample_loc, **kwargs) -> Dict[str, Any]
    def passage_cells(source, target, split_ratio) -> Dict[str, Any]
    def treat_with_compound(vessel_id, compound, dose_uM) -> Dict[str, Any]
    def incubate(duration_seconds, temperature_c) -> Dict[str, Any]
    def advance_time(hours)  # Updates all vessel states
```

**Usage Example**:
```python
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

vm = BiologicalVirtualMachine(simulation_speed=0.0)  # Instant execution

# Seed cells
vm.seed_vessel("T75_1", "HEK293T", initial_count=1e6, capacity=1e7)

# Grow for 24h (cells double)
vm.incubate(24 * 3600, 37.0)

# Passage 1:4
vm.passage_cells("T75_1", "T75_2", split_ratio=4.0)

# Treat with compound
vm.treat_with_compound("T75_2", "staurosporine", dose_uM=0.05)

# Measure
result = vm.count_cells("T75_2", vessel_id="T75_2")
print(f"Count: {result['count']:.2e}, Viability: {result['viability']:.2%}")
```

**Benefits**:
- ✅ Realistic cell growth curves
- ✅ Passage number tracking for quality control
- ✅ Minimal code changes (extends existing HAL)
- ✅ Drop-in replacement for `VirtualMachine` in `WorkflowExecutor`

**Data Generation**:
See `examples/generate_synthetic_data.py` for:
- Dose-response datasets
- Passage series tracking
- Growth curve generation

### **Phase 2: Unified Simulation Framework**

Create `src/cell_os/simulation_framework.py`:

```python
class BiologicalSimulator:
    """
    Central simulation engine that models:
    - Cell growth and death
    - Reagent consumption
    - Assay readouts (viability, imaging, flow cytometry)
    - Batch effects and noise
    """
    
    def __init__(self, cell_line_db, inventory):
        self.cell_line_db = cell_line_db
        self.inventory = inventory
        self.vessels = {}  # VesselID -> VesselState
        self.time = 0.0
        
    def execute_unitop(self, unitop: UnitOp) -> Dict[str, Any]:
        """
        Simulate a single UnitOp and update world state.
        Returns synthetic measurement data.
        """
        if unitop.operation == "seed":
            return self._simulate_seed(unitop)
        elif unitop.operation == "passage":
            return self._simulate_passage(unitop)
        elif unitop.operation == "treat":
            return self._simulate_treatment(unitop)
        # ... etc
        
    def _simulate_treatment(self, unitop: UnitOp) -> Dict[str, Any]:
        """Simulate compound treatment and generate dose-response data."""
        vessel = self.vessels[unitop.vessel_id]
        compound = unitop.parameters["compound"]
        dose = unitop.parameters["dose_uM"]
        
        # Get cell line-specific IC50
        cell_line = vessel.cell_line
        ic50 = self._get_ic50(cell_line, compound)
        
        # Apply dose-response model
        viability = self._logistic_model(dose, ic50)
        viability += np.random.normal(0, 0.05)  # Measurement noise
        
        # Update vessel state
        vessel.viability *= viability
        
        return {
            "viability": viability,
            "cell_count": vessel.cell_count * viability,
            "dose_actual": dose * np.random.normal(1.0, 0.02)  # Pipetting error
        }
```

**Benefits**:
- ✅ Single source of truth for simulation
- ✅ Integrates with WorkflowExecutor
- ✅ Tracks state across entire workflow

### **Phase 3: Data-Driven Biological Parameters**

Extend `data/cell_lines.yaml` with simulation parameters:

```yaml
HEK293T:
  profile:
    name: "HEK293T"
    cell_type: "immortalized"
    
  simulation:
    doubling_time_h: 24.0
    max_passage: 30
    senescence_rate: 0.01  # per passage
    seeding_efficiency: 0.85
    
    # Compound sensitivity (IC50 in μM)
    compound_sensitivity:
      staurosporine: 0.05
      tunicamycin: 0.80
      doxorubicin: 0.15
      
    # Assay-specific noise
    viability_assay_cv: 0.05
    cell_count_cv: 0.10
```

**Benefits**:
- ✅ Easy to add new cell lines
- ✅ Centralized parameter management
- ✅ Enables sensitivity analysis

### **Phase 4: Advanced Features**

1. **Spatial Simulation**
   - Edge effects in plates
   - Temperature gradients in incubators
   - Uneven liquid dispensing

2. **Multi-Assay Support**
   - Flow cytometry (multi-parameter)
   - High-content imaging (morphology)
   - qPCR (gene expression)
   - Western blot (protein levels)

3. **Failure Modes**
   - Contamination events (random)
   - Equipment failures
   - Out-of-spec reagents

4. **Experiment Design Validation**
   - Power analysis (can this design detect the effect?)
   - Batch confounding detection
   - Replication adequacy

---

## 4. **Implementation Roadmap**

### **Phase 1: Quick Wins** ✅ **COMPLETE**
- [x] Enhance `VirtualMachine.count_cells()` with growth model
- [x] Add cell line parameters to simulation
- [x] Create `BiologicalVirtualMachine` class
- [x] Implement passage tracking
- [x] Add dose-response simulation
- [x] Create comprehensive test suite
- [x] Build example data generation scripts

**Deliverables**:
- `src/cell_os/hardware/biological_virtual.py` (300+ lines)
- `tests/unit/test_biological_virtual_machine.py` (8 tests)
- `examples/generate_synthetic_data.py`

### **Phase 2: Framework Integration** 🚧 **IN PROGRESS**
- [ ] Integrate `BiologicalVirtualMachine` with `WorkflowExecutor`
- [ ] Add simulation mode flag to execution
- [ ] Create synthetic data collection pipeline
- [ ] Implement UnitOp-level simulation hooks

**Target**: Enable full workflow simulation with data collection

### **Phase 3: Data-Driven Parameters** 📋 **PLANNED**
- [ ] Extend `cell_lines.yaml` with simulation parameters
- [ ] Implement compound sensitivity database
- [ ] Add assay-specific noise profiles
- [ ] Create parameter estimation tools

**Target**: Easy addition of new cell lines and compounds

### **Phase 4: Advanced Features** 📋 **PLANNED**
- [ ] Spatial simulation (plate edge effects)
- [ ] Multi-assay support (flow cytometry, imaging)
- [ ] Failure mode injection
- [ ] Experiment design validation tools

**Target**: Production-grade simulation for ML training

---

## 5. **Example: End-to-End Simulation**

```python
# Initialize
sim = BiologicalSimulator(cell_line_db, inventory)
executor = WorkflowExecutor(hardware=sim)  # Use simulator as HAL

# Define workflow
workflow = [
    op_thaw("HEK293T", "T75"),
    op_feed("HEK293T", "T75", day=2),
    op_passage("HEK293T", "T75", "6-well", split_ratio=4),
    op_treat("HEK293T", "6-well", compound="staurosporine", doses=[0.01, 0.1, 1.0]),
    op_viability_assay("6-well")
]

# Execute and collect synthetic data
execution = executor.create_execution(workflow)
results = executor.execute(execution.execution_id)

# Results contain realistic synthetic measurements
print(results.steps[-1].result)
# {
#   "viability": [0.95, 0.65, 0.12],  # Dose-dependent
#   "cell_count": [1.2e6, 0.8e6, 0.15e6],
#   "cv": 0.05
# }
```

---

## 6. **Key Metrics for Success**

1. **Realism**: Synthetic data should be indistinguishable from real data in statistical tests
2. **Coverage**: Support all UnitOps in the system
3. **Performance**: Generate 1000s of experiments in seconds
4. **Reproducibility**: Same seed = same results
5. **Flexibility**: Easy to add new cell lines, assays, compounds

---

## 7. **Current vs. Proposed**

| Feature | Current | Proposed |
|---------|---------|----------|
| **State Tracking** | None | Full vessel/cell state |
| **Biological Models** | Hardcoded | Data-driven (YAML) |
| **Temporal Dynamics** | Static | Growth curves, passage effects |
| **Noise Sources** | 2-3 | 5+ (batch, pipetting, measurement, biological) |
| **Assay Types** | Viability only | Multi-modal (imaging, flow, etc.) |
| **Integration** | Separate systems | Unified via HAL |
| **Extensibility** | Hard to add | Config-driven |

---

## Conclusion

The current simulation infrastructure is **functional but limited**. The proposed improvements would create a **world-class synthetic data generation system** suitable for:
- Training ML models
- Benchmarking optimization algorithms
- Validating experimental designs
- Generating training datasets for new scientists

**Recommended Priority**: Start with **Phase 1** (Enhanced VirtualMachine) as it provides immediate value with minimal disruption.
