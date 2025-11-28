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
    vessel_lib, inv, ops, builder, inv_manager = init_automation_resources()
    
    if ops is None:
        st.error("Cannot load core automation resources. Check configuration files.")
        return

    st.success("Core Resources Initialized Successfully.")

    st.subheader("1. Inventory/Pricing Audit")
    # --- CRITICAL TEXT CORRECTION HERE ---
    st.markdown("Displays all priced items available for cost calculation (sourced from the **SQLite Inventory Database**). **Shows Pack Price (List Price) for purchasing audit.**")
    
    if pricing:
        items = []
        for item_id, data in pricing.get("items", {}).items():
            items.append({
                "ID": item_id,
                "Name": data.get("name"),
                "Category": data.get("category", "N/A"),
                "Pack Price ($)": data.get("pack_price_usd"), 
                "Pack Size": data.get("pack_size"),
                "Pack Unit": data.get("pack_unit"),
                "Unit Cost ($/mL)": data.get("unit_price_usd"),
                "Vendor": data.get("vendor", "N/A"),         
                "Catalog Number": data.get("catalog_number", "N/A")
            })
        
        # Create the DataFrame
        df_items = pd.DataFrame(items)
        
        # --- COLUMN REORDERING IMPLEMENTATION ---
        column_order = [
            "Name",             
            "Vendor",           
            "Catalog Number",   
            "Category",         
            "Pack Price ($)",   
            "Pack Size",        
            "Pack Unit",        
            "Unit Cost ($/mL)",
            "ID"                
        ]
        
        # Apply the new order
        df_items = df_items[column_order]
        
        st.dataframe(df_items, use_container_width=True)
    else:
        st.info("Pricing data failed to load or is empty.")

    st.subheader("2. Vessel Library Audit")
    # --- CRITICAL TEXT CORRECTION HERE ---
    st.markdown("Displays the properties of all defined lab vessels/plates (sourced from `data/raw/vessels.yaml`).")
    
    try:
        vessels = []
        for item_id, vessel in vessel_lib.vessels.items(): 
            vessels.append({
                "Generic ID": item_id, 
                "Actual Name": getattr(vessel, 'name', 'N/A'),  
                "Vendor": getattr(vessel, 'vendor', 'N/A'),     
                "Product ID": getattr(vessel, 'catalog_number', 'N/A'), 
                "Type": getattr(vessel, 'type', 'N/A'),         
                "Footprint": getattr(vessel, 'footprint', 'N/A'), 
                "Well Count": getattr(vessel, 'well_count', 'N/A'), 
                "Max Vol (mL)": getattr(vessel, 'max_volume_ml', 'N/A'),
            })
            
        df_vessels = pd.DataFrame(vessels)
        
        # Define the desired display order for the Vessel Audit
        column_order = [
            "Actual Name",
            "Vendor",
            "Product ID",
            "Type",
            "Well Count",
            "Footprint",
            "Max Vol (mL)",
            "Generic ID"
        ]
        
        df_vessels = df_vessels[column_order]
        
        st.dataframe(df_vessels, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not introspect VesselLibrary structure. Error: {e}")

    st.subheader("3. Parametric Unit Operations Audit")
    st.markdown("Lists all core unit operation methods available within the system's `ParametricOps` class.")
    
    # Introspect ParametricOps for callable methods (the UnitOps)
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