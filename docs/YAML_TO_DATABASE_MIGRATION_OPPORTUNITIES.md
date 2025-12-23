# YAML to Database Migration Opportunities

**Date**: 2025-12-23

---

## Executive Summary

After migrating cell line and compound parameters to database, here are **other YAML files that could benefit from database migration**:

---

## High Priority (Structured Data, Frequently Queried)

### 1. **Hardware Inventory** (`data/hardware_inventory.yaml`)

**Current**: Lab equipment specs in YAML
```yaml
liquid_handlers:
  - id: "biotek_el406_cell_dispenser"
    manufacturer: "BioTek"
    model: "EL406 Washer Dispenser"
    status: "operational"
    capabilities:
      - dispense_cells
      - feed_cells
```

**Benefits of Database:**
- Query available equipment by capability
- Track equipment status (operational, maintenance, broken)
- Track usage logs (which experiments used which equipment)
- Historical maintenance records
- Equipment reservations/scheduling

**Database Schema:**
```sql
CREATE TABLE equipment (
    equipment_id TEXT PRIMARY KEY,
    manufacturer TEXT,
    model TEXT,
    status TEXT,
    location TEXT,
    purchase_date TEXT,
    last_maintenance TEXT
);

CREATE TABLE equipment_capabilities (
    equipment_id TEXT,
    capability TEXT,
    PRIMARY KEY (equipment_id, capability)
);

CREATE TABLE equipment_usage_log (
    log_id INTEGER PRIMARY KEY,
    equipment_id TEXT,
    experiment_id TEXT,
    operation TEXT,
    timestamp TEXT,
    FOREIGN KEY (equipment_id) REFERENCES equipment(equipment_id)
);
```

---

### 2. **Hardware Specifications** (`data/hardware_specs/*.yaml`)

**Current**: Certus, EL406 technical noise parameters
```yaml
# certus.yaml
volume_cv_base: 0.02
volume_cv_edge: 0.03
position_error_std_mm: 0.05
```

**Benefits of Database:**
- Version control for calibration changes
- Track calibration history
- Compare performance across instruments
- Link to actual experimental outcomes

**Database Schema:**
```sql
CREATE TABLE hardware_calibration (
    calibration_id INTEGER PRIMARY KEY,
    equipment_id TEXT,
    parameter_name TEXT,
    parameter_value REAL,
    calibration_date TEXT,
    calibrated_by TEXT,
    notes TEXT,
    FOREIGN KEY (equipment_id) REFERENCES equipment(equipment_id)
);
```

---

### 3. **Cell Thalamus Parameters** (`data/cell_thalamus_params.yaml`)

**Current**: Stress axes, compound mappings, morphology responses
```yaml
stress_axes:
  oxidative:
    channels:
      er: 0.3
      mito: 1.5
      nucleus: 0.2
```

**Benefits of Database:**
- Query which compounds cause which stress responses
- Update calibration as Cell Painting data improves
- Track cell line-specific morphology responses
- Historical versions for reproducibility

**Database Schema:**
```sql
CREATE TABLE stress_axes (
    stress_axis TEXT PRIMARY KEY,
    description TEXT
);

CREATE TABLE morphology_response (
    stress_axis TEXT,
    channel TEXT,
    response_coefficient REAL,
    calibration_date TEXT,
    PRIMARY KEY (stress_axis, channel)
);

CREATE TABLE compound_stress_mapping (
    compound_id TEXT,
    stress_axis TEXT,
    intensity REAL,
    PRIMARY KEY (compound_id, stress_axis)
);
```

---

### 4. **CellROX & Segmentation Parameters** (in `simulation_parameters.yaml`)

**Current**: Nested under compounds in YAML
```yaml
tbhp:
  cellrox_params:
    U2OS:
      ec50_uM: 50.0
      max_fold: 5.0
  segmentation_params:
    U2OS:
      degradation_ic50_uM: 200.0
```

