/**
 * Run batch balance invariants on actual Phase0_v2 founder design
 *
 * Usage: npx tsx validateFounderDesign.ts
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { checkPhase0V2Design } from './src/pages/CellThalamus/invariants/index';
import type { Well, DesignCertificate, Violation } from './src/pages/CellThalamus/invariants/types';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load Phase0_v2 design from JSON
function loadFounderDesign(useRegenerated: boolean = false): { wells: Well[]; metadata: any } {
  const filename = useRegenerated
    ? 'phase0_founder_v2_regenerated.json'
    : 'phase0_design_v2_controls_stratified.json';
  const designPath = path.join(__dirname, '../data/designs', filename);
  const designData = JSON.parse(fs.readFileSync(designPath, 'utf-8'));
  return {
    wells: designData.wells,
    metadata: designData.metadata,
  };
}

// Format violation for console output
function formatViolation(v: Violation, index: number): string {
  const severitySymbol = v.severity === 'error' ? '❌' : '⚠️ ';
  const lines = [
    `${index}. ${severitySymbol} ${v.type} (${v.severity})`,
    `   Message: ${v.message}`,
  ];

  if (v.suggestion) {
    lines.push(`   Suggestion: ${v.suggestion}`);
  }

  if (v.plateId) {
    lines.push(`   Plate: ${v.plateId}`);
  }

  if (v.details) {
    const detailsStr = JSON.stringify(v.details, null, 2)
      .split('\n')
      .map((line, i) => (i === 0 ? line : `     ${line}`))
      .join('\n');
    lines.push(`   Details: ${detailsStr}`);
  }

  return lines.join('\n');
}

// Format certificate as calibration report
function formatCalibrationReport(certificate: DesignCertificate, metadata?: any): string {
  const lines = [
    '',
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

  // Add scaffold verification if present
  if (certificate.scaffoldMetadata) {
    lines.push('## Scaffold Verification');
    lines.push(`  Expected ID: ${certificate.scaffoldMetadata.expected.scaffoldId}`);
    lines.push(`  Expected Hash: ${certificate.scaffoldMetadata.expected.scaffoldHash}`);

    if (certificate.scaffoldMetadata.observed) {
      const obs = certificate.scaffoldMetadata.observed;
      const idMatch = obs.scaffoldId === certificate.scaffoldMetadata.expected.scaffoldId;
      const hashMatch = obs.scaffoldHash === certificate.scaffoldMetadata.expected.scaffoldHash;

      lines.push('');
      lines.push(`  Observed ID: ${obs.scaffoldId ?? 'missing'} ${idMatch ? '✓' : '✗'}`);
      lines.push(`  Observed Hash: ${obs.scaffoldHash ?? 'missing'} ${hashMatch ? '✓' : '✗'}`);

      if (obs.wellDerivedHash) {
        const wellMatch = obs.wellDerivedMatchesExpected;
        const matchSymbol = wellMatch ? '✓ MATCH' : '✗ MISMATCH';
        lines.push(`  Well-derived Hash: ${obs.wellDerivedHash} ${matchSymbol}`);
        if (!wellMatch) {
          lines.push(`    ⚠️  Expected: ${certificate.scaffoldMetadata.expected.scaffoldHash}`);
          lines.push(`    ⚠️  This indicates wells contain incorrect sentinel data`);
        }
      }
    }

    lines.push('');
  }

  // Add policy verification from metadata
  if (metadata?.sentinel_schema) {
    lines.push('## Sentinel Schema');
    lines.push(`  Policy: ${metadata.sentinel_schema.policy ?? 'missing'}`);
    if (metadata.sentinel_schema.scaffold_metadata?.scaffold_version) {
      lines.push(`  Scaffold Version: ${metadata.sentinel_schema.scaffold_metadata.scaffold_version}`);
    }
    lines.push('');
  }

  // Group violations by type and severity
  const errors = certificate.violations.filter((v) => v.severity === 'error');
  const warnings = certificate.violations.filter((v) => v.severity === 'warning');

  const violationsByType = new Map<string, Violation[]>();
  for (const v of certificate.violations) {
    const existing = violationsByType.get(v.type) ?? [];
    existing.push(v);
    violationsByType.set(v.type, existing);
  }

  lines.push('## Violations Summary');
  lines.push(`  Errors: ${errors.length}`);
  lines.push(`  Warnings: ${warnings.length}`);
  lines.push('');

  if (certificate.violations.length > 0) {
    lines.push('## Violations by Type');
    for (const [type, vList] of [...violationsByType.entries()].sort((a, b) => {
      // Sort: errors first, then by count descending
      const aSev = a[1][0].severity === 'error' ? 0 : 1;
      const bSev = b[1][0].severity === 'error' ? 0 : 1;
      if (aSev !== bSev) return aSev - bSev;
      return b[1].length - a[1].length;
    })) {
      const symbol = vList[0].severity === 'error' ? '❌' : '⚠️ ';
      lines.push(`  ${symbol} ${type}: ${vList.length}`);
    }
    lines.push('');
  }

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
      errors.slice(0, 10).forEach((v, i) => {
        lines.push(formatViolation(v, i + 1));
        lines.push('');
      });
      if (errors.length > 10) {
        lines.push(`... and ${errors.length - 10} more errors`);
        lines.push('');
      }
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
      warnings.slice(0, 10).forEach((v, i) => {
        lines.push(formatViolation(v, i + 1));
        lines.push('');
      });
      if (warnings.length > 10) {
        lines.push(`... and ${warnings.length - 10} more warnings`);
        lines.push('');
      }
    }
  }

  lines.push('═══════════════════════════════════════════════════════════════');

  return lines.join('\n');
}

// Main
function main() {
  // Check if we should validate the regenerated design
  const useRegenerated = process.argv.includes('--regenerated');
  const designLabel = useRegenerated ? 'REGENERATED' : 'ORIGINAL';

  console.log(`Loading Phase0_v2 founder design (${designLabel}) from JSON...\n`);

  try {
    const { wells, metadata } = loadFounderDesign(useRegenerated);
    console.log(`Loaded ${wells.length} wells\n`);

    console.log('Running invariant checks...\n');
    const certificate = checkPhase0V2Design(wells, metadata);

    const report = formatCalibrationReport(certificate, metadata);
    console.log(report);

    // Write certificate to file
    const outputPath = path.join(__dirname, 'FOUNDER_VALIDATION_CERTIFICATE.json');
    fs.writeFileSync(outputPath, JSON.stringify(certificate, null, 2));
    console.log(`\nCertificate written to: ${outputPath}`);

    // Exit with error code if there are errors
    if (certificate.violations.some((v) => v.severity === 'error')) {
      process.exit(1);
    }
  } catch (error) {
    console.error('Failed to validate founder design:', error);
    process.exit(1);
  }
}

main();
