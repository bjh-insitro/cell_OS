# Cell_OS - Developer Reference

**Last Updated**: 2025-01-12
**Status**: Production-ready development environment

---

## 🚀 Quick Start

### Setup
```bash
git clone https://github.com/brighart/cell_OS.git
cd cell_OS
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

### Running the Epistemic Agent
```bash
python scripts/runners/run_epistemic_agent.py --cycles 20 --budget 384 --seed 42
```

### Running the Dashboard
```bash
python3 -m streamlit run dashboard_app/app.py
```

### Running Tests
```bash
# All tests
pytest

# Specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/phase6a/  # Epistemic control tests
```

---

## 📁 Project Structure

```
cell_OS/
├── src/cell_os/                      # Main package
│   ├── epistemic_agent/              # Agent + epistemic control system
│   │   ├── loop.py                   # Main orchestration
│   │   ├── control.py                # EpistemicController (debt tracking)
│   │   ├── debt.py                   # Information gain computation
│   │   ├── penalty.py                # Cost inflation from debt
│   │   ├── beliefs/                  # Belief state management
│   │   ├── acquisition/              # Experiment selection (chooser.py)
│   │   └── agent/                    # Policy rules
│   │
│   ├── hardware/                     # Virtual machines & mechanisms
│   │   ├── biological_virtual.py     # BiologicalVirtualMachine (synthetic data)
│   │   ├── mechanism_posterior_v2.py # Bayesian inference
│   │   ├── beam_search/              # Beam search implementation
│   │   ├── assays/                   # Assay implementations
│   │   └── stress_mechanisms/        # Stress response models
│   │
│   ├── biology/                      # Pure biology models (was sim/)
│   │   ├── biology_core.py           # Pharmacology functions
│   │   ├── advanced_biology.py       # Cell cycle, stress models
│   │   ├── realistic_noise.py        # Noise models
│   │   └── imaging_artifacts_core.py # Imaging artifact simulation
│   │
│   ├── simulation/                   # Simulation executors
│   │   ├── executor.py               # SimulationExecutor
│   │   ├── simulated_executor.py     # SimulatedImagingExecutor
│   │   ├── simulated_perturbation_executor.py
│   │   └── legacy.py                 # Legacy simulation code
│   │
│   ├── posh/                         # POSH screen workflow
│   │   ├── scenario.py               # POSHScenario
│   │   ├── library_design.py         # Library design
│   │   ├── lv_moi.py                 # LV/MOI calculations
│   │   ├── screen_design.py          # Screen design orchestration
│   │   └── viz.py                    # Visualization
│   │
│   ├── imaging/                      # Imaging workflow
│   │   ├── acquisition.py            # Experiment planning
│   │   ├── goal.py                   # Imaging goals
│   │   ├── loop.py                   # Dose-response loop
│   │   └── cost.py                   # Cost calculations
│   │
│   ├── core/                         # Core data structures
│   ├── database/                     # Database repositories
│   ├── unit_ops/                     # Unit operations
│   ├── workflows/                    # Workflow builders
│   ├── calibration/                  # Calibration systems
│   ├── contracts/                    # Contract enforcement
│   ├── analysis/                     # Analysis utilities
│   ├── qc/                           # Quality control
│   └── legacy_core/                  # Legacy DB code (preserved)
│
├── scripts/                          # Organized utility scripts
│   ├── runners/                      # Entry points (run_*.py)
│   ├── analysis/                     # Analysis scripts
│   ├── validation/                   # Validation & verification
│   ├── testing/                      # Test utilities & benchmarks
│   ├── tools/                        # Utility scripts
│   ├── demos/                        # Demo scripts
│   ├── debugging/                    # Debug utilities
│   ├── experiments/                  # Experimental scripts
│   ├── visualization/                # Visualization scripts
│   └── deployment/                   # Deployment scripts
│
├── tests/                            # Test suite (10K+ lines)
│   ├── unit/                         # Component tests
│   ├── integration/                  # Integration tests
│   ├── phase6a/                      # Epistemic control tests
│   ├── contracts/                    # Contract tests
│   └── adversarial/                  # Adversarial agent tests
│
├── dashboard_app/                    # Streamlit dashboard
├── validation_frontend/              # React validation UI
├── docs/                             # Documentation
├── data/                             # Data files & databases
├── configs/                          # Configuration files
├── artifacts/                        # Generated images/plots
└── cases/                            # Test cases
```

---

## 🧪 Key Components

### 1. Epistemic Agent

**Location**: `src/cell_os/epistemic_agent/`

The epistemic agent is the core research contribution - it enforces honesty about uncertainty.

**Key Files**:
- `loop.py` - Main orchestration loop
- `control.py` - EpistemicController (debt tracking, cost inflation)
- `debt.py` - Information gain computation
- `penalty.py` - Penalty calculations
- `beliefs/state.py` - What the agent knows
- `acquisition/chooser.py` - Experiment selection

**Usage**:
```python
from cell_os.epistemic_agent import EpistemicController, EpistemicControllerConfig

config = EpistemicControllerConfig(
    debt_threshold=2.0,
    cost_inflation_rate=0.1
)
controller = EpistemicController(config)

