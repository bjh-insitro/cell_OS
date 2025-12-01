# cell_OS

**An Autonomous Operating System for Cell Biology** 🧬

`cell_OS` is a production-ready platform for autonomous scientific discovery. It designs experiments, executes them (via simulation or real hardware), fits models, makes decisions, and generates reports—all without human intervention.

[![Tests](https://img.shields.io/badge/tests-379%20passing-brightgreen)]() 
[![CI](https://github.com/brighart/cell_OS/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/brighart/cell_OS/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.9+-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

---

## 🚀 Quick Start

```bash
# Clone and install
git clone https://github.com/brighart/cell_OS.git
cd cell_OS
python -m venv venv
source venv/bin/activate
pip install -e .

# Run an autonomous titration campaign
cell-os-run --config config/campaign_example.yaml

# Launch the dashboard
streamlit run dashboard_app/app.py
```

**That's it!** The agent will autonomously titrate lentiviral vectors, fit models, make GO/NO-GO decisions, and generate an interactive report.

📖 **[Read the Full User Guide →](docs/guides/USER_GUIDE.md)**

---

## 🏗️ Architecture

```mermaid
graph TB
    subgraph "User Interfaces"
        CLI[CLI Tool<br/>YAML Configs] 
        Dashboard[Streamlit Dashboard<br/>8 Tabs]
    end
    
    subgraph "Autonomous Agents"
        TitrationAgent[Titration Agent<br/>LV Optimization]
        ImagingLoop[Imaging Loop<br/>Dose Finding]
        POSHDesigner[POSH Designer<br/>Screen Planning]
    end
    
    subgraph "Core Architecture"
        HAL[Hardware Abstraction Layer<br/>MockSimulator | LabController]
        StateManager[State Manager<br/>Crash Recovery]
        ExperimentDB[(ExperimentDB<br/>SQLite)]
    end
    
    subgraph "World Model"
        GP[Gaussian Processes<br/>Dose-Response]
        Bayesian[Bayesian Optimization<br/>Active Learning]
    end
    
    CLI --> TitrationAgent
    Dashboard --> ImagingLoop
    Dashboard --> POSHDesigner
    
    TitrationAgent --> StateManager
    TitrationAgent --> HAL
    ImagingLoop --> GP
    POSHDesigner --> Bayesian
    
    StateManager --> ExperimentDB
    HAL --> ExperimentDB
    
    style TitrationAgent fill:#e1f5ff
    style ExperimentDB fill:#f0e1ff
    style HAL fill:#fff4e1
    style GP fill:#e1ffe1
```

### **Core Components**

| Component | Purpose |
|-----------|---------|
| **Hardware Abstraction Layer** | Switch between simulation (`MockSimulator`) and real hardware (`LabController`) |
| **ExperimentDB** | SQLite database: `designs` → `batches` → `results` + agent state |
| **Agents** | Autonomous decision-makers (titration, imaging, POSH design) |
| **State Manager** | Crash recovery - agents checkpoint after every round |
| **Dashboard** | 8-tab Streamlit interface for monitoring and control |

---

## ✨ Key Features

### 🤖 Autonomous Agents
- **Titration Agent**: Designs 7-point titrations, fits Poisson models, makes GO/NO-GO decisions
- **Imaging Loop**: Finds optimal stress-window doses using Bayesian optimization
- **POSH Designer**: Generates libraries, plans screens, simulates outcomes

### 💾 Enterprise-Grade Persistence
- **Crash Recovery**: Resume campaigns from any point
- **Full Audit Trail**: Every decision logged to SQLite
- **Query API**: Complex queries like "find all screens with D_M > 2.0"

### 🎛️ Multi-Interface
- **CLI**: `cell-os-run --config my_config.yaml`
- **Dashboard**: Interactive Streamlit app with 8 tabs
- **Programmatic**: Import agents as Python modules

### 📊 Rich Reporting
- **HTML Reports**: Titration curves, cost breakdowns, decision manifests
- **Budget Calculator**: Pre-flight cost estimation
- **QC Dashboards**: Outlier detection, plate effects

### 🗂️ Data Sources & CLI
- **SQLite-first**: Cell-line protocols (`data/cell_lines.db`) and inventory/pricing (`data/inventory.db`) are loaded from SQLite by default for consistency with the automation stack.
- **Legacy YAML fallback**: Passing explicit YAML paths (e.g., `Inventory("data/raw/pricing.yaml")`) still works and seeds the historical stock defaults, which keeps notebooks/tests reproducible.
- **Protocol resolver**: Automatically falls back to the SQLite database when the deprecated `data/cell_lines.yaml` is absent, so fresh clones don’t need to restore archived YAML.
- **Installable CLI**: `pip install -e .` exposes the `cell-os-run` entry point, so you can run `cell-os-run --config ...` from anywhere without relying on repo-relative Python paths.

---

## 📂 Project Structure

```
cell_OS/
├── cli/                    # Command-line tools
│   └── run_campaign.py
├── config/                 # YAML configurations
│   └── campaign_example.yaml
├── dashboard_app/          # Streamlit dashboard (8 tabs)
│   ├── dashboard.py
│   └── app_main.py
├── src/
│   ├── core/              # Infrastructure
│   │   ├── experiment_db.py       # Unified database
│   │   ├── hardware_interface.py  # HAL
│   │   └── state_manager.py       # Persistence
│   ├── cell_os/           # Science modules
│   │   ├── titration_loop.py      # Autonomous agent
│   │   ├── posh_lv_moi.py         # LV modeling
│   │   └── budget_manager.py      # Cost tracking
├── tests/                 # 186 passing tests
└── docs/guides/           # Documentation
    └── USER_GUIDE.md
```

---

## 🔬 Example: Run a Campaign

Create `my_campaign.yaml`:
```yaml
experiment_id: "MY_EXP_001"
cell_lines:
  - name: "U2OS"
    true_titer: 150000
    true_alpha: 0.92
  - name: "HEK293T"
    true_titer: 200000
    true_alpha: 0.88

screen_config:
  max_titration_rounds: 5
  target_bfp: 0.30

budget:
  max_titration_budget_usd: 5000.0
```

Run it:
```bash
cell-os-run --config my_campaign.yaml
```

View results:
- **HTML Report**: `results/campaigns/MY_EXP_001_report.html`
- **Database**: Query `data/experiments.db`
- **Dashboard**: Tab 7 "Campaign Reports"

---

## 📊 Dashboard Tabs

Launch with: `streamlit run dashboard_app/app.py`

1. **🚀 Mission Control** - Budget, cycle count, recent activity
2. **🔬 Science** - Dose-response curves with GP fits
3. **💰 Economics** - Cost tracking and inventory
4. **🕸️ Workflow Visualizer** - Interactive workflow graphs
5. **🧭 POSH Decision Assistant** - Configuration recommendations
6. **🧪 POSH Screen Designer** - Design libraries and titrations
7. **📊 Campaign Reports** - View generated HTML reports
8. **🧮 Budget Calculator** - Estimate costs before running

---

## 🧪 Testing

```bash
# Run the full suite (379 tests, ~40 seconds on a laptop)
python3 -m pytest -v

# Target a suite
python3 -m pytest tests/integration/test_persistence.py -v

# Run the focused static-analysis checks (pylint)
make lint
```

All tests passing ✅ (`python3 -m pytest -v`)

### Linting & Static Analysis

Run `make lint` to execute `tests/static/test_code_analysis.py`, which shells out to `pylint`
using the curated rules in [.pylintrc](.pylintrc). This keeps dashboard code free of
undefined/unused variables without forcing contributors to remember the exact pylintrc flags.
CI runs the same pytest target, so keep it green before opening a PR.

### Bootstrapping Local Databases

Fresh clones need the SQLite fixtures seeded from the authoritative YAML files. Use:

```bash
make bootstrap-data
# or: python3 scripts/bootstrap_data.py
```

The helper script runs both seeding utilities:

1. `scripts/seed_cell_line_protocols.py` → `data/cell_lines.db`
2. `scripts/seed_simulation_params.py` → `data/simulation_params.db`

Re-run it whenever the YAML fixtures change so protocol resolver and simulation tests stay in sync.

---

## 📚 Documentation

- **[User Guide](docs/guides/USER_GUIDE.md)** - Installation, CLI usage, troubleshooting
- **Architecture Notes** - See `docs/architecture/` for subsystem deep dives
- **Tutorial Notebooks** - Explore `notebooks/` for hands-on examples

---

## 🛠️ Advanced Features

### Multi-Fidelity Learning
Transfer knowledge from cheap assays to expensive ones:
```python
reporter_gp = DoseResponseGP.from_dataframe(df_reporter, ...)

primary_gp = DoseResponseGP.from_dataframe_with_prior(
    df_primary, ..., 
    prior_model=reporter_gp,
    prior_weight=0.3
)
```

### Inventory Depletion
Track reagent consumption:
```python
inventory = Inventory("data/raw/pricing.yaml")
inventory.consume("DMEM_MEDIA", 500.0, "mL")
```

### Custom Agents
Extend the platform:
```python
from core.state_manager import StateManager

class MyAgent:
    def __init__(self, config, experiment_id=None):
        self.state_manager = StateManager(experiment_id)
        
    def run(self):
        state = self.state_manager.load_state("MyAgent_v1")
        # Your logic here
        self.state_manager.save_state("MyAgent_v1", {"status": "done"})
```

---

## 🎯 Roadmap

- [x] Hardware Abstraction Layer
- [x] Unified ExperimentDB
- [x] Agent Persistence & Crash Recovery
- [x] CLI Tools with YAML configs
- [x] 8-Tab Dashboard
- [ ] Real hardware integration (SiLA2/vendor APIs)
- [ ] DINO embedding analysis
- [ ] Hit calling pipeline
- [ ] Notification system (Slack/Email)

---

## 📜 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 🙏 Credits

Built by the cell_OS team. Inspired by the vision of autonomous biology.

**Questions?** Open an issue or read the [User Guide](docs/guides/USER_GUIDE.md).
