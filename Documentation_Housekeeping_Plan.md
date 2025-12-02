# Documentation Housekeeping Plan

## Overview
The project currently has more than 101 Markdown files scattered across multiple directories. This plan organizes them into logical categories and proposes consolidation to improve maintainability and discoverability.

## Current State Analysis

### File Distribution
- Root directory: 7 files (`REFACTORING_PROGRESS.md`, `PRICING_YAML_DEPRECATED.md`, etc.)
- `docs/`: 21 files + 6 subdirectories
- `docs/guides/`: 15 files
- `docs/architecture/`: 6 files
- `docs/refactor_plans/`: 1 file
- `dashboard_assets/**`: 3 validation reports
- `tests/`: 2 files

### Key Categories Identified
1. **Session Summaries (4 files) – CONSOLIDATE**
   - `SESSION_SUMMARY.md` (root)
   - `docs/SESSION_SUMMARY.md`
   - `docs/SESSION_SUMMARY_20251129.md`
   - `docs/BIO_VM_SESSION_SUMMARY.md`
   - **Action:** Archive to `docs/archive/sessions/` with date prefixes.

2. **Refactoring Documentation (7 files) – CONSOLIDATE**
   - `REFACTORING_PROGRESS.md` (root)
   - `REFACTORING_QUICK_REF.md` (root)
   - `FINAL_REFACTORING_SUMMARY.md` (root)
   - `dashboard_app/REFACTORING_SUMMARY.md`
   - `docs/REFACTORING_OPPORTUNITIES.md`
   - `docs/PARAMETRIC_OPS_REFACTORING.md`
   - `docs/refactor_plans/BOM_TRACKING_REFACTOR.md` (**KEEP – active**)
   - **Action:**
     - Keep `BOM_TRACKING_REFACTOR.md` in `docs/refactor_plans/`.
     - Archive completed refactorings to `docs/archive/refactorings/`.
     - Keep `REFACTORING_OPPORTUNITIES.md` as the active planning doc.

3. **Migration/Implementation Summaries (13 files) – CONSOLIDATE**
   - `HOUSEKEEPING_SUMMARY.md` (root)
   - `docs/DATABASE_MIGRATION_SUMMARY.md`
   - `docs/DATABASE_REPOSITORY_MIGRATION.md`
   - `docs/CELL_LINE_DB_MIGRATION.md`
   - `docs/SIMULATION_PARAMS_DB_SUMMARY.md`
   - `docs/IMPLEMENTATION_SUMMARY.md`
   - `docs/MCB_SIMULATION_AUDIT.md`
   - `docs/guides/REAGENT_PRICING_SUMMARY.md`
   - `docs/guides/AUTOMATION_SUMMARY.md`
   - `tests/integration/MCB_TEST_SUMMARY.md`
   - Plus validation reports
   - **Action:** Consolidate into a single `docs/MIGRATION_HISTORY.md` with sections.

4. **Active Guides (15 files) – ORGANIZE**
   - Location: `docs/guides/`
   - **Action:** Keep existing files but add index file `docs/guides/README.md`.

5. **Architecture Documentation (6 files) – KEEP**
   - Location: `docs/architecture/`
   - **Action:** Keep as-is; these are reference docs.

## Proposed New Structure
```
cell_OS/
├── README.md
├── STATUS.md (consolidated status + next steps)
├── CHANGELOG.md
│
├── docs/
│   ├── README.md (documentation index)
│   ├── MIGRATION_HISTORY.md (consolidated)
│   ├── REFACTORING_OPPORTUNITIES.md
│   │
│   ├── guides/
│   │   ├── README.md
│   │   └── [15 existing guide files]
│   │
│   ├── architecture/
│   │   └── [6 existing files]
│   │
│   ├── refactor_plans/
│   │   └── BOM_TRACKING_REFACTOR.md
│   │
│   └── archive/
│       ├── sessions/
│       ├── refactorings/
│       └── migrations/
```

## Implementation Steps
1. **Phase 1: Create Archive Structure**
   - Create `docs/archive/`.
   - Create subdirectories: `sessions/`, `refactorings/`, `migrations/`.

2. **Phase 2: Archive Session Summaries**
   - Move session summaries to `docs/archive/sessions/`.
   - Rename with date prefixes (YYYY-MM-DD).

3. **Phase 3: Consolidate Migration Docs**
   - Create `docs/MIGRATION_HISTORY.md`.
   - Extract key information from each migration summary.
   - Move originals to `docs/archive/migrations/`.

4. **Phase 4: Archive Completed Refactorings**
   - Move completed refactoring docs to `docs/archive/refactorings/`.
   - Keep active plans in `docs/refactor_plans/`.

5. **Phase 5: Consolidate Root Status Files**
   - Create new `STATUS.md` in root.
   - Archive old status files.

6. **Phase 6: Create Index Files**
   - Create `docs/README.md`.
   - Create `docs/guides/README.md`.

## Success Criteria
- ✅ Root directory has ≤5 Markdown files.
- ✅ All session summaries archived with dates.
- ✅ Single consolidated migration history.
- ✅ Clear documentation index.
- ✅ Active vs. archived docs clearly separated.

## Estimated Impact
- **Before:** 101+ Markdown files across 10+ directories.
- **After:** ~60 active files + ~40 archived files.
- **Reduction:** Approximately 40% fewer files in active directories.
