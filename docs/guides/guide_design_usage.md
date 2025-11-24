# Guide Design Integration - Usage Guide

## Overview
The cell_OS repository now includes an adapter for the external `guide_design_v2` constraint-based solver. This allows you to design optimized gRNA libraries with solver-enforced constraints.

## Quick Start

### Basic Usage (Mock Fallback)
```python
from src.upstream import LibraryDesign, GeneTarget

# Create library design
lib = LibraryDesign(
    design_id="my_library",
    genes=[
        GeneTarget("BRCA1"),
        GeneTarget("TP53"),
        GeneTarget("KRAS")
    ],
    guides_per_gene=4,
    use_solver=False  # Use mock (default)
)

# Generate guides
guides = lib.generate_guides()
print(f"Generated {len(guides)} guides")
```

### Using Constraint-Based Solver

**Requirements:**
- `ml_projects.posh.guide_design_v2` package must be installed
- Access to sgRNA repositories (S3 or local paths)

```python
from src.upstream import LibraryDesign, GeneTarget

lib = LibraryDesign(
    design_id="solver_library",
    genes=[GeneTarget("BRCA1"), GeneTarget("TP53")],
    guides_per_gene=4,
    use_solver=True,  # Enable solver
    repositories_yaml="data/configs/sgRNA_repositories.yaml"
)

guides = lib.generate_guides()
```

## Configuration

### sgRNA Repositories
Edit `data/configs/sgRNA_repositories.yaml`:
```yaml
vbc: s3://insitro-posh-production/guide_repository/tech-dev/vbc_rs3_scored_w_location.csv
crispick: s3://insitro-posh-production/guide_repository/tech-dev/crispick_rs3_scored_w_location.csv
my_custom_repo: /path/to/local/library.csv
```

### Design Parameters
The solver uses these constraints (customizable in `src/guide_design_v2.py`):
- **min_guides_per_gene**: 1 (default)
- **max_guides_per_gene**: 4 (from `LibraryDesign.guides_per_gene`)
- **posh_barcode_hamming_distance**: 2
- **overlap_threshold**: 6 bases
- **score_name**: "rs3_sequence_score"

## Fallback Behavior
If the external solver is unavailable, the system automatically falls back to mock guide generation. This ensures your workflows continue to function during:
- Development environments without solver access
- Testing scenarios
- Proof-of-concept work

## Testing
Run integration tests:
```bash
venv/bin/python tests/integration/test_guide_design_integration.py
```

## Architecture

```
LibraryDesign.generate_guides()
  └─→ use_solver=True?
       ├─→ Yes: _generate_with_solver()
       │    └─→ GuideLibraryAdapter
       │         └─→ ml_projects.posh.guide_design_v2.create_library
       └─→ No: _generate_mock()
```

## References
- **VBC**: [Multilayered VBC score predicts sgRNAs that efficiently generate loss-of-function alleles](https://doi.org/10.1038/s41467-021-21650-w)
- **CRISPick**: [Optimized sgRNA design to maximize activity and minimize off-target effects](https://doi.org/10.1038/nbt.3437)
