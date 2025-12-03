import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# Cell OS Imports
from cell_os.simulation.mcb_wrapper import simulate_mcb_generation, VendorVialSpec
from cell_os.simulation.wcb_wrapper import simulate_wcb_generation, MCBVialSpec
from cell_os.simulation.titration_wrapper import simulate_titration
from cell_os.simulation.library_banking_wrapper import simulate_library_banking
from cell_os.simulation.posh_screen_wrapper import (
    simulate_posh_screen, 
    simulate_screen_data,
    generate_embeddings,
    analyze_screen_results,
    CELL_PAINTING_FEATURES
)
from cell_os.cell_line_database import get_cell_line_profile

# Dashboard Imports
from dashboard_app.utils import download_button
from dashboard_app.components.campaign_visualizers import (
    render_lineage,
    render_unit_ops_table,
    render_titration_resources,
    get_item_cost,
    get_item_pack_price,
    get_item_name,
    PricingInventory
)

# Visualization Modules
from .visualization.volcano_plot import render_volcano_plot
from .visualization.hit_list import render_hit_list
from .visualization.raw_measurements import render_raw_measurements
from .visualization.channel_intensities import render_channel_intensities
from .visualization.embeddings import render_embeddings
from .visualization.operations import render_operations


# ==============================================================================
# Cached Simulation Wrappers
# ==============================================================================

@st.cache_resource(show_spinner=False)
def _cached_mcb_simulation(
    cell_line: str,
    vendor_name: str,
    initial_cells: float,
    lot_number: str,
    vial_id: str,
    target_vials: int,
    cells_per_vial: float,
    random_seed: int
):
    """Cached wrapper for MCB simulation."""
    return simulate_mcb_generation(
        VendorVialSpec(
            cell_line=cell_line,
            vendor=vendor_name,
            lot_number=lot_number,
            vial_id=vial_id,
            cells_per_vial=initial_cells
        ),
        target_vials=target_vials,
        cells_per_vial=cells_per_vial,
        random_seed=random_seed
    )


@st.cache_data(show_spinner=False)
def _cached_screen_data_simulation(
    cell_line: str,
    treatment: str,
    dose_uM: float,
    library_size: int,
    random_seed: int
):
    """Cached wrapper for raw screen data generation."""
    return simulate_screen_data(
        cell_line=cell_line,
        treatment=treatment,
        dose_uM=dose_uM,
        library_size=library_size,
        random_seed=random_seed
    )


@st.cache_data(show_spinner=False)
def _cached_embedding_generation(
    df_raw: pd.DataFrame,
    df_channels: pd.DataFrame,
    random_seed: int
):
    """Cached wrapper for embedding generation."""
    # Combine channels and raw measurements for embedding generation
    df_combined = pd.merge(df_channels, df_raw, on="Gene")
    return generate_embeddings(df_combined, random_seed=random_seed)


@st.cache_resource(show_spinner=False)
def _cached_wcb_simulation(
    cell_line: str,
    mcb_vial_id: str,
    target_vials: int,
    cells_per_vial: float,
    random_seed: int
):
    """Cached wrapper for WCB simulation."""
    # Create a mock MCB vial (in real app, would load from DB)
    mcb_vial = MCBVialSpec(
        cell_line=cell_line,
        lot_number="MCB-LOT-001",
        vial_id=mcb_vial_id,
        cells_per_vial=1e6,
        passage_number=3
    )
    return simulate_wcb_generation(
        mcb_vial,
        target_vials=target_vials,
        cells_per_vial=cells_per_vial,
        random_seed=random_seed
    )

@st.cache_resource(show_spinner=False)
def _cached_titration_simulation(
    cell_line: str,
    wcb_vial_id: str,
    random_seed: int
):
    """Cached wrapper for Titration simulation."""
    return simulate_titration(
        cell_line=cell_line,
        wcb_vial_id=wcb_vial_id,
        random_seed=random_seed
    )

@st.cache_resource(show_spinner=False)
def _cached_library_banking_simulation(
    cell_line: str,
    wcb_vial_id: str,
    library_size: int,
    random_seed: int
):
    """Cached wrapper for Library Banking simulation."""
    return simulate_library_banking(
        cell_line=cell_line,
        wcb_vial_id=wcb_vial_id,
        library_size=library_size,
        random_seed=random_seed
    )


# ==============================================================================
# Main Render Function
# ==============================================================================

