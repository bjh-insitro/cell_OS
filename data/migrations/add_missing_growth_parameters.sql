-- Migration: Add Missing Growth Parameters and Verification Status
-- Date: 2025-12-23
-- Purpose: Add max_passage, senescence_rate, assay noise CVs, and parameter verification tracking

-- ==============================================================================
-- Add missing growth parameter columns
-- ==============================================================================

ALTER TABLE cell_line_growth_parameters ADD COLUMN max_passage INTEGER;
ALTER TABLE cell_line_growth_parameters ADD COLUMN senescence_rate REAL;

-- Assay noise parameters (coefficient of variation)
ALTER TABLE cell_line_growth_parameters ADD COLUMN cell_count_cv REAL;
ALTER TABLE cell_line_growth_parameters ADD COLUMN viability_cv REAL;
ALTER TABLE cell_line_growth_parameters ADD COLUMN biological_cv REAL;

-- ==============================================================================
-- Add parameter verification/confidence tracking
-- ==============================================================================

-- For each parameter, track if it's verified, estimated, or needs validation
-- We'll use a separate table to track parameter-level verification

CREATE TABLE IF NOT EXISTS parameter_verification (
    cell_line_id TEXT NOT NULL,
    parameter_name TEXT NOT NULL,
    value REAL NOT NULL,
    verification_status TEXT NOT NULL,  -- 'verified', 'literature_consensus', 'estimated', 'needs_validation'
    source TEXT,
    reference_url TEXT,
    notes TEXT,
    date_verified TEXT,
    PRIMARY KEY (cell_line_id, parameter_name),
    FOREIGN KEY (cell_line_id) REFERENCES cell_line_growth_parameters(cell_line_id)
);

-- ==============================================================================
-- Populate missing parameters from YAML
-- ==============================================================================

-- A549
UPDATE cell_line_growth_parameters SET
    max_passage = 30,
    senescence_rate = 0.01,
    cell_count_cv = 0.11,
    viability_cv = 0.02,
    biological_cv = 0.06
WHERE cell_line_id = 'A549';

-- HepG2
UPDATE cell_line_growth_parameters SET
    max_passage = 25,
    senescence_rate = 0.015,
    cell_count_cv = 0.12,
    viability_cv = 0.03,
    biological_cv = 0.07
WHERE cell_line_id = 'HepG2';

-- HEK293
UPDATE cell_line_growth_parameters SET
    max_passage = 30,
    senescence_rate = 0.01,
    cell_count_cv = 0.10,
    viability_cv = 0.02,
    biological_cv = 0.05
WHERE cell_line_id = 'HEK293';

-- HeLa
UPDATE cell_line_growth_parameters SET
    max_passage = 25,
    senescence_rate = 0.015,
    cell_count_cv = 0.10,
    viability_cv = 0.02,
    biological_cv = 0.05
WHERE cell_line_id = 'HeLa';

-- U2OS
UPDATE cell_line_growth_parameters SET
    max_passage = 28,
    senescence_rate = 0.012,
    cell_count_cv = 0.12,
    viability_cv = 0.02,
    biological_cv = 0.06
WHERE cell_line_id = 'U2OS';

-- iPSC_NGN2 (post-mitotic, different parameters)
UPDATE cell_line_growth_parameters SET
    max_passage = NULL,  -- Post-mitotic neurons don't passage
    senescence_rate = NULL,
    cell_count_cv = 0.15,
    viability_cv = 0.05,
    biological_cv = 0.10
WHERE cell_line_id = 'iPSC_NGN2';

-- iPSC_Microglia
UPDATE cell_line_growth_parameters SET
    max_passage = 30,  -- Estimated
    senescence_rate = 0.02,  -- Estimated
    cell_count_cv = 0.15,
    viability_cv = 0.05,
    biological_cv = 0.10
WHERE cell_line_id = 'iPSC_Microglia';

-- ==============================================================================
-- Mark parameter verification status
-- ==============================================================================

-- VERIFIED PARAMETERS (with ATCC or PubMed citations)

-- A549 - doubling_time verified
INSERT OR REPLACE INTO parameter_verification VALUES
('A549', 'doubling_time_h', 22.0, 'verified', 'ATCC CCL-185', 'https://www.atcc.org/products/ccl-185', 'ATCC official: approximately 22 hrs', '2025-12-22');

