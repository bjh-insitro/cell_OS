-- Migration: Add Missing Cell Lines
-- Date: 2025-12-23
-- Purpose: Add Jurkat, CHO, and undifferentiated iPSC to database

-- ==============================================================================
-- Add Jurkat (Suspension T-cell line)
-- ==============================================================================

INSERT OR REPLACE INTO cell_line_growth_parameters (
    cell_line_id, doubling_time_h, doubling_time_range_min_h, doubling_time_range_max_h,
    max_confluence, seeding_efficiency, passage_stress, lag_duration_h, edge_penalty,
    max_passage, senescence_rate, cell_count_cv, viability_cv, biological_cv,
    tissue_type, disease, organism, sex, morphology, growth_mode,
    culture_medium, serum_percent, coating_required,
    atcc_id, rrid, cellosaurus_id,
    source, reference_url, notes, date_verified
) VALUES (
    'Jurkat',
    18.0,  -- Doubling time
    NULL, NULL,
    1.0,  -- Suspension cells don't have confluence limit
    0.95,  -- High viability
    0.01,  -- Low passage stress (suspension)
    8.0,   -- Shorter lag
    0.0,   -- No edge effect (suspension)
    40,    -- High max passage
    0.005, -- Low senescence
    0.08,  -- Low CV
    0.02,
    0.04,
    'Blood',
    'Acute T-cell leukemia',
    'Homo sapiens',
    'Male',
    'Lymphoblast',
    'Suspension',
    'RPMI-1640 (ATCC 30-2001)',
    10.0,
    0,  -- No coating
    'TIB-152',
    'CVCL_0065',
    'CVCL_0065',
    'ATCC TIB-152 / Literature consensus',
    'https://www.atcc.org/products/tib-152',
    'Suspension T-cell line. Fast-growing, robust. No confluence limit.',
    '2025-12-23'
);

-- ==============================================================================
-- Add CHO (Chinese Hamster Ovary)
-- ==============================================================================

INSERT OR REPLACE INTO cell_line_growth_parameters (
    cell_line_id, doubling_time_h, doubling_time_range_min_h, doubling_time_range_max_h,
    max_confluence, seeding_efficiency, passage_stress, lag_duration_h, edge_penalty,
    max_passage, senescence_rate, cell_count_cv, viability_cv, biological_cv,
    tissue_type, disease, organism, sex, morphology, growth_mode,
    culture_medium, serum_percent, coating_required,
    atcc_id, rrid, cellosaurus_id,
    source, reference_url, notes, date_verified
) VALUES (
    'CHO',
    22.0,  -- Doubling time
    20.0, 24.0,
    0.92,
    0.88,
    0.018,
    12.0,
    0.15,
    35,
    0.008,
    0.10,
    0.02,
    0.05,
    'Ovary',
    'Normal (immortalized)',
    'Cricetulus griseus',  -- Chinese hamster
    'Female',
    'Epithelial',
    'Adherent',
    'F-12 (ATCC 30-2004)',
    10.0,
    0,
    'CCL-61',
    'CVCL_0214',
    'CVCL_0214',
    'ATCC CCL-61 / Literature consensus',
    'https://www.atcc.org/products/ccl-61',
    'Chinese Hamster Ovary. Widely used for protein production and biomanufacturing.',
    '2025-12-23'
);

-- ==============================================================================
-- Add iPSC (undifferentiated induced Pluripotent Stem Cells)
-- ==============================================================================

INSERT OR REPLACE INTO cell_line_growth_parameters (
    cell_line_id, doubling_time_h, doubling_time_range_min_h, doubling_time_range_max_h,
    max_confluence, seeding_efficiency, passage_stress, lag_duration_h, edge_penalty,
    max_passage, senescence_rate, cell_count_cv, viability_cv, biological_cv,
    tissue_type, disease, organism, sex, morphology, growth_mode,
    culture_medium, serum_percent, coating_required, coating_type,
    atcc_id, rrid, cellosaurus_id,
    source, reference_url, notes, date_verified
) VALUES (
    'iPSC',
    32.0,  -- Slower doubling
    30.0, 36.0,
    1.0,  -- Grows in colonies
    0.50,  -- Low attachment efficiency
    0.10,  -- High passage stress
    24.0,  -- Long lag
    0.15,
    50,  -- Can passage many times if maintained properly
    0.02,
    0.15,  -- High CV
    0.05,
    0.10,
    'Pluripotent stem cells',
    'Normal (reprogrammed)',
    'Homo sapiens',
    NULL,  -- Donor-dependent
    'Stem cell',
    'Adherent',
    'mTeSR1 or E8 (serum-free)',
    0.0,  -- Serum-free
    1,  -- Requires coating
    'Matrigel or vitronectin',
    NULL,  -- Multiple sources
    NULL,
    NULL,
    'Literature consensus / Protocol-dependent',
    '',
    'Undifferentiated iPSCs. Require feeder-free coating (Matrigel/vitronectin). Serum-free medium. Sensitive to dissociation. Colony-forming.',
    '2025-12-23'
);

