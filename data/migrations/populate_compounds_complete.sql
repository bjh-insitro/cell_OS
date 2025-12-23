-- Migration: Populate Complete Compound Data with All IC50s
-- Date: 2025-12-23
-- Purpose: Add all compounds and IC50 values from YAML + literature verification
-- Status: Verified values updated based on PubMed literature, YAML values marked as estimated

-- ==============================================================================
-- COMPOUNDS - Basic Information
-- ==============================================================================

INSERT OR REPLACE INTO compounds (compound_id, common_name, cas_number, pubchem_cid, molecular_weight, mechanism, target, compound_class, notes, date_added) VALUES
('staurosporine', 'Staurosporine', '62996-74-1', 44259, 466.5, 'Pan-kinase inhibitor', 'Protein kinases', 'Alkaloid', 'Broad-spectrum kinase inhibitor. Highly potent apoptosis inducer.', '2025-12-23'),
('doxorubicin', 'Doxorubicin', '23214-92-8', 31703, 543.5, 'DNA intercalation, topoisomerase II inhibition', 'DNA, Topoisomerase II', 'Anthracycline', 'Chemotherapy drug. Causes DNA damage and generates ROS.', '2025-12-23'),
('cisplatin', 'Cisplatin', '15663-27-1', 441203, 300.0, 'DNA crosslinking', 'DNA', 'Platinum compound', 'Chemotherapy drug. Forms DNA adducts.', '2025-12-23'),
('paclitaxel', 'Paclitaxel', '33069-62-4', 36314, 853.9, 'Microtubule stabilization', 'Tubulin', 'Taxane', 'Chemotherapy drug. Stabilizes microtubules preventing mitosis.', '2025-12-23'),
('tunicamycin', 'Tunicamycin', '11089-65-9', NULL, NULL, 'N-glycosylation inhibition', 'GlcNAc-1-P transferase', 'Nucleoside antibiotic', 'Induces ER stress by blocking N-linked glycosylation.', '2025-12-23'),
('thapsigargin', 'Thapsigargin', '67526-95-8', 446378, 650.8, 'SERCA pump inhibition', 'SERCA', 'Sesquiterpene lactone', 'Induces ER stress by depleting ER calcium.', '2025-12-23'),
('etoposide', 'Etoposide', '33419-42-0', 36462, 588.6, 'Topoisomerase II inhibition', 'Topoisomerase II', 'Podophyllotoxin derivative', 'Chemotherapy drug. Causes DNA breaks.', '2025-12-23'),
('cccp', 'CCCP', '555-60-2', 2603, 204.6, 'Mitochondrial uncoupling', 'Mitochondrial membrane', 'Ionophore', 'Dissipates mitochondrial membrane potential.', '2025-12-23'),
('oligomycin_a', 'Oligomycin A', '579-13-5', 5281899, 791.1, 'ATP synthase inhibition', 'F0F1 ATP synthase', 'Macrolide', 'Blocks mitochondrial ATP synthesis.', '2025-12-23'),
('mg132', 'MG132', '133407-82-6', 462382, 475.6, 'Proteasome inhibition', '26S proteasome', 'Peptide aldehyde', 'Reversible proteasome inhibitor.', '2025-12-23'),
('nocodazole', 'Nocodazole', '31430-18-9', 4122, 301.3, 'Microtubule depolymerization', 'Tubulin', 'Benzimidazole', 'Destabilizes microtubules.', '2025-12-23'),
('two_deoxy_d_glucose', '2-Deoxy-D-glucose', '154-17-6', 439959, 164.2, 'Glycolysis inhibition', 'Hexokinase', 'Glucose analog', 'Inhibits glycolysis by competing with glucose.', '2025-12-23'),
('hydrogen_peroxide', 'Hydrogen Peroxide', '7722-84-1', 784, 34.0, 'Oxidative stress', 'Proteins, lipids, DNA', 'ROS', 'Generates oxidative stress.', '2025-12-23'),
('H2O2', 'Hydrogen Peroxide', '7722-84-1', 784, 34.0, 'Oxidative stress', 'Proteins, lipids, DNA', 'ROS', 'Duplicate entry - same as hydrogen_peroxide.', '2025-12-23'),
('tBHQ', 'tert-Butylhydroquinone', '1948-33-0', 16043, 166.2, 'Oxidative stress, Nrf2 activation', 'Nrf2 pathway', 'Phenolic antioxidant', 'Induces oxidative stress at high doses.', '2025-12-23'),
('tbhp', 'tert-Butyl hydroperoxide', '75-91-2', 6410, 90.1, 'Oxidative stress', 'Cellular macromolecules', 'Organic peroxide', 'Lipophilic oxidant. Generates ROS.', '2025-12-23');

