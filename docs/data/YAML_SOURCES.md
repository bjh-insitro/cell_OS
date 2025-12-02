# YAML Data Sources

| File | Purpose | Status | Notes |
|------|---------|--------|-------|
| `data/raw/vessels.yaml` | Vessel definitions and capacities | Active | Loaded by `VesselLibrary` |
| `data/raw/unit_ops.yaml` | Legacy unit-op catalog | Deprecated | Replaced by `cell_os/unit_ops` modules |
| `data/raw/pricing.yaml` | Historical reagent pricing | Legacy fixture | Use `data/inventory.db` + `scripts/seed_inventory_resources.py` |
| `data/cell_lines.yaml` | Shim for protocol resolver tests | Legacy fixture | Canonical data in `data/cell_lines.db` |
| `data/simulation_parameters.yaml` | Bio VM defaults | Active | Seeded into `data/simulation_params.db` via `scripts/seed_simulation_params.py` |

## Workflow

1. `make bootstrap-data` seeds **cell lines** and **simulation params** into SQLite.
2. `python scripts/seed_inventory_resources.py` hydrates `data/inventory.db` with catalog entries and stock levels.
3. Legacy YAMLs remain for notebooks/tests but should not be edited for production updates. Archive additional historical files under `data/archive/`.
