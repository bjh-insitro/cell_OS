# Repository Interconnectivity Audit

**Date:** 2025-12-17
**Total Scripts:** 47
**Total Source Modules:** 157

---

## Executive Summary

This repository has **7 major systems** with clear boundaries:
1. **Cell Thalamus** (3,382 LOC) - Experimental design & dose-response
2. **Simulation** (3,028 LOC) - Biological simulation & screens
3. **Unit Ops** (2,387 LOC) - Laboratory operations
4. **Database** (1,649 LOC) - Data persistence
5. **API** (1,541 LOC) - REST API endpoints
6. **Hardware** (1,424 LOC) - Liquid handling, imaging, incubators
7. **Workflows** (826 LOC) - Workflow execution

**Key Findings:**
- ✅ Well-organized subdirectory structure (debugging/, demos/, testing/, migrations/)
- ⚠️ **34 potentially unused scripts** (not imported, >7 days old)
- ✅ Design generators are purpose-built (Phase 0, Phase 1, Shape Learning)
- ⚠️ Some legacy modules remain from deprecated APIs

---

## 1. Core Systems Map

### src/cell_os/ Architecture

```
cell_os/
├── cell_thalamus/       3,382 LOC  [Core: Experimental design system]
│   ├── thalamus_agent.py           - Main orchestrator
│   ├── design_generator.py         - Plate layout generation
│   └── dose_response_analyzer.py   - Analysis
│
├── simulation/          3,028 LOC  [Core: Virtual biology]
│   ├── posh_screen_wrapper.py      - POSH screen simulation
│   ├── mcb_wrapper.py              - Master Cell Bank workflows
│   └── spatial_effects.py          - Plate artifacts
│
├── unit_ops/            2,387 LOC  [Core: Lab operations]
│   ├── operations/                 - Cell culture, QC, transfection
│   ├── protocols.py                - Protocol templates
│   └── recipes.py                  - Reagent recipes
│
├── database/            1,649 LOC  [Core: Persistence]
│   ├── cell_thalamus_db.py         - Thalamus results
│   ├── models.py                   - SQLAlchemy models
│   └── repositories/               - Data access layer
│
├── api/                 1,541 LOC  [Core: REST API]
│   ├── thalamus_api.py             - Thalamus endpoints
│   └── main.py                     - FastAPI app
│
├── hardware/            1,424 LOC  [Core: Instrument drivers]
│   ├── biological_virtual.py       - Virtual lab (1,223 LOC)
│   └── hamilton.py, tecan.py       - Liquid handlers
│
└── workflows/             826 LOC  [Core: Workflow engine]
    └── builder.py                  - Workflow construction
```

### Top-Level Modules (single files)

**Most significant:**
- `cellpaint_panels.py` (545 LOC) - Cell Painting assay panels
- `autonomous_executor.py` (514 LOC) - Autonomous experiment execution
- `perturbation_goal.py` (502 LOC) - Perturbation screening goals
- `modeling.py` (463 LOC) - Statistical modeling
- `acquisition.py` (433 LOC) - Adaptive acquisition strategies

---

## 2. Scripts Directory Analysis

### Structure

```
scripts/
├── (root)                15 files  [Entry points & core utilities]
├── debugging/             6 files  [Diagnostic tools]
├── demos/                 9 files  [Examples & demos]
├── migrations/            6 files  [Database migrations]
├── testing/               7 files  [Test utilities]
└── visualization/         4 files  [Plotting tools]
```

### Entry Points (have `if __name__ == '__main__'`)

**Active & maintained:**
- `design_catalog.py` - Design catalog manager
- `design_generator_phase0.py` - Phase 0 design generator
- `design_generator_phase1_causal.py` - Phase 1 causal design generator
- `design_generator_shape_learning.py` - Shape learning design generator
- `export_design_report.py` - Export design to markdown
- `inventory_manager.py` - Inventory management CLI
- `phase0_sentinel_scaffold.py` - Sentinel scaffold generator

**Testing utilities:**
- `testing/spatial_diagnostic.py` - Diagnose spatial artifacts
- `testing/verify_sentinel_scaffold.py` - Validate scaffold integrity

### Module Usage Statistics

**Most imported cell_os modules (from scripts/):**
```
posteriors:           10 scripts  [Bayesian inference]
simulated_executor:    9 scripts  [Simulation execution]
imaging_world_model:   9 scripts  [Imaging simulation]
imaging_goal:          9 scripts  [Imaging objectives]
modeling:              9 scripts  [Statistical models]
imaging_acquisition:   8 scripts  [Imaging data collection]
database:              7 scripts  [Database access]
imaging_loop:          5 scripts  [Closed-loop imaging]
```