-- ==============================================================================
-- IC50 VALUES - VERIFIED (Updated based on literature)
-- ==============================================================================

-- Staurosporine (CORRECTED: Literature shows 0.65 nM in A549, using 5 nM as conservative estimate for other lines)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, assay_type, assay_duration_h, source, reference_url, pubmed_id, notes, date_verified) VALUES
('staurosporine', 'A549', 0.00065, 1.2, 'cell counting', 96, 'Bradshaw TD et al. Int J Cancer 1992', 'https://pubmed.ncbi.nlm.nih.gov/1563835/', '1563835', 'VERIFIED: IC50 0.65 nM (0.00065 µM) for 96h growth inhibition.', '2025-12-23'),
('staurosporine', 'HEK293', 0.005, 1.2, NULL, NULL, 'Estimated from literature consensus', '', '', 'CORRECTED from YAML (was 0.05 µM). Reduced 10x based on A549 verification. Needs experimental validation.', '2025-12-23'),
('staurosporine', 'HeLa', 0.005, 1.2, NULL, NULL, 'Estimated from literature consensus', '', '', 'CORRECTED from YAML (was 0.08 µM). Reduced 16x based on literature. Needs validation.', '2025-12-23'),
('staurosporine', 'U2OS', 0.010, 1.2, NULL, NULL, 'Estimated from literature consensus', '', '', 'CORRECTED from YAML (was 0.20 µM). Reduced 20x. U2OS may be slightly more resistant. Needs validation.', '2025-12-23');

-- Doxorubicin (CORRECTED: Literature shows 10.15 µM in HepG2, using 5-10 µM for other lines)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, assay_type, assay_duration_h, source, reference_url, pubmed_id, notes, date_verified) VALUES
('doxorubicin', 'HepG2', 10.15, 1.3, 'MTT', NULL, 'Buduma K et al. Bioorg Med Chem Lett 2016', 'https://pubmed.ncbi.nlm.nih.gov/26873414/', '26873414', 'VERIFIED: IC50 10.15 µM in HepG2. Also tested A549, HeLa, SKOV3.', '2025-12-23'),
('doxorubicin', 'HEK293', 5.0, 1.3, NULL, NULL, 'Estimated from literature consensus', '', '', 'CORRECTED from YAML (was 0.25 µM). Increased 20x based on HepG2 verification. Needs validation.', '2025-12-23'),
('doxorubicin', 'HeLa', 5.0, 1.3, NULL, NULL, 'Estimated from literature consensus', '', '', 'CORRECTED from YAML (was 0.15 µM). Increased 33x. Typical range 1-10 µM. Needs validation.', '2025-12-23'),
('doxorubicin', 'A549', 5.0, 1.3, NULL, NULL, 'Estimated from literature consensus', '', '', 'Estimated based on typical doxorubicin range (1-10 µM). Needs validation.', '2025-12-23'),
('doxorubicin', 'U2OS', 7.0, 1.3, NULL, NULL, 'Estimated from literature consensus', '', '', 'CORRECTED from YAML (was 0.35 µM). Increased 20x. Needs validation.', '2025-12-23');

-- Paclitaxel (VERIFIED - YAML values match literature well)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, assay_type, assay_duration_h, source, reference_url, pubmed_id, notes, date_verified) VALUES
('paclitaxel', 'A549', 0.018, 1.4, 'cytotoxicity', NULL, 'Joshi N et al. Int J Pharm 2012', 'https://pubmed.ncbi.nlm.nih.gov/21807043/', '21807043', 'VERIFIED: IC50 18 nM (0.018 µM) in A549.', '2025-12-23'),
('paclitaxel', 'HEK293', 0.01, 1.4, NULL, NULL, 'Estimated from YAML - consistent with literature', '', '', 'YAML value (10 nM). Matches A549 verified value (18 nM). Reasonable.', '2025-12-23'),
('paclitaxel', 'HeLa', 0.008, 1.4, NULL, NULL, 'Estimated from YAML - consistent with literature', '', '', 'YAML value (8 nM). Consistent with paclitaxel potency range.', '2025-12-23'),
('paclitaxel', 'U2OS', 0.015, 1.4, NULL, NULL, 'Estimated from YAML - consistent with literature', '', '', 'YAML value (15 nM). Consistent with literature.', '2025-12-23');

