"""
Script to populate inventory with resources needed for BOM tracking.
"""
import sqlite3
import json
from datetime import datetime

DB_PATH = "data/inventory.db"

NEW_RESOURCES = [
    # Analysis
    {
        "resource_id": "flow_sheath_fluid",
        "name": "Flow Cytometry Sheath Fluid",
        "category": "reagent",
        "vendor": "Thermo Fisher",
        "catalog_number": "88-8888",
        "pack_size": 20.0,
        "pack_unit": "L",
        "pack_price_usd": 50.0,
        "logical_unit": "mL",
        "unit_price_usd": 50.0 / (20.0 * 1000),
    },
    {
        "resource_id": "flow_tube_5ml",
        "name": "5mL Polystyrene Round-Bottom Tube",
        "category": "consumable",
        "vendor": "Corning",
        "catalog_number": "352054",
        "pack_size": 1000.0,
        "pack_unit": "unit",
        "pack_price_usd": 200.0,
        "logical_unit": "unit",
        "unit_price_usd": 0.20,
    },
    {
        "resource_id": "flow_cytometer_usage",
        "name": "Flow Cytometer Usage",
        "category": "instrument_usage",
        "vendor": "Internal",
        "catalog_number": "N/A",
        "pack_size": 1.0,
        "pack_unit": "hour",
        "pack_price_usd": 60.0,
        "logical_unit": "sample",
        "unit_price_usd": 0.50, # Per sample estimate
    },
    {
        "resource_id": "cell_counter_slides",
        "name": "Cell Counter Slides",
        "category": "consumable",
        "vendor": "ChemoMetec",
        "catalog_number": "941-0012",
        "pack_size": 100.0,
        "pack_unit": "unit",
        "pack_price_usd": 300.0,
        "logical_unit": "unit",
        "unit_price_usd": 3.00,
    },
    {
        "resource_id": "nc202_usage",
        "name": "NucleoCounter NC-202 Usage",
        "category": "instrument_usage",
        "vendor": "Internal",
        "catalog_number": "N/A",
        "pack_size": 1.0,
        "pack_unit": "hour",
        "pack_price_usd": 0.0,
        "logical_unit": "sample",
        "unit_price_usd": 0.10,
    },
    {
        "resource_id": "cloud_compute_analysis",
        "name": "Cloud Compute Analysis",
        "category": "service",
        "vendor": "AWS",
        "catalog_number": "N/A",
        "pack_size": 1.0,
        "pack_unit": "hour",
        "pack_price_usd": 1.0,
        "logical_unit": "sample",
        "unit_price_usd": 0.05,
    },
    {
        "resource_id": "ngs_library_prep_kit",
        "name": "NGS Library Prep Kit",
        "category": "reagent",
        "vendor": "Illumina",
        "catalog_number": "20020594",
        "pack_size": 96.0,
        "pack_unit": "reaction",
        "pack_price_usd": 4800.0,
        "logical_unit": "reaction",
        "unit_price_usd": 50.0,
    },
    {
        "resource_id": "sequencer_usage",
        "name": "Sequencer Usage",
        "category": "instrument_usage",
        "vendor": "Internal",
        "catalog_number": "N/A",
        "pack_size": 1.0,
        "pack_unit": "run",
        "pack_price_usd": 500.0,
        "logical_unit": "sample",
        "unit_price_usd": 10.0,
    },
    # Common Consumables
    {
        "resource_id": "plate_96well_u",
        "name": "96-Well U-Bottom Plate",
        "category": "consumable",
        "vendor": "Corning",
        "catalog_number": "3799",
        "pack_size": 50.0,
        "pack_unit": "unit",
        "pack_price_usd": 150.0,
        "logical_unit": "unit",
        "unit_price_usd": 3.00,
    },
    {
        "resource_id": "pipette_200ul",
        "name": "200µL Pipette Tips",
        "category": "consumable",
        "vendor": "Rainin",
        "catalog_number": "30389239",
        "pack_size": 960.0,
        "pack_unit": "unit",
        "pack_price_usd": 100.0,
        "logical_unit": "unit",
        "unit_price_usd": 0.10,
    },
]

def update_inventory():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Ensure table exists (it should from InventoryManager, but just in case)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            resource_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            vendor TEXT,
            catalog_number TEXT,
            pack_size REAL,
            pack_unit TEXT,
            pack_price_usd REAL,
            logical_unit TEXT,
            unit_price_usd REAL,
            extra_json TEXT
        )
    """)
    
    for res in NEW_RESOURCES:
        print(f"Updating {res['resource_id']}...")
        cursor.execute("""
            INSERT OR REPLACE INTO resources (
                resource_id, name, category, vendor, catalog_number,
                pack_size, pack_unit, pack_price_usd, logical_unit, unit_price_usd, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            res["resource_id"],
            res["name"],
            res["category"],
            res["vendor"],
            res["catalog_number"],
            res["pack_size"],
            res["pack_unit"],
            res["pack_price_usd"],
            res["logical_unit"],
            res["unit_price_usd"],
            json.dumps({})
        ))
        
    conn.commit()
    conn.close()
    print("Inventory updated successfully.")

if __name__ == "__main__":
    update_inventory()
