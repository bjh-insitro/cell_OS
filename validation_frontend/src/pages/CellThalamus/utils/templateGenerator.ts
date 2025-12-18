/**
 * Cell Thalamus Phase 0 Plate Template Generator
 *
 * Generates fixed plate layouts with:
 * - 2 cell lines (rows A-D, E-H)
 * - 16 fixed sentinel wells (8 per cell line)
 * - 80 treatment wells (40 per cell line: 10 compounds × 4 doses)
 */

export interface Well {
  row: string;
  col: number;
  wellId: string;
  cellLine: string;
  type: 'sentinel' | 'dmso' | 'experimental';
  compound?: string;
  dose?: string;
  sentinelType?: 'mild' | 'strong' | 'dmso' | 'reference';
}

// Plate structure
const ROWS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
const COLS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

// Cell line assignments
const CELL_LINE_1 = 'A549';
const CELL_LINE_2 = 'HepG2';
const CELL_LINE_1_ROWS = ['A', 'B', 'C', 'D'];
const CELL_LINE_2_ROWS = ['E', 'F', 'G', 'H'];

// Sentinel pattern (per cell line block)
// These positions are the SAME across all templates and timepoints
const SENTINEL_PATTERN = [
  { relRow: 0, col: 1, type: 'dmso' as const },      // A1 or E1
  { relRow: 1, col: 1, type: 'dmso' as const },      // B1 or F1
  { relRow: 2, col: 1, type: 'mild' as const },      // C1 or G1
  { relRow: 3, col: 1, type: 'strong' as const },    // D1 or H1
  { relRow: 0, col: 12, type: 'dmso' as const },     // A12 or E12
  { relRow: 1, col: 12, type: 'dmso' as const },     // B12 or F12
  { relRow: 2, col: 12, type: 'reference' as const }, // C12 or G12
  { relRow: 3, col: 12, type: 'reference' as const }, // D12 or H12
];

// Treatment compounds and doses
const COMPOUNDS = [
  'tBHQ',
  'H2O2',
  'tunicamycin',
  'thapsigargin',
  'CCCP',
  'oligomycin',
  'etoposide',
  'MG132',
  'nocodazole',
  'paclitaxel',
];

const DOSES = ['0.1', '1', '10', '100']; // µM

// Sentinel compound/dose mappings
const SENTINEL_COMPOUNDS = {
  mild: { compound: 'tBHQ', dose: '1' },
  strong: { compound: 'tBHQ', dose: '100' },
  dmso: { compound: 'DMSO', dose: '0' },
  reference: { compound: 'DMSO', dose: '0' },
};

/**
 * Seeded random number generator (LCG)
 * Simple linear congruential generator for reproducible randomness
 */
class SeededRandom {
  private seed: number;

  constructor(seed: number) {
    this.seed = seed;
  }

  next(): number {
    this.seed = (this.seed * 1664525 + 1013904223) % 2 ** 32;
    return this.seed / 2 ** 32;
  }

  shuffle<T>(array: T[]): T[] {
    const shuffled = [...array];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(this.next() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
  }
}

/**
 * Generate a single template layout
 */
export function generateTemplate(seed: number, templateName: string): Well[] {
  const wells: Well[] = [];
  const rng = new SeededRandom(seed);

  // Helper to create well ID
  const createWellId = (row: string, col: number): string => {
    return `${row}${col.toString().padStart(2, '0')}`;
  };

  // Process each cell line block
  const cellLineBlocks = [
    { cellLine: CELL_LINE_1, rows: CELL_LINE_1_ROWS },
    { cellLine: CELL_LINE_2, rows: CELL_LINE_2_ROWS },
  ];

  cellLineBlocks.forEach(({ cellLine, rows }) => {
    // Step 1: Add fixed sentinel wells
    SENTINEL_PATTERN.forEach((pattern) => {
      const row = rows[pattern.relRow];
      const col = pattern.col;
      const sentinelInfo = SENTINEL_COMPOUNDS[pattern.type];

      wells.push({
        row,
        col,
        wellId: createWellId(row, col),
        cellLine,
        type: pattern.type === 'dmso' || pattern.type === 'reference' ? 'dmso' : 'sentinel',
        compound: sentinelInfo.compound,
        dose: sentinelInfo.dose,
        sentinelType: pattern.type,
      });
    });

    // Step 2: Get available positions (all except sentinels)
    const sentinelPositions = new Set(
      SENTINEL_PATTERN.map((p) => `${rows[p.relRow]}_${p.col}`)
    );

    const availablePositions: { row: string; col: number }[] = [];
    rows.forEach((row) => {
      COLS.forEach((col) => {
        if (!sentinelPositions.has(`${row}_${col}`)) {
          availablePositions.push({ row, col });
        }
      });
    });

    // Step 3: Create treatment conditions (10 compounds × 4 doses = 40)
    const treatmentConditions: { compound: string; dose: string }[] = [];
    COMPOUNDS.forEach((compound) => {
      DOSES.forEach((dose) => {
        treatmentConditions.push({ compound, dose });
      });
    });

    // Step 4: Shuffle positions using seeded RNG
    const shuffledPositions = rng.shuffle(availablePositions);

    // Step 5: Assign treatments to positions
    treatmentConditions.forEach((condition, idx) => {
      if (idx < shuffledPositions.length) {
        const pos = shuffledPositions[idx];
        wells.push({
          row: pos.row,
          col: pos.col,
          wellId: createWellId(pos.row, pos.col),
          cellLine,
          type: 'experimental',
          compound: condition.compound,
          dose: condition.dose,
        });
      }
    });
  });

  // Sort by row then column for easier inspection
  wells.sort((a, b) => {
    const rowCompare = ROWS.indexOf(a.row) - ROWS.indexOf(b.row);
    if (rowCompare !== 0) return rowCompare;
    return a.col - b.col;
  });

  return wells;
}

/**
 * Generate both templates with fixed seeds
 */
export const TEMPLATE_SEEDS = {
  A: 12345,
  B: 67890,
};

export const TEMPLATE_A = generateTemplate(TEMPLATE_SEEDS.A, 'A');
export const TEMPLATE_B = generateTemplate(TEMPLATE_SEEDS.B, 'B');
