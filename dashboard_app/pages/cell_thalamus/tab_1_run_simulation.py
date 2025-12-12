"""Tab 1: Run Simulation - Execute Phase 0 campaigns"""

import streamlit as st
import sys
from pathlib import Path

src_path = Path(__file__).parent.parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from cell_os.cell_thalamus import CellThalamusAgent, Phase0Design
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.database.cell_thalamus_db import CellThalamusDB


def render_tab_1():
    """Render the Run Simulation tab."""

    st.header("Configure and Run Phase 0 Simulation")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Experimental Parameters")

        # Cell line selection
        cell_lines = st.multiselect(
            "Cell Lines",
            options=["A549", "HepG2", "U2OS"],
            default=["A549", "HepG2"]
        )

        # Compound selection
        all_compounds = [
            "tBHQ", "hydrogen_peroxide", "tunicamycin", "thapsigargin",
            "etoposide", "cccp", "oligomycin_a", "two_deoxy_d_glucose",
            "mg132", "nocodazole"
        ]

        run_mode = st.radio(
            "Run Mode",
            options=["Demo Mode (~7 wells, 30 sec)", "Quick Test (3 compounds, ~20 min)", "Full Panel (10 compounds)"],
            horizontal=False
        )

        if run_mode == "Demo Mode (~7 wells, 30 sec)":
            compounds = ["tBHQ", "tunicamycin"]
            st.info("⚡ Ultra-fast demo: 2 compounds, 2 doses, ~7 wells total")
        elif run_mode.startswith("Quick Test"):
            compounds = st.multiselect(
                "Compounds",
                options=all_compounds,
                default=["tBHQ", "tunicamycin", "etoposide"]
            )
        else:
            compounds = all_compounds
            st.info(f"Using all {len(compounds)} compounds")

        # Database path
        db_path = st.text_input(
            "Database Path",
            value="data/cell_thalamus.db"
        )

    with col2:
        st.subheader("Design Summary")

        if cell_lines and compounds:
            # Calculate design size
            design_gen = Phase0Design()
            n_compounds = len(compounds)
            n_cell_lines = len(cell_lines)
            n_doses = 4
            n_timepoints = 2
            n_plates = 3
            n_days = 2
            n_operators = 2

            experimental_wells = n_compounds * n_cell_lines * n_doses * n_timepoints * n_plates * n_days * n_operators
            sentinel_wells = (4 + 2 + 2) * n_cell_lines * n_timepoints * n_plates * n_days * n_operators  # DMSO + mild + strong
            total_wells = experimental_wells + sentinel_wells

            st.metric("Total Wells", f"{total_wells:,}")
            st.metric("Experimental Wells", f"{experimental_wells:,}")
            st.metric("Sentinel Wells", f"{sentinel_wells:,}")
            st.metric("Unique Conditions", n_compounds * n_cell_lines * n_doses * n_timepoints)
        else:
            st.warning("Select cell lines and compounds")

    # Run button
    st.markdown("---")

    col_a, col_b, col_c = st.columns([1, 2, 1])

    with col_b:
        if st.button("🚀 Run Phase 0 Campaign", type="primary", use_container_width=True):
            if not cell_lines:
                st.error("Please select at least one cell line")
            elif not compounds:
                st.error("Please select at least one compound")
            else:
                # Pass the run_mode to the function
                run_simulation(cell_lines, compounds, db_path, run_mode)


def run_simulation(cell_lines, compounds, db_path, run_mode):
    """Execute the Phase 0 simulation."""

    with st.status("Running Phase 0 simulation...", expanded=True) as status:
        st.write("Initializing hardware and database...")

        # Initialize
        hardware = BiologicalVirtualMachine()
        db = CellThalamusDB(db_path=db_path)
        agent = CellThalamusAgent(phase=0, hardware=hardware, db=db)

        # Choose mode
        if run_mode == "Demo Mode (~7 wells, 30 sec)":
            st.write("Running DEMO MODE (ultra-fast)...")
            design_id = agent.run_demo_mode()
        else:
            st.write(f"Generating experimental design for {len(cell_lines)} cell lines and {len(compounds)} compounds...")
            # Run campaign
            design_id = agent.run_phase_0(cell_lines=cell_lines, compounds=compounds)

        st.write(f"Campaign complete! Design ID: {design_id}")

        # Get summary
        summary = agent.get_results_summary(design_id)

        status.update(label="✅ Simulation Complete!", state="complete", expanded=False)

    # Display results
    st.success(f"Phase 0 campaign completed successfully!")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Wells", summary['total_wells'])

    with col2:
        st.metric("Experimental Wells", summary['experimental_wells'])

    with col3:
        st.metric("Sentinel Wells", summary['sentinel_wells'])

    st.info(f"**Design ID**: `{design_id}`\n\nUse this ID in other tabs to analyze results.")

    # Store in session state for other tabs
    st.session_state['latest_design_id'] = design_id
    st.session_state['db_path'] = db_path
