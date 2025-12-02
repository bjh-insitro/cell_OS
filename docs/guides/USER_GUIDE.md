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
cell-os-run --config config/campaign_example.yaml

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
cell-os-run --config <path-to-config.yaml>
```

### Options

| Flag | Description | Example |
|------|-------------|---------|
| `--config` | Path to YAML config | `--config config/my_campaign.yaml` |
| `--experiment-id` | Override experiment ID | `--experiment-id EXP_001` |
| `--dry-run` | Validate config without running | `--dry-run` |

### Example: Dry Run

```bash
cell-os-run --config config/campaign_example.yaml --dry-run
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
9. **🔍 Workflow BOM Audit** - Detailed bill of materials for workflows

### Bill of Materials (BOM) Tracking

The **Workflow BOM Audit** tab provides detailed resource tracking for all operations:

**Features:**
- **Itemized resource lists**: Every operation tracks specific consumables, reagents, and instrument usage
- **Dynamic cost calculation**: Costs are calculated from the pricing database in real-time
- **Three-tier auditing**: Audit individual operations, process blocks, or full campaign workflows
- **Detailed vs. Grouped views**: See all sub-steps or group by parametric operation

**Example Usage:**
```python
# All operations now populate BOM items automatically
from cell_os.unit_ops.operations.cell_culture import CellCultureOps

ops = CellCultureOps(vessel_lib, inv, lh)
thaw_op = ops.thaw("flask_t75", "HeLa")

# Access BOM items
for item in thaw_op.items:
    print(f"{item.resource_id}: {item.quantity}")
# Output:
# flask_T75: 1
# dmem_high_glucose: 15.0
# pipette_10ml: 2
# incubator_usage: 24.0
```

**Dashboard Audit:**
1. Navigate to **Workflow BOM Audit** tab
2. Select workflow level (Parametric Operation, Process Block, or Campaign)
3. Choose specific workflow to audit
4. Click "Generate Step-by-Step BOM Audit"
5. View detailed breakdown with consumable IDs, costs, and timing

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

### Data Sources & Fallbacks

- **SQLite-first**: By default, `ProtocolResolver` reads cell-line protocols from `data/cell_lines.db` and `Inventory` loads pricing/stock from `data/inventory.db`. This keeps the automation stack consistent with production deployments.
- **Legacy YAML fixtures**: Passing explicit YAML paths (e.g., `Inventory("data/raw/pricing.yaml")`) still works and seeds the historical stock defaults. These YAML files are considered **deprecated fixtures** meant for tests/notebooks; edit the SQLite databases for real changes.
- **CLI entry point**: `cell-os-run` is installed automatically via `pip install -e .`. Use it instead of `python cli/run_campaign.py` unless you’re editing the CLI module itself.

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
