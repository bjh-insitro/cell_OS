# Abandoned Configuration Files

## master_pricing.yaml (Nov 27, 2025)

**Created:** commit e03f579 - "consolidated pricing" schema reorganization
**Abandoned:** Same day - pricing.yaml restored from earlier state (commit 0057673)

### Why abandoned
- Proposed reorganization: "BASE CONSUMABLES" first, better categorization
- Never wired into code (all 10 refs use pricing.yaml, not master_pricing.yaml)
- Comment in base.py:19 claimed to reference master_pricing.yaml but code uses pricing.yaml

### Schema differences
- `pricing.yaml`: Media components first (production)
- `master_pricing.yaml`: Pipette tips first, more structured categories

### If you want to resurrect this
1. Merge improvements from master_pricing into pricing.yaml
2. Update all Inventory() calls to use new path
3. Remove this file from archive
