# cell_OS

**A Silicon-based "Lila SSI" for Autonomous Cell Biology.**

`cell_OS` is a prototype operating system for autonomous scientific discovery. It is designed to reason about biological experiments, manage resources, and execute goal-directed campaigns.

## Core Architecture

The system is built on three pillars of "Scientific Superintelligence" (SSI):

1.  **World Model (Phase 0)**: A probabilistic representation of the biological world (Gaussian Processes), learned from baseline data.
2.  **Campaign Manager (Goal Seeking)**: A high-level orchestration layer that pursues specific scientific objectives (e.g., "Find a selective compound").
3.  **Economic Engine (Physics of Cost)**: A detailed economic model that calculates the true cost, time, and risk of assays by breaking them down into atomic Unit Operations (UOs) and Bill of Materials (BOM).

## Key Features

*   **Closed-Loop Experimentation**: Automatically proposes, executes (simulates), and analyzes experiments to reduce uncertainty.
*   **Mission Logs**: Generates human-readable narratives explaining the agent's decision-making process.
*   **Cost-Aware Decision Support**: Intelligent agent that optimizes for budget.
    *   **Recipe Optimizer**: Auto-selects methods (e.g., "trypsin" vs "accutase") based on cell type and budget.
    *   **Workflow Optimizer**: Identifies cost-saving opportunities and calculates ROI.
    *   **Automation Analysis**: Scores protocols for automation feasibility.

## Directory Structure

```
cell_OS/
├── data/
│   ├── raw/
│   │   ├── pricing.yaml             # Price catalog (Reagents, Plastics, Services)
│   │   ├── vessels.yaml             # Labware definitions
│   │   └── ...
├── src/
│   ├── acquisition.py    # Decision engine (Max Uncertainty)
│   ├── assay_selector.py # Budget-aware assay selection
│   ├── automation_analysis.py # Automation feasibility scoring
│   ├── campaign.py       # Goal definitions
│   ├── cell_line_database.py # Cell type specific defaults
│   ├── inventory.py      # Inventory and Cost calculation logic
│   ├── modeling.py       # Gaussian Process models
│   ├── recipe_optimizer.py # Method optimization logic
│   ├── reporting.py      # Mission Log generator
│   ├── simulation.py     # In-silico wet lab
│   ├── unit_ops.py       # Recipe definitions
│   └── workflow_optimizer.py # ROI analysis
├── results/              # Experiment outputs and logs
├── run_loop.py           # Main entry point
└── requirements.txt
```

## Getting Started

### 1. Setup Environment
```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### 2. Run a Campaign
The default campaign seeks a compound selective for HepG2 over U2OS, optimizing for budget.
```bash
python run_loop.py
```

### 3. Verify Costs & Optimization
Check the cost models and decision support tools:
```bash
# Verify Cost-Aware System (Recipe & Workflow Optimization)
python verify_cost_aware_system.py

# Verify Automation Analysis
python verify_automation_analysis.py

# Verify Cell Line Database
python verify_cell_line_database.py
```

## Documentation

-   [System Architecture](ARCHITECTURE.md)
-   [Cost-Aware Decision Support](COST_AWARE_DECISION_SUPPORT.md)
-   [Automation Summary](AUTOMATION_SUMMARY.md)
-   [Reagent Pricing](REAGENT_PRICING_SUMMARY.md)

## Roadmap

*   [x] **Phase 0 World Model**: GP-based dose-response learning.
*   [x] **Autonomous Loop**: Acquisition -> Execution -> Modeling.
*   [x] **Mission Logs**: Explainable AI decisions.
*   [x] **Economic Engine**: Granular cost modeling with Inventory & BOM.
*   [x] **Complex Protocols**: iMicroglia, NGN2, Phagocytosis.
*   [x] **Assay Selector**: Agent chooses *which* assay to run based on ROI.
*   [x] **Cost-Aware Decision Support**: Recipe and Workflow optimization.
*   [ ] **Multi-Fidelity Learning**: Transfer learning from cheap assays to expensive ones.
*   [ ] **Multi-Fidelity Learning**: Transfer learning from cheap assays to expensive ones.

## Philosophy

This repo treats biology as a landscape that can be learned.

*   **Phase 0**: Model noise, model drift, model curves, model uncertainty.
*   **Phase 1**: Choose experiments that reduce ignorance per unit pain.

Nothing here is optimized. This is the backbone you iterate on.
The OS grows from here.
