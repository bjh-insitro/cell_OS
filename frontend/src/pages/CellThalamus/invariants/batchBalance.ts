/**
 * Invariant: Batch Balance
 *
 * For Phase 0 founder (max identifiability), experimental design must be orthogonal to batch structure.
 * This prevents confounding: cannot separate compound effect from batch effect if they're correlated.
 *
 * Three levels of checks:
 * 1. Marginal balance: Each batch factor level has equal well counts (necessary but not sufficient)
 * 2. Condition independence: Each condition distributed uniformly across batches (catches confounding)
 * 3. Chi-square test + Cramér's V: Statistical test with effect size (gated on sparse tables)
 *
 * Sharp edges addressed:
 * - Dose canonicalization to avoid float comparison traps
 * - Sparse table detection for chi-square
 * - Effect size (Cramér's V) to avoid p-value theater
 * - Per-plate checking to catch local confounding
 * - Small count tolerance: max(1 well, 10% of expected)
 */

import type { Well, Violation } from './types';

export type FactorPolicy =
  | 'orthogonal'  // Must be independent of conditions (day, operator, timepoint)
  | 'separate'    // Must be constant within plate (cell_line)
  | 'ignore';     // No balance checks (plate_id)

export interface BatchInvariantConfig {
  // Batch factors to check (e.g., day, operator, timepoint)
  batchFactors: Array<{
    name: string;
    extractor: (w: Well) => string | number | undefined;
    policy: FactorPolicy;
  }>;

  // Condition definition (what defines a unique experimental condition)
  // CRITICAL: Must canonicalize dose to avoid float comparison traps
  conditionKey: (w: Well) => string;

  // Tolerance for marginal balance (wells per level)
  marginalBalanceTolerance: number;

  // Tolerance for condition distribution across batches (proportion deviation)
  conditionDistributionTolerance: number;

  // Whether to run chi-square test
  runChiSquareTest: boolean;

  // Significance level for chi-square test
  chiSquareAlpha: number;

  // Minimum expected count for chi-square (gating sparse tables)
  chiSquareMinExpected: number;

  // Cramér's V threshold for "large" effect size
  cramersVThreshold: number;

  // Whether to check per-plate (stronger, catches local confounding)
  checkPerPlate: boolean;
}

/**
 * Canonicalize dose to avoid float comparison traps
 * ONE THROAT TO CHOKE: all dose comparisons go through here
 */
function canonicalizeDose(dose_uM: number | undefined): string {
  if (dose_uM === undefined || dose_uM === null) return 'UNKNOWN';
  // Round to 6 decimal places to avoid float formatting differences
  return dose_uM.toFixed(6);
}

/**
 * Phase0_v2 batch balance configuration
 *
 * Batch structure: day × operator × timepoint × cell_line
 * - Days: 1, 2 (2 biological replicates)
 * - Operators: Operator_A, Operator_B (2 technical operators)
 * - Timepoints: 12.0h, 24.0h, 48.0h (3 kinetic samples)
 * - Cell lines: A549, HepG2 (2 cell lines)
 *
 * Each condition should appear uniformly across batch levels.
 */
export const PHASE0_V2_BATCH_CONFIG: BatchInvariantConfig = {
  batchFactors: [
    { name: 'day', extractor: (w) => w.day, policy: 'orthogonal' },
    { name: 'operator', extractor: (w) => w.operator, policy: 'orthogonal' },
    { name: 'timepoint', extractor: (w) => w.timepoint_h, policy: 'orthogonal' },
    { name: 'cell_line', extractor: (w) => w.cell_line, policy: 'separate' },
  ],
  // Condition = compound + dose (ignore replicates for this check)
  // CRITICAL: Canonicalize dose to avoid float comparison traps
  conditionKey: (w) => `${w.compound}@${canonicalizeDose(w.dose_uM)}uM`,
  marginalBalanceTolerance: 1, // ±1 well deviation per level
  conditionDistributionTolerance: 0.1, // Max 10% deviation from uniform
  runChiSquareTest: true,
  chiSquareAlpha: 0.05,
  chiSquareMinExpected: 5, // Gate chi-square on sparse tables (≥80% cells ≥ 5)
  cramersVThreshold: 0.3, // Cramér's V > 0.3 = "large" effect size
  checkPerPlate: true, // Check independence within each plate (catches local confounding)
};