def render_posh_campaign_manager(df, pricing):
    """Render the POSH Campaign Manager tab."""
    st.header("🧬 POSH Campaign Simulation")
    st.markdown("""
    Simulate the full multi-cell-line POSH campaign.
    **Phase 1: Master Cell Bank (MCB) Generation**
    """)
    
    # --- Configuration Controls ---
    with st.expander("Campaign Configuration", expanded=True):
        st.subheader("Campaign Settings")
        cell_line = st.selectbox("Cell Line", ["U2OS", "HepG2", "A549", "iPSC"], key="posh_sim_cell_line")
        
        # Hardcoded defaults (UI removed per user request)
        initial_cells = 1.0e6
        vendor_lot = "LOT-2025-X"
        target_vials = 10
            
        st.divider()
        run_sim = st.button("▶️ Simulate MCB Generation", type="primary", key="posh_run_mcb_sim")

    # --- Main Content ---
    
    # Initialize session state for results if not present
    if "posh_mcb_results" not in st.session_state:
        st.session_state.posh_mcb_results = {}
        
    if run_sim:
        with st.spinner(f"Simulating MCB generation for {cell_line}..."):
            seed = st.session_state.get("posh_mcb_seed", 0) + 1
            st.session_state["posh_mcb_seed"] = seed
            result = _cached_mcb_simulation(
                cell_line=cell_line,
                vendor_name="ATCC",
                initial_cells=initial_cells,
                lot_number=vendor_lot,
                vial_id=f"VENDOR-{cell_line}-001",
                target_vials=target_vials,
                cells_per_vial=1e6,
                random_seed=seed,
            )
            st.session_state.posh_mcb_results[cell_line] = result
            
    # Display MCB Results
    if cell_line in st.session_state.posh_mcb_results:
        result = st.session_state.posh_mcb_results[cell_line]
        
        if result.success:
                st.success(f"✅ MCB Generated: {len(result.vials)} vials of {result.cell_line}")
                _render_mcb_result(result, pricing)
                download_button(
                    pd.DataFrame([v.__dict__ for v in result.vials]),
                    "⬇️ Download MCB Vials (CSV)",
                    f"{cell_line.lower()}_mcb_vials.csv",
                )
        else:
            st.error(f"❌ Simulation Failed: {result.summary.get('failed_reason', 'Unknown')}")

    st.divider()
    st.markdown("""
    **Phase 2: Working Cell Bank (WCB) Generation**
    Select a generated MCB vial to expand into a Working Cell Bank.
    """)

    if not st.session_state.posh_mcb_results:
        st.info("⚠️ Please complete Phase 1 (MCB Generation) above to proceed to Phase 2.")
    else:
        # Phase 2 UI
        _render_phase_2_wcb(pricing)
        
    # Phase 3: Assay Development (Titration)
    st.divider()
    st.markdown("""
    **Phase 3: Assay Development (Titration)**
    Determine optimal viral titer (MOI) for the screen.
    """)
    
    if "posh_wcb_results" not in st.session_state or not st.session_state.posh_wcb_results:
        st.info("⚠️ Please complete Phase 2 (WCB Generation) above to proceed to Phase 3.")
    else:
        _render_phase_3_titration(pricing)
        
    # Phase 4: Library Banking
    st.divider()
    st.markdown("""
    **Phase 4: Library Banking**
    Expand the library and create assay-ready banks.
    """)
    
    if "titration_results" not in st.session_state or not st.session_state.titration_results:
        st.info("⚠️ Please complete Phase 3 (Titration) above to proceed to Phase 4.")
    else:
        _render_phase_4_library_banking(pricing)
        
    # Phase 5: QC (Skipped for now, placeholder)
    
    # Phase 6: POSH Screen Execution
    st.divider()
    st.markdown("""
    **Phase 6: POSH Screen Execution**
    Thaw library bank, treat with compound, and image for phenotypic readout.
    """)
    
    _render_phase_6_screen_execution()


# ==============================================================================
# Helper Render Functions (Phase 2-6)
# ==============================================================================