-- ==============================================================================
-- Add seeding densities for new cell lines
-- ==============================================================================

-- Jurkat (suspension - higher seeding density, no vessel size effect)
INSERT OR REPLACE INTO seeding_densities (
    cell_line_id, vessel_type_id, nominal_cells_per_well,
    low_multiplier, high_multiplier,
    source, reference_url, date_verified, notes
) VALUES
    ('Jurkat', '384-well', 5000, 0.7, 1.3, 'Suspension cell protocol', '', '2025-12-23', 'Suspension cells. Higher density than adherent.'),
    ('Jurkat', '96-well', 20000, 0.7, 1.3, 'Suspension cell protocol', '', '2025-12-23', 'Suspension cells.'),
    ('Jurkat', '24-well', 100000, 0.7, 1.3, 'Suspension cell protocol', '', '2025-12-23', 'Suspension cells.'),
    ('Jurkat', '6-well', 500000, 0.7, 1.3, 'Suspension cell protocol', '', '2025-12-23', 'Suspension cells.');

-- CHO (adherent, similar to HEK293)
INSERT OR REPLACE INTO seeding_densities (
    cell_line_id, vessel_type_id, nominal_cells_per_well,
    low_multiplier, high_multiplier,
    source, reference_url, date_verified, notes
) VALUES
    ('CHO', '384-well', 3000, 0.7, 1.3, 'ATCC CCL-61 guidelines', 'https://www.atcc.org/products/ccl-61', '2025-12-23', 'Similar to HEK293. Robust adherent cells.'),
    ('CHO', '96-well', 10000, 0.7, 1.3, 'ATCC CCL-61 guidelines', 'https://www.atcc.org/products/ccl-61', '2025-12-23', 'Scaled from surface area.'),
    ('CHO', '24-well', 50000, 0.7, 1.3, 'ATCC CCL-61 guidelines', 'https://www.atcc.org/products/ccl-61', '2025-12-23', 'Scaled from surface area.'),
    ('CHO', '6-well', 250000, 0.7, 1.3, 'ATCC CCL-61 guidelines', 'https://www.atcc.org/products/ccl-61', '2025-12-23', 'Scaled from surface area.'),
    ('CHO', 'T75', 1000000, 0.7, 1.3, 'ATCC CCL-61 guidelines', 'https://www.atcc.org/products/ccl-61', '2025-12-23', 'For expansion.');

-- iPSC (adherent, very low seeding for colony formation)
INSERT OR REPLACE INTO seeding_densities (
    cell_line_id, vessel_type_id, nominal_cells_per_well,
    low_multiplier, high_multiplier,
    source, reference_url, date_verified, notes
) VALUES
    ('iPSC', '384-well', 2000, 0.7, 1.3, 'iPSC culture protocols', '', '2025-12-23', 'Lower seeding for colony formation. Requires Matrigel coating.'),
    ('iPSC', '96-well', 7500, 0.7, 1.3, 'iPSC culture protocols', '', '2025-12-23', 'Colony-forming cells.'),
    ('iPSC', '24-well', 40000, 0.7, 1.3, 'iPSC culture protocols', '', '2025-12-23', 'Colony-forming cells.'),
    ('iPSC', '6-well', 200000, 0.7, 1.3, 'iPSC culture protocols', '', '2025-12-23', 'Colony-forming cells.'),
    ('iPSC', 'T75', 500000, 0.7, 1.3, 'iPSC culture protocols', '', '2025-12-23', 'Lower density for stem cell expansion.');

-- ==============================================================================
-- Add parameter verification entries
-- ==============================================================================

-- Jurkat - doubling time
INSERT OR REPLACE INTO parameter_verification VALUES
('Jurkat', 'doubling_time_h', 18.0, 'literature_consensus', 'ATCC TIB-152 / Multiple sources', 'https://www.atcc.org/products/tib-152', 'Fast-growing T-cell line. Range 18-20h.', '2025-12-23');

