# cell_OS

**An Autonomous Operating System for Cell Biology** 🧬

`cell_OS` is a production-ready platform for autonomous scientific discovery. It designs experiments, executes them (via simulation or real hardware), fits models, makes decisions, and generates reports—all without human intervention.

[![Tests](https://img.shields.io/badge/tests-186%20passing-brightgreen)]() 
[![Python](https://img.shields.io/badge/python-3.11-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

---

## 🚀 Quick Start

```bash
# Clone and install
git clone <your-repo-url>
cd cell_OS
python -m venv venv
source venv/bin/activate
pip install -e .

# Run an autonomous titration campaign
python cli/run_campaign.py --config config/campaign_example.yaml

# Launch the dashboard
streamlit run dashboard_app/dashboard.py
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
- **CLI**: `python cli/run_campaign.py --config my_config.yaml`
- **Dashboard**: Interactive Streamlit app with 8 tabs
- **Programmatic**: Import agents as Python modules

### 📊 Rich Reporting
- **HTML Reports**: Titration curves, cost breakdowns, decision manifests
- **Budget Calculator**: Pre-flight cost estimation
- **QC Dashboards**: Outlier detection, plate effects

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
python cli/run_campaign.py --config my_campaign.yaml
```

View results:
- **HTML Report**: `results/campaigns/MY_EXP_001_report.html`
- **Database**: Query `data/experiments.db`
- **Dashboard**: Tab 7 "Campaign Reports"

---

## 📊 Dashboard Tabs

Launch with: `streamlit run dashboard_app/dashboard.py`

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
# Run all tests (186 tests, ~6 seconds)
pytest tests -v

# Run specific suite
pytest tests/integration/test_persistence.py -v
```

All tests passing ✅

---

## 📚 Documentation

- **[User Guide](docs/guides/USER_GUIDE.md)** - Installation, CLI usage, troubleshooting
- **[API Docs](docs/api/)** - Module-level documentation (coming soon)
- **[Tutorial Notebooks](notebooks/)** - Hands-on examples

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