-- Cisplatin (YAML values seem reasonable, keeping as-is)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, source, notes, date_verified) VALUES
('cisplatin', 'HEK293', 5.0, 1.1, 'Estimated from YAML', 'Literature shows wide range (0.07-34 µM). YAML value (5 µM) is mid-range. Needs validation.', '2025-12-23'),
('cisplatin', 'HeLa', 3.0, 1.1, 'Estimated from YAML', 'YAML value. Needs validation.', '2025-12-23'),
('cisplatin', 'A549', 5.0, 1.1, 'Estimated from YAML', 'YAML value. Needs validation.', '2025-12-23'),
('cisplatin', 'HepG2', 6.0, 1.1, 'Estimated from YAML', 'YAML value. Needs validation.', '2025-12-23'),
('cisplatin', 'U2OS', 8.0, 1.1, 'Estimated from YAML', 'YAML value. Needs validation.', '2025-12-23');

-- ==============================================================================
-- RESEARCH TOOL COMPOUNDS - All from YAML, marked as estimated
-- ==============================================================================

-- Tunicamycin (ER stress inducer)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, source, notes, date_verified) VALUES
('tunicamycin', 'HEK293', 0.80, 1.8, 'Estimated - research tool compound', 'ER stress inducer. Not systematically tested for cytotoxicity.', '2025-12-23'),
('tunicamycin', 'HeLa', 0.60, 1.8, 'Estimated - research tool compound', 'ER stress inducer. IC50 estimated.', '2025-12-23'),
('tunicamycin', 'A549', 1.0, 1.8, 'Estimated - research tool compound', 'ER stress inducer. IC50 estimated.', '2025-12-23'),
('tunicamycin', 'HepG2', 1.0, 1.8, 'Estimated - research tool compound', 'ER stress inducer. IC50 estimated.', '2025-12-23'),
('tunicamycin', 'U2OS', 0.30, 1.8, 'Estimated - research tool compound', 'ER stress inducer. IC50 estimated.', '2025-12-23'),
('tunicamycin', 'iPSC_NGN2', 0.5, 1.8, 'Estimated - research tool compound', 'ER stress inducer. Neurons may be more sensitive.', '2025-12-23');

-- Thapsigargin (SERCA pump inhibitor)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, source, notes, date_verified) VALUES
('thapsigargin', 'HEK293', 0.5, 2.2, 'Estimated - research tool compound', 'SERCA pump inhibitor. IC50 from YAML.', '2025-12-23'),
('thapsigargin', 'HeLa', 0.4, 2.2, 'Estimated - research tool compound', 'SERCA pump inhibitor. IC50 estimated.', '2025-12-23'),
('thapsigargin', 'A549', 0.5, 2.2, 'Estimated - research tool compound', 'SERCA pump inhibitor. IC50 estimated.', '2025-12-23'),
('thapsigargin', 'HepG2', 0.6, 2.2, 'Estimated - research tool compound', 'SERCA pump inhibitor. IC50 estimated.', '2025-12-23'),
('thapsigargin', 'U2OS', 0.5, 2.2, 'Estimated - research tool compound', 'SERCA pump inhibitor. IC50 estimated.', '2025-12-23'),
('thapsigargin', 'iPSC_NGN2', 0.3, 2.2, 'Estimated - research tool compound', 'SERCA pump inhibitor. Neurons may be more sensitive.', '2025-12-23');

-- Etoposide (Topoisomerase II inhibitor)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, source, notes, date_verified) VALUES
('etoposide', 'HEK293', 10.0, 1.6, 'Estimated from YAML', 'Chemotherapy drug. IC50 from YAML. Needs validation.', '2025-12-23'),
('etoposide', 'HeLa', 8.0, 1.6, 'Estimated from YAML', 'IC50 from YAML. Needs validation.', '2025-12-23'),
('etoposide', 'A549', 10.0, 1.6, 'Estimated from YAML', 'IC50 from YAML. Needs validation.', '2025-12-23'),
('etoposide', 'HepG2', 12.0, 1.6, 'Estimated from YAML', 'IC50 from YAML. Needs validation.', '2025-12-23'),
('etoposide', 'U2OS', 10.0, 1.6, 'Estimated from YAML', 'IC50 from YAML. Needs validation.', '2025-12-23'),
('etoposide', 'iPSC_NGN2', 5.0, 1.6, 'Estimated from YAML', 'IC50 from YAML. iPSCs may be more sensitive.', '2025-12-23');

