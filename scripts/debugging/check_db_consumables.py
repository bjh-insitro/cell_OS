import sqlite3
import pandas as pd

DB_PATH = "data/cell_os_inventory.db"
TABLE_NAME = "inventory_items"

def search_consumables_db():
    if not os.path.exists(DB_PATH):
        print(f"\nERROR: Inventory database not found at {DB_PATH}. Run the migration script first.")
        return

    conn = sqlite3.connect(DB_PATH)
    
    # SQL query to search for tubes and pipette tips by name (case-insensitive)
    search_keywords = ['tube', 'pipette tip', 'ul tip', 'ml tube']
    search_conditions = [f"name LIKE '%{keyword}%'" for keyword in search_keywords]
    search_sql = " OR ".join(search_conditions)
    
    query = f"""
    SELECT 
        item_id, 
        name, 
        category, 
        vendor, 
        pack_price_usd,
        pack_size,
        pack_unit
    FROM {TABLE_NAME}
    WHERE {search_sql}
    ORDER BY name;
    """
    
    df_results = pd.read_sql(query, conn)
    conn.close()
    
    if df_results.empty:
        print("\n--- CONFIRMATION: NO matching pipette tips or tubes found in the database. ---")
        print("You must proceed with creating and migrating the consumables.yaml file.")
    else:
        print("\n--- CONFIRMATION: Found existing consumables data ---")
        print(df_results.to_markdown(index=False, numalign="left", stralign="left"))
        print("\nThese items already exist and do not need to be added again.")

if __name__ == "__main__":
    import os
    search_consumables_db()