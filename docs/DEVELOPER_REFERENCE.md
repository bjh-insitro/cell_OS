# Cell_OS - Developer Reference for Codex Work

**Last Updated**: 2025-12-01  
**Status**: Production-ready development environment

---

## 🚀 Quick Start

### Running the Dashboard
```bash
cd /Users/brighart/cell_OS/cell_OS
python3 -m streamlit run dashboard_app/app.py
```

**Dashboard URLs**:
- Local: http://localhost:8501 (or 8502 if 8501 is taken)
- Network: http://192.168.86.114:8501

### Running Tests
```bash
# All tests
pytest

# Specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/dashboard/
```

---

## 📁 Project Structure

```
cell_OS/
├── src/cell_os/              # Core simulation engine
│   ├── hardware/             # Virtual machines (BiologicalVirtualMachine)
│   ├── unit_ops/            # Unit operations (cell culture, QC, etc.)
│   ├── workflows/           # Workflow builders and execution
│   ├── database/            # Database repositories
│   │   └── repositories/    # Repository pattern implementations
│   ├── inventory.py         # Resource management
│   ├── inventory_manager.py # Persistent inventory with lot tracking
│   └── simulation_params_db.py  # Legacy parameter database
│
├── dashboard_app/           # Streamlit dashboard
│   ├── app.py              # Main entry point
│   ├── pages/              # Dashboard pages (tabs)
│   ├── components/         # Reusable UI components
│   └── utils.py            # Dashboard utilities
│
├── data/                   # Configuration and databases
│   ├── simulation_parameters.yaml
│   ├── simulation_params.db
│   ├── inventory.db
│   └── campaigns.db
│
├── config/                 # Example configurations
│   ├── posh_screen_example.yaml
│   └── titration_example.yaml
│
├── scripts/               # Utility scripts
│   ├── migrations/       # Database migration scripts
│   └── seed_inventory_resources.py
│
├── tests/                # Test suite
│   ├── unit/
│   ├── integration/
│   └── dashboard/
│
└── docs/                 # Documentation
    ├── STATUS.md
    ├── MIGRATION_HISTORY.md
    └── archive/          # Historical documentation
```

---

## 🔧 Recent Fixes (2025-12-01)

### 1. **Streamlit Deprecation Warnings - FIXED ✅**
- **Issue**: `use_container_width` parameter deprecated
- **Fix**: Replaced all instances with `width="stretch"` across dashboard pages
- **Files Modified**: All files in `dashboard_app/pages/`
- **Command Used**: 
  ```bash
  find dashboard_app/pages -name "*.py" -type f -exec sed -i '' 's/use_container_width=True/width="stretch"/g' {} +
  ```

### 2. **Database Schema Mismatch - FIXED ✅**
- **Issue**: `CompoundSensitivity` initialization error with `sensitivity_id`
- **Root Cause**: Database query returns `sensitivity_id` (or `id`) field which doesn't exist in dataclass
- **Fix**: Updated repository to filter out both `id` and `sensitivity_id` fields
- **File**: `src/cell_os/database/repositories/simulation_params.py`
- **Lines Modified**: 185, 198

### 3. **Arrow Serialization Error - FIXED ✅**
- **Issue**: Mixed data types in inventory lots causing Pandas/Arrow serialization failures
- **Fix**: Explicit type casting in `get_lots()` method
- **File**: `src/cell_os/inventory_manager.py`
- **Lines Modified**: 300-307

---

## 💾 Database Architecture

### Primary Databases

#### 1. **inventory.db**
- **Purpose**: Inventory management with lot tracking
- **Tables**:
  - `resources` - Catalog of all resources (reagents, vessels, etc.)
  - `lots` - Individual lot tracking (FIFO consumption)
  - `stock_levels` - Cached stock levels for performance
  - `transactions` - Complete audit trail

**Key Design Pattern**: Repository pattern with connection pooling

#### 2. **simulation_params.db**
- **Purpose**: Cell line parameters and compound sensitivities
- **Tables**:
  - `cell_line_params` - Growth parameters per cell line
  - `compound_sensitivity` - IC50 and dose-response data
  - `default_params` - Fallback parameter values
  - `simulation_runs` - Execution history

**Migration Status**: Fully migrated from YAML, with YAML fallback

#### 3. **campaigns.db**
- **Purpose**: POSH campaign definitions and execution history
- **Managed By**: `CampaignRepository`

### Database Access Patterns

**DO**:
- Use repository classes (e.g., `SimulationParamsRepository`, `InventoryManager`)
- Filter out database-specific fields (`id`, `created_at`, `sensitivity_id`) before instantiating dataclasses
- Use connection pooling for concurrent access

