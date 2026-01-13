#!/usr/bin/env node
/**
 * Generate runs_manifest.json for epistemic agent results.
 *
 * Usage:
 *   node scripts/make_runs_manifest.mjs [output_dir]
 *
 * Default output_dir: results/epistemic_agent/
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');

// Parse args
const args = process.argv.slice(2);
const outputDir = args[0] || path.join(projectRoot, 'results', 'epistemic_agent');

if (!fs.existsSync(outputDir)) {
    console.error(`Error: Directory not found: ${outputDir}`);
    process.exit(1);
}

// Find all run_*.json files
const files = fs.readdirSync(outputDir)
    .filter(f => f.match(/^run_.*\.json$/))
    .sort()
    .reverse(); // Most recent first

if (files.length === 0) {
    console.error(`Warning: No run_*.json files found in ${outputDir}`);
    process.exit(0);
}

// Write manifest
const manifestPath = path.join(outputDir, 'runs_manifest.json');
fs.writeFileSync(manifestPath, JSON.stringify(files, null, 2) + '\n');

console.log(`✓ Created manifest with ${files.length} runs: ${manifestPath}`);
files.forEach(f => console.log(`  - ${f}`));