-- Jurkat - estimated parameters
INSERT OR REPLACE INTO parameter_verification VALUES
('Jurkat', 'max_confluence', 1.0, 'estimated', 'N/A - suspension cells', '', 'Suspension cells do not have confluence limit.', '2025-12-23'),
('Jurkat', 'seeding_efficiency', 0.95, 'estimated', 'Suspension cell protocol', '', 'High viability for suspension cells. Needs validation.', '2025-12-23'),
('Jurkat', 'passage_stress', 0.01, 'estimated', 'Observation-based estimate', '', 'Low stress for suspension cells. Needs validation.', '2025-12-23'),
('Jurkat', 'max_passage', 40.0, 'estimated', 'Industry guideline', '', 'Can passage extensively. Needs validation.', '2025-12-23'),
('Jurkat', 'senescence_rate', 0.005, 'estimated', 'Model parameter', '', 'Low senescence rate. Needs validation.', '2025-12-23'),
('Jurkat', 'lag_duration_h', 8.0, 'estimated', 'Model parameter', '', 'Shorter lag for suspension cells. Needs validation.', '2025-12-23'),
('Jurkat', 'edge_penalty', 0.0, 'estimated', 'N/A - suspension cells', '', 'No edge effect for suspension cells.', '2025-12-23'),
('Jurkat', 'cell_count_cv', 0.08, 'estimated', 'Assay variability estimate', '', 'Lower CV for suspension cells. Needs validation.', '2025-12-23');

-- CHO - doubling time
INSERT OR REPLACE INTO parameter_verification VALUES
('CHO', 'doubling_time_h', 22.0, 'literature_consensus', 'ATCC CCL-61 / Multiple sources', 'https://www.atcc.org/products/ccl-61', 'Range 20-24h depending on conditions.', '2025-12-23');

-- CHO - estimated parameters
INSERT OR REPLACE INTO parameter_verification VALUES
('CHO', 'max_confluence', 0.92, 'estimated', 'Observation-based estimate', '', 'High confluence tolerance. Needs validation.', '2025-12-23'),
('CHO', 'seeding_efficiency', 0.88, 'estimated', 'Industry standard estimate', '', 'Good attachment. Needs validation.', '2025-12-23'),
('CHO', 'passage_stress', 0.018, 'estimated', 'Observation-based estimate', '', 'Robust line. Needs validation.', '2025-12-23'),
('CHO', 'max_passage', 35.0, 'estimated', 'Industry guideline', '', 'Can passage extensively. Needs validation.', '2025-12-23'),
('CHO', 'senescence_rate', 0.008, 'estimated', 'Model parameter', '', 'Low senescence. Needs validation.', '2025-12-23'),
('CHO', 'lag_duration_h', 12.0, 'estimated', 'Model parameter', '', 'Typical lag period. Needs validation.', '2025-12-23'),
('CHO', 'edge_penalty', 0.15, 'estimated', 'Model parameter', '', 'Edge well effect. Needs validation.', '2025-12-23'),
('CHO', 'cell_count_cv', 0.10, 'estimated', 'Assay variability estimate', '', 'Typical CV. Needs validation.', '2025-12-23');

-- iPSC - doubling time
INSERT OR REPLACE INTO parameter_verification VALUES
('iPSC', 'doubling_time_h', 32.0, 'literature_consensus', 'iPSC culture protocols', '', 'Range 30-36h. Slower than cancer lines.', '2025-12-23');

-- iPSC - estimated parameters
INSERT OR REPLACE INTO parameter_verification VALUES
('iPSC', 'max_confluence', 1.0, 'estimated', 'Colony-based growth', '', 'Grows in colonies, not monolayer. Needs validation.', '2025-12-23'),
('iPSC', 'seeding_efficiency', 0.50, 'estimated', 'iPSC protocol estimate', '', 'Low attachment, sensitive to dissociation. Needs validation.', '2025-12-23'),
('iPSC', 'passage_stress', 0.10, 'estimated', 'iPSC protocol estimate', '', 'High stress, sensitive cells. Needs validation.', '2025-12-23'),
('iPSC', 'max_passage', 50.0, 'estimated', 'Industry guideline', '', 'Can passage if maintained properly. Check karyotype regularly.', '2025-12-23'),
('iPSC', 'senescence_rate', 0.02, 'estimated', 'Model parameter', '', 'Can lose pluripotency with passage. Needs validation.', '2025-12-23'),
('iPSC', 'lag_duration_h', 24.0, 'estimated', 'Model parameter', '', 'Long recovery post-seeding. Needs validation.', '2025-12-23'),
('iPSC', 'edge_penalty', 0.15, 'estimated', 'Model parameter', '', 'Edge well effect. Needs validation.', '2025-12-23'),
('iPSC', 'cell_count_cv', 0.15, 'estimated', 'Assay variability estimate', '', 'High CV due to colony formation. Needs validation.', '2025-12-23');

-- ==============================================================================
-- Verification query
-- ==============================================================================

SELECT
    cell_line_id,
    tissue_type,
    growth_mode,
    doubling_time_h,
    culture_medium
FROM cell_line_growth_parameters
ORDER BY growth_mode, cell_line_id;
