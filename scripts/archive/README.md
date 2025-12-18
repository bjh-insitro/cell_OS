# Scripts Archive

This directory contains scripts that have been archived because they:
- Were one-time use (migrations, seed/bootstrap)
- Have been superseded by newer implementations
- Are no longer actively maintained

**These scripts are preserved for historical reference.**

---

## Directory Structure

### `migrations/` (6 scripts)
One-time database migration scripts executed during development.
- `migrate_campaigns.py`
- `migrate_cell_lines.py`
- `migrate_experiments.py`
- `migrate_pricing.py`
- `migrate_simulation_params.py`
- `migrate_yaml_to_db.py`

**Status:** Completed migrations, no longer needed

---

### `seed/` (4 scripts)
Bootstrap and seed scripts for initial data setup.
- `bootstrap_data.py` - Initial data setup
- `seed_cell_line_protocols.py` - Protocol seeding
- `seed_inventory_resources.py` - Inventory seeding
- `seed_simulation_params.py` - Params seeding

**Status:** One-time setup, database already populated

---

### `audit/` (2 scripts)
Platform audit scripts superseded by automated tests.
- `audit_entire_platform.py`
- `audit_inventory.py`

**Status:** Replaced by pytest test suite (98% passing)

---

### `demos/` (7 scripts)
Old demonstration scripts superseded by newer implementations.
- `automation_feasibility_demo.py`
- `run_imaging_loop_cli.py`
- `run_imaging_loop_demo.py`
- `run_loop.py`
- `run_loop_v2.py`
- `run_posh_campaign_demo.py`
- `simple_posh_demo.py`

**Status:** Superseded by current demos in `scripts/demos/`

---

## Archived: 2025-12-17

These scripts were archived as part of repository cleanup (see `INTERCONNECTIVITY_AUDIT.md`).

If you need to restore any of these scripts:
```bash
git mv scripts/archive/[category]/[script].py scripts/[category]/
```
