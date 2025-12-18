/**
 * Mock Founder Validation Test
 *
 * Simulates running invariants on phase0_v2 founder design
 * to demonstrate certificate output format.
 */

import { describe, it } from '@jest/globals';
import { checkPhase0V2Design } from '../index';
import type { Well } from '../types';

describe('Founder Validation - Mock Phase0_v2', () => {
  /**
   * Create a realistic mock of phase0_v2 design
   *
   * Structure:
   * - 24 plates: 2 days × 2 operators × 3 timepoints × 2 cell lines
   * - 88 wells per plate (96-well with 8 excluded)
   * - 28 sentinels per plate (DMSO×8, tBHQ×5, thapsigargin×5, oligomycin×5, MG132×5)
   * - 60 experimental wells per plate (5 compounds × 6 doses × 2 replicates)
   */
  function createMockFounderDesign(): Well[] {
    const wells: Well[] = [];

    const days = [1, 2];
    const operators = ['Operator_A', 'Operator_B'];
    const timepoints = [12.0, 24.0, 48.0];
    const cellLines = ['A549', 'HepG2'];

    const compounds = ['tBHQ', 'H2O2', 'tunicamycin', 'thapsigargin', 'CCCP'];
    const doses = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0];
    const sentinelTypes = [
      ...Array(8).fill('DMSO'),
      ...Array(5).fill('tBHQ'),
      ...Array(5).fill('thapsigargin'),
      ...Array(5).fill('oligomycin'),
      ...Array(5).fill('MG132'),
    ];

    let wellIdx = 0;

    for (const cellLine of cellLines) {
      for (const day of days) {
        for (const operator of operators) {
          for (const timepoint of timepoints) {
            const plateId = `${cellLine}_Day${day}_${operator}_T${timepoint}h`;

            // Add sentinels (interspersed)
            for (let i = 0; i < sentinelTypes.length; i++) {
              wells.push({
                plate_id: plateId,
                well_pos: `W${wellIdx++}`,
                cell_line: cellLine,
                compound: sentinelTypes[i],
                dose_uM: 0,
                is_sentinel: true,
                sentinel_type: sentinelTypes[i],
                day,
                operator,
                timepoint_h: timepoint,
              });
            }

            // Add experimental wells (balanced across batch factors)
            for (const compound of compounds) {
              for (const dose of doses) {
                for (let rep = 0; rep < 2; rep++) {
                  wells.push({
                    plate_id: plateId,
                    well_pos: `W${wellIdx++}`,
                    cell_line: cellLine,
                    compound,
                    dose_uM: dose,
                    is_sentinel: false,
                    day,
                    operator,
                    timepoint_h: timepoint,
                  });
                }
              }
            }
          }
        }
      }
    }

    return wells;
  }

  it('should generate calibration report for mock founder design', () => {
    const wells = createMockFounderDesign();

    console.log(`\nCreated mock design with ${wells.length} wells\n`);

    const certificate = checkPhase0V2Design(wells);

    // Format as calibration report
    const lines = [
      '═══════════════════════════════════════════════════════════════',
      '  PHASE 0 FOUNDER CALIBRATION REPORT (MOCK)',
      '═══════════════════════════════════════════════════════════════',
      '',
      '## Design Stats',
      `  Total wells: ${certificate.stats.totalWells}`,
      `  Sentinel wells: ${certificate.stats.sentinelWells} (${((certificate.stats.sentinelWells / certificate.stats.totalWells) * 100).toFixed(1)}%)`,
      `  Experimental wells: ${certificate.stats.experimentalWells} (${((certificate.stats.experimentalWells / certificate.stats.totalWells) * 100).toFixed(1)}%)`,
      `  Plates: ${certificate.stats.nPlates}`,
      '',
    ];

    // Group violations by type
    const violationsByType = new Map<string, any[]>();
    for (const v of certificate.violations) {
      const existing = violationsByType.get(v.type) ?? [];
      existing.push(v);
      violationsByType.set(v.type, existing);
    }

    lines.push('## Violations by Type');
    lines.push(`  Total: ${certificate.violations.length}`);
    lines.push('');

    if (certificate.violations.length === 0) {
      lines.push('✅ CLEAN PASS - Mock founder satisfies all invariants');
    } else {
      for (const [type, violations] of violationsByType.entries()) {
        const severity = violations[0].severity;
        const symbol = severity === 'error' ? '❌' : '⚠️ ';
        lines.push(`${symbol} ${type}: ${violations.length}`);

        // Show first violation as example
        if (violations.length > 0) {
          lines.push(`  Example: ${violations[0].message.substring(0, 120)}...`);
        }
        lines.push('');
      }
    }

    lines.push('═══════════════════════════════════════════════════════════════');

    const report = lines.join('\n');
    console.log(report);

    // Log first few violations for inspection
    if (certificate.violations.length > 0) {
      console.log('\n## First 3 Violations (detailed):');
      certificate.violations.slice(0, 3).forEach((v, i) => {
        console.log(`\n${i + 1}. ${v.type} (${v.severity})`);
        console.log(`   Message: ${v.message}`);
        if (v.suggestion) {
          console.log(`   Suggestion: ${v.suggestion}`);
        }
        if (v.details) {
          console.log(`   Details:`, JSON.stringify(v.details, null, 2));
        }
      });
    }
  });

  it('should show what a confounded design looks like', () => {
    // Create adversarial design: globally balanced but confounded
    const wells: Well[] = [];

    const compounds = ['tBHQ', 'H2O2'];
    const doses = [1.0, 10.0];

    let wellIdx = 0;

    // Day 1: Only tBHQ (confounded)
    for (const dose of doses) {
      for (let rep = 0; rep < 10; rep++) {
        wells.push({
          plate_id: 'plate1',
          well_pos: `W${wellIdx++}`,
          cell_line: 'A549',
          compound: 'tBHQ',
          dose_uM: dose,
          is_sentinel: false,
          day: 1,
          operator: 'Operator_A',
          timepoint_h: 12.0,
        });
      }
    }

    // Day 2: Only H2O2 (confounded)
    for (const dose of doses) {
      for (let rep = 0; rep < 10; rep++) {
        wells.push({
          plate_id: 'plate2',
          well_pos: `W${wellIdx++}`,
          cell_line: 'A549',
          compound: 'H2O2',
          dose_uM: dose,
          is_sentinel: false,
          day: 2,
          operator: 'Operator_A',
          timepoint_h: 12.0,
        });
      }
    }

    const certificate = checkPhase0V2Design(wells);

    console.log('\n═══ ADVERSARIAL DESIGN: Perfect Marginal, Total Confounding ═══\n');
    console.log(`Total violations: ${certificate.violations.length}\n`);

    // Show batch confounding violations
    const confoundingViolations = certificate.violations.filter(
      (v) => v.type === 'batch_condition_confounding'
    );

    if (confoundingViolations.length > 0) {
      console.log('Confounding detected:');
      confoundingViolations.forEach((v) => {
        console.log(`  • ${v.message}`);
      });
    }

    // Show chi-square violations
    const chiSquareViolations = certificate.violations.filter(
      (v) => v.type === 'batch_condition_dependence'
    );

    if (chiSquareViolations.length > 0) {
      console.log('\nChi-square test results:');
      chiSquareViolations.forEach((v) => {
        console.log(`  • ${v.message}`);
        console.log(`    Cramér's V: ${v.details?.cramersV} (${v.details?.effectSize})`);
      });
    }
  });
});