export function inv_batchBalance(
  wells: Well[],
  cfg: BatchInvariantConfig
): Violation[] {
  const violations: Violation[] = [];

  // Filter to experimental wells only (sentinels don't participate in batch balance)
  const expWells = wells.filter((w) => !w.is_sentinel);

  if (expWells.length === 0) {
    return violations; // No experimental wells to check
  }

  // Separate factors by policy
  const orthogonalFactors = cfg.batchFactors.filter((f) => f.policy === 'orthogonal');
  const separateFactors = cfg.batchFactors.filter((f) => f.policy === 'separate');

  // Check 1: Marginal balance per batch factor (globally, orthogonal only)
  for (const factor of orthogonalFactors) {
    const marginalViolations = checkMarginalBalance(
      expWells,
      factor,
      cfg.marginalBalanceTolerance
    );
    violations.push(...marginalViolations);
  }

  // Check 2: Condition × batch independence (globally, orthogonal only)
  const conditions = [...new Set(expWells.map(cfg.conditionKey))].filter(
    (c) => c && !c.includes('undefined') && !c.includes('UNKNOWN')
  );

  for (const factor of orthogonalFactors) {
    for (const condition of conditions) {
      const conditionWells = expWells.filter((w) => cfg.conditionKey(w) === condition);
      const distViolations = checkConditionDistribution(
        conditionWells,
        condition,
        factor,
        cfg.conditionDistributionTolerance,
        'global'
      );
      violations.push(...distViolations);
    }
  }

  // Check 3: Chi-square test for independence (globally, orthogonal only)
  if (cfg.runChiSquareTest) {
    for (const factor of orthogonalFactors) {
      const chiViolations = checkChiSquareIndependence(
        expWells,
        cfg.conditionKey,
        factor,
        cfg.chiSquareAlpha,
        cfg.chiSquareMinExpected,
        cfg.cramersVThreshold,
        'global'
      );
      violations.push(...chiViolations);
    }
  }

  // Check 4: Separate factors must be constant within plate
  for (const factor of separateFactors) {
    const separateViolations = checkSeparateFactorConstancy(
      expWells,
      factor
    );
    violations.push(...separateViolations);
  }

  // Check 5: Per-plate independence (stronger, catches local confounding, orthogonal only)
  if (cfg.checkPerPlate) {
    const wellsByPlate = groupBy(expWells, (w) => w.plate_id);

    for (const [plateId, plateWells] of Object.entries(wellsByPlate)) {
      const plateConditions = [...new Set(plateWells.map(cfg.conditionKey))].filter(
        (c) => c && !c.includes('undefined') && !c.includes('UNKNOWN')
      );

      for (const factor of orthogonalFactors) {
        for (const condition of plateConditions) {
          const conditionWells = plateWells.filter((w) => cfg.conditionKey(w) === condition);
          const distViolations = checkConditionDistribution(
            conditionWells,
            condition,
            factor,
            cfg.conditionDistributionTolerance,
            `plate ${plateId}`
          );
          violations.push(...distViolations);
        }
      }
    }
  }

  return violations;
}

/* ============ Check 1: Marginal Balance ============ */

