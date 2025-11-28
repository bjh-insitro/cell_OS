# Simulation and Synthetic Data Generation in cell_OS

**Status**: Phases 1, 2 & 3 Complete ✅ | Last Updated: 2025-11-28

## Executive Summary

cell_OS now has a **production-ready, data-driven biological simulation system** fully integrated with the workflow execution engine:
- ✅ **Phase 1**: `BiologicalVirtualMachine` with realistic cell growth, passage tracking, and dose-response
- ✅ **Phase 2**: Full integration with `WorkflowExecutor` - drop-in replacement for any hardware
- ✅ **Phase 3**: YAML-based parameter database - add cell lines/compounds without code changes
- Realistic synthetic data generation for ML training and benchmarking
- Stateful biological modeling across complete workflows
- Multi-vessel experiment simulation with realistic noise profiles
- 5 cell lines, 6 compounds pre-configured

**Quick Start**: 
```python
from cell_os.workflow_executor import WorkflowExecutor
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

executor = WorkflowExecutor(hardware=BiologicalVirtualMachine())
# Now all workflows use biological simulation with YAML parameters!
```

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

### **Phase 2: Framework Integration** ✅ **COMPLETE**

**Status**: Fully integrated with `WorkflowExecutor`

`BiologicalVirtualMachine` is now a **drop-in replacement** for the standard `VirtualMachine`:

**Integration Points**:
- ✅ Implements complete `HardwareInterface` contract
- ✅ Works with existing `WorkflowExecutor` via `hardware` parameter
- ✅ Compatible with all existing UnitOps from `parametric.py`
- ✅ Automatic state tracking across workflow execution
- ✅ Realistic biological simulation for all operations

**Usage with WorkflowExecutor**:
```python
from cell_os.workflow_executor import WorkflowExecutor
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.protocol_resolver import ProtocolResolver

# Initialize with biological simulation
hardware = BiologicalVirtualMachine(simulation_speed=0.0)
executor = WorkflowExecutor(hardware=hardware)
resolver = ProtocolResolver()

# Resolve and execute a real protocol
unit_ops = resolver.resolve_thaw("HEK293T", "T75")
execution = executor.create_execution_from_protocol(
    protocol_name="Thaw HEK293T",
    cell_line="HEK293T",
    vessel_id="T75_1",
    operation_type="thaw",
    unit_ops=unit_ops
)

# Execute with biological simulation
result = executor.execute(execution.execution_id)

# Access simulated biological state
vessel_state = hardware.get_vessel_state("T75_1")
print(f"Cell count: {vessel_state['cell_count']:.2e}")
print(f"Viability: {vessel_state['viability']:.2%}")
print(f"Passage: P{vessel_state['passage_number']}")
```

**Data Collection**:

For advanced data collection, use `SimulationExecutor`:

```python
from cell_os.simulation_executor import SimulationExecutor

# Initialize with automatic data collection
executor = SimulationExecutor(
    collect_data=True,
    simulation_speed=0.0
)

# Execute workflows
execution = executor.create_execution_from_protocol(...)
result = executor.execute(execution.execution_id)

# Export collected data
executor.export_data("results/simulation_data.json")
executor.export_data("results/simulation_data.csv", format='csv')

# Access vessel states
states = executor.get_vessel_states()
```

**Benefits**:
- ✅ Zero code changes to existing workflows
- ✅ Instant execution (configurable speed)
- ✅ Realistic biological outcomes
- ✅ State persistence across operations
- ✅ Data export for ML training

**Simulation Mode Flag**:

Control simulation behavior via `WorkflowExecutor` initialization:

```python
# Real hardware (when available)
from cell_os.hardware.opentrons import OpentronsInterface
executor = WorkflowExecutor(hardware=OpentronsInterface())

# Virtual simulation (basic)
from cell_os.hardware.virtual import VirtualMachine
executor = WorkflowExecutor(hardware=VirtualMachine())

# Biological simulation (realistic)
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
executor = WorkflowExecutor(hardware=BiologicalVirtualMachine())
```

**UnitOp-Level Simulation**:

The system automatically simulates all UnitOp types:
- **Liquid handling**: `aspirate`, `dispense`, `mix` - with volume tracking
- **Incubation**: `incubate` - cells grow based on doubling time
- **Cell operations**: `count_cells` - realistic counts with noise
- **Passage**: Custom handler via `passage_cells()` method
- **Treatment**: Custom handler via `treat_with_compound()` method

To add custom simulation for new UnitOp types, extend the hardware interface:

```python
class CustomBiologicalVM(BiologicalVirtualMachine):
    def custom_operation(self, **kwargs):
        # Implement custom biological simulation
        pass
```

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

### **Phase 2: Framework Integration** ✅ **COMPLETE**
- [x] Integrate `BiologicalVirtualMachine` with `WorkflowExecutor`
- [x] Add simulation mode flag to execution
- [x] Create synthetic data collection pipeline (`SimulationExecutor`)
- [x] Implement UnitOp-level simulation hooks

**Deliverables**:
- `BiologicalVirtualMachine` fully compatible with `WorkflowExecutor`
- `SimulationExecutor` for automatic data collection
- Drop-in replacement via `hardware` parameter
- Examples in `examples/simulate_workflows.py`

**Status**: Production ready - use `BiologicalVirtualMachine` in any workflow

### **Phase 3: Data-Driven Parameters** ✅ **COMPLETE**
- [x] Extend simulation with YAML parameter file (`data/simulation_parameters.yaml`)
- [x] Implement compound sensitivity database (6 compounds, 5 cell lines)
- [x] Add assay-specific noise profiles (cell line-specific CVs)
- [x] Create parameter management tool (`tools/manage_simulation_params.py`)

**Deliverables**:
- `data/simulation_parameters.yaml` - Centralized parameter database
- Updated `BiologicalVirtualMachine` to load from YAML
- `tools/manage_simulation_params.py` - Tool for adding cell lines/compounds
- Cell line-specific parameters: doubling time, confluence, passage stress, noise
- Compound-specific parameters: IC50 values per cell line, Hill slopes

**Features**:
```yaml
# data/simulation_parameters.yaml
cell_lines:
  HEK293T:
    doubling_time_h: 24.0
    max_confluence: 0.9
    passage_stress: 0.02
    cell_count_cv: 0.10
    
compound_sensitivity:
  staurosporine:
    HEK293T: 0.05
    HeLa: 0.08
    hill_slope: 1.2
```

**Usage**:
```python
from tools.manage_simulation_params import SimulationParameterManager

manager = SimulationParameterManager()

# Add new cell line
manager.add_cell_line("A549", doubling_time_h=22.0, max_passage=25)

# Add new compound
manager.add_compound("etoposide", ic50_values={"HEK293T": 2.5, "HeLa": 1.8})

# List all
manager.list_cell_lines()
manager.list_compounds()
```

**Benefits**:
- ✅ No code changes needed to add cell lines/compounds
- ✅ Easy parameter tuning and sensitivity analysis
- ✅ Centralized configuration
- ✅ Version control friendly (YAML)

**Status**: Production ready - 5 cell lines, 6 compounds configured

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
