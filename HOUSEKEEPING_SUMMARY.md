# Post-Housekeeping Summary

## 2025-11-25 – Repo hygiene pass

- Packaging
  - `cell_os` is the canonical package (src-layout).
  - `cell_os.core.world_model` is a thin shim exposing:
    - core unit-op primitives (`Artifact`, `UnitOp`, etc.)
    - `LabWorldModel` as `WorldModel` for legacy imports.
- Phase -1 (imaging dose loop)
  - All imaging acquisition tests passing.
  - `scripts/imaging_loop_smoketest.py` runs without errors.
- Phase 0 (perturbation loop)
  - POSH pooled barcode capacity model replaces plate-based constraints.
  - MorphologyEngine scaffold integrated; posterior supports embeddings.
  - Integration tests for perturbation loop all green.
- Infrastructure
  - `Inventory` depletion / restock tests green (`DMEM_MEDIA`, `FBS` defined in pricing.yaml).
  - ActiveLearner / run_loop imports ok via `cell_os.core.world_model`.
  - Full `venv/bin/pytest -q` passes as of this date.


## ✅ Completed Phase 1 Housekeeping

All safe, non-breaking organizational improvements complete.

## Key Changes

### 1. Scripts Directory
**Created**: `scripts/`  
**Moved files**:
- `automation_feasibility_demo.py`
- `dashboard.py`  
- `debug_recipe.py`
- `run_loop.py`

### 2. Config Consolidation  
**Created**: `config/` (root level)  
**Moved**:
- Guide design templates
- sgRNA repository configs

### 3. Data Cleanup
**Fixed**: `data/raw/sbat_gene_list.csv`
- Removed messy tab-delimited headers
- Now clean single-column format

### 4. Documentation
**Archived**: `phase0_task.md` → `docs/archive/`
**Updated**: `README.md` with new structure

### 5. Git Hygiene
Updated `.gitignore` to exclude large guide CSVs

## Updated Quick Start

```bash
# Run the loop (updated path)
python scripts/run_loop.py

# Launch dashboard (updated path)
streamlit run scripts/dashboard.py
```

## Recommendation

✅ **Commit these changes** - they're all safe and improve organization  
⏸️ **Phase 2** (src/ reorganization) - save for later to avoid breaking active dev
