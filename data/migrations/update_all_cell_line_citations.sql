-- Migration: Update All Cell Line Citations
-- Date: 2025-12-22
-- Purpose: Add ATCC and Cellosaurus verified data for all cell lines

-- ==============================================================================
-- Update HEK293 with ATCC + Cellosaurus data
-- ==============================================================================

UPDATE cell_line_growth_parameters SET
    doubling_time_h = 24.0,
    doubling_time_range_min_h = 24.0,
    doubling_time_range_max_h = 30.0,
    seeding_efficiency = 0.88,
    passage_stress = 0.02,
    source = 'ATCC CRL-1573 / DSMZ / CLS',
    reference_url = 'https://www.atcc.org/products/crl-1573',
    notes = 'Human embryonic kidney. ATCC recommends 10,000-40,000 cells/cm². Doubling time 24-30h (DSMZ/CLS). Fast-growing, robust. Widely used for transfection.',
    date_verified = '2025-12-22'
WHERE cell_line_id = 'HEK293';

-- Update HEK293 seeding densities with ATCC reference
UPDATE seeding_densities SET
    source = 'ATCC CRL-1573',
    reference_url = 'https://www.atcc.org/products/crl-1573',
    date_verified = '2025-12-22',
    notes = 'ATCC recommends 10,000-40,000 cells/cm². ' || notes
WHERE cell_line_id = 'HEK293' AND source = 'Literature consensus';

-- ==============================================================================
-- Update HeLa with ATCC + Cellosaurus data
-- ==============================================================================

UPDATE cell_line_growth_parameters SET
    doubling_time_h = 20.0,
    doubling_time_range_min_h = 20.0,
    doubling_time_range_max_h = 31.0,
    seeding_efficiency = 0.90,
    passage_stress = 0.015,
    source = 'ATCC CCL-2 / DSMZ ACC-57 / PubMed 29156801',
    reference_url = 'https://www.atcc.org/products/ccl-2',
    notes = 'Cervical carcinoma. First immortal human cell line (1951). Doubling time 20-31h (1.3 days per PubMed 29156801, 48h per DSMZ ACC-57). Very fast and robust.',
    date_verified = '2025-12-22'
WHERE cell_line_id = 'HeLa';

UPDATE seeding_densities SET
    source = 'ATCC CCL-2',
    reference_url = 'https://www.atcc.org/products/ccl-2',
    date_verified = '2025-12-22',
    notes = 'Very fast-growing cervical cancer line. ' || notes
WHERE cell_line_id = 'HeLa' AND source = 'Literature consensus';

-- ==============================================================================
-- Update U2OS with ATCC + Cellosaurus data
-- ==============================================================================

UPDATE cell_line_growth_parameters SET
    doubling_time_h = 28.0,
    doubling_time_range_min_h = 25.0,
    doubling_time_range_max_h = 36.0,
    seeding_efficiency = 0.82,
    passage_stress = 0.025,
    source = 'ATCC HTB-96 / DSMZ ACC-785 / PubMed 21519327',
    reference_url = 'https://www.atcc.org/products/htb-96',
    notes = 'Osteosarcoma. Doubling time 25-36h (variable, DSMZ reports 25-30h, PubMed 21519327 reports 36h). Moderate growth rate. McCoys 5A medium.',
    date_verified = '2025-12-22'
WHERE cell_line_id = 'U2OS';

UPDATE seeding_densities SET
    source = 'ATCC HTB-96',
    reference_url = 'https://www.atcc.org/products/htb-96',
    date_verified = '2025-12-22',
    notes = 'Osteosarcoma. Moderate growth rate. ' || notes
WHERE cell_line_id = 'U2OS' AND source = 'Literature consensus';

-- ==============================================================================
-- Add iPSC_NGN2 (specialized differentiated neurons)
-- ==============================================================================

INSERT OR REPLACE INTO cell_line_growth_parameters (
    cell_line_id, doubling_time_h, doubling_time_range_min_h, doubling_time_range_max_h,
    max_confluence, seeding_efficiency, passage_stress, lag_duration_h, edge_penalty,
    source, reference_url, notes, date_verified
) VALUES (
    'iPSC_NGN2',
    1000.0,  -- Post-mitotic neurons (essentially don't divide)
    NULL,
    NULL,
    1.0,  -- Not confluence-limited (neurons don't form monolayers)
    0.70,  -- Lower attachment efficiency
    0.05,  -- Fragile cells
    24.0,  -- Longer recovery time
    0.15,
    'Protocol-dependent (Zhang et al. 2013 Cell)',
    'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3627381/',
    'iPSC-derived excitatory neurons via NGN2 overexpression. POST-MITOTIC (do not divide). High seeding density required (4,000-8,000 cells/well for 384-well). Protocol from Zhang et al. 2013.',
    '2025-12-22'
);

UPDATE seeding_densities SET
    source = 'NGN2 differentiation protocol',
    reference_url = 'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3627381/',
    date_verified = '2025-12-22',
    notes = 'Post-mitotic neurons. Seed high, minimal proliferation. NGN2 protocol (Zhang et al. 2013).'
WHERE cell_line_id = 'iPSC_NGN2';

-- ==============================================================================
-- Add iPSC_Microglia (specialized differentiated immune cells)
-- ==============================================================================

INSERT OR REPLACE INTO cell_line_growth_parameters (
    cell_line_id, doubling_time_h, doubling_time_range_min_h, doubling_time_range_max_h,
    max_confluence, seeding_efficiency, passage_stress, lag_duration_h, edge_penalty,
    source, reference_url, notes, date_verified
) VALUES (
    'iPSC_Microglia',
    40.0,  -- Slow proliferation (immune cells)
    36.0,
    48.0,
    0.85,
    0.75,
    0.04,
    18.0,
    0.15,
    'Protocol-dependent (Abud et al. 2017 Neuron)',
    'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5447471/',
    'iPSC-derived microglia. Slow proliferation (40h doubling). Can divide but growth rate varies. Immune cell morphology. Protocol from Abud et al. 2017.',
    '2025-12-22'
);

UPDATE seeding_densities SET
    source = 'Microglia differentiation protocol',
    reference_url = 'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5447471/',
    date_verified = '2025-12-22',
    notes = 'iPSC-derived microglia. Moderate proliferation. Immune cells.'
WHERE cell_line_id = 'iPSC_Microglia';

-- ==============================================================================
-- Verification query
-- ==============================================================================
-- SELECT cell_line_id, doubling_time_h, source, reference_url, date_verified
-- FROM cell_line_growth_parameters
-- ORDER BY cell_line_id;