**Rarely used modules:**
```
cell_thalamus:         1 script   [Only used in standalone_cell_thalamus.py]
```

---

## 3. Potentially Unused Scripts

### 🗑️ Candidates for Archival (34 scripts)

**Criteria:** Not imported anywhere, >7 days old

#### High Confidence (likely superseded or one-time use)

**Auditing scripts (replaced by tests):**
- `audit_entire_platform.py` - Platform audit
- `audit_inventory.py` - Inventory audit

**Seed/bootstrap scripts (one-time setup):**
- `bootstrap_data.py` - Initial data setup
- `seed_cell_line_protocols.py` - Protocol seeding
- `seed_inventory_resources.py` - Inventory seeding
- `seed_simulation_params.py` - Params seeding

**Migration scripts (one-time):**
- `migrations/migrate_campaigns.py`
- `migrations/migrate_cell_lines.py`
- `migrations/migrate_experiments.py`
- `migrations/migrate_pricing.py`
- `migrations/migrate_yaml_to_db.py`

**Old debugging scripts:**
- `debugging/check_db_consumables.py`
- `debugging/debug_recipe.py`
- `debugging/debug_workflow.py`
- `debugging/diagnose_posh_optimizer.py`
- `debugging/diagnose_score_landscape.py`
- `debugging/generate_synthetic_embeddings.py`

**Old demo scripts:**
- `demos/automation_feasibility_demo.py`
- `demos/demo_bio_vm_improvements.py`
- `demos/run_imaging_loop_cli.py`
- `demos/run_imaging_loop_demo.py`
- `demos/run_loop.py`
- `demos/run_loop_v2.py`
- `demos/run_posh_campaign_demo.py`
- `demos/simple_posh_demo.py`

**Old testing scripts:**
- `testing/imaging_loop_smoketest.py`
- `testing/qc_slope_test.py`
- `testing/run_imaging_simulation.py`
- `testing/test_imaging_cost.py`

**Utility scripts (check if still used):**
- `update_inventory_bom.py` - Update BOMs
- `upload_db_to_s3.py` - S3 sync

#### Medium Confidence (verify usage)

**demos/create_custom_design.py** - May be replaced by UI or design generators

---

## 4. Design Generator Analysis

### Three Purpose-Built Generators

```
design_generator_phase0.py            16,525 bytes  [Generic Phase 0 explorer]
design_generator_phase1_causal.py     12,050 bytes  [Focused causal estimation]
design_generator_shape_learning.py    17,301 bytes  [Nuisance identification]
```

**Status:** ✅ All three are actively maintained and serve distinct purposes
- Phase 0: Broad compound screening, 2 reps/dose
- Phase 1: Tight dose-response, 8 reps + 12 vehicle
- Shape Learning: 6 enhancements for nuisance model

**No duplicates detected.** Each has unique design philosophy per `docs/designs/`.

---

## 5. Dependency Patterns

### Import Patterns

**Scripts → cell_os connections:**
- 25/47 scripts (53%) import cell_os modules
- 22/47 scripts (47%) are standalone utilities (design generators, migrations, etc.)

**Most common external dependencies:**
```
numpy:      15 scripts
pandas:     12 scripts
yaml:        9 scripts
matplotlib:  4 scripts
```

### Interconnectivity Score: **Medium-Low**

**Observations:**
- ✅ Core systems are well-separated (hardware, database, simulation)
- ✅ Most scripts are independent entry points (not libraries)
- ⚠️ Some older modules (`cell_line_db`, `campaign_db`) may be superseded by `database/repositories/`

---

## 6. Legacy/Deprecated Code

### Potentially Deprecated Modules (verify)

**Old database APIs (may be superseded by `database/repositories/`):**
- `cell_line_db.py` (407 LOC) - Used in 2 scripts
- `campaign_db.py` (380 LOC) - Used in 2 scripts
- `simulation_params_db.py` (371 LOC) - Marked as deprecated in test warnings

**Check:** Are these still needed, or fully replaced by `database/repositories/`?

### Migration Status

**Active warning in tests:**
```
tests/integration/test_legacy_databases.py:
  DeprecationWarning: cell_os.simulation_params_db is deprecated and will be removed.
  Use cell_os.database.repositories.simulation_params instead.
```

**Recommendation:** Complete the migration and remove old APIs.

---

## 7. Cleanup Recommendations

### Phase 1: Archive One-Time Scripts (Low Risk)

**Move to `scripts/archive/`:**
```bash
mkdir -p scripts/archive/{migrations,seed,audit}

# Migrations (one-time use)
mv scripts/migrations/*.py scripts/archive/migrations/

# Seed scripts (one-time setup)
mv scripts/seed_*.py scripts/archive/seed/
mv scripts/bootstrap_data.py scripts/archive/seed/

# Audit scripts (replaced by tests)
mv scripts/audit_*.py scripts/archive/audit/
```

