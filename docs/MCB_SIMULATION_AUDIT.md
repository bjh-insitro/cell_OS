# MCB Simulation Capability Audit

## 1. Existing Capabilities (Pre-Audit)

### MCB Workflows
- **`src/cell_os/mcb_crash.py`**: Contains `MCBSimulation` class designed for "crash testing" (running many simulations to estimate failure rates).
- **`MCBTestConfig`**: Configuration dataclass for simulations.
- **`MCBTestResult`**: Dataclass for results (though `MCBSimulation.run()` returns a dict).

### Lab World Model
- **`BiologicalVirtualMachine`**: Simulates cell growth, viability, and contamination.
- **`LabWorldModel`**: Exists in `src/cell_os/core/world_model.py` but `MCBSimulation` uses a local `WorkflowExecutor` with a memory DB.

### Streamlit App
- **`dashboard_app/app.py`**: Main entry point with tab registration.
- **Existing Tabs**: Mission Control, Science, Economics, Workflow Visualizer, etc.
- **`tab_campaign_manager.py`**: Focuses on scheduling maintenance jobs, not simulation.

## 2. New Capabilities Added

### MCB Simulation API
- **`src/cell_os/simulation/mcb_wrapper.py`**: Created a clean wrapper around `MCBSimulation`.
- **`simulate_mcb_generation(spec, target_vials)`**: Single entry point for generating MCB artifacts.
- **`MCBResultBundle`**: Structured return object containing:
    - `vials`: List of `MCBVial` objects with metadata (ID, passage, viability, source).
    - `daily_metrics`: DataFrame of growth metrics.
    - `logs`: Human-readable execution logs.
    - `success`: Boolean status.

### Streamlit "POSH Campaign Sim" Tab
- **`dashboard_app/pages/tab_campaign_posh.py`**: New tab dedicated to simulating the POSH campaign.
- **Features**:
    - **Controls**: Select cell line (U2OS, HepG2, A549), initial cells, target vials.
    - **Simulation**: Runs `simulate_mcb_generation` on demand.
    - **Visualization**:
        - KPI Metrics (Vials Banked, Avg Viability, Duration).
        - Growth Curve & Viability Trend plots (Plotly).
        - Detailed Vial Table.
        - Execution Logs.

### Integration
- **`dashboard_app/app.py`**: Registered the new tab as "🧬 POSH Campaign Sim".

## 3. Future Extension Plan

The `tab_campaign_posh.py` is designed to be the home for the entire POSH campaign simulation.

**Next Steps:**
1.  **WCB Generation**: Add a "Phase 2: Working Cell Bank" section that takes generated MCB vials as input.
2.  **tBHP Dose Finding**: Add a section to run the `TBHPDoseFinder` agent.
3.  **LV Titering**: Add LV titration simulation.
4.  **POSH Screening**: Simulate the full screen using banked WCB and optimized parameters.

The `st.session_state` is used to persist results between reruns, allowing a stepwise workflow (MCB -> WCB -> Screen).