def _render_phase_2_wcb(pricing):
    # Logic for WCB UI
    # Get available MCB vials
    mcb_options = []
    for cl, res in st.session_state.posh_mcb_results.items():
        if res.success:
            for v in res.vials:
                mcb_options.append(f"{v.vial_id} ({cl})")
                
    if not mcb_options:
        st.warning("No valid MCB vials available.")
        return

    col1, col2 = st.columns(2)
    with col1:
        selected_mcb = st.selectbox("Select MCB Vial", mcb_options)
        
    with col2:
        target_wcb_vials = st.number_input("Target WCB Vials", value=50, step=10)
        
    run_wcb = st.button("▶️ Simulate WCB Generation", key="run_wcb_btn")
    
    if "posh_wcb_results" not in st.session_state:
        st.session_state.posh_wcb_results = {}
        
    if run_wcb:
        # Parse selection
        vial_id = selected_mcb.split(" ")[0]
        cell_line = selected_mcb.split("(")[1].replace(")", "")
        
        with st.spinner(f"Simulating WCB generation for {cell_line}..."):
            seed = st.session_state.get("wcb_seed", 0) + 1
            st.session_state["wcb_seed"] = seed
            
            res = _cached_wcb_simulation(
                cell_line=cell_line,
                mcb_vial_id=vial_id,
                target_vials=target_wcb_vials,
                cells_per_vial=1e6,
                random_seed=seed
            )
            st.session_state.posh_wcb_results[cell_line] = res
            
    # Display Results
    # For simplicity, show result for the cell line selected in MCB dropdown (inferred)
    selected_cl = selected_mcb.split("(")[1].replace(")", "")
    if selected_cl in st.session_state.posh_wcb_results:
        res = st.session_state.posh_wcb_results[selected_cl]
        if res.success:
            st.success(f"✅ WCB Generated: {len(res.vials)} vials of {res.cell_line}")
            _render_wcb_result(res, pricing)
        else:
            st.error(f"❌ WCB Failed: {res.summary.get('failed_reason', 'Unknown')}")


def _render_phase_3_titration(pricing):
    # Logic for Titration UI
    # Select WCB vial
    wcb_options = []
    for cl, res in st.session_state.posh_wcb_results.items():
        if res.success:
            for v in res.vials[:5]: # Show first 5
                wcb_options.append(f"{v.vial_id} ({cl})")
                
    col1, col2 = st.columns(2)
    with col1:
        selected_wcb = st.selectbox("Select WCB Vial", wcb_options, key="titration_wcb_sel")
    
    run_titration = st.button("▶️ Run Titration Assay", key="run_titration_btn")
    
    if "titration_results" not in st.session_state:
        st.session_state.titration_results = {}
    if "optimal_dose_results" not in st.session_state:
        st.session_state.optimal_dose_results = {}
        
    if run_titration:
        cell_line = selected_wcb.split("(")[1].replace(")", "")
        vial_id = selected_wcb.split(" ")[0]
        
        with st.spinner(f"Running titration for {cell_line}..."):
            seed = st.session_state.get("titration_seed", 0) + 1
            st.session_state["titration_seed"] = seed
            
            res = _cached_titration_simulation(cell_line, vial_id, seed)
            st.session_state.titration_results[cell_line] = res
            st.session_state.optimal_dose_results[cell_line] = res.optimal_moi # Store optimal dose/MOI
            
    # Display Results
    cell_line = selected_wcb.split("(")[1].replace(")", "")
    if cell_line in st.session_state.titration_results:
        res = st.session_state.titration_results[cell_line]
        if res.success:
            st.success(f"✅ Titration Complete. Optimal MOI: {res.optimal_moi:.2f}")
            
            tab1, tab2 = st.tabs(["Dose Response 📉", "Resources 💰"])
            with tab1:
                st.line_chart(res.dose_response_curve.set_index("MOI")["Viability"])
            with tab2:
                render_titration_resources(res, pricing)


def _render_phase_4_library_banking(pricing):
    # Logic for Library Banking
    # Select WCB vial
    wcb_options = []
    for cl, res in st.session_state.posh_wcb_results.items():
        if res.success:
            for v in res.vials[:5]:
                wcb_options.append(f"{v.vial_id} ({cl})")
                
    col1, col2 = st.columns(2)
    with col1:
        selected_wcb = st.selectbox("Select WCB Vial for Library", wcb_options, key="lib_wcb_sel")
    with col2:
        lib_size = st.number_input("Library Size (Genes)", value=1000, step=100)
        
    run_lib = st.button("▶️ Generate Library Bank", key="run_lib_btn")
    
    if "library_banking_results" not in st.session_state:
        st.session_state.library_banking_results = {}
        
    if run_lib:
        cell_line = selected_wcb.split("(")[1].replace(")", "")
        vial_id = selected_wcb.split(" ")[0]
        
        with st.spinner(f"Banking library for {cell_line}..."):
            seed = st.session_state.get("lib_seed", 0) + 1
            st.session_state["lib_seed"] = seed
            
            res = _cached_library_banking_simulation(cell_line, vial_id, lib_size, seed)
            st.session_state.library_banking_results[cell_line] = res
            
    # Display Results
    cell_line = selected_wcb.split("(")[1].replace(")", "")
    if cell_line in st.session_state.library_banking_results:
        res = st.session_state.library_banking_results[cell_line]
        if res.success:
            st.success(f"✅ Library Banked: {res.total_vials} vials")
            st.metric("Total Cost", f"${res.total_cost:,.2f}")


