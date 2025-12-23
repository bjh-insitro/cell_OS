-- Migration: Add Vessel Types and Seeding Densities
-- Date: 2025-12-22
-- Purpose: Properly model seeding densities as normalized database tables

-- ============================================================================
-- vessel_types: Physical properties of culture vessels
-- ============================================================================
CREATE TABLE IF NOT EXISTS vessel_types (
    vessel_type_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('plate', 'flask', 'dish', 'bioreactor')),
    surface_area_cm2 REAL NOT NULL,
    working_volume_ml REAL NOT NULL,
    max_volume_ml REAL NOT NULL,
    well_count INTEGER,  -- NULL for flasks/dishes (single compartment)
    max_capacity_cells_per_well REAL NOT NULL,  -- At confluence
    description TEXT,
    UNIQUE(display_name)
);

-- ============================================================================
-- seeding_densities: Cell-line-specific seeding parameters per vessel type
-- ============================================================================
CREATE TABLE IF NOT EXISTS seeding_densities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cell_line_id TEXT NOT NULL,
    vessel_type_id TEXT NOT NULL,
    nominal_cells_per_well INTEGER NOT NULL,
    low_multiplier REAL NOT NULL DEFAULT 0.7,
    high_multiplier REAL NOT NULL DEFAULT 1.3,
    notes TEXT,
    FOREIGN KEY (cell_line_id) REFERENCES cell_lines(cell_line_id) ON DELETE CASCADE,
    FOREIGN KEY (vessel_type_id) REFERENCES vessel_types(vessel_type_id) ON DELETE CASCADE,
    UNIQUE(cell_line_id, vessel_type_id)
);

-- ============================================================================
-- Insert vessel types (plates)
-- ============================================================================
INSERT INTO vessel_types (
    vessel_type_id, display_name, category,
    surface_area_cm2, working_volume_ml, max_volume_ml,
    well_count, max_capacity_cells_per_well, description
) VALUES
    -- Microplates (multi-well)
    ('384-well', '384-Well Plate', 'plate',
     0.112, 0.080, 0.100, 384, 15000,
     'High-density screening plate. Surface area per well: 0.112 cm². Common for HTS.'),

    ('96-well', '96-Well Plate', 'plate',
     0.32, 0.200, 0.300, 96, 50000,
     'Standard screening plate. Surface area per well: 0.32 cm². Most common format.'),

    ('24-well', '24-Well Plate', 'plate',
     1.9, 1.0, 2.0, 24, 200000,
     'Medium-scale culture plate. Surface area per well: 1.9 cm².'),

    ('12-well', '12-Well Plate', 'plate',
     3.8, 2.0, 3.0, 12, 400000,
     'Large-scale culture plate. Surface area per well: 3.8 cm².'),

    ('6-well', '6-Well Plate', 'plate',
     9.6, 2.0, 3.0, 6, 1500000,
     'Very large culture plate. Surface area per well: 9.6 cm². Good for cell harvest.');

-- ============================================================================
-- Insert vessel types (flasks)
-- ============================================================================
INSERT INTO vessel_types (
    vessel_type_id, display_name, category,
    surface_area_cm2, working_volume_ml, max_volume_ml,
    well_count, max_capacity_cells_per_well, description
) VALUES
    ('T25', 'T25 Flask', 'flask',
     25.0, 5.0, 7.0, NULL, 3000000,
     'Small tissue culture flask. Surface area: 25 cm². Good for maintenance.'),

    ('T75', 'T75 Flask', 'flask',
     75.0, 12.0, 20.0, NULL, 10000000,
     'Standard tissue culture flask. Surface area: 75 cm². Most common flask size.'),

    ('T175', 'T175 Flask', 'flask',
     175.0, 25.0, 50.0, NULL, 25000000,
     'Large tissue culture flask. Surface area: 175 cm². For large-scale culture.'),

    ('T225', 'T225 Flask', 'flask',
     225.0, 30.0, 60.0, NULL, 35000000,
     'Extra-large tissue culture flask. Surface area: 225 cm². High-yield culture.');

-- ============================================================================
-- Insert seeding densities for A549 (fast-growing lung cancer)
-- ============================================================================
INSERT INTO seeding_densities (
    cell_line_id, vessel_type_id, nominal_cells_per_well,
    low_multiplier, high_multiplier, notes
) VALUES
    ('A549', '384-well', 3000, 0.7, 1.3,
     'Fast-growing lung carcinoma. Doubling time ~22h. Reaches 90% confluence at 48h.'),

    ('A549', '96-well', 10000, 0.7, 1.3,
     'Standard 96-well seeding. Reaches 80-90% confluence at 48h.'),

    ('A549', '24-well', 50000, 0.7, 1.3,
     'Medium-scale culture. Appropriate for 48-72h experiments.'),

    ('A549', '12-well', 100000, 0.7, 1.3,
     'Large-scale well culture.'),

    ('A549', '6-well', 500000, 0.7, 1.3,
     'Very large well format. Good for harvest or high cell numbers.'),

    ('A549', 'T25', 500000, 0.7, 1.3,
     'T25 flask seeding for maintenance cultures.'),

    ('A549', 'T75', 1000000, 0.7, 1.3,
     'Standard T75 seeding. Reaches confluence in 3-4 days.'),

    ('A549', 'T175', 2500000, 0.7, 1.3,
     'Large flask for high-yield culture.');

