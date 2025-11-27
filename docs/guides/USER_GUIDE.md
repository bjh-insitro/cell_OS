# cell_OS User Guide

Welcome to **cell_OS** - an autonomous operating system for cell biology experiments.

## Quick Start

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd cell_OS

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

### Running Your First Campaign

```bash
# Run an example titration campaign
python cli/run_campaign.py --config config/campaign_example.yaml

# View results in the dashboard
streamlit run dashboard_app/dashboard.py
```

That's it! The campaign will autonomously titrate lentiviral vectors across multiple cell lines and generate an interactive report.

---

## Core Concepts

### 1. Campaigns
A **campaign** is an autonomous experimental run managed by an agent. The agent:
- Designs experiments (e.g., which LV volumes to test)
- Executes them (via simulation or real hardware)
- Fits models to the data
- Makes GO/NO-GO decisions
- Generates reports

### 2. Configuration Files
Campaigns are configured via YAML files. Example:

```yaml
experiment_id: "TITRATION_2025"
cell_lines:
  - name: "U2OS"
    true_titer: 150000  # TU/uL (for simulation)
    true_alpha: 0.92
```

### 3. Persistence
All data is saved to `data/experiments.db` (SQLite). This enables:
- **Crash recovery**: Restart a campaign and it resumes where it left off
- **History tracking**: Query all past experiments
- **Reproducibility**: Every step is logged

---

## Using the CLI

### Basic Command

```bash
python cli/run_campaign.py --config <path-to-config.yaml>
```

### Options

| Flag | Description | Example |
|------|-------------|---------|
| `--config` | Path to YAML config | `--config config/my_campaign.yaml` |
| `--experiment-id` | Override experiment ID | `--experiment-id EXP_001` |
| `--dry-run` | Validate config without running | `--dry-run` |

### Example: Dry Run

```bash
python cli/run_campaign.py --config config/campaign_example.yaml --dry-run
```

Output:
```
✅ Config loaded successfully from: config/campaign_example.yaml
   Experiment: 3-Line LV Titration Test
   Cell Lines: 3
```

---

## Using the Dashboard

Launch the dashboard:

```bash
streamlit run dashboard_app/dashboard.py
```

### Dashboard Tabs

1. **🚀 Mission Control** - Budget, cycle count, recent activity
2. **🔬 Science** - Dose-response curves with Gaussian Process fits
3. **💰 Economics** - Cost tracking and inventory
4. **🕸️ Workflow Visualizer** - Interactive workflow graphs
5. **🧭 POSH Decision Assistant** - Configuration recommendations
6. **🧪 POSH Screen Designer** - Design libraries and titrations
7. **📊 Campaign Reports** - View generated HTML reports
8. **🧮 Budget Calculator** - Estimate costs before running

### Key Features

- **Real-time monitoring**: Dashboard updates as campaigns run
- **Interactive plots**: Click, zoom, pan on all visualizations
- **Export**: Download configs and reports

---

## Understanding Results

### Campaign Reports

After a campaign completes, an HTML report is saved to:
```
results/campaigns/<experiment_id>_report.html
```

The report includes:
- **Decision Manifest**: GO/NO-GO for each cell line
- **Titration Curves**: Fitted models with uncertainty
- **Cost Summary**: Breakdown of reagents, virus, flow cytometry
- **Execution Log**: Full agent decision history

### Database Queries

You can query the database directly:

```python
from core.experiment_db import ExperimentDB

db = ExperimentDB()

# Get all experiments
db.cursor.execute("SELECT * FROM experiments")
for row in db.cursor.fetchall():
    print(row)

# Get titration results for a specific cell line
db.cursor.execute("""
    SELECT * FROM titration_results 
    WHERE cell_line = 'U2OS' 
    ORDER BY round_number
""")
```

---

## Advanced Usage

### Custom Scenarios

Create your own YAML config:

```yaml
experiment_id: "MY_CUSTOM_EXP"
experiment_name: "Custom Screen"

cell_lines:
  - name: "MyCell"
    true_titer: 100000
    true_alpha: 0.95

screen_config:
  max_titration_rounds: 10
  target_bfp: 0.30
  bfp_tolerance: [0.25, 0.35]

budget:
  max_titration_budget_usd: 10000.0
```

### Extending Agents

To create a new autonomous agent:

```python
from core.state_manager import StateManager

class MyCustomAgent:
    def __init__(self, config, experiment_id=None):
        self.state_manager = StateManager(experiment_id)
        self.agent_id = "MyAgent_v1"
        
    def run(self):
        # Load previous state
        state = self.state_manager.load_state(self.agent_id)
        
        # Your logic here
        
        # Save state
        self.state_manager.save_state(self.agent_id, {"status": "complete"})
```

---

## Troubleshooting

### Campaign Won't Resume

If a campaign doesn't resume after interruption:

```python
# Check database for saved state
from core.experiment_db import ExperimentDB
db = ExperimentDB()
db.cursor.execute("SELECT * FROM agent_state WHERE agent_id='TitrationAgent_v1'")
print(db.cursor.fetchone())
```

### Dashboard Import Errors

If the dashboard won't load:

```bash
# Verify all dependencies installed
pip install streamlit altair plotly pandas pyyaml

# Check for syntax errors
python -c "import dashboard_app.dashboard"
```

### Tests Failing

```bash
# Run specific test
pytest tests/integration/test_persistence.py -v

# Run all tests
pytest tests -v
```

---

## Next Steps

- 📖 Read the [API Documentation](../api/)
- 🧪 Try the [Tutorial Notebooks](../../notebooks/)
- 🏗️ Learn the [Architecture](../system/architecture.md)
- 💬 Join our community discussions

---

**Questions?** Open an issue or check the [FAQ](FAQ.md).
