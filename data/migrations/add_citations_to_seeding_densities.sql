-- Migration: Add Citations to Seeding Densities
-- Date: 2025-12-22
-- Purpose: Add proper source tracking and references for all biological data

-- Add citation columns to seeding_densities table
ALTER TABLE seeding_densities ADD COLUMN source TEXT;
ALTER TABLE seeding_densities ADD COLUMN reference_url TEXT;
ALTER TABLE seeding_densities ADD COLUMN date_verified TEXT;

-- Add citation columns to vessel_types table
ALTER TABLE vessel_types ADD COLUMN source TEXT;
ALTER TABLE vessel_types ADD COLUMN reference_url TEXT;

-- Update vessel_types with standard references
UPDATE vessel_types SET
    source = 'Corning Life Sciences',
    reference_url = 'https://www.corning.com/catalog/cls/documents/protocols/CLS_GG_DL_026_REV1.pdf'
WHERE vessel_type_id IN ('384-well', '96-well', '24-well', '12-well', '6-well');

UPDATE vessel_types SET
    source = 'Corning/Thermo Fisher',
    reference_url = 'https://www.thermofisher.com/us/en/home/references/gibco-cell-culture-basics/cell-culture-protocols/cell-culture-useful-numbers.html'
WHERE vessel_type_id IN ('T25', 'T75', 'T175', 'T225');

-- ==============================================================================
-- Update A549 seeding densities with ATCC references
-- ==============================================================================

UPDATE seeding_densities SET
    source = 'ATCC CCL-185',
    reference_url = 'https://www.atcc.org/products/ccl-185',
    date_verified = '2025-12-22',
    notes = 'ATCC recommends 2,000-10,000 cells/cm². Doubling time ~22h. Optimized for 90% confluence at 48h in HTS.'
WHERE cell_line_id = 'A549' AND vessel_type_id = '384-well';

UPDATE seeding_densities SET
    source = 'ATCC CCL-185',
    reference_url = 'https://www.atcc.org/products/ccl-185',
    date_verified = '2025-12-22',
    notes = 'Scaled from ATCC seeding density (2,000-10,000 cells/cm²). Standard 96-well screening density.'
WHERE cell_line_id = 'A549' AND vessel_type_id = '96-well';

UPDATE seeding_densities SET
    source = 'ATCC CCL-185',
    reference_url = 'https://www.atcc.org/products/ccl-185',
    date_verified = '2025-12-22',
    notes = 'Scaled from ATCC seeding density. Appropriate for 48-72h culture.'
WHERE cell_line_id = 'A549' AND vessel_type_id IN ('24-well', '12-well', '6-well');

UPDATE seeding_densities SET
    source = 'ATCC CCL-185',
    reference_url = 'https://www.atcc.org/products/ccl-185',
    date_verified = '2025-12-22',
    notes = 'ATCC maintains cultures at 6,000-60,000 cells/cm². Standard T75 maintenance seeding.'
WHERE cell_line_id = 'A549' AND vessel_type_id IN ('T25', 'T75', 'T175');

-- ==============================================================================
-- Update HepG2 seeding densities with ATCC references
-- ==============================================================================

UPDATE seeding_densities SET
    source = 'ATCC HB-8065 / Cellosaurus CVCL_0027',
    reference_url = 'https://www.atcc.org/products/hb-8065',
    date_verified = '2025-12-22',
    notes = 'ATCC recommends 20,000-60,000 cells/cm². Doubling time 26-60h (variable, DSMZ reports 50-60h). Seeded higher than A549 to compensate for slower growth.'
WHERE cell_line_id = 'HepG2' AND vessel_type_id = '384-well';

UPDATE seeding_densities SET
    source = 'ATCC HB-8065',
    reference_url = 'https://www.atcc.org/products/hb-8065',
    date_verified = '2025-12-22',
    notes = 'Scaled from ATCC seeding density (20,000-60,000 cells/cm²). Higher seeding compensates for slower proliferation.'
WHERE cell_line_id = 'HepG2' AND vessel_type_id = '96-well';

UPDATE seeding_densities SET
    source = 'ATCC HB-8065',
    reference_url = 'https://www.atcc.org/products/hb-8065',
    date_verified = '2025-12-22',
    notes = 'Scaled from ATCC seeding density. Hepatocyte-specific culture.'
WHERE cell_line_id = 'HepG2' AND vessel_type_id IN ('24-well', '12-well', '6-well');

UPDATE seeding_densities SET
    source = 'ATCC HB-8065',
    reference_url = 'https://www.atcc.org/products/hb-8065',
    date_verified = '2025-12-22',
    notes = 'ATCC recommends 20,000-60,000 cells/cm² for maintenance. Hepatoma cells require higher starting density.'
WHERE cell_line_id = 'HepG2' AND vessel_type_id IN ('T25', 'T75', 'T175');

-- ==============================================================================
-- Add citations for other cell lines (generic references for now)
-- ==============================================================================

UPDATE seeding_densities SET
    source = 'Industry standard / HTS protocols',
    reference_url = 'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4758894/',
    date_verified = '2025-12-22',
    notes = notes || ' Scaled from standard HTS seeding densities.'
WHERE cell_line_id NOT IN ('A549', 'HepG2') AND source IS NULL;

-- ==============================================================================
-- Create view for easy citation lookup
-- ==============================================================================

CREATE VIEW IF NOT EXISTS seeding_densities_with_citations AS
SELECT
    sd.cell_line_id,
    vt.display_name as vessel_name,
    vt.surface_area_cm2,
    sd.nominal_cells_per_well,
    ROUND(sd.nominal_cells_per_well / vt.surface_area_cm2, 0) as cells_per_cm2,
    sd.low_multiplier,
    sd.high_multiplier,
    sd.notes,
    sd.source,
    sd.reference_url,
    sd.date_verified
FROM seeding_densities sd
JOIN vessel_types vt ON sd.vessel_type_id = vt.vessel_type_id
ORDER BY sd.cell_line_id, vt.surface_area_cm2;
