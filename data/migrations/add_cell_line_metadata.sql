-- Migration: Add Cell Line Metadata
-- Date: 2025-12-23
-- Purpose: Add rich metadata to cell_line_growth_parameters table

-- Add metadata columns
ALTER TABLE cell_line_growth_parameters ADD COLUMN tissue_type TEXT;
ALTER TABLE cell_line_growth_parameters ADD COLUMN disease TEXT;
ALTER TABLE cell_line_growth_parameters ADD COLUMN organism TEXT DEFAULT 'Homo sapiens';
ALTER TABLE cell_line_growth_parameters ADD COLUMN sex TEXT;
ALTER TABLE cell_line_growth_parameters ADD COLUMN age_years INTEGER;
ALTER TABLE cell_line_growth_parameters ADD COLUMN morphology TEXT;
ALTER TABLE cell_line_growth_parameters ADD COLUMN growth_mode TEXT;  -- adherent, suspension, mixed
ALTER TABLE cell_line_growth_parameters ADD COLUMN culture_medium TEXT;
ALTER TABLE cell_line_growth_parameters ADD COLUMN serum_percent REAL;
ALTER TABLE cell_line_growth_parameters ADD COLUMN coating_required BOOLEAN DEFAULT 0;
ALTER TABLE cell_line_growth_parameters ADD COLUMN coating_type TEXT;
ALTER TABLE cell_line_growth_parameters ADD COLUMN atcc_id TEXT;
ALTER TABLE cell_line_growth_parameters ADD COLUMN rrid TEXT;  -- Research Resource Identifier
ALTER TABLE cell_line_growth_parameters ADD COLUMN cellosaurus_id TEXT;

-- ==============================================================================
-- Update existing cell lines with metadata
-- ==============================================================================

-- A549 - Lung Adenocarcinoma
UPDATE cell_line_growth_parameters SET
    tissue_type = 'Lung',
    disease = 'Adenocarcinoma',
    organism = 'Homo sapiens',
    sex = 'Male',
    age_years = 58,
    morphology = 'Epithelial',
    growth_mode = 'Adherent',
    culture_medium = 'F-12K (ATCC 30-2004)',
    serum_percent = 10.0,
    coating_required = 0,
    atcc_id = 'CCL-185',
    rrid = 'CVCL_0023',
    cellosaurus_id = 'CVCL_0023'
WHERE cell_line_id = 'A549';

-- HepG2 - Hepatoblastoma
UPDATE cell_line_growth_parameters SET
    tissue_type = 'Liver',
    disease = 'Hepatoblastoma',
    organism = 'Homo sapiens',
    sex = 'Male',
    age_years = 15,
    morphology = 'Epithelial',
    growth_mode = 'Adherent',
    culture_medium = 'EMEM (ATCC 30-2003)',
    serum_percent = 10.0,
    coating_required = 0,
    atcc_id = 'HB-8065',
    rrid = 'CVCL_0027',
    cellosaurus_id = 'CVCL_0027'
WHERE cell_line_id = 'HepG2';

-- HEK293 - Human Embryonic Kidney
UPDATE cell_line_growth_parameters SET
    tissue_type = 'Kidney',
    disease = 'Normal (adenovirus transformed)',
    organism = 'Homo sapiens',
    sex = 'Female',
    age_years = NULL,  -- Embryonic
    morphology = 'Epithelial',
    growth_mode = 'Adherent',
    culture_medium = 'DMEM (ATCC 30-2002)',
    serum_percent = 10.0,
    coating_required = 0,
    atcc_id = 'CRL-1573',
    rrid = 'CVCL_0045',
    cellosaurus_id = 'CVCL_0045'
WHERE cell_line_id = 'HEK293';

-- HeLa - Cervical Carcinoma
UPDATE cell_line_growth_parameters SET
    tissue_type = 'Cervix',
    disease = 'Adenocarcinoma',
    organism = 'Homo sapiens',
    sex = 'Female',
    age_years = 31,
    morphology = 'Epithelial',
    growth_mode = 'Adherent',
    culture_medium = 'DMEM (ATCC 30-2002) or EMEM',
    serum_percent = 10.0,
    coating_required = 0,
    atcc_id = 'CCL-2',
    rrid = 'CVCL_0030',
    cellosaurus_id = 'CVCL_0030'
WHERE cell_line_id = 'HeLa';

-- U2OS - Osteosarcoma
UPDATE cell_line_growth_parameters SET
    tissue_type = 'Bone',
    disease = 'Osteosarcoma',
    organism = 'Homo sapiens',
    sex = 'Female',
    age_years = 15,
    morphology = 'Epithelial',
    growth_mode = 'Adherent',
    culture_medium = 'McCoy''s 5A (ATCC 30-2007)',
    serum_percent = 10.0,
    coating_required = 0,
    atcc_id = 'HTB-96',
    rrid = 'CVCL_0042',
    cellosaurus_id = 'CVCL_0042'
WHERE cell_line_id = 'U2OS';

-- iPSC_NGN2 - Induced Neurons
UPDATE cell_line_growth_parameters SET
    tissue_type = 'Brain (iPSC-derived)',
    disease = 'Normal (differentiated)',
    organism = 'Homo sapiens',
    sex = NULL,  -- Depends on iPSC source
    age_years = NULL,
    morphology = 'Neuronal',
    growth_mode = 'Adherent',
    culture_medium = 'Neurobasal + B27 + Glutamax',
    serum_percent = 0.0,  -- Serum-free
    coating_required = 1,
    coating_type = 'Matrigel or poly-D-lysine/laminin',
    atcc_id = NULL,
    rrid = NULL,
    cellosaurus_id = NULL,
    notes = notes || ' Protocol-dependent differentiation from iPSCs via NGN2 overexpression (Zhang et al. 2013 Cell). Post-mitotic excitatory neurons. Coating required.'
WHERE cell_line_id = 'iPSC_NGN2';

-- iPSC_Microglia - Induced Microglia
UPDATE cell_line_growth_parameters SET
    tissue_type = 'Brain (iPSC-derived)',
    disease = 'Normal (differentiated)',
    organism = 'Homo sapiens',
    sex = NULL,  -- Depends on iPSC source
    age_years = NULL,
    morphology = 'Macrophage-like',
    growth_mode = 'Adherent',
    culture_medium = 'DMEM/F12 + microglia supplements',
    serum_percent = 10.0,  -- Protocol-dependent
    coating_required = 1,
    coating_type = 'Matrigel or poly-D-lysine',
    atcc_id = NULL,
    rrid = NULL,
    cellosaurus_id = NULL,
    notes = notes || ' Protocol-dependent differentiation from iPSCs (Abud et al. 2017 Neuron). Immune cell morphology. Coating required.'
WHERE cell_line_id = 'iPSC_Microglia';

-- ==============================================================================
-- Verification query
-- ==============================================================================

SELECT
    cell_line_id,
    tissue_type,
    disease,
    morphology,
    culture_medium,
    atcc_id
FROM cell_line_growth_parameters
ORDER BY cell_line_id;
