# Changelog

All notable changes to the cell_OS project will be documented in this file.

## [Unreleased] - 2025-11-23

### Added
- **Cost-Aware Decision Support System**:
    - `RecipeOptimizer`: Automatically selects optimal methods (dissociation, freezing, etc.) based on cell type, budget tier, and automation requirements.
    - `WorkflowOptimizer`: Analyzes workflows to identify cost-saving opportunities and calculates ROI for method changes.
    - `CostConstrainedSelector`: Selects assays based on available budget, prioritizing either information gain or ROI.
- **Granular Cost Modeling**:
    - Implemented atomic unit operations (`op_aspirate`, `op_dispense`, `op_incubate`, `op_centrifuge`, `op_count`) for precise cost tracking.
    - Parameterized high-level operations (`op_passage`, `op_transfect`, `op_transduce`, `op_freeze`) to support multiple methods.
- **Automation Feasibility Analysis**:
    - `AutomationAnalysis` module to score operations and recipes for automation potential.
    - Labor cost estimation based on manual steps and staff attention scores.
- **Cell Line Database**:
    - Centralized database (`src/cell_line_database.py`) with optimal culture conditions and method defaults for 14 cell types.
- **Documentation**:
    - `ARCHITECTURE.md`: High-level system overview and data flow.
    - `COST_AWARE_DECISION_SUPPORT.md`: Detailed guide to the new optimization tools.
    - `AUTOMATION_SUMMARY.md`: Report on automation feasibility.
    - `REAGENT_PRICING_SUMMARY.md`: Comprehensive list of reagent costs.
- **Zombie POSH protocol implementation**, including decross‑linking, T7 IVT operations, and a complete recipe function.
- **Zombie POSH shopping list generator** (`src/zombie_posh_shopping_list.py`).
- **QC checkpoints** for Zombie POSH (`zombie_posh_qc_checkpoints.md`).
- **Modular Cell Painting panel system** (`src/cellpaint_panels.py`) with core, specialized (NeuroPaint, HepatoPaint, ALSPaint), and custom panels, plus automatic secondary antibody selection.
- **Updated pricing.yaml** with detailed reagent costs for Zombie POSH and new Cell Painting dyes/antibodies.
- **Verification script** `tests/integration/verify_zombie_posh.py` to validate Zombie POSH operations and cost savings.
- **Refactored `src/unit_ops.py`** to include new operations (`op_decross_linking`, `op_t7_ivt`, `op_hcr_fish`, `op_ibex_immunofluorescence`) and updated the Zombie POSH recipe.
- **Updated documentation files** (`zombie_posh_protocol.md`, `zombie_posh_inhouse_protocol.md`).

### Changed
- **Main Loop (`run_loop.py`)**:
    - Integrated `RecipeOptimizer` and `CostConstrainedSelector`.
    - Implemented budget tracking ("wallet") to simulate financial constraints.
    - Updated assay selection to be dynamic and budget‑aware.
- **Unit Operations**:
    - Refactored `UnitOp` to support `sub_steps` for composite operations.
    - Moved from static `unit_ops.yaml` to dynamic `ParametricOps` class.
    - **Refactored `unit_ops.py` into a package** (`src/cell_os/unit_ops/`) with submodules for liquid handling, incubation, imaging, and analysis.
- **Inventory**:
    - Updated to support YAML‑based pricing catalog (`data/raw/pricing.yaml`).
- **Executors**:
    - Consolidated simulated executors: `simulated_perturbation_executor.py` is now canonical; `simulated_executor.py` archived.
- **LabWorldModel**:
    - **Refactored `lab_world_model.py` into a package** (`src/cell_os/lab_world_model/`) with components: `cell_registry`, `experiment_history`, `resource_costs`, `workflow_index`.
    - **Added `resource_accounting` module** for cost calculations from usage logs.
    - Enhanced `ResourceCosts` with `get_unit_price()` method.
    - Preserved full backward compatibility.
- **Inventory**:
    - **Added automatic usage logging** to `consume()` method for cost tracking.
- **Scenario Execution**:
    - **Added cost reporting** to `run_scenario.py` with detailed breakdown by resource.
- **Workflows**:
    - Moved `zombie_posh_shopping_list.py` to `src/cell_os/workflows/`.
    - Fixed workflows package structure (converted `workflows.py` to `workflows/__init__.py`).

### Removed
- `data/raw/unit_ops.yaml`: Replaced by dynamic parametric operations.
```
