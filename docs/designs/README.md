# Experimental Design Documentation

This directory contains documentation for Cell Thalamus experimental designs organized by phase and purpose.

## Design Philosophy

Cell Thalamus uses a **phased approach** to experimental design:

- **Phase 0**: Shape learning and nuisance model identification
  - Goal: Understand system behavior, detect artifacts, characterize batch effects
  - Not for: Mechanism claims, causal inference

- **Phase 1**: Focused causal estimation
  - Goal: Defensible dose-response curves for specific interventions
  - High replication, within-plate randomization, single timepoint

- **Phase 2+**: (Future) Mechanism mapping, combinatorial screening, adaptive sampling

## Active Design Documentation

### Phase 0 Designs
- **[SHAPE_LEARNING_DESIGN.md](SHAPE_LEARNING_DESIGN.md)** - Phase 0 shape learning design with 6 enhancements for nuisance identification
  - Instrument sentinels (non-biological controls)
  - Diagnostic sentinel geometry
  - Bridge controls for batch effect estimation
  - Absolute dose anchors
  - Timepoint perturbation
  - Explicit metadata about goals and constraints

### Phase 1 Designs
- **[PHASE1_CAUSAL_DESIGN.md](PHASE1_CAUSAL_DESIGN.md)** - Phase 1 causal design for focused dose-response estimation (to be created)

### Generator Documentation
- **[DESIGN_GENERATOR_GUIDE.md](DESIGN_GENERATOR_GUIDE.md)** - How to use design generators

## Design Invariants

All designs enforce strict invariants (see `frontend/INVARIANT_SYSTEM.md`):
- Fixed sentinel scaffold (cryptographic provenance)
- Exact plate fill (no silent truncation)
- Position stability or randomization (explicit, not accidental)
- Batch balance
- Spatial dispersion metrics

## Archived Documentation

See `archive/` for historical design documents and templates that have been superseded by UI features or newer approaches.

## Related Files

- **Design catalog**: `data/designs/catalog.json`
- **Active designs**: `data/designs/*.json`
- **Archived designs**: `data/designs/archive/`
- **Generators**: `scripts/design_generator_*.py`
- **Validation**: `frontend/INVARIANT_SYSTEM.md`