-- HepG2 - doubling_time verified (but highly variable)
INSERT OR REPLACE INTO parameter_verification VALUES
('HepG2', 'doubling_time_h', 48.0, 'verified', 'ATCC HB-8065 / DSMZ ACC-180', 'https://www.atcc.org/products/hb-8065', 'Variable 26-60h range, using 48h conservative estimate', '2025-12-22');

-- HEK293 - doubling_time literature consensus
INSERT OR REPLACE INTO parameter_verification VALUES
('HEK293', 'doubling_time_h', 24.0, 'literature_consensus', 'DSMZ / CLS', '', 'Range 24-30h from multiple sources', '2025-12-22');

-- HeLa - doubling_time literature consensus
INSERT OR REPLACE INTO parameter_verification VALUES
('HeLa', 'doubling_time_h', 20.0, 'literature_consensus', 'DSMZ ACC-57 / PubMed 29156801', 'https://pubmed.ncbi.nlm.nih.gov/29156801/', 'Range 20-31h from multiple sources', '2025-12-22');

-- U2OS - doubling_time literature consensus
INSERT OR REPLACE INTO parameter_verification VALUES
('U2OS', 'doubling_time_h', 28.0, 'literature_consensus', 'DSMZ ACC-785 / PubMed 21519327', 'https://pubmed.ncbi.nlm.nih.gov/21519327/', 'Range 25-36h from multiple sources', '2025-12-22');

-- iPSC_NGN2 - doubling_time protocol-dependent
INSERT OR REPLACE INTO parameter_verification VALUES
('iPSC_NGN2', 'doubling_time_h', 1000.0, 'verified', 'Zhang et al. 2013 Cell', 'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3627381/', 'Post-mitotic neurons (essentially infinite doubling time)', '2025-12-22');

-- iPSC_Microglia - doubling_time protocol-dependent
INSERT OR REPLACE INTO parameter_verification VALUES
('iPSC_Microglia', 'doubling_time_h', 40.0, 'literature_consensus', 'Abud et al. 2017 Neuron', 'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5447471/', 'Slow proliferation, protocol-dependent', '2025-12-22');

-- ESTIMATED PARAMETERS (need validation)

-- Max confluence - all estimated from observation
INSERT OR REPLACE INTO parameter_verification VALUES
('A549', 'max_confluence', 0.88, 'estimated', 'Observation-based estimate', '', 'Needs experimental validation', '2025-12-23'),
('HepG2', 'max_confluence', 0.85, 'estimated', 'Observation-based estimate', '', 'Needs experimental validation', '2025-12-23'),
('HEK293', 'max_confluence', 0.9, 'estimated', 'Observation-based estimate', '', 'Needs experimental validation', '2025-12-23'),
('HeLa', 'max_confluence', 0.85, 'estimated', 'Observation-based estimate', '', 'Needs experimental validation', '2025-12-23'),
('U2OS', 'max_confluence', 0.88, 'estimated', 'Observation-based estimate', '', 'Needs experimental validation', '2025-12-23');

-- Seeding efficiency - all estimated
INSERT OR REPLACE INTO parameter_verification VALUES
('A549', 'seeding_efficiency', 0.85, 'estimated', 'Industry standard estimate', '', 'Typical for adherent cells. Needs experimental validation.', '2025-12-23'),
('HepG2', 'seeding_efficiency', 0.80, 'estimated', 'Industry standard estimate', '', 'Lower than A549 due to slower attachment. Needs validation.', '2025-12-23'),
('HEK293', 'seeding_efficiency', 0.88, 'estimated', 'Industry standard estimate', '', 'Fast-growing line. Needs validation.', '2025-12-23'),
('HeLa', 'seeding_efficiency', 0.90, 'estimated', 'Industry standard estimate', '', 'Very robust. Needs validation.', '2025-12-23'),
('U2OS', 'seeding_efficiency', 0.82, 'estimated', 'Industry standard estimate', '', 'Moderate attachment. Needs validation.', '2025-12-23'),
('iPSC_NGN2', 'seeding_efficiency', 0.70, 'estimated', 'Protocol-based estimate', '', 'Neurons more fragile. Needs validation.', '2025-12-23'),
('iPSC_Microglia', 'seeding_efficiency', 0.75, 'estimated', 'Protocol-based estimate', '', 'Immune cells. Needs validation.', '2025-12-23');