def _render_phase_6_screen_execution():
    with st.expander("Screen Configuration", expanded=True):
        s_col1, s_col2, s_col3, s_col4 = st.columns(4)
        with s_col1:
            screen_cell_line = st.selectbox("Cell Line", ["A549", "U2OS", "HepG2", "iPSC"], key="screen_cell_line")
        with s_col2:
            treatment = st.selectbox("Treatment", ["tBHP", "Staurosporine", "Tunicamycin"], key="screen_treatment")
        with s_col3:
            # Get optimal dose from Assay Development
            if "optimal_dose_results" in st.session_state and screen_cell_line in st.session_state.optimal_dose_results:
                dose = st.session_state.optimal_dose_results[screen_cell_line]
                st.metric("Dose (µM)", f"{dose:.1f}", help=f"Optimal dose from Assay Development for {screen_cell_line}")
            else:
                # Allow manual override during development
                use_default = st.toggle("Use Default Dose (40µM)", value=True, key="use_default_dose",
                                       help="Toggle off to manually enter dose")
                if use_default:
                    dose = 40.0
                    st.metric("Dose (µM)", f"{dose:.1f}", help="Default development dose")
                else:
                    dose = st.number_input("Manual Dose (µM)", value=40.0, step=5.0, key="manual_dose")
                st.info(f"💡 Tip: Run Assay Development to find optimal dose for {screen_cell_line}")
        with s_col4:
            # Check if library banking results exist to pre-fill
            default_lib_size = 1000
            if screen_cell_line in st.session_state.get("library_banking_results", {}):
                res = st.session_state.library_banking_results[screen_cell_line]
                if res.success:
                    default_lib_size = res.library_size
                    st.success(f"✓ Linked to {screen_cell_line} Bank ({default_lib_size} genes)")
            
            screen_lib_size = st.number_input("Library Size", value=default_lib_size, key="screen_lib_size")
        
        # Feature selection row
        st.markdown("**Cell Painting Feature to Analyze:**")
        feature_options = {k: v["name"] for k, v in CELL_PAINTING_FEATURES.items()}
        selected_feature_name = st.selectbox(
            "Morphological Feature",
            options=list(feature_options.values()),
            key="screen_feature",
            help="Select which Cell Painting morphological feature to analyze"
        )
        # Reverse lookup to get feature key
        selected_feature = [k for k, v in feature_options.items() if v == selected_feature_name][0]
            
        run_screen = st.button("▶️ Run POSH Screen", key="run_screen_btn")
        
    if "screen_results" not in st.session_state:
        st.session_state.screen_results = {}
    if "screen_last_params" not in st.session_state:
        st.session_state.screen_last_params = {}
        
    # Check if we need to run (Button Clicked OR Feature Changed for existing run)
    should_run = False
    use_existing_data = False
    
    if run_screen:
        should_run = True
        # New run -> New seed
        seed = st.session_state.get("screen_seed_counter", 0) + 1
        st.session_state["screen_seed_counter"] = seed
    elif screen_cell_line in st.session_state.screen_results:
        # Check if feature changed for this cell line
        last_params = st.session_state.screen_last_params.get(screen_cell_line, {})
        if last_params and last_params.get("feature") != selected_feature:
            # Feature changed! Re-analyze using EXISTING data (same seed)
            should_run = True
            use_existing_data = True
            seed = last_params.get("seed")
            # Verify other params match (safety check)
            if (last_params.get("treatment") != treatment or 
                last_params.get("dose") != dose or 
                last_params.get("lib_size") != screen_lib_size):
                # Params changed but user didn't click Run -> Don't auto-run
                should_run = False
                st.warning("⚠️ Settings changed. Click 'Run POSH Screen' to update.")
            
    if should_run:
        action_msg = "Re-analyzing" if use_existing_data else "Running"
        with st.spinner(f"{action_msg} POSH Screen on {screen_cell_line}..."):
            
            # 1. Get Data (Cached if seed/params same)
            df_raw, df_channels = _cached_screen_data_simulation(
                cell_line=screen_cell_line,
                treatment=treatment,
                dose_uM=dose,
                library_size=screen_lib_size,
                random_seed=seed
            )
            
            # 2. Get Embeddings (Cached if seed/params same)
            df_embeddings, df_proj = _cached_embedding_generation(
                df_raw=df_raw,
                df_channels=df_channels,
                random_seed=seed
            )
            
            # 3. Analyze (Fast, no cache needed)
            s_result = analyze_screen_results(
                df_raw=df_raw,
                df_channels=df_channels,
                df_embeddings=df_embeddings,
                df_proj=df_proj,
                cell_line=screen_cell_line,
                treatment=treatment,
                dose_uM=dose,
                library_size=screen_lib_size,
                feature=selected_feature
            )
            
            st.session_state.screen_results[screen_cell_line] = s_result
            
            # Store params
            st.session_state.screen_last_params[screen_cell_line] = {
                "seed": seed,
                "treatment": treatment,
                "dose": dose,
                "lib_size": screen_lib_size,
                "feature": selected_feature
            }
            
            if use_existing_data:
                st.toast(f"Updated analysis for {selected_feature_name}")
            
    if screen_cell_line in st.session_state.screen_results:
        s_result = st.session_state.screen_results[screen_cell_line]
        
        if s_result.success:
            st.success(f"✅ Screen Complete: {len(s_result.hit_list)} hits identified")
            
            # Tabs for results
            tab_volcano, tab_hits, tab_raw, tab_channels, tab_embed, tab_ops = st.tabs(["Volcano Plot 🌋", "Hit List 🎯", "Raw Measurements 📊", "Channel Intensities 🔬", "Embeddings 🕸️", "Operations ⚙️"])
            
            with tab_volcano:
                render_volcano_plot(s_result, screen_cell_line, treatment, dose)
                
            with tab_hits:
                render_hit_list(s_result, screen_cell_line)
            
            with tab_raw:
                render_raw_measurements(s_result, treatment, dose)
            
            with tab_channels:
                render_channel_intensities(s_result)
                    
            with tab_embed:
                render_embeddings(s_result)
                
            with tab_ops:
                render_operations(s_result)
        else:
            st.error(f"❌ Screen Failed: {s_result.error_message}")


