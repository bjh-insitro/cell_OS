# Pricing YAML Deprecation Notice

**Date:** 2025-11-30  
**Status:** ✅ DEPRECATED - Use inventory database instead

## Summary

The `data/raw/pricing.yaml` file has been **deprecated** in favor of the SQLite-based inventory database (`data/inventory.db`).

## Migration

All pricing data has been migrated to the `resources` table in `data/inventory.db`.

To re-run the migration (if you've updated pricing.yaml):
```bash
python3 tools/migrate_pricing_to_db.py
```

## Recommended Workflow

```bash
# 1. Bootstrap cell lines + simulation params
make bootstrap-data

# 2. Seed inventory catalog entries (replaces pricing.yaml editing)
python3 scripts/seed_inventory_resources.py --db data/inventory.db

# 3. Launch the dashboard/agents
streamlit run dashboard_app/app.py
```

## What Changed

### Before (YAML-based)
```python
from cell_os.inventory import Inventory

inv = Inventory("data/raw/pricing.yaml")
```

### After (Database-based)
```python
from cell_os.inventory import Inventory

inv = Inventory()  # Automatically loads from data/inventory.db
```

## Updated Files

The following files have been updated to use the database:

### Core Library
- ✅ `src/cell_os/inventory.py` - Now prioritizes database, falls back to YAML
- ✅ `src/cell_os/inventory_manager.py` - Added `resources` table schema
- ✅ `src/cell_os/budget_manager.py` - `YamlPricingInventory` now loads from DB
- ✅ `src/cell_os/world_init.py` - Removed `pricing_yaml_path` parameter
- ✅ `src/cell_os/protocol_resolver.py` - Uses DB by default
- ✅ `src/cell_os/scenarios.py` - Uses DB by default

### Dashboard
- ✅ `dashboard_app/utils.py` - Removed YAML fallback, DB-only

### Migration Tool
- ✅ `tools/migrate_pricing_to_db.py` - Migrates YAML → SQLite

## Files Still Referencing pricing.yaml

The following files still reference `pricing.yaml` but are **non-critical** (examples, notebooks, docs):

- `src/examples/simple_process_demo.py` - Example file
- `notebooks/*.ipynb` - Jupyter notebooks (historical)
- `scripts/*.py` - Standalone scripts
- `docs/**/*.md` - Documentation
- `README.md` - Documentation

These can be updated incrementally or left as-is for backward compatibility examples.
See `docs/data/YAML_SOURCES.md` for the current catalog of YAML fixtures vs. database-backed sources.

## Database Schema

The `resources` table in `data/inventory.db`:

```sql
CREATE TABLE resources (
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
);
```

## Benefits

1. **Single Source of Truth** - All inventory data (catalog + stock) in one database
2. **Better Performance** - SQL queries faster than YAML parsing
3. **Transactional Safety** - Database ACID properties
4. **Easier Updates** - SQL UPDATE instead of YAML editing
5. **Integration Ready** - Can connect to external inventory systems

## Backward Compatibility

The `Inventory` class still accepts `pricing_path` for backward compatibility:

```python
# This still works (but not recommended)
inv = Inventory(pricing_path="data/raw/pricing.yaml")
```

However, the database is checked **first**, so if `data/inventory.db` exists, it will be used.

## Future Work

- [ ] Update example scripts to use database
- [ ] Update documentation to reflect database usage
- [ ] Consider removing YAML fallback entirely in v2.0
- [ ] Add database migration/versioning system