**DON'T**:
- Access databases directly with raw SQL (except in repositories)
- Assume field names match dataclass attributes
- Hardcode database paths (use defaults or config)

---

## 🧪 Key Components

### BiologicalVirtualMachine
**Location**: `src/cell_os/hardware/biological_virtual.py`

**Purpose**: Simulates realistic cell biology with:
- Exponential growth with confluence saturation
- Lag phase dynamics
- Edge well effects (evaporation/temp gradients)
- Stochastic noise injection
- Compound dose-response (Hill equation)

**Parameter Loading**:
1. Try database first (if `use_database=True`)
2. Fallback to YAML (`data/simulation_parameters.yaml`)
3. Fallback to hardcoded defaults

**Key Methods**:
- `seed_vessel()` - Initialize vessel with cells
- `count_cells()` - Count with biological variation
- `passage_cells()` - Transfer cells with passage stress
- `treat_with_compound()` - Apply dose-response model
- `advance_time()` - Update all vessel growth states

### Unit Operations
**Location**: `src/cell_os/unit_ops/operations/`

All unit operations now:
- Accept parametric resource definitions (no hardcoded volumes)
- Track BOM (Bill of Materials) for cost analysis
- Report to InventoryManager for consumption tracking
- Validate parameters at execution time

**Key Operations**:
- `cell_culture.py` - Seeding, expansion, feeding
- `harvest_freeze.py` - Harvest, QC, cryopreservation
- `qc_ops.py` - Cell counting, viability, identity testing
- `transfection.py` - Transfection protocols

### Inventory Management
**Location**: `src/cell_os/inventory_manager.py`

**Features**:
- FIFO lot consumption
- Expiration tracking
- Transaction audit trail
- Stock level alerts
- Resource catalog with pricing

**Usage**:
```python
from cell_os.inventory_manager import InventoryManager
from cell_os.inventory import Inventory

inventory = Inventory()
inv_manager = InventoryManager(inventory, db_path="data/inventory.db")

# Add stock
inv_manager.add_stock("pbs", quantity=500.0, lot_id="LOT-123")

# Consume stock (FIFO)
inv_manager.consume_stock("pbs", quantity=50.0, transaction_meta={"reason": "MCB prep"})

# Query
lots = inv_manager.get_lots("pbs")
transactions = inv_manager.get_transactions(resource_id="pbs", limit=10)
```

---

## 🎨 Dashboard Architecture

**Framework**: Streamlit  
**Entry Point**: `dashboard_app/app.py`

### Tab Structure
- **Home** - System status and quick actions
- **Mission Control** - Active executions and monitoring
- **Science** - Biological data visualization
- **Workflow Builder** - Visual workflow designer
- **POSH Campaign** - Campaign simulation and analysis
- **Cell Line Inspector** - Cell line database browser
- **Inventory** - Stock management
- **BOM Audit** - Cost and resource tracking
- **Analytics** - Historical data analysis

### Common Utilities
**Location**: `dashboard_app/utils.py`

```python
from dashboard_app.utils import init_automation_resources

vessel_lib, inv, ops, builder, inv_manager = init_automation_resources()
```

### Styling Guidelines
- Use `width="stretch"` for full-width components (NOT `use_container_width=True`)
- Use `st.columns()` for responsive layouts
- Prefer `st.dataframe()` over `st.table()` for large datasets
- Use `st.cache_data` for expensive computations

---

## ⚠️ Known Issues & Gotchas

### 1. **Streamlit Caching**
- Streamlit aggressively caches dataframes
- Use `st.rerun()` after database modifications to refresh UI
- Clear cache with `st.cache_data.clear()` if needed

### 2. **Database Connection Pooling**
- Some repositories use pooling (`use_pooling=True`)
- Others use traditional connection management
- **Rule**: Let repositories handle connections, don't manage manually

### 3. **YAML vs Database**
- System designed for gradual migration from YAML to SQLite
- Many components have dual-loading (DB first, YAML fallback)
- Don't remove YAML files yet - they're still fallback sources

### 4. **Plotly Deprecation Warnings**
- Using old `key` parameter style in some plotly charts
- **TODO**: Migrate to `config` parameter
- Not urgent - functionality works fine

### 5. **Dataclass Field Filtering**
- Always filter database columns before passing to dataclasses with `**row`
- Common fields to exclude: `id`, `sensitivity_id`, `created_at`, `updated_at`

### 6. **Time Zones**
- All timestamps should be ISO format with UTC
- Use `datetime.now().isoformat()` for consistency

---

## 🔄 Common Development Workflows

