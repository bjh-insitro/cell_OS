# Codebase Cleanup Status

**Last Updated**: 2025-01-12

This document tracks cleanup recommendations and their status.

## Completed Cleanup (2025-01-12)

### Module Consolidation

| Task | Status |
|------|--------|
| Rename `sim/` to `biology/` | Done |
| Move epistemic modules into `epistemic_agent/` | Done |
| Consolidate POSH modules into `posh/` | Done |
| Consolidate imaging modules into `imaging/` | Done |
| Move simulation executors into `simulation/` | Done |
| Remove empty orphan packages | Done |
| Archive deprecated `plate_executor.py` | Done |

### Root Directory Cleanup

| Task | Status |
|------|--------|
| Move loose markdown docs to `docs/` | Done |
| Move images to `artifacts/` | Done |
| Move shell scripts to `scripts/` | Done |
| Consolidate `output/`, `runs/` (gitignored) | Done |
| Clean up `.gitignore` duplicates | Done |

### Scripts Organization

| Task | Status |
|------|--------|
| Move `run_*.py` to `scripts/runners/` | Done |
| Move `analyze_*.py` to `scripts/analysis/` | Done |
| Move `validate_*.py` to `scripts/validation/` | Done |
| Move `demo_*.py` to `scripts/demos/` | Done |
| Merge `debug/` into `debugging/` | Done |
| Merge `verify/` into `validation/` | Done |
| Merge `utils/` into `tools/` | Done |

### Documentation Updates

| Task | Status |
|------|--------|
| Update README.md project structure | Done |
| Update DEVELOPER_REFERENCE.md | Done |
| Create CONTRIBUTING.md | Done |
| Create CHANGELOG.md | Done |
| Fix old import paths in docs | Done |

## Remaining Cleanup Tasks

### Low Priority

- [ ] Review and potentially archive old milestone docs in `docs/`
- [ ] Consolidate duplicate guides content
- [ ] Add type hints to legacy modules
- [ ] Remove unused utility functions

### Not Planned

- **Wet-lab integration** - Out of scope
- **UI/UX overhaul** - Not needed for research testbed
- **Performance optimization** - Current performance is adequate

## Current Project Structure

```
cell_OS/
├── src/cell_os/
│   ├── epistemic_agent/     # Epistemic control system
│   ├── hardware/            # Synthetic data generator
│   ├── biology/             # Pure biology models
│   ├── simulation/          # Simulation executors
│   ├── posh/                # POSH workflow
│   ├── imaging/             # Imaging workflow
│   ├── core/                # Data structures
│   ├── database/            # Repositories
│   └── ...
├── scripts/
│   ├── runners/             # Entry points
│   ├── analysis/            # Analysis
│   ├── validation/          # Verification
│   ├── tools/               # Utilities
│   └── ...
├── tests/
├── docs/
├── data/
└── ...
```

See `README.md` and `docs/DEVELOPER_REFERENCE.md` for full structure.
