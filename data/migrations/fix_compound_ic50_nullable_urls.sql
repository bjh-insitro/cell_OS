-- Migration: Fix compound_ic50 to allow NULL reference_url
-- Date: 2025-12-23
-- Purpose: Make reference_url nullable since estimated values don't have URLs

-- SQLite doesn't support ALTER COLUMN, so we need to recreate the table

-- Create new table with corrected schema
CREATE TABLE compound_ic50_new (
    compound_id TEXT NOT NULL,
    cell_line_id TEXT NOT NULL,
    ic50_uM REAL NOT NULL,
    ic50_range_min_uM REAL,
    ic50_range_max_uM REAL,
    hill_slope REAL DEFAULT 1.0,
    assay_type TEXT,
    assay_duration_h INTEGER,
    source TEXT NOT NULL,
    reference_url TEXT,  -- NOW NULLABLE
    pubmed_id TEXT,
    notes TEXT,
    date_verified TEXT NOT NULL,
    PRIMARY KEY (compound_id, cell_line_id),
    FOREIGN KEY (compound_id) REFERENCES compounds(compound_id),
    FOREIGN KEY (cell_line_id) REFERENCES cell_line_growth_parameters(cell_line_id)
);

-- Copy any existing data
INSERT INTO compound_ic50_new
SELECT * FROM compound_ic50;

-- Drop old table
DROP TABLE compound_ic50;

-- Rename new table
ALTER TABLE compound_ic50_new RENAME TO compound_ic50;

-- Recreate view
DROP VIEW IF EXISTS compound_ic50_with_citations;

CREATE VIEW compound_ic50_with_citations AS
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
