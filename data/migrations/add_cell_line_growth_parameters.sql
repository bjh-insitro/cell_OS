-- Migration: Add Cell Line Growth Parameters Table
-- Date: 2025-12-22
-- Purpose: Store authoritative growth kinetics data with citations

-- Create comprehensive growth parameters table
CREATE TABLE IF NOT EXISTS cell_line_growth_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cell_line_id TEXT NOT NULL,
    doubling_time_h REAL NOT NULL,
    doubling_time_range_min_h REAL,  -- For cell lines with variable doubling times
    doubling_time_range_max_h REAL,
    max_confluence REAL DEFAULT 0.9,
    seeding_efficiency REAL,  -- Fraction of seeded cells that attach
    passage_stress REAL,  -- Viability loss during passage (fraction)
    lag_duration_h REAL DEFAULT 12.0,  -- Time to recover after seeding
    edge_penalty REAL DEFAULT 0.15,  -- Growth penalty for edge wells
    source TEXT NOT NULL,
    reference_url TEXT NOT NULL,
    notes TEXT,
    date_verified TEXT NOT NULL,
    FOREIGN KEY (cell_line_id) REFERENCES cell_lines(cell_line_id) ON DELETE CASCADE,
    UNIQUE(cell_line_id)
);

-- Insert A549 growth parameters (from ATCC CCL-185)
INSERT INTO cell_line_growth_parameters (
    cell_line_id, doubling_time_h, doubling_time_range_min_h, doubling_time_range_max_h,
    max_confluence, seeding_efficiency, passage_stress, lag_duration_h, edge_penalty,
    source, reference_url, notes, date_verified
) VALUES (
    'A549',
    22.0,  -- ATCC official value
    20.0,  -- Observed range minimum
    24.0,  -- Observed range maximum
    0.88,  -- From simulation_parameters.yaml (validated)
    0.85,  -- From simulation_parameters.yaml (typical for adherent cells)
    0.02,  -- From simulation_parameters.yaml (low passage stress)
    12.0,  -- Standard lag phase for recovered cells
    0.15,  -- Standard edge effect
    'ATCC CCL-185',
    'https://www.atcc.org/products/ccl-185',
    'Lung adenocarcinoma. Fast-growing, robust cell line. ATCC states "approximately 22 hrs" doubling time. Recommended seeding: 2,000-10,000 cells/cm².',
    '2025-12-22'
);

-- Insert HepG2 growth parameters (from ATCC HB-8065 + Cellosaurus)
INSERT INTO cell_line_growth_parameters (
    cell_line_id, doubling_time_h, doubling_time_range_min_h, doubling_time_range_max_h,
    max_confluence, seeding_efficiency, passage_stress, lag_duration_h, edge_penalty,
    source, reference_url, notes, date_verified
) VALUES (
    'HepG2',
    48.0,  -- Conservative estimate (DSMZ reports 50-60h)
    26.0,  -- Minimum from PubMed 31378681
    60.0,  -- Maximum from DSMZ ACC-180
    0.85,  -- From simulation_parameters.yaml (validated)
    0.80,  -- Lower than A549 (hepatocytes attach more slowly)
    0.03,  -- Higher passage stress (more sensitive)
    16.0,  -- Longer lag phase (slower recovery)
    0.15,  -- Standard edge effect
    'ATCC HB-8065 / DSMZ ACC-180 / PubMed 31378681',
    'https://www.atcc.org/products/hb-8065',
    'Hepatoblastoma (originally thought to be hepatocellular carcinoma). Variable doubling time: 26h (PubMed) to 50-60h (DSMZ). ATCC recommends 20,000-60,000 cells/cm². Using 48h as conservative estimate.',
    '2025-12-22'
);

-- Insert HEK293 (commonly used, no ATCC lookup yet but add placeholder)
INSERT INTO cell_line_growth_parameters (
    cell_line_id, doubling_time_h, max_confluence, seeding_efficiency, passage_stress,
    source, reference_url, notes, date_verified
) VALUES (
    'HEK293',
    24.0,
    0.90,
    0.88,
    0.02,
    'Literature consensus',
    'https://www.atcc.org/products/crl-1573',
    'Fast-growing kidney cell line. Standard workhorse for transfection. Values from simulation_parameters.yaml pending ATCC verification.',
    '2025-12-22'
);

-- Insert HeLa (commonly used)
INSERT INTO cell_line_growth_parameters (
    cell_line_id, doubling_time_h, max_confluence, seeding_efficiency, passage_stress,
    source, reference_url, notes, date_verified
) VALUES (
    'HeLa',
    20.0,
    0.85,
    0.90,
    0.015,
    'Literature consensus',
    'https://www.atcc.org/products/ccl-2',
    'Very fast-growing cervical cancer line. Highly robust. Values from simulation_parameters.yaml pending ATCC verification.',
    '2025-12-22'
);

-- Insert U2OS
INSERT INTO cell_line_growth_parameters (
    cell_line_id, doubling_time_h, max_confluence, seeding_efficiency, passage_stress,
    source, reference_url, notes, date_verified
) VALUES (
    'U2OS',
    26.0,
    0.88,
    0.82,
    0.025,
    'Literature consensus',
    'https://www.atcc.org/products/htb-96',
    'Osteosarcoma. Moderate growth rate. Values from simulation_parameters.yaml pending ATCC verification.',
    '2025-12-22'
);

-- Create view for easy lookup with seeding densities
CREATE VIEW IF NOT EXISTS cell_line_complete_profile AS
SELECT
    gp.cell_line_id,
    gp.doubling_time_h,
    gp.doubling_time_range_min_h,
    gp.doubling_time_range_max_h,
    gp.max_confluence,
    gp.seeding_efficiency,
    gp.passage_stress,
    gp.lag_duration_h,
    gp.edge_penalty,
    gp.source as growth_source,
    gp.reference_url as growth_reference,
    gp.notes as growth_notes,
    gp.date_verified
FROM cell_line_growth_parameters gp
ORDER BY gp.cell_line_id;