**Benefits of Database:**
- Same table as IC50s, just different assay types
- Track assay-specific parameters alongside viability IC50s
- Query "Which compounds cause strong CellROX response in U2OS?"

**Database Schema:**
```sql
-- Extend existing compound_ic50 table with assay_type
ALTER TABLE compound_ic50 ADD COLUMN assay_type TEXT DEFAULT 'viability';

-- Add CellROX parameters
INSERT INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, assay_type, ...)
VALUES ('tbhp', 'U2OS', 50.0, 'cellrox_ec50', ...);

-- Or create separate table
CREATE TABLE assay_parameters (
    compound_id TEXT,
    cell_line_id TEXT,
    assay_type TEXT,  -- 'cellrox', 'segmentation', 'ldh', etc.
    parameter_name TEXT,  -- 'ec50_uM', 'max_fold', 'baseline', etc.
    parameter_value REAL,
    PRIMARY KEY (compound_id, cell_line_id, assay_type, parameter_name)
);
```

---

## Medium Priority (Configuration Data)

### 5. **scRNA-seq Parameters** (`data/scrna_seq_params.yaml`)

**Current**: Gene expression noise models
```yaml
technical_noise:
  capture_efficiency: 0.1
  amplification_cv: 0.15
```

**Benefits of Database:**
- Version control for different protocols
- Track changes in sequencing technology
- Protocol-specific parameters

---

### 6. **Gene Signatures** (`data/gene_signatures/stress_programs.yaml`)

**Current**: Gene expression programs for stress responses
```yaml
oxidative_stress:
  genes: [NRF2, SOD1, SOD2, ...]
  fold_changes: [3.5, 2.1, 2.8, ...]
```

**Benefits of Database:**
- Query genes by stress program
- Track signature updates from literature
- Cell line-specific signature variations

---

## Low Priority (Static Reference Data)

### 7. **Pricing Data** (`data/raw/pricing.yaml`, `master_pricing.yaml`)

**Current**: Consumable costs
- Could stay in YAML (rarely changes)
- Or migrate for procurement tracking

### 8. **Unit Operations** (`data/raw/unitops.yaml`, `unit_ops.yaml`)

**Current**: Lab protocol definitions
- Could stay in YAML (workflow definitions)
- Or migrate for workflow scheduling

### 9. **Scenarios** (`data/scenarios/*.yaml`)

**Current**: Experimental designs
- Could stay in YAML (one-off experiments)
- Or migrate to link experiments to results

---

## Recommendation: Priority Order

### **Phase 1: Complete Current Migration** ✅
1. Remove YAML fallback from `biological_virtual.py`
2. Database is now primary source

### **Phase 2: Assay Parameters** (High Impact)
3. Migrate CellROX/segmentation parameters to database
4. Extend `compound_ic50` or create `assay_parameters` table

### **Phase 3: Hardware Tracking** (Lab Operations)
5. Migrate hardware inventory to database
6. Migrate hardware calibration specs
7. Add equipment usage logging

### **Phase 4: Cell Thalamus** (Cell Painting)
8. Migrate stress axis definitions
9. Migrate morphology response coefficients
10. Add compound-stress mappings

### **Phase 5: Everything Else** (Optional)
11. Gene signatures
12. scRNA-seq params
13. Pricing/consumables (if tracking procurement)

---

## Summary

**Already Migrated** ✅:
- Cell line growth parameters
- Seeding densities
- Compound IC50s
- Parameter verification tracking

**High Priority to Migrate:**
1. **CellROX/segmentation params** - Already partially structured in compound table
2. **Hardware inventory** - Enables equipment tracking and scheduling
3. **Cell Thalamus params** - Critical for Cell Painting simulations
4. **Hardware calibration** - Version control for technical noise

**Can Stay in YAML:**
- Scenarios (experimental designs)
- Unit operations (workflow definitions)
- Pricing (static reference)
- Gene signatures (reference data)

---

**Next Step**: Remove YAML fallback from `biological_virtual.py` now that database is primary source.
