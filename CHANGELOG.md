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

### Changed
- **Main Loop (`run_loop.py`)**:
    - Integrated `RecipeOptimizer` and `CostConstrainedSelector`.
    - Implemented budget tracking ("wallet") to simulate financial constraints.
    - Updated assay selection to be dynamic and budget-aware.
- **Unit Operations**:
    - Refactored `UnitOp` to support `sub_steps` for composite operations.
    - Moved from static `unit_ops.yaml` to dynamic `ParametricOps` class.
- **Inventory**:
    - Updated to support YAML-based pricing catalog (`data/raw/pricing.yaml`).

### Removed
- `data/raw/unit_ops.yaml`: Replaced by dynamic parametric operations.