**Impact:** Zero (these are never imported)

### Phase 2: Archive Old Demos (Medium Risk)

**Move to `scripts/archive/demos/`:**
```bash
mkdir -p scripts/archive/demos

# Old imaging loop demos (superseded)
mv scripts/demos/run_loop*.py scripts/archive/demos/
mv scripts/demos/run_imaging_loop*.py scripts/archive/demos/

# Old POSH demos
mv scripts/demos/simple_posh_demo.py scripts/archive/demos/
mv scripts/demos/run_posh_campaign_demo.py scripts/archive/demos/
```

**Impact:** Low (check if referenced in docs)

### Phase 3: Clean Up Debugging Scripts (Medium Risk)

**Review & archive if unused:**
```bash
# Check if these are still used for development
scripts/debugging/diagnose_posh_optimizer.py
scripts/debugging/diagnose_score_landscape.py
scripts/debugging/generate_synthetic_embeddings.py
```

**Action:** Ask user if these are still needed for debugging workflows.

### Phase 4: Complete Legacy Database Migration (High Impact)

**Steps:**
1. Confirm all code uses `database/repositories/` instead of old APIs
2. Remove deprecated modules:
   - `cell_line_db.py`
   - `campaign_db.py`
   - `simulation_params_db.py`
3. Update all imports
4. Run full test suite

**Impact:** Medium-High (requires careful migration)

---

## 8. System Health

### ✅ Strengths

1. **Clear separation of concerns** - 7 major systems, minimal coupling
2. **Well-organized scripts/** - Subdirectories for debugging, demos, testing
3. **Purpose-built design generators** - No duplicate functionality
4. **Good test coverage** - 495 tests, 98% passing

### ⚠️ Areas for Improvement

1. **34 unused scripts** - Can be archived
2. **Legacy database APIs** - Migration incomplete
3. **Some scripts lack documentation** - Purpose unclear from filename alone

### 🎯 Overall Assessment: **Good**

The repository is well-structured with clear system boundaries. Main cleanup needed:
- Archive one-time use scripts (migrations, seed, audit)
- Complete database API migration
- Document purpose of remaining scripts

---

## 9. Quick Reference: What Calls What

### Core Systems Entry Points

**Cell Thalamus:**
```
standalone_cell_thalamus.py
  └─> cell_thalamus/thalamus_agent.py
      ├─> cell_thalamus/design_generator.py
      ├─> hardware/biological_virtual.py
      └─> database/cell_thalamus_db.py
```

**Design Generation:**
```
design_generator_phase0.py
design_generator_phase1_causal.py
design_generator_shape_learning.py
  └─> phase0_sentinel_scaffold.py (shared)
  └─> outputs: data/designs/*.json
```

**API Server:**
```
src/cell_os/api/main.py
  ├─> api/thalamus_api.py
  ├─> cell_thalamus/thalamus_agent.py
  └─> database/
```

**Dashboard:**
```
dashboard_app/
  └─> frontend/ (React)
      └─> CellThalamusService.ts
          └─> api/thalamus_api.py
```

---

## 10. Action Items

### Immediate (Low Risk)
- [ ] Archive migrations/, seed scripts, audit scripts
- [ ] Archive old demo scripts (after doc review)
- [ ] Update QUICKSTART.md to reference active scripts only

### Short Term (Medium Risk)
- [ ] Review debugging/ scripts with team
- [ ] Archive unused debugging scripts
- [ ] Add README.md to each scripts/ subdirectory

### Long Term (High Impact)
- [ ] Complete database API migration
- [ ] Remove deprecated modules (cell_line_db, campaign_db, simulation_params_db)
- [ ] Update all imports to use database/repositories/

---

## Appendix: File Counts

```
System                    Files    Lines    Status
─────────────────────────────────────────────────────
cell_thalamus               10    3,382    ✅ Active
simulation                  12    3,028    ✅ Active
unit_ops                    15    2,387    ✅ Active
database                    10    1,649    ✅ Active
api                          3    1,541    ✅ Active
hardware                     5    1,424    ✅ Active
lab_world_model              7    1,044    ✅ Active
workflows                    5      826    ✅ Active
workflow_execution           5      629    ✅ Active

scripts/ (active)           13      N/A    ✅ Active
scripts/debugging            6      N/A    ⚠️ Review
scripts/demos                9      N/A    ⚠️ Archive 7/9
scripts/migrations           6      N/A    🗑️ Archive all
scripts/testing              7      N/A    ✅ Active
```

**Legend:**
- ✅ Active: In use, well-maintained
- ⚠️ Review: Needs verification
- 🗑️ Archive: Can be moved to archive/
