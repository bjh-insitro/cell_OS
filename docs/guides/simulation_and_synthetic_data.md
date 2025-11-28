# Simulation and Synthetic Data Generation in cell_OS

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

### **Phase 1: Enhanced VirtualMachine (Quick Win)**

Create a **stateful, biologically-aware** `VirtualMachine`:

```python
class BiologicalVirtualMachine(VirtualMachine):
    """
    Extends VirtualMachine with biological state tracking and synthetic data generation.
    """
    
    def __init__(self, simulation_speed: float = 1.0):
        super().__init__(simulation_speed)
        self.vessel_states = {}  # Track contents of each vessel
        self.time_tracker = 0.0  # Simulated time in hours
        
    def count_cells(self, sample_loc: str, **kwargs) -> Dict[str, Any]:
        """Generate realistic cell counts based on vessel state."""
        vessel_id = kwargs.get("vessel_id", "unknown")
        state = self.vessel_states.get(vessel_id, self._default_state())
        
        # Apply growth model
        hours_since_seed = self.time_tracker - state["last_passage_time"]
        doubling_time = state["cell_line_params"]["doubling_time_h"]
        
        count = state["initial_count"] * (2 ** (hours_since_seed / doubling_time))
        count *= np.random.normal(1.0, 0.1)  # 10% CV
        
        # Viability decreases with confluence
        confluence = count / state["vessel_capacity"]
        viability = 0.98 if confluence < 0.8 else 0.98 - (confluence - 0.8) * 0.5
        
        return {
            "status": "success",
            "count": count,
            "viability": viability,
            "confluence": confluence
        }
```

**Benefits**:
- ✅ Realistic cell growth
- ✅ Passage tracking
- ✅ Minimal code changes (extends existing HAL)

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

### **Week 1: Quick Wins**
- [ ] Enhance `VirtualMachine.count_cells()` with growth model
- [ ] Add cell line parameters to `cell_lines.yaml`
- [ ] Create `BiologicalVirtualMachine` class

### **Week 2: Framework**
- [ ] Design `BiologicalSimulator` API
- [ ] Implement core UnitOp simulations (seed, passage, feed)
- [ ] Integrate with `WorkflowExecutor`

### **Week 3: Data Generation**
- [ ] Implement treatment simulation with dose-response
- [ ] Add assay-specific readouts
- [ ] Create synthetic dataset generator for benchmarking

### **Week 4: Validation**
- [ ] Compare synthetic data to real lab data (if available)
- [ ] Tune noise parameters
- [ ] Document simulation assumptions

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
