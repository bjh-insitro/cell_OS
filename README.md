# cell_OS

**A Silicon-based "Lila SSI" for Autonomous Cell Biology.**

`cell_OS` is a prototype operating system for autonomous scientific discovery. It is designed to reason about biological experiments, manage resources, and execute goal-directed campaigns.

## Core Architecture

The system is built on three pillars of "Scientific Superintelligence" (SSI):

1.  **World Model (Phase 0)**: A probabilistic representation of the biological world (Gaussian Processes), learned from baseline data.
2.  **Campaign Manager (Goal Seeking)**: A high-level orchestration layer that pursues specific scientific objectives (e.g., "Find a selective compound").
3.  **Unit Op Model (Physics of Cost)**: A detailed economic model that calculates the true cost, time, and risk of assays by breaking them down into atomic Unit Operations (UOs).

## Key Features

*   **Closed-Loop Experimentation**: Automatically proposes, executes (simulates), and analyzes experiments to reduce uncertainty.
*   **Mission Logs**: Generates human-readable narratives explaining the agent's decision-making process (e.g., "Why did I choose this experiment?").
*   **Selectivity Optimization**: Can be tasked to find compounds that kill cancer cells (HepG2) while sparing healthy cells (U2OS).
*   **Physics-Based Costing**: Understands that "Cell Painting" is expensive because it requires a microscope and multiple wash steps, not just because a config file says "Cost=5".

## Directory Structure

```
cell_OS/
├── data/
│   ├── raw/
│   │   ├── cell_world_model_export.csv  # The "Map" of cell models
│   │   └── unit_op_world_model.csv      # The "Physics" of assay costs
├── src/
│   ├── acquisition.py    # Decision engine (Max Uncertainty)
│   ├── campaign.py       # Goal definitions (Potency, Selectivity)
│   ├── modeling.py       # Gaussian Process models
│   ├── reporting.py      # Mission Log generator
│   ├── schema.py         # Data structures
│   ├── simulation.py     # In-silico wet lab
│   └── unit_ops.py       # Unit Operation logic
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

### 3. Inspect Results
*   **Mission Log**: `results/mission_log.md` (The agent's diary)
*   **Experiment History**: `results/experiment_history.csv`
*   **Assay Costs**: Run `python -c "from src.unit_ops import get_posh_recipe, UnitOpLibrary; print(get_posh_recipe().derive_score(UnitOpLibrary('data/raw/unit_op_world_model.csv')))"`

## Roadmap

*   [x] **Phase 0 World Model**: GP-based dose-response learning.
*   [x] **Autonomous Loop**: Acquisition -> Execution -> Modeling.
*   [x] **Mission Logs**: Explainable AI decisions.
*   [x] **Campaign Manager**: Goal-directed science (Potency & Selectivity).
*   [x] **Unit Op Model**: Physics-based assay costing (POSH recipe).
*   [ ] **Assay Selector**: Agent chooses *which* assay to run based on ROI.
*   [ ] **Multi-Fidelity Learning**: Transfer learning from cheap assays to expensive ones.

## Philosophy

This repo treats biology as a landscape that can be learned.

*   **Phase 0**: Model noise, model drift, model curves, model uncertainty.
*   **Phase 1**: Choose experiments that reduce ignorance per unit pain.

Nothing here is optimized. This is the backbone you iterate on.
The OS grows from here.
