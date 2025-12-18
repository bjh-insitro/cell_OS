/**
 * Input parsing utilities - consistent handling of comma-separated values
 */

/**
 * Parse comma-separated numbers (floats)
 * Filters out NaN, Infinity, and empty strings
 */
export function parseNumberList(input: string): number[] {
  return input
    .split(',')
    .map(s => parseFloat(s.trim()))
    .filter(x => Number.isFinite(x));
}

/**
 * Parse comma-separated integers
 * Filters out NaN, Infinity, and empty strings
 */
export function parseIntList(input: string): number[] {
  return input
    .split(',')
    .map(s => parseInt(s.trim(), 10))
    .filter(x => Number.isFinite(x));
}

/**
 * Parse comma-separated strings
 * Filters out empty strings and trims whitespace
 */
export function parseStringList(input: string): string[] {
  return input
    .split(',')
    .map(s => s.trim())
    .filter(Boolean);
}

/**
 * Normalize string for comparison (trim, lowercase, collapse whitespace)
 */
export function normalizeString(input: string): string {
  return input.trim().toLowerCase().replace(/\s+/g, ' ');
}

/**
 * Compare two comma-separated lists for equality (order-independent)
 */
export function compareStringLists(a: string, b: string): boolean {
  const listA = parseStringList(a).sort();
  const listB = parseStringList(b).sort();
  return listA.length === listB.length && listA.every((val, idx) => val === listB[idx]);
}
