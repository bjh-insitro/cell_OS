# Project Structure - cell_OS

**Last Updated**: 2025-11-23

This document provides a comprehensive overview of the cell_OS codebase structure, file purposes, and navigation guide.

---

## 📁 Root Directory

### Core Application Files
- **`dashboard.py`** - Main Streamlit dashboard with 6 tabs (Mission Control, Science, Economics, Workflow Visualizer, POSH Decision Assistant, Screen Designer)
- **`run_loop.py`** - Closed-loop experimental optimization script
- **`workflow_visualizer.py`** - Standalone workflow visualization tool (DEPRECATED - integrated into dashboard)
- **`requirements.txt`** - Python dependencies

### Documentation Files
- **`README.md`** - Project overview and getting started guide
- **`ARCHITECTURE.md`** - System architecture and design patterns
- **`ONTOLOGY.md`** - Semantic framework (Campaign → Workflow → Process → Unit Operation)
- **`POSH_SYSTEM_OVERVIEW.md`** - Overview of POSH variants (Zombie, Vanilla)
- **`COST_AWARE_DECISION_SUPPORT.md`** - Cost-aware decision making documentation
- **`docs/archive/migrations/2025-11-27-automation-parameterization-summary.md`** *(archived, formerly `AUTOMATION_SUMMARY.md`)* - Automation scoring and recommendations
- **`docs/archive/migrations/2025-11-27-reagent-pricing-summary.md`** *(archived, formerly `REAGENT_PRICING_SUMMARY.md`)* - Pricing database documentation
- **`STATUS.md`** - Consolidated program status and next steps
- **`upstream_protocol.md`** - Upstream workflow (library design → virus production)
- **`CHANGELOG.md`** - Version history and changes
- **`phase0_task.md`** - Task tracking (copied from artifacts)

### Configuration
- **`config/`** - Configuration files (if any)

---

## 📁 src/ - Source Code

### Core Modules (Essential)

#### **`unit_ops.py`** ⭐ CORE
- Parametric unit operations system
- All POSH operations (fixation, decross-linking, T7 IVT, SBS, etc.)
- Recipe builders for complete workflows
- Cost and time scoring
- **Status**: Active, heavily used

#### **`inventory.py`** ⭐ CORE
- Reagent inventory management
- Pricing database interface
- Consumption tracking
- **Status**: Active

#### **`cell_line_database.py`** ⭐ CORE
- Cell line profiles with optimal methods
- Dissociation, transfection, transduction, freezing protocols
- Includes A549, HEK293, HeLa, iPSC, iMicroglia, etc.
- **Status**: Active

#### **`cellpaint_panels.py`** ⭐ CORE
- Modular Cell Painting panel system
- Standard 5-channel, 6-channel, 8-channel panels
- Custom panel builder
- **Status**: Active

### POSH-Specific Modules

#### **`posh_screen_designer.py`** ⭐ NEW
- Experimental planning calculator
- Cell counts, plates, viral volume, banking strategy
- Accounts for barcode efficiency, confluence, thaw-passage workflow
- **Status**: Active, recently added

#### **`posh_decision_engine.py`** ⭐ NEW
- Interactive decision tree for POSH configuration
- Recommends protocol, multimodal, automation level
- Budget and timeline validation
- **Status**: Active, recently added

#### **`posh_complete_workflow.py`** ⭐ NEW
- Integrates screen designer with parametric ops
- Complete workflow from transduction to analysis
- Metadata extraction for tracking
- **Status**: Active, recently added

#### **`zombie_posh_shopping_list.py`**
- Generates shopping lists with catalog numbers
- **Status**: Active

#### **`posh_automation_decision.py`**
- Automation recommendations for POSH
- **Status**: Active

### Upstream/Genetic Supply Chain

#### **`upstream.py`** ⭐
- Library design classes (GeneTarget, GuideRNA, LibraryDesign, OligoPool)
- Genetic supply chain modeling
- **Status**: Active

### Workflow & Visualization

#### **`workflows.py`**
- Workflow builder and process definitions
- **Status**: Active

#### **`workflow_renderer.py`**
- Graphviz-based workflow visualization
- **Status**: Active (used in dashboard)

#### **`workflow_renderer_plotly.py`**
- Plotly-based interactive workflow visualization
- **Status**: Active (used in dashboard)

#### **`workflow_optimizer.py`**
- Workflow optimization logic
- **Status**: Needs review

### Decision Support & Analysis

#### **`assay_selector.py`**
- Assay selection logic based on goals
- **Status**: Active

#### **`campaign.py`**
- Campaign management
- **Status**: Active

