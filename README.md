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
*   **Granular Cost Modeling**: Tracks every dollar spent on reagents, plastics, and labor.
    *   **Inventory System**: YAML-based price catalog (`pricing.yaml`) and unit op definitions (`unit_ops.yaml`).
    *   **Differentiation Protocols**: Detailed cost models for iMicroglia and NGN2 neurons.
    *   **Banking Workflows**: Models the economics of cell banking (MCB -> WCB).

## Directory Structure

```
cell_OS/
├── data/
│   ├── raw/
│   │   ├── pricing.yaml             # Price catalog (Reagents, Plastics, Services)
│   │   ├── unit_ops.yaml            # Unit Operation definitions (BOM + Overhead)
│   │   ├── cell_world_model_export.csv
│   │   └── ...
├── src/
│   ├── acquisition.py    # Decision engine (Max Uncertainty)
│   ├── campaign.py       # Goal definitions
│   ├── inventory.py      # Inventory and Cost calculation logic
│   ├── modeling.py       # Gaussian Process models
│   ├── reporting.py      # Mission Log generator
│   ├── simulation.py     # In-silico wet lab
│   └── unit_ops.py       # Recipe definitions
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
The default campaign seeks a compound selective for HepG2 over U2OS.
```bash
python run_loop.py
```

### 3. Verify Costs
Check the cost of complex workflows:
```bash
# iMicroglia Differentiation
python verify_diff_costs.py

# NGN2 Differentiation
python verify_ngn2_costs.py

# Phagocytosis Assay
python verify_phago_costs.py
```

## Roadmap

*   [x] **Phase 0 World Model**: GP-based dose-response learning.
*   [x] **Autonomous Loop**: Acquisition -> Execution -> Modeling.
*   [x] **Mission Logs**: Explainable AI decisions.
*   [x] **Economic Engine**: Granular cost modeling with Inventory & BOM.
*   [x] **Complex Protocols**: iMicroglia, NGN2, Phagocytosis.
*   [ ] **Assay Selector**: Agent chooses *which* assay to run based on ROI.
*   [ ] **Multi-Fidelity Learning**: Transfer learning from cheap assays to expensive ones.

## Philosophy

This repo treats biology as a landscape that can be learned.

*   **Phase 0**: Model noise, model drift, model curves, model uncertainty.
*   **Phase 1**: Choose experiments that reduce ignorance per unit pain.

Nothing here is optimized. This is the backbone you iterate on.
The OS grows from here.