# Track debt
controller.record_claim(claimed_gain=0.8)
controller.record_observation(actual_gain=0.3)
# debt += max(0, 0.8 - 0.3) = 0.5 bits
```

### 2. BiologicalVirtualMachine

**Location**: `src/cell_os/hardware/biological_virtual.py`

Generates realistic synthetic cell biology data with known ground truth.

**Features**:
- Death conservation enforcement (`viable + Σ(deaths) = 1.0`)
- Observer-independent physics
- Deterministic execution (same seed → identical results)
- 5-channel Cell Painting + LDH cytotoxicity
- Batch effects, edge biases, noise injection

**Key Methods**:
- `seed_vessel()` - Initialize vessel with cells
- `count_cells()` - Count with biological variation
- `passage_cells()` - Transfer cells with passage stress
- `treat_with_compound()` - Apply dose-response model
- `advance_time()` - Update all vessel growth states

### 3. Biology Models

**Location**: `src/cell_os/biology/`

Pure pharmacology and biology functions (no side effects):
- `biology_core.py` - Hill curves, dose-response
- `advanced_biology.py` - Cell cycle, stress models
- `realistic_noise.py` - Noise generation
- `imaging_artifacts_core.py` - Imaging artifacts

### 4. POSH Workflow

**Location**: `src/cell_os/posh/`

Pooled Optical Screens in Human cells workflow:
```python
from cell_os.posh import POSHScenario, POSHLibrary, ScreenConfig

scenario = POSHScenario.load("data/scenarios/my_scenario.yaml")
library = design_posh_library(scenario, world_model)
```

### 5. Imaging Workflow

**Location**: `src/cell_os/imaging/`

Dose-response imaging experiments:
```python
from cell_os.imaging import ImagingDoseLoop, ImagingWindowGoal

goal = ImagingWindowGoal(target_viability=0.7, max_std=0.1)
loop = ImagingDoseLoop(world_model, executor, goal)
```

---

## 💾 Database Architecture

### Primary Databases

| Database | Purpose | Location |
|----------|---------|----------|
| `simulation_params.db` | Cell line params, compound sensitivity | `data/` |
| `inventory.db` | Resource tracking, lot management | `data/` |
| `campaigns.db` | POSH campaign definitions | `data/` |

### Repository Pattern

```python
from cell_os.database.repositories.simulation_params import SimulationParamsRepository

repo = SimulationParamsRepository()
params = repo.get_cell_line_params("U2OS")
```

---

## 🧪 Testing

### Test Categories

| Directory | Purpose | Run Command |
|-----------|---------|-------------|
| `tests/unit/` | Component tests | `pytest tests/unit/` |
| `tests/integration/` | End-to-end tests | `pytest tests/integration/` |
| `tests/phase6a/` | Epistemic control | `pytest tests/phase6a/` |
| `tests/contracts/` | Contract enforcement | `pytest tests/contracts/` |

### Key Test Files

- `tests/integration/test_epistemic_debt_enforcement.py` - Debt tracking tests
- `tests/phase6a/test_death_accounting_honesty.py` - Conservation laws
- `tests/unit/test_active_learner.py` - Agent behavior

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src/cell_os tests/

# Single test
pytest tests/unit/test_imaging_acquisition.py::test_propose_imaging_doses -v

# Stop on first failure
pytest -x
```

---

## 🎨 Frontend Applications

### Dashboard (Streamlit)

**Location**: `dashboard_app/`

```bash
python3 -m streamlit run dashboard_app/app.py
```

### Validation Frontend (React)

**Location**: `validation_frontend/`

```bash
cd validation_frontend
npm install
npm run dev
```

---

## 📝 Code Standards

### Imports

Use the new consolidated package paths:
```python
# Epistemic control
from cell_os.epistemic_agent import EpistemicController
from cell_os.epistemic_agent.control import EpistemicControllerConfig

# Biology
from cell_os.biology.biology_core import hill_curve

# POSH
from cell_os.posh import POSHScenario, POSHLibrary

# Imaging
from cell_os.imaging import ImagingDoseLoop, ExperimentPlan

# Simulation
from cell_os.simulation import SimulationExecutor
```

### Docstrings

Google style:
```python
def compute_debt(claimed: float, actual: float) -> float:
    """Compute epistemic debt from overclaiming.

    Args:
        claimed: Claimed information gain in bits
        actual: Actual information gain in bits

    Returns:
        Debt accumulated (0 if underclaimed)
    """
    return max(0, claimed - actual)
```

### Commit Messages

Use conventional commits:
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation
- `refactor:` - Code restructuring
- `test:` - Test changes
- `chore:` - Maintenance

---

## 🐛 Debugging

### Common Issues

**Import Errors**:
```bash
# Ensure package is installed
pip install -e .

# Check PYTHONPATH
PYTHONPATH=src python -c "from cell_os.epistemic_agent import EpistemicController"
```

**Test Failures**:
```bash
# Run with verbose output
pytest -v --tb=long tests/path/to/test.py

# Run single test
pytest tests/path/to/test.py::test_function_name -v
```

**Database Issues**:
```bash
# Check database exists
ls -la data/*.db

# Inspect schema
sqlite3 data/simulation_params.db ".schema"
```

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| `README.md` | Project overview |
| `docs/DEVELOPER_REFERENCE.md` | This file |
| `docs/CONTRIBUTING.md` | Contribution guidelines |
| `docs/WHAT_WE_BUILT.md` | System overview |
| `docs/guides/` | Feature guides |

---

**Happy Coding! 🚀**