-- Passage stress - all estimated
INSERT OR REPLACE INTO parameter_verification VALUES
('A549', 'passage_stress', 0.02, 'estimated', 'Observation-based estimate', '', 'Low stress for robust line. Needs validation.', '2025-12-23'),
('HepG2', 'passage_stress', 0.03, 'estimated', 'Observation-based estimate', '', 'More sensitive to passage. Needs validation.', '2025-12-23'),
('HEK293', 'passage_stress', 0.02, 'estimated', 'Observation-based estimate', '', 'Robust line. Needs validation.', '2025-12-23'),
('HeLa', 'passage_stress', 0.015, 'estimated', 'Observation-based estimate', '', 'Very robust. Needs validation.', '2025-12-23'),
('U2OS', 'passage_stress', 0.025, 'estimated', 'Observation-based estimate', '', 'Moderate stress. Needs validation.', '2025-12-23'),
('iPSC_NGN2', 'passage_stress', 0.05, 'estimated', 'Protocol-based estimate', '', 'Fragile neurons. Needs validation.', '2025-12-23'),
('iPSC_Microglia', 'passage_stress', 0.04, 'estimated', 'Protocol-based estimate', '', 'Moderate stress. Needs validation.', '2025-12-23');

-- Max passage - all estimated
INSERT OR REPLACE INTO parameter_verification VALUES
('A549', 'max_passage', 30, 'estimated', 'Industry guideline', '', 'Typical recommendation. May vary by lab.', '2025-12-23'),
('HepG2', 'max_passage', 25, 'estimated', 'Industry guideline', '', 'Lower due to variability. May vary by lab.', '2025-12-23'),
('HEK293', 'max_passage', 30, 'estimated', 'Industry guideline', '', 'Typical recommendation. May vary by lab.', '2025-12-23'),
('HeLa', 'max_passage', 25, 'estimated', 'Industry guideline', '', 'Typical recommendation. May vary by lab.', '2025-12-23'),
('U2OS', 'max_passage', 28, 'estimated', 'Industry guideline', '', 'Typical recommendation. May vary by lab.', '2025-12-23'),
('iPSC_Microglia', 'max_passage', 30, 'estimated', 'Protocol estimate', '', 'Differentiated cells may have lower limits. Needs validation.', '2025-12-23');

-- Senescence rate - all estimated
INSERT OR REPLACE INTO parameter_verification VALUES
('A549', 'senescence_rate', 0.01, 'estimated', 'Model parameter', '', 'Viability loss per passage. Needs experimental validation.', '2025-12-23'),
('HepG2', 'senescence_rate', 0.015, 'estimated', 'Model parameter', '', 'Slightly higher than A549. Needs validation.', '2025-12-23'),
('HEK293', 'senescence_rate', 0.01, 'estimated', 'Model parameter', '', 'Robust line. Needs validation.', '2025-12-23'),
('HeLa', 'senescence_rate', 0.015, 'estimated', 'Model parameter', '', 'Needs validation.', '2025-12-23'),
('U2OS', 'senescence_rate', 0.012, 'estimated', 'Model parameter', '', 'Needs validation.', '2025-12-23'),
('iPSC_Microglia', 'senescence_rate', 0.02, 'estimated', 'Model parameter', '', 'Higher for differentiated cells. Needs validation.', '2025-12-23');

-- Lag duration - all estimated
INSERT OR REPLACE INTO parameter_verification VALUES
('A549', 'lag_duration_h', 12.0, 'estimated', 'Model parameter', '', 'Recovery time post-seeding. Needs validation.', '2025-12-23'),
('HepG2', 'lag_duration_h', 16.0, 'estimated', 'Model parameter', '', 'Longer recovery for slower line. Needs validation.', '2025-12-23'),
('HEK293', 'lag_duration_h', 12.0, 'estimated', 'Model parameter', '', 'Typical lag period. Needs validation.', '2025-12-23'),
('HeLa', 'lag_duration_h', 12.0, 'estimated', 'Model parameter', '', 'Fast recovery. Needs validation.', '2025-12-23'),
('U2OS', 'lag_duration_h', 12.0, 'estimated', 'Model parameter', '', 'Needs validation.', '2025-12-23'),
('iPSC_NGN2', 'lag_duration_h', 24.0, 'estimated', 'Model parameter', '', 'Post-mitotic neurons, longer recovery. Needs validation.', '2025-12-23'),
('iPSC_Microglia', 'lag_duration_h', 18.0, 'estimated', 'Model parameter', '', 'Moderate recovery. Needs validation.', '2025-12-23');

