# dashboard_app/pages/tab_audit_resources.py
import streamlit as st
import pandas as pd
# Import necessary components from utils
from dashboard_app.utils import init_automation_resources

def render_resource_audit(df, pricing):
    st.header("🛠️ Unit Operations & Resource Audit")
    st.markdown("Verify the loaded **resource definitions** (`VesselLibrary`, `Inventory`) and **unit operation mappings** (`ParametricOps`).")

    # -----------------------------------
    # A. Resource Setup 
    # -----------------------------------
    # Use the cached utility function
    vessel_lib, inv, ops, builder = init_automation_resources()
    
    if ops is None:
        st.error("Cannot load core automation resources. Check `data/raw/vessels.yaml` and `data/raw/pricing.yaml`.")
        return

    st.success("Core Resources Initialized Successfully.")

    st.subheader("1. Inventory/Pricing Audit")
    st.markdown("Displays all priced items available for cost calculation (from `data/raw/pricing.yaml`).")
    
    if pricing:
        items = []
        for item_id, data in pricing.get("items", {}).items():
            items.append({
                "ID": item_id,
                "Name": data.get("name"),
                "Category": data.get("category", "N/A"),
                "Unit Price ($)": data.get("unit_price_usd"),
                "Unit": data.get("logical_unit"),
                "Vendor": data.get("vendor", "N/A"),         
                "Catalog Number": data.get("catalog_number", "N/A")
            })
        
        df_items = pd.DataFrame(items)
        column_order = ["ID", "Name", "Category", "Unit Price ($)", "Unit", "Vendor", "Catalog Number"]
        df_items = df_items[column_order]
        
        st.dataframe(df_items, use_container_width=True)
    else:
        st.info("Pricing data failed to load or is empty.")

    st.subheader("2. Vessel Library Audit")
    st.markdown("Displays the properties of all defined lab vessels/plates (from `data/raw/vessels.yaml`).")
    
    try:
        vessels = []
        # NOTE: Assumes VesselLibrary has a .vessels attribute which is a dictionary
        for name, vessel in vessel_lib.vessels.items(): 
            vessels.append({
                "Name": name,
                "Type": getattr(vessel, 'vessel_type', 'N/A'),
                "Max Vol (mL)": getattr(vessel, 'max_volume_ml', 'N/A'),
                "Footprint": getattr(vessel, 'footprint', 'N/A'),
                "Well Count": getattr(vessel, 'well_count', 'N/A')
            })
        st.dataframe(pd.DataFrame(vessels), use_container_width=True)
    except Exception as e:
        st.warning(f"Could not introspect VesselLibrary structure. Error: {e}")

    st.subheader("3. Parametric Unit Operations Audit")
    st.markdown("Lists all core unit operation methods available within the system's `ParametricOps` class.")
    
    op_names = [
        attr for attr in dir(ops) 
        if callable(getattr(ops, attr)) 
        and not attr.startswith("_") 
        and attr not in ['create', 'copy', 'index', 'count'] 
    ]
    
    op_names.sort()
    
    st.info(f"Detected **{len(op_names)}** distinct Parametric Unit Operations:")
    st.code("\n".join(op_names))
    
    st.caption("To verify the cost inputs for a specific operation (e.g., `dispense_reagent`), you must check the source code for `ParametricOps`.")