function checkMarginalBalance(
  wells: Well[],
  factor: { name: string; extractor: (w: Well) => string | number | undefined },
  tolerance: number
): Violation[] {
  const violations: Violation[] = [];

  // Count wells per level
  const countsPerLevel = new Map<string, number>();
  for (const w of wells) {
    const level = String(factor.extractor(w) ?? 'UNKNOWN');
    countsPerLevel.set(level, (countsPerLevel.get(level) ?? 0) + 1);
  }

  const levels = [...countsPerLevel.keys()].filter((l) => l !== 'UNKNOWN');
  if (levels.length === 0) {
    return violations;
  }

  const expected = wells.length / levels.length;

  for (const [level, actual] of countsPerLevel.entries()) {
    if (level === 'UNKNOWN') continue;

    const deviation = Math.abs(actual - expected);
    if (deviation > tolerance) {
      violations.push({
        type: 'batch_marginal_imbalance',
        severity: 'error',
        message: `Batch factor '${factor.name}' level '${level}': ${actual} wells (expected ${expected.toFixed(1)}, deviation ${deviation.toFixed(1)} > tolerance ${tolerance}). [Note: Marginal balance is necessary but not sufficient - you can be marginally balanced and still confounded.]`,
        suggestion: `Allocation must balance wells across batch levels. Check compound/dose assignment logic.`,
        details: {
          factor: factor.name,
          level,
          actual,
          expected: expected.toFixed(1),
          deviation: deviation.toFixed(1),
          tolerance,
        },
      });
    }
  }

  return violations;
}

/* ============ Check 2: Condition Distribution ============ */

function checkConditionDistribution(
  conditionWells: Well[],
  condition: string,
  factor: { name: string; extractor: (w: Well) => string | number | undefined },
  toleranceProportion: number,
  scope: string
): Violation[] {
  const violations: Violation[] = [];

  // Count condition wells per batch level
  const countsPerLevel = new Map<string, number>();
  for (const w of conditionWells) {
    const level = String(factor.extractor(w) ?? 'UNKNOWN');
    countsPerLevel.set(level, (countsPerLevel.get(level) ?? 0) + 1);
  }

  const levels = [...countsPerLevel.keys()].filter((l) => l !== 'UNKNOWN');
  if (levels.length === 0) {
    return violations;
  }

  // Expected proportion: uniform distribution
  const expectedProportion = 1 / levels.length;
  const expectedCount = conditionWells.length / levels.length;

  // Tolerance in counts: max(1 well, toleranceProportion * expected)
  // This makes tolerance behave correctly for small counts
  const toleranceCount = Math.max(1, toleranceProportion * expectedCount);

  // Compute distribution
  const distribution = new Map<string, number>();
  for (const [level, count] of countsPerLevel.entries()) {
    if (level === 'UNKNOWN') continue;
    distribution.set(level, count / conditionWells.length);
  }

  // Check max deviation from uniform (in counts, not just proportion)
  let maxDeviationProportion = 0;
  let maxDeviationCount = 0;
  let worstLevel = '';

  for (const level of levels) {
    const count = countsPerLevel.get(level) ?? 0;
    const proportion = distribution.get(level) ?? 0;
    const deviationProportion = Math.abs(proportion - expectedProportion);
    const deviationCount = Math.abs(count - expectedCount);

    if (deviationCount > maxDeviationCount) {
      maxDeviationCount = deviationCount;
      maxDeviationProportion = deviationProportion;
      worstLevel = level;
    }
  }

  if (maxDeviationCount > toleranceCount) {
    violations.push({
      type: 'batch_condition_confounding',
      severity: 'warning',
      message: `Condition '${condition}' not uniformly distributed across '${factor.name}' (${scope}). Max deviation: ${maxDeviationCount.toFixed(1)} wells (${(maxDeviationProportion * 100).toFixed(1)}%) at level '${worstLevel}' (tolerance ${toleranceCount.toFixed(1)} wells).`,
      suggestion: `Shuffle compound assignment to break correlation with batch factors.`,
      details: {
        condition,
        factor: factor.name,
        scope,
        maxDeviationCount: maxDeviationCount.toFixed(1),
        maxDeviationProportion: maxDeviationProportion.toFixed(3),
        worstLevel,
        distribution: Object.fromEntries(
          [...distribution.entries()].map(([k, v]) => [k, v.toFixed(3)])
        ),
        toleranceCount: toleranceCount.toFixed(1),
        toleranceProportion,
      },
    });
  }

  return violations;
}

/* ============ Check 3: Chi-Square Test + Cramér's V ============ */