-- Edge penalty - all estimated (same value for all)
INSERT OR REPLACE INTO parameter_verification VALUES
('A549', 'edge_penalty', 0.15, 'estimated', 'Model parameter', '', 'Edge well effect. Needs experimental validation across plate formats.', '2025-12-23'),
('HepG2', 'edge_penalty', 0.15, 'estimated', 'Model parameter', '', 'Edge well effect. Needs validation.', '2025-12-23'),
('HEK293', 'edge_penalty', 0.15, 'estimated', 'Model parameter', '', 'Edge well effect. Needs validation.', '2025-12-23'),
('HeLa', 'edge_penalty', 0.15, 'estimated', 'Model parameter', '', 'Edge well effect. Needs validation.', '2025-12-23'),
('U2OS', 'edge_penalty', 0.15, 'estimated', 'Model parameter', '', 'Edge well effect. Needs validation.', '2025-12-23'),
('iPSC_NGN2', 'edge_penalty', 0.15, 'estimated', 'Model parameter', '', 'Edge well effect. Needs validation.', '2025-12-23'),
('iPSC_Microglia', 'edge_penalty', 0.15, 'estimated', 'Model parameter', '', 'Edge well effect. Needs validation.', '2025-12-23');

-- Assay noise parameters - all estimated
INSERT OR REPLACE INTO parameter_verification VALUES
('A549', 'cell_count_cv', 0.11, 'estimated', 'Assay variability estimate', '', 'Typical CV for cell counting assays. Needs validation on specific equipment.', '2025-12-23'),
('HepG2', 'cell_count_cv', 0.12, 'estimated', 'Assay variability estimate', '', 'Slightly higher due to variable morphology. Needs validation.', '2025-12-23'),
('HEK293', 'cell_count_cv', 0.10, 'estimated', 'Assay variability estimate', '', 'Typical CV. Needs validation.', '2025-12-23'),
('HeLa', 'cell_count_cv', 0.10, 'estimated', 'Assay variability estimate', '', 'Typical CV. Needs validation.', '2025-12-23'),
('U2OS', 'cell_count_cv', 0.12, 'estimated', 'Assay variability estimate', '', 'Higher CV. Needs validation.', '2025-12-23'),
('iPSC_NGN2', 'cell_count_cv', 0.15, 'estimated', 'Assay variability estimate', '', 'Neurons harder to count. Needs validation.', '2025-12-23'),
('iPSC_Microglia', 'cell_count_cv', 0.15, 'estimated', 'Assay variability estimate', '', 'Variable morphology. Needs validation.', '2025-12-23');

-- ==============================================================================
-- Create view for parameter verification summary
-- ==============================================================================

CREATE VIEW IF NOT EXISTS parameter_verification_summary AS
SELECT
    pv.cell_line_id,
    COUNT(*) as total_parameters,
    SUM(CASE WHEN pv.verification_status = 'verified' THEN 1 ELSE 0 END) as verified,
    SUM(CASE WHEN pv.verification_status = 'literature_consensus' THEN 1 ELSE 0 END) as literature_consensus,
    SUM(CASE WHEN pv.verification_status = 'estimated' THEN 1 ELSE 0 END) as estimated,
    SUM(CASE WHEN pv.verification_status = 'needs_validation' THEN 1 ELSE 0 END) as needs_validation
FROM parameter_verification pv
GROUP BY pv.cell_line_id;

-- ==============================================================================
-- Verification query
-- ==============================================================================

SELECT
    cell_line_id,
    doubling_time_h,
    max_passage,
    senescence_rate,
    cell_count_cv
FROM cell_line_growth_parameters
ORDER BY cell_line_id;
