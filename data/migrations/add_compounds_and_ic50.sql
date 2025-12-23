-- Migration: Add Compounds and IC50 Database
-- Date: 2025-12-23
-- Purpose: Create normalized compound database with IC50 values and citations

-- ==============================================================================
-- Compounds Table - Basic compound information
-- ==============================================================================

CREATE TABLE IF NOT EXISTS compounds (
    compound_id TEXT PRIMARY KEY,
    common_name TEXT NOT NULL,
    cas_number TEXT,
    pubchem_cid INTEGER,
    chembl_id TEXT,
    molecular_weight REAL,
    smiles TEXT,
    mechanism TEXT,
    target TEXT,
    compound_class TEXT,
    notes TEXT,
    date_added TEXT NOT NULL
);

-- ==============================================================================
-- Compound IC50 Values - Cell line specific cytotoxicity
-- ==============================================================================

CREATE TABLE IF NOT EXISTS compound_ic50 (
    compound_id TEXT NOT NULL,
    cell_line_id TEXT NOT NULL,
    ic50_uM REAL NOT NULL,
    ic50_range_min_uM REAL,
    ic50_range_max_uM REAL,
    hill_slope REAL DEFAULT 1.0,
    assay_type TEXT,  -- e.g., "viability", "proliferation", "cytotoxicity"
    assay_duration_h INTEGER,  -- e.g., 48, 72
    source TEXT NOT NULL,
    reference_url TEXT NOT NULL,
    pubmed_id TEXT,
    notes TEXT,
    date_verified TEXT NOT NULL,
    PRIMARY KEY (compound_id, cell_line_id),
    FOREIGN KEY (compound_id) REFERENCES compounds(compound_id),
    FOREIGN KEY (cell_line_id) REFERENCES cell_line_growth_parameters(cell_line_id)
);

-- ==============================================================================
-- Compound Physical Properties
-- ==============================================================================

CREATE TABLE IF NOT EXISTS compound_properties (
    compound_id TEXT PRIMARY KEY,
    solubility_dmso_mM REAL,
    solubility_water_uM REAL,
    stock_concentration_mM REAL,
    stock_solvent TEXT,
    storage_temp_c INTEGER,
    light_sensitive BOOLEAN,
    stability_days INTEGER,
    vendor TEXT,
    catalog_number TEXT,
    FOREIGN KEY (compound_id) REFERENCES compounds(compound_id)
);

-- ==============================================================================
-- Views for easy querying
-- ==============================================================================

CREATE VIEW IF NOT EXISTS compound_summary AS
SELECT
    c.compound_id,
    c.common_name,
    c.mechanism,
    c.cas_number,
    COUNT(ic50.cell_line_id) as num_cell_lines,
    AVG(ic50.ic50_uM) as avg_ic50_uM,
    MIN(ic50.ic50_uM) as min_ic50_uM,
    MAX(ic50.ic50_uM) as max_ic50_uM
FROM compounds c
LEFT JOIN compound_ic50 ic50 ON c.compound_id = ic50.compound_id
GROUP BY c.compound_id;

CREATE VIEW IF NOT EXISTS compound_ic50_with_citations AS
SELECT
    ic50.compound_id,
    c.common_name,
    ic50.cell_line_id,
    ic50.ic50_uM,
    ic50.hill_slope,
    ic50.source,
    ic50.reference_url,
    ic50.date_verified
FROM compound_ic50 ic50
JOIN compounds c ON ic50.compound_id = c.compound_id
ORDER BY ic50.compound_id, ic50.cell_line_id;
