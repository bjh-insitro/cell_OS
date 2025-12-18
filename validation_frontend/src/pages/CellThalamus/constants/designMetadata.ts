/**
 * Design metadata constants - single source of truth for compound/cell line info
 */

export interface CompoundMetadata {
  color: string;
  label: string;
  ic50_uM: number;
  mechanism: string;
  tooltip: string;
}

export interface CellLineMetadata {
  color: string;
  label: string;
  tooltip: string;
}

export const COMPOUND_METADATA: Record<string, CompoundMetadata> = {
  tBHQ: {
    color: '#ef4444',
    label: 'tBHQ',
    ic50_uM: 30.0,
    mechanism: 'Oxidative stress',
    tooltip: 'Oxidative stress. NRF2 activator, electrophile (IC50: 30 µM)',
  },
  H2O2: {
    color: '#f97316',
    label: 'H₂O₂',
    ic50_uM: 100.0,
    mechanism: 'Oxidative stress',
    tooltip: 'Oxidative stress. Direct ROS, hydrogen peroxide (IC50: 100 µM)',
  },
  tunicamycin: {
    color: '#f59e0b',
    label: 'tunicamycin',
    ic50_uM: 1.0,
    mechanism: 'ER stress',
    tooltip: 'ER stress. N-glycosylation inhibitor (IC50: 1 µM)',
  },
  thapsigargin: {
    color: '#eab308',
    label: 'thapsigargin',
    ic50_uM: 0.5,
    mechanism: 'ER stress',
    tooltip: 'ER stress. SERCA pump inhibitor, Ca²⁺ disruption (IC50: 0.5 µM)',
  },
  CCCP: {
    color: '#84cc16',
    label: 'CCCP',
    ic50_uM: 5.0,
    mechanism: 'Mitochondrial stress',
    tooltip: 'Mitochondrial stress. Protonophore uncoupler (IC50: 5 µM)',
  },
  oligomycin: {
    color: '#22c55e',
    label: 'oligomycin',
    ic50_uM: 1.0,
    mechanism: 'Mitochondrial stress',
    tooltip: 'Mitochondrial stress. ATP synthase inhibitor (IC50: 1 µM)',
  },
  etoposide: {
    color: '#14b8a6',
    label: 'etoposide',
    ic50_uM: 10.0,
    mechanism: 'DNA damage',
    tooltip: 'DNA damage. Topoisomerase II inhibitor (IC50: 10 µM)',
  },
  MG132: {
    color: '#06b6d4',
    label: 'MG132',
    ic50_uM: 1.0,
    mechanism: 'Proteasome inhibitor',
    tooltip: 'Proteasome inhibitor. Protein degradation blockade (IC50: 1 µM)',
  },
  nocodazole: {
    color: '#3b82f6',
    label: 'nocodazole',
    ic50_uM: 0.5,
    mechanism: 'Microtubule poison',
    tooltip: 'Microtubule poison. Depolymerizer (IC50: 0.5 µM)',
  },
  paclitaxel: {
    color: '#8b5cf6',
    label: 'paclitaxel',
    ic50_uM: 0.01,
    mechanism: 'Microtubule poison',
    tooltip: 'Microtubule poison. Stabilizer (IC50: 0.01 µM)',
  },
};

export const CELL_LINE_METADATA: Record<string, CellLineMetadata> = {
  A549: {
    color: '#8b5cf6',
    label: 'A549',
    tooltip: 'Lung cancer. NRF2-primed (oxidative resistant), fast cycling (microtubule sensitive)',
  },
  HepG2: {
    color: '#ec4899',
    label: 'HepG2',
    tooltip: 'Hepatoma. High ER load, OXPHOS-dependent, H2O2 resistant',
  },
  iPSC_NGN2: {
    color: '#06b6d4',
    label: 'iPSC_NGN2',
    tooltip: 'Neurons. Post-mitotic, extreme OXPHOS dependence, transport-critical',
  },
  iPSC_Microglia: {
    color: '#22c55e',
    label: 'iPSC_Microglia',
    tooltip: 'Immune cells. High ROS resistance, phagocytic, pro-inflammatory',
  },
};

export const AVAILABLE_CELL_LINES = Object.keys(CELL_LINE_METADATA);
export const AVAILABLE_COMPOUNDS = Object.keys(COMPOUND_METADATA);
