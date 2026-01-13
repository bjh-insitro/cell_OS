# Changelog

All notable changes to cell_OS are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- CONTRIBUTING.md with contribution guidelines
- CHANGELOG.md (this file)

### Changed
- Updated README.md with new project structure
- Updated DEVELOPER_REFERENCE.md with current paths and components

### Fixed
- Fixed outdated import paths in 46+ documentation files

## [2025-01-12] - Project Reorganization

### Added
- `biology/` package (renamed from `sim/`) for pure biology models
- `posh/` package consolidating POSH workflow modules
- `imaging/` package consolidating imaging workflow modules
- `legacy_core/` package for backward-compatible legacy DB code
- `scripts/runners/` directory for all run_*.py entry points
- Organized scripts into subdirectories (analysis/, validation/, tools/, etc.)

### Changed
- **BREAKING**: Renamed `sim/` to `biology/` - update imports:
  - `from cell_os.sim.biology_core` → `from cell_os.biology.biology_core`
- **BREAKING**: Moved epistemic modules into `epistemic_agent/`:
  - `from cell_os.epistemic_control` → `from cell_os.epistemic_agent.control`
  - `from cell_os.epistemic_debt` → `from cell_os.epistemic_agent.debt`
  - `from cell_os.epistemic_penalty` → `from cell_os.epistemic_agent.penalty`
- **BREAKING**: Consolidated POSH modules into `posh/` package:
  - `from cell_os.posh_scenario` → `from cell_os.posh.scenario`
  - `from cell_os.posh_library_design` → `from cell_os.posh.library_design`
  - `from cell_os.posh_lv_moi` → `from cell_os.posh.lv_moi`
- **BREAKING**: Consolidated imaging modules into `imaging/` package:
  - `from cell_os.imaging_acquisition` → `from cell_os.imaging.acquisition`
  - `from cell_os.imaging_loop` → `from cell_os.imaging.loop`
  - `from cell_os.imaging_goal` → `from cell_os.imaging.goal`
- **BREAKING**: Moved simulation executors into `simulation/` package:
  - `from cell_os.simulated_executor` → `from cell_os.simulation.simulated_executor`
  - `from cell_os.simulation_executor` → `from cell_os.simulation.executor`
- Reorganized 108 loose scripts into categorized subdirectories
- Moved root-level docs/images to appropriate directories
- Cleaned up .gitignore (removed duplicates, organized by category)

### Removed
- Empty orphan packages (`src/acquisition/`, `src/economics/`, etc.)
- `src/cell_os.egg-info/` from git tracking
- Duplicate/redundant directories (`scripts/debug/` merged into `scripts/debugging/`)

### Fixed
- Internal imports within moved packages now use relative imports
- Updated all external imports across codebase

## [2025-01-11] - Advanced Biology Models

### Added
- `advanced_biology.py` - Cell cycle and stress response models
- `realistic_noise.py` - Channel-correlated noise model
- Integration tests for advanced biology features

### Changed
- Enhanced noise model with channel correlations
- Improved cell cycle phase modeling

## [2025-01-10] - Epistemic Honesty Machinery

### Added
- Complete epistemic honesty auditing framework
- 10-issue roadmap implementation for calibration honesty
- Feala manifesto optimizations (closed-loop learning)
- Data engine and continuous learning capabilities
- Automation readiness tracker

### Fixed
- Template kwargs handling in agent
- Beam search schedule length calculation

## [2025-01-08] - Epistemic Debt Enforcement

### Added
- Hard debt threshold (2.0 bits) that blocks non-calibration actions
- Cost inflation from accumulated debt
- Debt repayment through calibration actions
- Comprehensive test suite for debt enforcement

### Changed
- Asymmetric penalties: overclaiming hurts more than underclaiming

## [Earlier]

See git history for changes prior to 2025-01-08. Key milestones:

- **Phase 6A**: Epistemic control system, beam search with COMMIT gating
- **Phase 5**: Population heterogeneity, confidence collapse
- **Phase 1**: Pay-for-calibration, noise gate, evidence ledgers
- **Phase 0**: Synthetic data generator, death conservation, determinism

---

## Migration Guide

### Updating Imports (2025-01-12)

If you have code using old import paths, update as follows:

```python
# Old → New

# Epistemic control
from cell_os.epistemic_control import EpistemicController
# → from cell_os.epistemic_agent.control import EpistemicController

from cell_os.epistemic_debt import compute_information_gain_bits
# → from cell_os.epistemic_agent.debt import compute_information_gain_bits

# Biology
from cell_os.sim.biology_core import hill_curve
# → from cell_os.biology.biology_core import hill_curve

# POSH
from cell_os.posh_scenario import POSHScenario
# → from cell_os.posh.scenario import POSHScenario

# Imaging
from cell_os.imaging_acquisition import ExperimentPlan
# → from cell_os.imaging.acquisition import ExperimentPlan

# Simulation
from cell_os.simulated_executor import SimulatedImagingExecutor
# → from cell_os.simulation.simulated_executor import SimulatedImagingExecutor
```

### Package Re-exports

For convenience, main classes are re-exported from package `__init__.py`:

```python
# These work:
from cell_os.epistemic_agent import EpistemicController
from cell_os.posh import POSHScenario, POSHLibrary
from cell_os.imaging import ImagingDoseLoop, ExperimentPlan
from cell_os.simulation import SimulationExecutor
```