function checkChiSquareIndependence(
  wells: Well[],
  conditionKey: (w: Well) => string,
  factor: { name: string; extractor: (w: Well) => string | number | undefined },
  alpha: number,
  minExpected: number,
  cramersVThreshold: number,
  scope: string
): Violation[] {
  const violations: Violation[] = [];

  // Build contingency table: condition × batch level
  const conditions = [...new Set(wells.map(conditionKey))].filter(
    (c) => c && !c.includes('undefined') && !c.includes('UNKNOWN')
  );
  const levels = [
    ...new Set(
      wells.map((w) => String(factor.extractor(w) ?? 'UNKNOWN')).filter((l) => l !== 'UNKNOWN')
    ),
  ];

  if (conditions.length === 0 || levels.length === 0) {
    return violations;
  }

  // Observed counts
  const observed = new Map<string, Map<string, number>>();
  for (const w of wells) {
    const cond = conditionKey(w);
    const level = String(factor.extractor(w) ?? 'UNKNOWN');
    if (!cond || cond.includes('undefined') || cond.includes('UNKNOWN') || level === 'UNKNOWN')
      continue;

    if (!observed.has(cond)) {
      observed.set(cond, new Map());
    }
    const condMap = observed.get(cond)!;
    condMap.set(level, (condMap.get(level) ?? 0) + 1);
  }

  // Compute expected counts under independence
  const rowTotals = new Map<string, number>();
  const colTotals = new Map<string, number>();
  let grandTotal = 0;

  for (const [cond, levelCounts] of observed.entries()) {
    let rowTotal = 0;
    for (const [level, count] of levelCounts.entries()) {
      rowTotal += count;
      colTotals.set(level, (colTotals.get(level) ?? 0) + count);
      grandTotal += count;
    }
    rowTotals.set(cond, rowTotal);
  }

  // Check if table is too sparse for chi-square
  let cellsWithLowExpected = 0;
  let totalCells = 0;

  for (const cond of conditions) {
    const rowTotal = rowTotals.get(cond) ?? 0;
    for (const level of levels) {
      const colTotal = colTotals.get(level) ?? 0;
      const expectedCount = (rowTotal * colTotal) / grandTotal;
      totalCells++;
      if (expectedCount < minExpected) {
        cellsWithLowExpected++;
      }
    }
  }

  const proportionLowExpected = cellsWithLowExpected / totalCells;

  // Gate chi-square: only run if >= 80% of cells have expected ≥ minExpected
  if (proportionLowExpected > 0.2) {
    violations.push({
      type: 'batch_table_too_sparse',
      severity: 'warning',
      message: `Contingency table for '${factor.name}' (${scope}) too sparse for chi-square test: ${cellsWithLowExpected}/${totalCells} cells (${(proportionLowExpected * 100).toFixed(1)}%) have expected count < ${minExpected}. Chi-square may be unreliable. Consider using permutation test or G-test instead.`,
      suggestion: `Increase sample size, reduce number of conditions, or use a more robust test.`,
      details: {
        factor: factor.name,
        scope,
        totalCells,
        cellsWithLowExpected,
        proportionLowExpected: proportionLowExpected.toFixed(3),
        minExpected,
      },
    });
    // Don't run chi-square on sparse tables
    return violations;
  }

  // Chi-square statistic: sum((O - E)^2 / E)
  let chiSquare = 0;
  for (const [cond, levelCounts] of observed.entries()) {
    const rowTotal = rowTotals.get(cond)!;
    for (const level of levels) {
      const observedCount = levelCounts.get(level) ?? 0;
      const colTotal = colTotals.get(level) ?? 0;
      const expectedCount = (rowTotal * colTotal) / grandTotal;

      if (expectedCount > 0) {
        chiSquare += Math.pow(observedCount - expectedCount, 2) / expectedCount;
      }
    }
  }

  // Degrees of freedom
  const dof = (conditions.length - 1) * (levels.length - 1);

  // Approximate p-value using chi-square CDF
  const pValue = approxChiSquarePValue(chiSquare, dof);

  // Cramér's V (effect size)
  // V = sqrt(χ² / (n * min(r-1, c-1)))
  const minDim = Math.min(conditions.length - 1, levels.length - 1);
  const cramersV = Math.sqrt(chiSquare / (grandTotal * minDim));

  if (pValue < alpha) {
    const effectSizeLabel =
      cramersV < 0.1 ? 'negligible' : cramersV < 0.3 ? 'small' : cramersV < 0.5 ? 'medium' : 'large';

    violations.push({
      type: 'batch_condition_dependence',
      severity: 'warning',
      message: `Conditions not independent of batch factor '${factor.name}' (${scope}): χ²=${chiSquare.toFixed(2)}, df=${dof}, p=${pValue.toFixed(4)} < α=${alpha}. Effect size: Cramér's V=${cramersV.toFixed(3)} (${effectSizeLabel}).`,
      suggestion:
        cramersV > cramersVThreshold
          ? `Large effect size detected (V=${cramersV.toFixed(3)} > ${cramersVThreshold}). This is not just statistically significant but practically important. Review compound assignment algorithm to ensure orthogonality with batch structure.`
          : `Statistically significant but small effect size (V=${cramersV.toFixed(3)}). May be acceptable for pilot studies, but Phase 0 founder should aim for independence.`,
      details: {
        factor: factor.name,
        scope,
        chiSquare: chiSquare.toFixed(2),
        dof,
        pValue: pValue.toFixed(4),
        alpha,
        cramersV: cramersV.toFixed(3),
        effectSize: effectSizeLabel,
        cramersVThreshold,
      },
    });
  }

  return violations;
}

