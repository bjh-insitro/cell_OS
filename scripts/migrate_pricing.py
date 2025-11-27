# scripts/migrate_pricing.py
import yaml
import sqlite3
import pandas as pd
import os

# --- Configuration ---
YAML_PATH = "data/raw/pricing.yaml"
DB_PATH = "data/cell_os_inventory.db"
TABLE_NAME = "inventory_items"

def migrate_yaml_to_db():
    print(f"--- Starting Migration from {YAML_PATH} to {DB_PATH} ---")
    
    # 1. Load data from YAML
    if not os.path.exists(YAML_PATH):
        print(f"ERROR: YAML file not found at {YAML_PATH}")
        return
    
    with open(YAML_PATH, 'r') as f:
        data = yaml.safe_load(f)
    
    # Prepare data for insertion
    records = []
    for item_id, item_data in data.get('items', {}).items():
        records.append({
            'item_id': item_id,
            'name': item_data.get('name'),
            'category': item_data.get('category'),
            'vendor': item_data.get('vendor'),
            'catalog_number': item_data.get('catalog_number'),
            'pack_size': item_data.get('pack_size'),
            'pack_unit': item_data.get('pack_unit'),
            'pack_price_usd': item_data.get('pack_price_usd'),
            'unit_price_usd': item_data.get('unit_price_usd')
        })
    
    if not records:
        print("WARNING: No items found in YAML file. Database will be empty.")
        return

    # 2. Connect to SQLite and create table
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Define the CREATE TABLE SQL command
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        item_id TEXT PRIMARY KEY,
        name TEXT,
        category TEXT,
        vendor TEXT,
        catalog_number TEXT,
        pack_size REAL,
        pack_unit TEXT,
        pack_price_usd REAL,
        unit_price_usd REAL
    );
    """
    cursor.execute(create_table_sql)
    conn.commit()

    # 3. Insert or Replace data (ensures clean update if run multiple times)
    insert_sql = f"""
    INSERT OR REPLACE INTO {TABLE_NAME} VALUES (
        :item_id, :name, :category, :vendor, :catalog_number, 
        :pack_size, :pack_unit, :pack_price_usd, :unit_price_usd
    );
    """
    cursor.executemany(insert_sql, records)
    conn.commit()

    # 4. Verification and Cleanup
    count = cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
    conn.close()
    
    print(f"SUCCESS: Migrated {count} items to the database.")

if __name__ == "__main__":
    # Ensure the data directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    migrate_yaml_to_db()

# NOTE: You will need to install the PyYAML library if you haven't already: pip install PyYAML