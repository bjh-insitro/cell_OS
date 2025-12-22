# Plate Design Library

This directory contains standardized plate layout definitions for the Cell OS validation frontend.

## Available Designs

### CAL_384_RULES_WORLD_v1.json
**Calibration Plate** - Learn the measurement rules before exploring biology

- **Format**: 384-well (16 rows × 24 columns)
- **Cell Lines**: HepG2 (rows A-H), A549 (rows I-P)
- **Timepoint**: 48 hours
- **Purpose**: Calibrate instrument before compound experiments

**Treatments:**
- Vehicle (DMSO) - 288 wells (75%)
- Anchor Mild (1µM) - 16 wells
- Anchor Strong (100µM) - 16 wells
- Tiles (2x2 vehicle replicates) - 32 wells

**Design Goals:**
1. Learn plate spatial effects (edges, gradients)
2. Learn noise floor (tiles show local vs global variation)
3. Learn feature family variance
4. Learn cell line-specific spatial sensitivity
5. Establish dynamic range with anchors
6. **Avoid compound exploration** - this is about the instrument

**Color Coding:**
- Fill color = treatment type
- Border color = cell line (Pink=HepG2, Purple=A549)

## JSON Schema

```json
{
  "schema_version": "calibration_plate_v1",
  "intent": "string",
  "plate": {
    "plate_id": "string",
    "format": "96|384|1536",
    "rows": ["A", "B", ...],
    "cols": [1, 2, ...]
  },
  "cell_lines": {
    "A": { "rows": [...], "name": "string" },
    "B": { "rows": [...], "name": "string" }
  },
  "anchors": {
    "MILD": { "wells": [...], "dose": number, "dose_unit": "string" },
    "STRONG": { "wells": [...], "dose": number, "dose_unit": "string" }
  },
  "tiles": {
    "wells": [...],
    "description": "string"
  },
  "design_goals": ["string"],
  "sanity_checks": ["string"],
  "statistics": {},
  "cost_estimate": {}
}
```

## Usage

These JSON files can be:
1. Downloaded from the UI (Download JSON button)
2. Imported into analysis pipelines
3. Used for plate setup automation
4. Referenced in documentation
