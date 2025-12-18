/**
 * Validate Phase0_v2 Founder Design
 *
 * Fetch the actual phase0_v2 design from catalog and run all invariants.
 * Treat output as calibration report - founder should be our zero point.
 */

import { checkPhase0V2Design } from './index';
import type { Well, DesignCertificate } from './types';

/**
 * Fetch phase0_v2 design from catalog API
 */
async function fetchPhase0V2Design(): Promise<Well[]> {
  const response = await fetch(
    '/api/thalamus/catalog/designs/phase0_founder_v2_controls_stratified'
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch design: ${response.statusText}`);
  }

  const data = await response.json();

  // Extract wells from response
  // Adjust this based on actual API response structure
  return data.design_data?.wells ?? data.wells ?? [];
}

/**
 * Format violation for console output
 */
function formatViolation(v: any): string {
  const severityLabel = v.severity === 'error' ? '❌ ERROR' : '⚠️  WARNING';
  const lines = [
    `${severityLabel}: ${v.type}`,
    `  Message: ${v.message}`,
  ];

  if (v.suggestion) {
    lines.push(`  Suggestion: ${v.suggestion}`);
  }

  if (v.details) {
    lines.push(`  Details: ${JSON.stringify(v.details, null, 2)}`);
  }

  return lines.join('\n');
}

/**
 * Format certificate as calibration report
 */
function formatCalibrationReport(certificate: DesignCertificate): string {
  const lines = [
    '═══════════════════════════════════════════════════════════════',
    '  PHASE 0 FOUNDER CALIBRATION REPORT',
    '═══════════════════════════════════════════════════════════════',
    '',
    '## Design Stats',
    `  Total wells: ${certificate.stats.totalWells}`,
    `  Sentinel wells: ${certificate.stats.sentinelWells} (${((certificate.stats.sentinelWells / certificate.stats.totalWells) * 100).toFixed(1)}%)`,
    `  Experimental wells: ${certificate.stats.experimentalWells} (${((certificate.stats.experimentalWells / certificate.stats.totalWells) * 100).toFixed(1)}%)`,
    `  Plates: ${certificate.stats.nPlates}`,
    `  Plate format: ${certificate.plateFormat}-well`,
    '',
    `## Invariants Version: ${certificate.invariantsVersion}`,
    `## Timestamp: ${certificate.timestamp}`,
    `## Params Hash: ${certificate.paramsHash}`,
    '',
  ];

  // Group violations by severity
  const errors = certificate.violations.filter((v) => v.severity === 'error');
  const warnings = certificate.violations.filter((v) => v.severity === 'warning');

  lines.push('## Violations Summary');
  lines.push(`  Errors: ${errors.length}`);
  lines.push(`  Warnings: ${warnings.length}`);
  lines.push('');

  if (errors.length === 0 && warnings.length === 0) {
    lines.push('✅ CLEAN PASS - Founder design satisfies all invariants');
    lines.push('');
    lines.push('Interpretation:');
    lines.push('  • Thresholds are aligned with reality');
    lines.push('  • Founder is the zero point for comparison');
    lines.push('  • Future designs should match or exceed this quality');
    lines.push('');
  } else {
    if (errors.length > 0) {
      lines.push('❌ ERRORS DETECTED - Likely allocation or labeling bug');
      lines.push('');
      lines.push('## Errors:');
      lines.push('');
      errors.forEach((v) => {
        lines.push(formatViolation(v));
        lines.push('');
      });
    }

    if (warnings.length > 0) {
      lines.push('⚠️  WARNINGS DETECTED - Review and decide');
      lines.push('');
      lines.push('Interpretation:');
      lines.push('  • Either founder is imperfect (possible), OR');
      lines.push('  • Invariant encodes policy founder never satisfied (also possible)');
      lines.push('');
      lines.push('## Warnings:');
      lines.push('');
      warnings.forEach((v) => {
        lines.push(formatViolation(v));
        lines.push('');
      });
    }
  }

  lines.push('═══════════════════════════════════════════════════════════════');

  return lines.join('\n');
}

/**
 * Main validation function
 */
export async function validateFounderDesign(): Promise<void> {
  console.log('Fetching Phase0_v2 founder design...');

  try {
    const wells = await fetchPhase0V2Design();

    console.log(`Loaded ${wells.length} wells`);
    console.log('Running invariant checks...');

    const certificate = checkPhase0V2Design(wells);

    const report = formatCalibrationReport(certificate);
    console.log(report);

    // Return certificate for programmatic use
    return certificate as any;
  } catch (error) {
    console.error('Failed to validate founder design:', error);
    throw error;
  }
}

/**
 * Derive thresholds from founder (for sanity checking)
 */
export function deriveFounderThresholds(wells: Well[]): FounderThresholds {
  // TODO: Implement threshold derivation
  // This should compute actual metrics from founder design:
  // - Max per-plate deviation observed
  // - Max Cramér's V observed (global and per-plate)
  // - Percent sparse-table hits
  //
  // Then recommend:
  // - "Warn if worse than founder + margin"
  // - "Error if grossly worse than founder"

  return {
    marginalBalance: {
      observed: [],
      recommended: 0,
    },
    cramersV: {
      observedGlobal: [],
      observedPerPlate: [],
      recommended: 0,
    },
    sparseTableRate: {
      observed: 0,
      acceptable: 0.2,
    },
  };
}

interface FounderThresholds {
  marginalBalance: {
    observed: number[];
    recommended: number;
  };
  cramersV: {
    observedGlobal: number[];
    observedPerPlate: number[];
    recommended: number;
  };
  sparseTableRate: {
    observed: number;
    acceptable: number;
  };
}
