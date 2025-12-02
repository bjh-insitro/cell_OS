#!/usr/bin/env python3
"""
Seed core inventory resources into the canonical SQLite database.

This migrates the most commonly referenced reagents/consumables from the
deprecated pricing.yaml into `data/inventory.db` so economics dashboards
and InventoryManager have real catalog entries to work with.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any

DEFAULT_DB = "data/inventory.db"

RESOURCE_CATALOG = [
    # Cell culture consumables
    {
        "resource_id": "pipette_10ml",
        "name": "10 mL Serological Pipette",
        "category": "consumable",
        "vendor": "Corning",
        "catalog_number": "4488",
        "pack_size": 1,
        "pack_unit": "ea",
        "pack_price_usd": 0.40,
        "logical_unit": "ea",
        "unit_price_usd": 0.40,
        "stock_level": 250,
    },
    {
        "resource_id": "pipette_2ml",
        "name": "2 mL Serological Pipette",
        "category": "consumable",
        "vendor": "Corning",
        "catalog_number": "4487",
        "pack_size": 1,
        "pack_unit": "ea",
        "pack_price_usd": 0.30,
        "logical_unit": "ea",
        "unit_price_usd": 0.30,
        "stock_level": 250,
    },
    {
        "resource_id": "tip_200ul_lr",
        "name": "200 µL Filter Tips (Low Retention)",
        "category": "consumable",
        "vendor": "ThermoFisher",
        "catalog_number": "2079",
        "pack_size": 960,
        "pack_unit": "ea",
        "pack_price_usd": 32.00,
        "logical_unit": "ea",
        "unit_price_usd": 32.00 / 960,
        "stock_level": 2000,
    },
    {
        "resource_id": "tube_15ml_conical",
        "name": "15 mL Conical Tube",
        "category": "consumable",
        "vendor": "Falcon",
        "catalog_number": "352095",
        "pack_size": 50,
        "pack_unit": "ea",
        "pack_price_usd": 16.0,
        "logical_unit": "ea",
        "unit_price_usd": 16.0 / 50,
        "stock_level": 300,
    },
    {
        "resource_id": "micronic_tube",
        "name": "0.75 mL Micronic Tube",
        "category": "consumable",
        "vendor": "Micronic",
        "catalog_number": "MP55151",
        "pack_size": 96,
        "pack_unit": "ea",
        "pack_price_usd": 90.0,
        "logical_unit": "ea",
        "unit_price_usd": 90.0 / 96,
        "stock_level": 400,
    },
    # Media and reagents
    {
        "resource_id": "mtesr_plus_kit",
        "name": "mTeSR Plus Kit",
        "category": "media",
        "vendor": "STEMCELL",
        "catalog_number": "100-0276",
        "pack_size": 500,
        "pack_unit": "mL",
        "pack_price_usd": 395.0,
        "logical_unit": "mL",
        "unit_price_usd": 395.0 / 500,
        "stock_level": 200,
    },
    {
        "resource_id": "dmem_10fbs",
        "name": "DMEM + 10% FBS",
        "category": "media",
        "vendor": "Gibco",
        "catalog_number": "11995-065",
        "pack_size": 500,
        "pack_unit": "mL",
        "pack_price_usd": 80.0,
        "logical_unit": "mL",
        "unit_price_usd": 80.0 / 500,
        "stock_level": 500,
    },
    {
        "resource_id": "cryostor_cs10",
        "name": "CryoStor CS10",
        "category": "media",
        "vendor": "BioLife",
        "catalog_number": "20801",
        "pack_size": 100,
        "pack_unit": "mL",
        "pack_price_usd": 220.0,
        "logical_unit": "mL",
        "unit_price_usd": 2.2,
        "stock_level": 150,
    },
    {
        "resource_id": "dpbs_ca_mg_free",
        "name": "DPBS (Ca/Mg free)",
        "category": "buffer",
        "vendor": "Gibco",
        "catalog_number": "14190-144",
        "pack_size": 500,
        "pack_unit": "mL",
        "pack_price_usd": 15.0,
        "logical_unit": "mL",
        "unit_price_usd": 15.0 / 500,
        "stock_level": 600,
    },
    {
        "resource_id": "accutase",
        "name": "Accutase",
        "category": "enzyme",
        "vendor": "Innovative Cell Tech",
        "catalog_number": "AT104",
        "pack_size": 100,
        "pack_unit": "mL",
        "pack_price_usd": 90.0,
        "logical_unit": "mL",
        "unit_price_usd": 0.90,
        "stock_level": 120,
    },
    {
        "resource_id": "trypsin_edta",
        "name": "Trypsin-EDTA (0.05%)",
        "category": "enzyme",
        "vendor": "Gibco",
        "catalog_number": "25300-054",
        "pack_size": 100,
        "pack_unit": "mL",
        "pack_price_usd": 20.0,
        "logical_unit": "mL",
        "unit_price_usd": 0.20,
        "stock_level": 200,
    },
    {
        "resource_id": "vitronectin",
        "name": "Vitronectin (rhVTN)",
        "category": "coating",
        "vendor": "ThermoFisher",
        "catalog_number": "A14700",
        "pack_size": 50,
        "pack_unit": "mL",
        "pack_price_usd": 350.0,
        "logical_unit": "mL",
        "unit_price_usd": 7.0,
        "stock_level": 25,
    },
    # Analytics + QC reagents
    {
        "resource_id": "mycoplasma_kit",
        "name": "MycoAlert Detection Kit",
        "category": "qc",
        "vendor": "Lonza",
        "catalog_number": "LT07-318",
        "pack_size": 50,
        "pack_unit": "rxn",
        "pack_price_usd": 350.0,
        "logical_unit": "rxn",
        "unit_price_usd": 7.0,
        "stock_level": 50,
    },
    {
        "resource_id": "sterility_kit",
        "name": "Sterility Test Kit",
        "category": "qc",
        "vendor": "BD Biosciences",
        "catalog_number": "225620",
        "pack_size": 10,
        "pack_unit": "tests",
        "pack_price_usd": 120.0,
        "logical_unit": "tests",
        "unit_price_usd": 12.0,
        "stock_level": 20,
    },
    {
        "resource_id": "flow_buffer",
        "name": "Flow Cytometry Buffer",
        "category": "consumable",
        "vendor": "BioLegend",
        "catalog_number": "422201",
        "pack_size": 500,
        "pack_unit": "mL",
        "pack_price_usd": 55.0,
        "logical_unit": "mL",
        "unit_price_usd": 55.0 / 500,
        "stock_level": 300,
    },
    # Instrument time entries modelled as resources for BOMs
    {
        "resource_id": "instrument_bsc_hour",
        "name": "Biosafety Cabinet Hour",
        "category": "instrument",
        "vendor": "cell_OS",
        "catalog_number": "BSC-HOUR",
        "pack_size": 1,
        "pack_unit": "hour",
        "pack_price_usd": 40.0,
        "logical_unit": "hour",
        "unit_price_usd": 40.0,
        "stock_level": 200,
    },
    {
        "resource_id": "instrument_incubator_day",
        "name": "Incubator Day",
        "category": "instrument",
        "vendor": "cell_OS",
        "catalog_number": "INC-DAY",
        "pack_size": 1,
        "pack_unit": "day",
        "pack_price_usd": 25.0,
        "logical_unit": "day",
        "unit_price_usd": 25.0,
        "stock_level": 200,
    },
]


def upsert_resource(cursor: sqlite3.Cursor, resource: Dict[str, Any]) -> None:
    """Insert or update a catalog entry."""
    extra = resource.get("extra", {})
    cursor.execute(
        """
        INSERT INTO resources (
            resource_id, name, category, vendor, catalog_number,
            pack_size, pack_unit, pack_price_usd, logical_unit,
            unit_price_usd, extra_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(resource_id) DO UPDATE SET
            name=excluded.name,
            category=excluded.category,
            vendor=excluded.vendor,
            catalog_number=excluded.catalog_number,
            pack_size=excluded.pack_size,
            pack_unit=excluded.pack_unit,
            pack_price_usd=excluded.pack_price_usd,
            logical_unit=excluded.logical_unit,
            unit_price_usd=excluded.unit_price_usd,
            extra_json=excluded.extra_json
        """,
        (
            resource["resource_id"],
            resource["name"],
            resource.get("category"),
            resource.get("vendor"),
            resource.get("catalog_number"),
            resource.get("pack_size"),
            resource.get("pack_unit"),
            resource.get("pack_price_usd"),
            resource.get("logical_unit"),
            resource.get("unit_price_usd"),
            json.dumps(extra),
        ),
    )
    cursor.execute(
        """
        INSERT INTO stock_levels (resource_id, total_quantity)
        VALUES (?, ?)
        ON CONFLICT(resource_id) DO UPDATE SET
            total_quantity=excluded.total_quantity
        """,
        (resource["resource_id"], float(resource.get("stock_level", 0.0))),
    )


def seed_inventory(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for resource in RESOURCE_CATALOG:
        upsert_resource(cursor, resource)
    conn.commit()
    conn.close()
    return len(RESOURCE_CATALOG)


def main():
    parser = argparse.ArgumentParser(description="Seed inventory resources into SQLite DB.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to inventory SQLite database.")
    args = parser.parse_args()

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    count = seed_inventory(args.db)
    print(f"Seeded {count} catalog resources into {args.db}")


if __name__ == "__main__":
    main()