/* ============ Check 4: Separate Factor Constancy ============ */

function checkSeparateFactorConstancy(
  wells: Well[],
  factor: { name: string; extractor: (w: Well) => string | number | undefined; policy: FactorPolicy }
): Violation[] {
  const violations: Violation[] = [];

  // Group wells by plate
  const wellsByPlate = groupBy(wells, (w) => w.plate_id);

  for (const [plateId, plateWells] of Object.entries(wellsByPlate)) {
    // Get unique values for this factor on this plate
    const factorValues = new Set(
      plateWells.map((w) => String(factor.extractor(w) ?? 'UNKNOWN')).filter((v) => v !== 'UNKNOWN')
    );

    // Should have exactly ONE value per plate (constant within plate)
    if (factorValues.size > 1) {
      violations.push({
        type: 'batch_separate_factor_violation',
        severity: 'error',
        message: `Batch factor '${factor.name}' has policy 'separate' but varies within plate '${plateId}': found ${factorValues.size} distinct values [${[...factorValues].join(', ')}]. Expected constant within plate (e.g., one cell line per plate).`,
        suggestion: `Ensure '${factor.name}' is constant within each plate. This is typically enforced during allocation by creating separate plates per ${factor.name} level.`,
        details: {
          factor: factor.name,
          policy: factor.policy,
          plateId,
          valuesFound: [...factorValues],
          countFound: factorValues.size,
          expected: 1,
        },
      });
    }
  }

  return violations;
}

/**
 * Approximate chi-square p-value using incomplete gamma function approximation
 * For production use, replace with proper stats library (jstat, simple-statistics, etc.)
 */
function approxChiSquarePValue(chiSquare: number, dof: number): number {
  // Quick approximation using Wilson-Hilferty transformation
  // χ² ~ N(dof, 2*dof) for large dof
  if (dof < 1) return 1;

  const mean = dof;
  const stddev = Math.sqrt(2 * dof);
  const z = (chiSquare - mean) / stddev;

  // Standard normal CDF approximation (one-tailed)
  return 1 - standardNormalCDF(z);
}

function standardNormalCDF(z: number): number {
  // Approximation using error function
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989423 * Math.exp((-z * z) / 2);
  const prob =
    d *
    t *
    (0.3193815 +
      t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));

  return z > 0 ? 1 - prob : prob;
}

/* ============ Helpers ============ */

function groupBy<T>(items: T[], keyFn: (t: T) => string): Record<string, T[]> {
  const out: Record<string, T[]> = {};
  for (const it of items) {
    const k = keyFn(it);
    (out[k] ??= []).push(it);
  }
  return out;
}