#### **`modeling.py`**
- Dose-response Gaussian Process models
- **Status**: Active (used in dashboard)

#### **`llm_scientist.py`**
- LLM-based scientific reasoning
- **Status**: Experimental, not integrated

#### **`recipe_optimizer.py`**
- Recipe optimization algorithms
- **Status**: Needs review

### Simulation & Automation

#### **`simulation.py`**
- Experimental simulation
- **Status**: Active

#### **`automation_analysis.py`**
- Automation scoring and analysis
- **Status**: Active

#### **`acquisition.py`**
- Data acquisition logic
- **Status**: Needs review

### Utilities

#### **`plotting.py`**
- Plotting utilities
- **Status**: Active

#### **`reporting.py`**
- Report generation
- **Status**: Active

#### **`schema.py`**
- Data schemas
- **Status**: Active

---

## 📁 data/ - Data Files

### **`data/raw/`**
- **`pricing.yaml`** ⭐ - Complete reagent pricing database
- **`vessels.yaml`** ⭐ - Lab vessel specifications (plates, flasks, tubes)
- **`cell_lines.yaml`** - Cell line database (if separate from code)

---

## 📁 tests/ - Test Suite

### **`tests/integration/`**
- **`verify_upstream.py`** - Upstream workflow verification
- **`verify_cellpaint_panels.py`** - Cell Painting panel tests
- **`verify_cost_aware_system.py`** - Cost-aware system tests
- **`test_posh_decision_engine.py`** ⭐ NEW - Decision engine tests
- **`test_posh_screen_designer.py`** ⭐ NEW - Screen designer tests

---

## 📁 results/ - Output Files
- **`mission_log.md`** - Experimental log
- **`experiment_history.csv`** - Historical data

---

## 📁 notebooks/ - Jupyter Notebooks
- Exploratory analysis and prototyping

---

## 🗑️ Files to Consider Removing/Consolidating

### Potentially Redundant
1. **`workflow_visualizer.py`** - Functionality now in dashboard.py (Tab 4)
2. **`examples_cell_line_database.py`** - Example usage, could move to docs

### Documentation Consolidation Opportunities
- Multiple protocol docs could be consolidated into a single `protocols/` directory
- Consider moving all `.md` files to a `docs/` directory

---

## 🎯 Recommended Actions

### High Priority
1. ✅ **Create this PROJECT_STRUCTURE.md** - Done!
2. 🔄 **Move deprecated files** - Create `deprecated/` folder for old code
3. 📚 **Consolidate docs** - Create `docs/` directory for all markdown files
4. 🧪 **Add more tests** - Especially for new POSH modules

### Medium Priority
5. 📦 **Package structure** - Consider making cell_OS a proper Python package
6. 🔧 **Config management** - Centralize configuration in `config/`
7. 📝 **API documentation** - Generate API docs from docstrings

### Low Priority
8. 🎨 **Code cleanup** - Remove unused imports, standardize formatting
9. 📊 **Performance profiling** - Identify bottlenecks
10. 🔐 **Add type hints** - Improve code quality and IDE support

---

## 🚀 Quick Start Guide

### For New Users
1. Read `README.md`
2. Review `ONTOLOGY.md` to understand system structure
3. Run `dashboard.py` to explore the system
4. Check `POSH_SYSTEM_OVERVIEW.md` for protocol details

### For Developers
1. Start with `src/unit_ops.py` - core operations
2. Review `src/posh_screen_designer.py` - experimental planning
3. Check `tests/integration/` for usage examples
4. Read `ARCHITECTURE.md` for design patterns

### For Protocol Users
1. Use dashboard.py → "POSH Screen Designer" tab
2. Or use dashboard.py → "POSH Decision Assistant" tab
3. Export protocols to Markdown for lab use

---

## 📊 Module Dependency Map

```
dashboard.py
├── src/unit_ops.py (core)
├── src/inventory.py (core)
├── src/posh_decision_engine.py
├── src/posh_screen_designer.py
├── src/workflow_renderer.py
├── src/workflow_renderer_plotly.py
├── src/workflows.py
└── src/modeling.py

src/posh_complete_workflow.py
├── src/unit_ops.py
└── src/posh_screen_designer.py

src/posh_screen_designer.py
└── src/cell_line_database.py

src/unit_ops.py
├── src/inventory.py
├── src/cellpaint_panels.py
└── src/upstream.py
```

---

## 📝 Notes

- **Active Development**: POSH Screen Designer, Decision Engine, Complete Workflow
- **Stable**: Core modules (unit_ops, inventory, cell_line_database)
- **Experimental**: LLM Scientist integration
- **Deprecated**: Standalone workflow_visualizer.py (use dashboard instead)
