import streamlit as st
import pandas as pd

def render_operations(s_result):
    """Render the Operations tab content."""
    if s_result.workflow:
        ops_data = []
        total_cost = 0.0
        for process in s_result.workflow.processes:
            for op in process.ops:
                cost = op.material_cost_usd + op.instrument_cost_usd
                total_cost += cost
                ops_data.append({
                    "Operation": op.name,
                    "Category": op.category,
                    "Cost": f"${cost:.2f}"
                })
        
        st.dataframe(pd.DataFrame(ops_data), use_container_width=True)
        st.metric("Total Screen Cost", f"${total_cost:,.2f}")