-- ============================================================================
-- Insert seeding densities for HepG2 (slower hepatoma)
-- ============================================================================
INSERT INTO seeding_densities (
    cell_line_id, vessel_type_id, nominal_cells_per_well,
    low_multiplier, high_multiplier, notes
) VALUES
    ('HepG2', '384-well', 5000, 0.7, 1.3,
     'Slower-growing hepatoma. Doubling time ~34h. Seeded higher than A549 to reach similar confluence at 48h.'),

    ('HepG2', '96-well', 15000, 0.7, 1.3,
     'Higher seeding compensates for slower growth rate.'),

    ('HepG2', '24-well', 80000, 0.7, 1.3,
     'Medium-scale hepatocyte culture.'),

    ('HepG2', '12-well', 150000, 0.7, 1.3,
     'Large-scale well culture.'),

    ('HepG2', '6-well', 600000, 0.7, 1.3,
     'High-density hepatocyte culture.'),

    ('HepG2', 'T25', 600000, 0.7, 1.3,
     'T25 flask maintenance culture.'),

    ('HepG2', 'T75', 1200000, 0.7, 1.3,
     'Standard T75 seeding. Takes 4-5 days to reach confluence.'),

    ('HepG2', 'T175', 3000000, 0.7, 1.3,
     'Large flask culture.');

-- ============================================================================
-- Insert seeding densities for other cell lines
-- ============================================================================
INSERT INTO seeding_densities (
    cell_line_id, vessel_type_id, nominal_cells_per_well,
    low_multiplier, high_multiplier, notes
) VALUES
    -- HEK293 (fast-growing kidney cells)
    ('HEK293', '384-well', 3000, 0.7, 1.3, 'Fast-growing, similar to A549'),
    ('HEK293', '96-well', 10000, 0.7, 1.3, 'Standard screening density'),
    ('HEK293', '6-well', 500000, 0.7, 1.3, 'Standard 6-well density'),
    ('HEK293', 'T75', 1000000, 0.7, 1.3, 'Standard flask density'),

    -- HeLa (very fast-growing cervical cancer)
    ('HeLa', '384-well', 3000, 0.7, 1.3, 'Very fast proliferation'),
    ('HeLa', '96-well', 10000, 0.7, 1.3, 'Standard screening density'),
    ('HeLa', '6-well', 500000, 0.7, 1.3, 'Standard 6-well density'),
    ('HeLa', 'T75', 1000000, 0.7, 1.3, 'Standard flask density'),

    -- U2OS (osteosarcoma, moderate growth)
    ('U2OS', '384-well', 3500, 0.7, 1.3, 'Moderate proliferation rate'),
    ('U2OS', '96-well', 12000, 0.7, 1.3, 'Standard screening density'),
    ('U2OS', '6-well', 550000, 0.7, 1.3, 'Standard 6-well density'),
    ('U2OS', 'T75', 1100000, 0.7, 1.3, 'Standard flask density'),

    -- iPSC_NGN2 (post-mitotic neurons - don't proliferate)
    ('iPSC_NGN2', '384-well', 4000, 0.7, 1.3, 'Post-mitotic neurons. Seed high, minimal proliferation.'),
    ('iPSC_NGN2', '96-well', 15000, 0.7, 1.3, 'High density for non-dividing cells'),
    ('iPSC_NGN2', '6-well', 800000, 0.7, 1.3, 'High starting density required'),
    ('iPSC_NGN2', 'T75', 2000000, 0.7, 1.3, 'Very high flask density for neurons'),

    -- iPSC_Microglia (moderate proliferation)
    ('iPSC_Microglia', '384-well', 3500, 0.7, 1.3, 'Immune cells, moderate division'),
    ('iPSC_Microglia', '96-well', 12000, 0.7, 1.3, 'Standard screening density'),
    ('iPSC_Microglia', '6-well', 600000, 0.7, 1.3, 'Standard 6-well density'),
    ('iPSC_Microglia', 'T75', 1500000, 0.7, 1.3, 'Standard flask density');

-- ============================================================================
-- Create indexes for fast lookups
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_seeding_densities_lookup
    ON seeding_densities(cell_line_id, vessel_type_id);

CREATE INDEX IF NOT EXISTS idx_vessel_types_category
    ON vessel_types(category);

-- ============================================================================
-- Verification queries
-- ============================================================================
-- Count entries per table
-- SELECT 'vessel_types' as table_name, COUNT(*) as count FROM vessel_types
-- UNION ALL
-- SELECT 'seeding_densities', COUNT(*) FROM seeding_densities;

-- Show all seeding densities for A549
-- SELECT sd.*, vt.display_name, vt.surface_area_cm2
-- FROM seeding_densities sd
-- JOIN vessel_types vt ON sd.vessel_type_id = vt.vessel_type_id
-- WHERE sd.cell_line_id = 'A549'
-- ORDER BY vt.surface_area_cm2;