### Adding a New Cell Line
1. Add parameters to `data/simulation_parameters.yaml` OR
2. Use `SimulationParamsRepository` to insert into DB:
   ```python
   from cell_os.database.repositories.simulation_params import SimulationParamsRepository, CellLineSimParams
   
   repo = SimulationParamsRepository()
   params = CellLineSimParams(
       cell_line_id="iPSC-001",
       doubling_time_h=20.0,
       max_confluence=0.85,
       # ... other params
   )
   repo.add_cell_line_params(params)
   ```

### Adding a New Resource
1. Update `data/raw/pricing.yaml` OR
2. Use inventory database:
   ```bash
   python scripts/seed_inventory_resources.py
   ```

### Creating a New Dashboard Tab
1. Create file: `dashboard_app/pages/tab_my_feature.py`
2. Implement: `def render_my_feature(df, pricing):`
3. Register in `dashboard_app/app.py` in the `TABS` dictionary

### Running a Simulation
```python
from cell_os.simulation.mcb_sim import MCBSimulation

sim = MCBSimulation(
    cell_line="U2OS",
    target_vials=50,
    use_automation=True
)
results = sim.run()
```

---

## 📊 Testing Strategy

### Unit Tests
- Test individual components in isolation
- Mock external dependencies (databases, files)
- Fast execution (< 1 second per test)

### Integration Tests
- Test database interactions
- Test workflow execution end-to-end
- Use temporary databases

### Dashboard Tests
- Test page loads without errors
- Verify all tabs render
- Check for import errors

### Running Specific Tests
```bash
# Single file
pytest tests/unit/test_inventory.py -v

# Single test
pytest tests/unit/test_inventory.py::test_add_stock -v

# With coverage
pytest --cov=src/cell_os tests/
```

---

## 🐛 Debugging Tips

### Dashboard Issues
1. Check terminal output where Streamlit is running
2. Look for Python errors in browser console (F12)
3. Check `streamlit.log` if running in background
4. Use `st.write()` for debugging - prints to dashboard

### Database Issues
1. Check database exists: `ls -la data/*.db`
2. Inspect schema: `sqlite3 data/inventory.db ".schema"`
3. Check data: `sqlite3 data/inventory.db "SELECT * FROM resources LIMIT 5;"`
4. Enable logging: Set `logging.basicConfig(level=logging.DEBUG)`

### Simulation Issues
1. Verify parameters loaded: Check logs for "Loaded parameters from..."
2. Check vessel states: Use `vm.get_vessel_state(vessel_id)`
3. Inspect BOM: `workflow.get_bom()` shows all consumed items
4. Review execution log: Check timestamps and order of operations

---

## 📝 Documentation Standards

### Code Documentation
- **Docstrings**: Google style for all public functions/classes
- **Type Hints**: Required for function signatures
- **Comments**: Explain WHY, not WHAT

### Commit Messages
- Use conventional commits: `fix:`, `feat:`, `docs:`, `refactor:`
- Reference issues/PRs when applicable
- Keep first line < 72 characters

### Documentation Files
- **README.md**: User-facing getting started guide
- **docs/STATUS.md**: Current system status
- **docs/MIGRATION_HISTORY.md**: Major changes and migrations
- **This file**: Developer reference and troubleshooting

---

## 🔐 Environment Variables

Currently minimal. Most configuration is in YAML or databases.

**Optional**:
- `CELL_OS_DB_PATH` - Override default database location
- `STREAMLIT_SERVER_PORT` - Change default Streamlit port

---

## 📞 Key Contacts & Resources

### Related Documentation
- `docs/STATUS.md` - Current system status
- `docs/MIGRATION_HISTORY.md` - Change history
- `dashboard_app/ARCHITECTURE.txt` - Dashboard design
- `dashboard_app/QUICK_REFERENCE.md` - Dashboard patterns

### External References
- Streamlit Docs: https://docs.streamlit.io
- PyArrow: https://arrow.apache.org/docs/python/
- SQLite: https://www.sqlite.org/docs.html

---

## ✅ Pre-Deployment Checklist

- [ ] All tests passing: `pytest`
- [ ] No linting errors: `ruff check .`
- [ ] Database migrations applied
- [ ] YAML configs validated
- [ ] Dashboard loads without errors
- [ ] Simulation runs complete successfully
- [ ] Documentation updated
- [ ] Git commit and push

---

## 🎯 Next Priorities

### High Priority
1. Fix remaining Plotly deprecation warnings (migrate to `config` parameter)
2. Complete migration of all YAML data to databases
3. Add connection pooling to all repositories
4. Comprehensive integration test suite

### Medium Priority
1. Add user authentication to dashboard
2. Export/import functionality for databases
3. Automated database backups
4. Performance profiling and optimization

### Low Priority
1. Dark mode for dashboard
2. Multi-language support
3. Mobile-responsive layouts
4. API endpoints for external integrations

---

**Happy Coding! 🚀**
