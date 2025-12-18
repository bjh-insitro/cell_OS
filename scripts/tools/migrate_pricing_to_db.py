import yaml
import sqlite3
import json
import os

PRICING_YAML = "data/raw/pricing.yaml"
DB_PATH = "data/inventory.db"

def migrate():
    if not os.path.exists(PRICING_YAML):
        print(f"Error: {PRICING_YAML} not found.")
        return

    print(f"Loading pricing from {PRICING_YAML}...")
    with open(PRICING_YAML, 'r') as f:
        data = yaml.safe_load(f) or {}

    items = data.get('items', {})
    print(f"Found {len(items)} items.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure table exists (in case InventoryManager wasn't run yet)
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

    count = 0
    for item_id, d in items.items():
        # Extract known fields
        name = d.get('name', '')
        category = d.get('category', '')
        vendor = d.get('vendor', '')
        catalog_number = str(d.get('catalog_number', ''))
        pack_size = float(d.get('pack_size', 0.0))
        pack_unit = d.get('pack_unit', '')
        pack_price_usd = float(d.get('pack_price_usd', 0.0))
        logical_unit = d.get('logical_unit', '')
        unit_price_usd = float(d.get('unit_price_usd', 0.0))

        # Extract extra fields
        known_keys = {
            'name', 'category', 'vendor', 'catalog_number',
            'pack_size', 'pack_unit', 'pack_price_usd',
            'logical_unit', 'unit_price_usd'
        }
        extra = {k: v for k, v in d.items() if k not in known_keys}
        extra_json = json.dumps(extra)

        cursor.execute("""
            INSERT OR REPLACE INTO resources (
                resource_id, name, category, vendor, catalog_number,
                pack_size, pack_unit, pack_price_usd,
                logical_unit, unit_price_usd, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_id, name, category, vendor, catalog_number,
            pack_size, pack_unit, pack_price_usd,
            logical_unit, unit_price_usd, extra_json
        ))
        count += 1

    conn.commit()
    conn.close()
    print(f"Successfully migrated {count} items to {DB_PATH}.")

if __name__ == "__main__":
    migrate()
