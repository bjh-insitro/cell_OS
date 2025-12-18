/**
 * Well positioning utilities - single source of truth for available wells
 */

export interface WellExclusions {
  excludeCorners: boolean;
  excludeMidRowWells: boolean;
  excludeEdges: boolean;
}

/**
 * Compute all available well positions for a given plate format and exclusions
 * Returns an array of well position strings (e.g., ["A01", "A02", ...])
 */
export function computeAvailableWellPositions(
  plateFormat: 96 | 384,
  exclusions: WellExclusions
): string[] {
  const nRows = plateFormat === 96 ? 8 : 16;
  const nCols = plateFormat === 96 ? 12 : 24;
  const rowLabels = Array.from({ length: nRows }, (_, i) => String.fromCharCode(65 + i));

  const excludedWells = new Set<string>();

  if (exclusions.excludeEdges) {
    // Edge exclusion supersedes all others
    // Exclude all wells in first/last row and first/last column
    for (const row of [rowLabels[0], rowLabels[nRows - 1]]) {
      for (let col = 1; col <= nCols; col++) {
        excludedWells.add(`${row}${String(col).padStart(2, '0')}`);
      }
    }
    for (const col of [1, nCols]) {
      for (const row of rowLabels) {
        excludedWells.add(`${row}${String(col).padStart(2, '0')}`);
      }
    }
  } else {
    // Apply corner and mid-row exclusions only if edges aren't excluded
    if (exclusions.excludeCorners) {
      // 4 corner wells
      excludedWells.add(`${rowLabels[0]}${String(1).padStart(2, '0')}`); // Top-left
      excludedWells.add(`${rowLabels[0]}${String(nCols).padStart(2, '0')}`); // Top-right
      excludedWells.add(`${rowLabels[nRows - 1]}${String(1).padStart(2, '0')}`); // Bottom-left
      excludedWells.add(`${rowLabels[nRows - 1]}${String(nCols).padStart(2, '0')}`); // Bottom-right
    }

    if (exclusions.excludeMidRowWells && plateFormat === 96) {
      // 4 mid-row wells (phase0_v2 pattern) - only for 96-well
      excludedWells.add(`${rowLabels[0]}${String(6).padStart(2, '0')}`); // A6
      excludedWells.add(`${rowLabels[0]}${String(7).padStart(2, '0')}`); // A7
      excludedWells.add(`${rowLabels[nRows - 1]}${String(6).padStart(2, '0')}`); // H6
      excludedWells.add(`${rowLabels[nRows - 1]}${String(7).padStart(2, '0')}`); // H7
    }
  }

  // Generate all positions and filter out excluded ones
  const availableWells: string[] = [];
  for (const row of rowLabels) {
    for (let col = 1; col <= nCols; col++) {
      const pos = `${row}${String(col).padStart(2, '0')}`;
      if (!excludedWells.has(pos)) {
        availableWells.push(pos);
      }
    }
  }

  return availableWells;
}

/**
 * Get the count of available wells (convenience wrapper)
 */
export function getAvailableWellCount(
  plateFormat: 96 | 384,
  exclusions: WellExclusions
): number {
  return computeAvailableWellPositions(plateFormat, exclusions).length;
}