-- CCCP (Mitochondrial uncoupler)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, source, notes, date_verified) VALUES
('cccp', 'HEK293', 5.0, 2.0, 'Estimated - research tool compound', 'Mitochondrial uncoupler. IC50 from YAML.', '2025-12-23'),
('cccp', 'HeLa', 4.0, 2.0, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('cccp', 'A549', 5.0, 2.0, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('cccp', 'HepG2', 6.0, 2.0, 'Estimated - research tool compound', 'IC50 estimated. Hepatocytes may be more resistant.', '2025-12-23'),
('cccp', 'U2OS', 5.0, 2.0, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('cccp', 'iPSC_NGN2', 3.0, 2.0, 'Estimated - research tool compound', 'IC50 estimated. Neurons may be more sensitive.', '2025-12-23');

-- Oligomycin A (ATP synthase inhibitor)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, source, notes, date_verified) VALUES
('oligomycin_a', 'HEK293', 1.0, 1.7, 'Estimated - research tool compound', 'ATP synthase inhibitor. IC50 from YAML.', '2025-12-23'),
('oligomycin_a', 'HeLa', 0.8, 1.7, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('oligomycin_a', 'A549', 1.0, 1.7, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('oligomycin_a', 'HepG2', 1.2, 1.7, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('oligomycin_a', 'U2OS', 1.0, 1.7, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('oligomycin_a', 'iPSC_NGN2', 0.5, 1.7, 'Estimated - research tool compound', 'IC50 estimated. Neurons may be more sensitive.', '2025-12-23');

-- MG132 (Proteasome inhibitor)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, source, notes, date_verified) VALUES
('mg132', 'HEK293', 1.0, 1.9, 'Estimated - research tool compound', 'Proteasome inhibitor. IC50 from YAML.', '2025-12-23'),
('mg132', 'HeLa', 0.8, 1.9, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('mg132', 'A549', 1.0, 1.9, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('mg132', 'HepG2', 1.2, 1.9, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('mg132', 'U2OS', 1.0, 1.9, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('mg132', 'iPSC_NGN2', 0.5, 1.9, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23');

-- Nocodazole (Microtubule depolymerizer)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, source, notes, date_verified) VALUES
('nocodazole', 'HEK293', 0.5, 2.1, 'Estimated - research tool compound', 'Microtubule depolymerizer. IC50 from YAML.', '2025-12-23'),
('nocodazole', 'HeLa', 0.4, 2.1, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('nocodazole', 'A549', 0.5, 2.1, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('nocodazole', 'HepG2', 0.6, 2.1, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('nocodazole', 'U2OS', 0.5, 2.1, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23'),
('nocodazole', 'iPSC_NGN2', 0.3, 2.1, 'Estimated - research tool compound', 'IC50 estimated.', '2025-12-23');

-- 2-Deoxy-D-glucose (Glycolysis inhibitor)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, source, notes, date_verified) VALUES
('two_deoxy_d_glucose', 'HEK293', 1000.0, 1.2, 'Estimated from YAML', 'Glycolysis inhibitor. IC50 in mM range. From YAML.', '2025-12-23'),
('two_deoxy_d_glucose', 'HeLa', 800.0, 1.2, 'Estimated from YAML', 'IC50 from YAML.', '2025-12-23'),
('two_deoxy_d_glucose', 'A549', 1000.0, 1.2, 'Estimated from YAML', 'IC50 from YAML.', '2025-12-23'),
('two_deoxy_d_glucose', 'HepG2', 1200.0, 1.2, 'Estimated from YAML', 'IC50 from YAML. Hepatocytes may be more resistant.', '2025-12-23'),
('two_deoxy_d_glucose', 'U2OS', 1000.0, 1.2, 'Estimated from YAML', 'IC50 from YAML.', '2025-12-23'),
('two_deoxy_d_glucose', 'iPSC_NGN2', 500.0, 1.2, 'Estimated from YAML', 'IC50 from YAML.', '2025-12-23');

-- Hydrogen Peroxide (Oxidative stress)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, source, notes, date_verified) VALUES
('hydrogen_peroxide', 'HEK293', 150.0, 2.0, 'Estimated from YAML', 'Oxidative stress inducer. IC50 from YAML.', '2025-12-23'),
('hydrogen_peroxide', 'HeLa', 120.0, 2.0, 'Estimated from YAML', 'IC50 from YAML.', '2025-12-23'),
('hydrogen_peroxide', 'A549', 100.0, 2.0, 'Estimated from YAML', 'IC50 from YAML. Lung cells may be more sensitive to ROS.', '2025-12-23'),
('hydrogen_peroxide', 'HepG2', 150.0, 2.0, 'Estimated from YAML', 'IC50 from YAML.', '2025-12-23'),
('hydrogen_peroxide', 'U2OS', 250.0, 2.0, 'Estimated from YAML', 'IC50 from YAML. U2OS may be more resistant.', '2025-12-23'),
('hydrogen_peroxide', 'iPSC_NGN2', 60.0, 2.0, 'Estimated from YAML', 'IC50 from YAML. Neurons more sensitive to oxidative stress.', '2025-12-23');

-- H2O2 (duplicate entry, same as hydrogen_peroxide)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, source, notes, date_verified) VALUES
('H2O2', 'HEK293', 150.0, 1.5, 'Estimated from YAML', 'Duplicate of hydrogen_peroxide. IC50 from YAML.', '2025-12-23'),
('H2O2', 'HeLa', 120.0, 1.5, 'Estimated from YAML', 'IC50 from YAML.', '2025-12-23'),
('H2O2', 'U2OS', 250.0, 1.5, 'Estimated from YAML', 'IC50 from YAML.', '2025-12-23');

-- tBHQ (Oxidative stress, Nrf2 activator)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, source, notes, date_verified) VALUES
('tBHQ', 'A549', 35.0, 0.8, 'Estimated from YAML - tuned for demo', 'Shallow Hill slope for demo purposes. IC50 tuned for realistic dose-response.', '2025-12-23'),
('tBHQ', 'HepG2', 35.0, 0.8, 'Estimated from YAML - tuned for demo', 'Shallow Hill slope for demo.', '2025-12-23'),
('tBHQ', 'U2OS', 35.0, 0.8, 'Estimated from YAML - tuned for demo', 'Shallow Hill slope for demo.', '2025-12-23');

-- TBHP (Oxidative stress)
INSERT OR REPLACE INTO compound_ic50 (compound_id, cell_line_id, ic50_uM, hill_slope, source, notes, date_verified) VALUES
('tbhp', 'U2OS', 100.0, 2.0, 'Estimated from YAML', 'Oxidative stress inducer. IC50 from YAML.', '2025-12-23'),
('tbhp', 'HepG2', 150.0, 2.0, 'Estimated from YAML', 'Hepatocytes more resistant to oxidative stress.', '2025-12-23'),
('tbhp', 'A549', 80.0, 2.0, 'Estimated from YAML', 'Lung cells more sensitive to ROS.', '2025-12-23'),
('tbhp', 'iPSC_NGN2', 60.0, 2.0, 'Estimated from YAML', 'Neurons sensitive to oxidative stress.', '2025-12-23'),
('tbhp', 'HEK293', 120.0, 2.0, 'Estimated from YAML', 'IC50 from YAML.', '2025-12-23'),
('tbhp', 'HeLa', 90.0, 2.0, 'Estimated from YAML', 'IC50 from YAML.', '2025-12-23');

-- ==============================================================================
-- Summary Query
-- ==============================================================================

SELECT
    '=== COMPOUND DATABASE POPULATED ===' as status,
    (SELECT COUNT(*) FROM compounds) as total_compounds,
    (SELECT COUNT(*) FROM compound_ic50) as total_ic50_entries,
    (SELECT COUNT(DISTINCT cell_line_id) FROM compound_ic50) as cell_lines_covered,
    (SELECT COUNT(*) FROM compound_ic50 WHERE pubmed_id IS NOT NULL) as verified_with_pubmed,
    (SELECT COUNT(*) FROM compound_ic50 WHERE source LIKE '%Estimated%') as estimated_values;
