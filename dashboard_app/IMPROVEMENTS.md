# Streamlit App Improvements

## 🧹 Cleanup & Organization
- **Moved CLI Scripts**: Moved `imaging_loop_dashboard.py` and `imaging_loop_simulator.py` from `dashboard_app/` to `scripts/` to separate CLI tools from the web dashboard.
  - `dashboard_app/imaging_loop_dashboard.py` → `scripts/demos/run_imaging_loop_cli.py`
  - `dashboard_app/imaging_loop_simulator.py` → `scripts/testing/run_imaging_simulation.py`

## 🧩 Component Refactoring
- **Created `dashboard_app/components/`**: New directory for reusable UI components.
- **Extracted Campaign Visualizers**: Created `dashboard_app/components/campaign_visualizers.py` containing reusable logic for:
  - `render_lineage`: Graphviz lineage trees
  - `render_resources`: BOM and cost analysis (generic)
  - `render_unit_ops_table`: Workflow step tables
  - `render_titration_resources`: Titration specific costs
  - Pricing helpers (`get_item_cost`, etc.)

## ⚡ Page Optimization
- **Refactored `tab_campaign_posh.py`**:
  - Reduced file size by extracting ~600 lines of helper code.
  - Improved readability by separating visualization logic from page logic.
  - Preserved complex MCB/WCB resource simulation logic while using shared components where possible.

## 🛠️ Utilities
- **Standardized Error Handling**: Added `render_error` to `dashboard_app/utils.py` for consistent error reporting across the app.