def _render_mcb_result(result, pricing):
    """Render metrics and plots for a single MCB result."""
    
    # 1. KPI Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Vials Banked", len(result.vials))
    with col2:
        avg_viability = pd.Series([v.viability for v in result.vials]).mean()
        st.metric("Avg Viability", f"{avg_viability*100:.1f}%")
    with col3:
        days = result.summary.get("duration_days", 0)
        st.metric("Duration", f"{days} days")
    with col4:
        status = "✅ Success" if result.success else "❌ Failed"
        st.metric("Status", status)
        
    st.divider()
    
    # Tabs Layout
    tab_lineage, tab_growth, tab_resources, tab_vials, tab_quality, tab_unit_ops = st.tabs([
        "Lineage 🧬", "Growth Curve 📈", "Resources 💰", "Vials 🧪", "Quality 📉", "Unit Operations 🔬"
    ])
    
    with tab_lineage:
        render_lineage(result)
        
    with tab_growth:
        if not result.daily_metrics.empty:
            st.line_chart(result.daily_metrics.set_index("Day")["Viable_Cells"])
        else:
            st.info("No growth data available.")
            
    with tab_resources:
        # Calculate costs
        total_cost = 0.0
        if result.workflow:
            for process in result.workflow.processes:
                for op in process.ops:
                    total_cost += op.material_cost_usd + op.instrument_cost_usd
        st.metric("Total Cost", f"${total_cost:,.2f}")
        render_unit_ops_table(result)
        
    with tab_vials:
        st.dataframe(pd.DataFrame([v.__dict__ for v in result.vials]), use_container_width=True)
        
    with tab_quality:
        st.info("Quality metrics placeholder")
        
    with tab_unit_ops:
        render_unit_ops_table(result)


def _render_wcb_result(result, pricing):
    """Render metrics and plots for a single WCB result."""
    _render_mcb_result(result, pricing) # Reuse MCB renderer for now
