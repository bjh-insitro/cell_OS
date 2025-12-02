import sqlite3
import pytest

from cell_os.inventory import Inventory, Resource
from cell_os.inventory_manager import InventoryManager


def build_inventory():
    resources = {
        "media": Resource(
            resource_id="media",
            name="Growth Media",
            vendor="Acme",
            catalog_number="GM-001",
            pack_size=1000,
            pack_unit="mL",
            pack_price_usd=120.0,
            logical_unit="mL",
            unit_price_usd=0.12,
            category="media",
            stock_level=0.0,
        )
    }
    return Inventory(resources=resources)


def test_inventory_syncs_with_manager(tmp_path):
    inv = build_inventory()
    db_path = tmp_path / "inventory.db"
    manager = InventoryManager(inv, db_path=str(db_path))

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT total_quantity FROM stock_levels WHERE resource_id = 'media'")
    base = cursor.fetchone()[0]
    conn.close()

    inv.add_stock("media", 5.0, "mL")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT total_quantity FROM stock_levels WHERE resource_id = 'media'")
    row = cursor.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == pytest.approx(base + 5.0)

    inv.consume("media", 2.0, "mL")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT total_quantity FROM stock_levels WHERE resource_id = 'media'")
    row_after = cursor.fetchone()
    conn.close()
    assert row_after[0] == pytest.approx(base + 3.0)
