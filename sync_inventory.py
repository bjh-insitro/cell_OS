import json
import sqlite3
from pathlib import Path

import yaml


def _infer_category(item_id: str) -> str:
    """Heuristic to guess a resource category."""
    lowered = item_id.lower()
    if any(token in lowered for token in ("media", "dmem", "fbs", "pbs", "buffer")):
        return "reagent"
    if "kit" in lowered:
        return "kit"
    if any(token in lowered for token in ("plate", "flask", "pipette", "tip")):
        return "consumable"
    return "misc"


def _extract_required_items(unit_ops: dict) -> set:
    """Collect every resource reference from the unit-op definitions."""
    required = set()
    for details in unit_ops.values():
        for consumable in details.get("consumables", []):
            item_id = consumable.get("item")
            if item_id:
                required.add(item_id)
        for item_id in details.get("items", {}).keys():
            required.add(item_id)
    return required


def sync_inventory(unitops_path: str = "data/raw/unitops.yaml", db_path: str = "data/inventory.db"):
    """Ensure every unit-op requirement exists in the SQLite inventory."""
    unitops_file = Path(unitops_path)
    db_file = Path(db_path)

    if not unitops_file.exists():
        print(f"❌ Error: {unitops_file} not found.")
        return

    if not db_file.exists():
        print(f"❌ Error: {db_file} not found. Have you run the database migrations?")
        return

    with open(unitops_file, "r", encoding="utf-8") as fh:
        raw_ops = yaml.safe_load(fh) or {}

    unit_ops = raw_ops.get("unit_ops", raw_ops)
    required_items = _extract_required_items(unit_ops)
    print(f"🔍 Scanning {len(unit_ops)} unit operations → {len(required_items)} unique resources.")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='resources'"
    )
    if not cursor.fetchone():
        conn.close()
        print("❌ Error: resources table missing in inventory database.")
        return

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='stock_levels'"
    )
    has_stock = bool(cursor.fetchone())
    if not has_stock:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_levels (
                resource_id TEXT PRIMARY KEY,
                total_quantity REAL NOT NULL DEFAULT 0
            )
            """
        )

    cursor.execute("SELECT resource_id FROM resources")
    existing = {row[0] for row in cursor.fetchall()}

    missing = sorted(required_items - existing)
    if not missing:
        conn.close()
        print("\n✅ Inventory DB already contains every referenced resource.")
        return

    print(f"\n⚠️ Found {len(missing)} missing items. Seeding placeholders in {db_file} ...")
    placeholder_rows = []
    for resource_id in missing:
        category = _infer_category(resource_id)
        display_name = resource_id.replace("_", " ").title()
        placeholder_rows.append(
            (
                resource_id,
                f"{display_name} (TODO: populate pricing)",
                category,
                "",
                "",
                1.0,
                "unit",
                0.0,
                "unit",
                0.0,
                json.dumps({"notes": "AUTO-GENERATED placeholder from sync_inventory.py"}),
            )
        )

    cursor.executemany(
        """
        INSERT INTO resources (
            resource_id,
            name,
            category,
            vendor,
            catalog_number,
            pack_size,
            pack_unit,
            pack_price_usd,
            logical_unit,
            unit_price_usd,
            extra_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        placeholder_rows,
    )

    cursor.executemany(
        "INSERT OR IGNORE INTO stock_levels (resource_id, total_quantity) VALUES (?, ?)",
        [(resource_id, 0.0) for resource_id in missing],
    )

    conn.commit()
    conn.close()

    for resource_id in missing:
        print(f"   + Added placeholder for: {resource_id}")

    print("\n✅ Done. Update data/inventory.db → resources table with real pricing/metadata.")


if __name__ == "__main__":
    sync_inventory()
