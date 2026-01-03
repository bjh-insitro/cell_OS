# Refactor Snapshots - December 22, 2024

## What happened
Three large modules were split into submodules:

1. **beam_search.py** → `beam_search/` submodule (commit 94922bd)
   - Split 1,300-line monolithic file into focused modules
   - action_bias.py, types.py, runner.py, search.py

2. **boundary_detection.py** → (need to check refactor commit)

3. **chooser.py** → (need to check refactor commit)

## Why these snapshots exist
Pre-refactor versions kept as rollback insurance during validation period.

## When to delete
- After January 15, 2025 if no rollback needed
- Or after all beam_search tests pass for 2+ weeks
- Or when commit is merged to main and stable

## How to recover if needed
```bash
# Restore from snapshot
cp archive/refactors/2024-12-22_module_splits/beam_search.py.bak \
   src/cell_os/hardware/beam_search.py
```

Or use git history:
```bash
git show 94922bd^:src/cell_os/hardware/beam_search.py
```
