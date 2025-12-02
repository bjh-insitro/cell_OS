# Codebase Cleanup Recommendations

## 🗑️ Files to Remove/Deprecate

### 1. Redundant Files
- **`workflow_visualizer.py`** → Functionality integrated into `dashboard.py` (Tab 4)
  - **Action**: Move to `deprecated/` folder
  
- **`examples_cell_line_database.py`** → Example usage only
  - **Action**: Move to `examples/` or `docs/examples/`

### 2. Temporary/Build Files
- **`.DS_Store`** → macOS system file
  - **Action**: Add to `.gitignore`

## 📚 Documentation Reorganization

### Create `docs/` Directory
Move all documentation files into organized structure:

```
docs/
├── protocols/
│   ├── zombie_posh_protocol.md
│   ├── zombie_posh_inhouse_protocol.md
│   ├── zombie_posh_qc_checkpoints.md
│   ├── vanilla_posh_implementation_plan.md
│   └── upstream_protocol.md
├── architecture/
│   ├── ARCHITECTURE.md
│   ├── ONTOLOGY.md
│   └── PROJECT_STRUCTURE.md
├── guides/
│   ├── POSH_SYSTEM_OVERVIEW.md
│   ├── COST_AWARE_DECISION_SUPPORT.md
│   ├── USER_GUIDE.md
│   ├── campaign.md
│   └── README.md (index)
├── archive/migrations/
│   ├── 2025-11-27-automation-parameterization-summary.md  # replaces AUTOMATION_SUMMARY.md
│   └── 2025-11-27-reagent-pricing-summary.md              # replaces REAGENT_PRICING_SUMMARY.md
└── README.md (keep in root)
```

## 🔧 Code Organization

### Create Subdirectories in `src/`

```
src/
├── core/
│   ├── unit_ops.py
│   ├── inventory.py
│   └── cell_line_database.py
├── posh/
│   ├── screen_designer.py
│   ├── decision_engine.py
│   ├── complete_workflow.py
│   ├── automation_decision.py
│   └── shopping_list.py
├── workflows/
│   ├── workflows.py
│   ├── workflow_optimizer.py
│   ├── workflow_renderer.py
│   └── workflow_renderer_plotly.py
├── analysis/
│   ├── modeling.py
│   ├── assay_selector.py
│   └── campaign.py
├── visualization/
│   ├── plotting.py
│   └── reporting.py
└── utils/
    ├── schema.py
    ├── simulation.py
    └── acquisition.py
```

## ✅ Immediate Actions (High Priority)

1. **Create `.gitignore`** if not exists:
```
.DS_Store
__pycache__/
*.pyc
env/
.venv/
*.egg-info/
.ipynb_checkpoints/
results/*.csv
results/*.png
```

2. **Move deprecated files**:
```bash
mkdir deprecated
mv workflow_visualizer.py deprecated/
```

3. **Create docs directory**:
```bash
mkdir -p docs/{protocols,architecture,guides}
```

4. **Update README.md** to reference PROJECT_STRUCTURE.md

## 🧪 Testing Improvements

### Add Missing Tests
- `test_posh_complete_workflow.py` - Test integrated workflow
- `test_cell_line_database.py` - Test cell line profiles
- `test_cellpaint_panels.py` - Test panel builder

### Test Coverage Goals
- Core modules: >80%
- POSH modules: >70%
- Utilities: >60%

## 📦 Package Structure (Future)

Consider converting to proper Python package:

```
cell_os/
├── setup.py
├── pyproject.toml
├── cell_os/
│   ├── __init__.py
│   ├── core/
│   ├── posh/
│   └── ...
├── tests/
├── docs/
└── examples/
```

## 🎯 Priority Order

### Week 1: Cleanup
- [ ] Create `.gitignore`
- [ ] Move deprecated files
- [ ] Create `docs/` structure
- [ ] Move documentation files

### Week 2: Organization
- [ ] Reorganize `src/` into subdirectories
- [ ] Update imports across codebase
- [ ] Add `__init__.py` files

### Week 3: Testing
- [ ] Add missing tests
- [ ] Run test coverage analysis
- [ ] Fix any broken tests

### Week 4: Documentation
- [ ] Update all documentation links
- [ ] Generate API documentation
- [ ] Create developer guide

## 📊 Current Status

### Active & Essential (Keep)
- ✅ `dashboard.py`
- ✅ `run_loop.py`
- ✅ `src/unit_ops.py`
- ✅ `src/inventory.py`
- ✅ `src/posh_screen_designer.py`
- ✅ `src/posh_decision_engine.py`
- ✅ `src/cell_line_database.py`

### Deprecated (Move)
- ❌ `workflow_visualizer.py`
- ❌ `examples_cell_line_database.py`

### Needs Review
- ⚠️ `src/llm_scientist.py` - Experimental, not integrated
- ⚠️ `src/recipe_optimizer.py` - Usage unclear
- ⚠️ `src/acquisition.py` - Usage unclear

## 💡 Additional Recommendations

1. **Version Control**: Tag current state as v0.1.0 before major reorganization
2. **Backup**: Create backup branch before moving files
3. **Documentation**: Update all internal links after reorganization
4. **Testing**: Run full test suite after each reorganization step
5. **Communication**: Document all changes in CHANGELOG.md
