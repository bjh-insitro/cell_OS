/**
 * Cross-language canonical JSON verification
 *
 * This test ensures Python and TypeScript produce byte-for-byte identical
 * canonical JSON for scaffold hashing. This is the "shared truth" that
 * prevents silent hash mismatches due to serialization differences.
 *
 * Tests the exact serialization rules:
 * - Alphabetical key ordering (compound, dose_uM, position, type)
 * - Float formatting (0 -> "0.0", not "0")
 * - No whitespace
 * - Case preservation
 */

import { describe, test, expect } from 'vitest';
import { execSync } from 'child_process';
import { canonicalJsonPythonCompatible } from '../../src/pages/CellThalamus/invariants/sentinelScaffold';
import type { ScaffoldHashItem } from '../../src/pages/CellThalamus/invariants/sentinelScaffold';

describe('Cross-Language Canonical JSON', () => {
  test('TypeScript and Python produce identical canonical JSON', () => {
    // Test data: simple scaffold items
    const items: ScaffoldHashItem[] = [
      { position: 'A02', type: 'vehicle', compound: 'DMSO', dose_uM: 0 },
      { position: 'A05', type: 'ER_mid', compound: 'thapsigargin', dose_uM: 0.1 },
      { position: 'B02', type: 'mito_mid', compound: 'rotenone', dose_uM: 1.0 },
    ];

    // Get TypeScript canonical JSON
    const tsCanonical = canonicalJsonPythonCompatible(items);

    // Get Python canonical JSON via subprocess
    // IMPORTANT: Use float literals (0.0, 1.0) not integers (0, 1) to match scaffold spec
    const pythonScript = `
import json
import sys

items = [
    {"position": "A02", "type": "vehicle", "compound": "DMSO", "dose_uM": 0.0},
    {"position": "A05", "type": "ER_mid", "compound": "thapsigargin", "dose_uM": 0.1},
    {"position": "B02", "type": "mito_mid", "compound": "rotenone", "dose_uM": 1.0},
]

# Sort by position (should already be sorted, but explicit)
items_sorted = sorted(items, key=lambda x: x['position'])

# Canonical JSON: alphabetical keys, no whitespace
canonical = json.dumps(items_sorted, sort_keys=True, separators=(',', ':'))
print(canonical, end='')
`;

    const pyCanonical = execSync('python3', {
      input: pythonScript,
      encoding: 'utf-8',
    });

    // CRITICAL: Byte-for-byte match
    expect(tsCanonical).toBe(pyCanonical);
  });

  test('Float formatting matches Python (integers get .0)', () => {
    const items: ScaffoldHashItem[] = [
      { position: 'A01', type: 'vehicle', compound: 'DMSO', dose_uM: 0 },
      { position: 'A02', type: 'test', compound: 'compound', dose_uM: 1 },
      { position: 'A03', type: 'test', compound: 'compound', dose_uM: 0.1 },
      { position: 'A04', type: 'test', compound: 'compound', dose_uM: 10.5 },
    ];

    const canonical = canonicalJsonPythonCompatible(items);

    // Integers should have .0 appended
    expect(canonical).toContain('"dose_uM":0.0');
    expect(canonical).toContain('"dose_uM":1.0');

    // Floats should keep their decimal representation
    expect(canonical).toContain('"dose_uM":0.1');
    expect(canonical).toContain('"dose_uM":10.5');
  });

  test('Key ordering is alphabetical (compound, dose_uM, position, type)', () => {
    const items: ScaffoldHashItem[] = [
      { position: 'A01', type: 'vehicle', compound: 'DMSO', dose_uM: 0 },
    ];

    const canonical = canonicalJsonPythonCompatible(items);

    // Keys should appear in alphabetical order
    const compoundIdx = canonical.indexOf('"compound"');
    const doseIdx = canonical.indexOf('"dose_uM"');
    const positionIdx = canonical.indexOf('"position"');
    const typeIdx = canonical.indexOf('"type"');

    expect(compoundIdx).toBeLessThan(doseIdx);
    expect(doseIdx).toBeLessThan(positionIdx);
    expect(positionIdx).toBeLessThan(typeIdx);
  });

  test('Case is preserved (ER_mid not er_mid)', () => {
    const items: ScaffoldHashItem[] = [
      { position: 'A01', type: 'ER_mid', compound: 'Thapsigargin', dose_uM: 0.1 },
    ];

    const canonical = canonicalJsonPythonCompatible(items);

    // Case should be preserved exactly as provided
    expect(canonical).toContain('"type":"ER_mid"');
    expect(canonical).toContain('"compound":"Thapsigargin"');
    expect(canonical).not.toContain('"type":"er_mid"');
  });

  test('No whitespace in canonical JSON', () => {
    const items: ScaffoldHashItem[] = [
      { position: 'A01', type: 'vehicle', compound: 'DMSO', dose_uM: 0 },
      { position: 'A02', type: 'test', compound: 'compound', dose_uM: 1 },
    ];

    const canonical = canonicalJsonPythonCompatible(items);

    // Should have no spaces after colons or commas (Python separators=(',', ':'))
    expect(canonical).not.toMatch(/,\s/);
    expect(canonical).not.toMatch(/:\s/);
  });

  test('Items are sorted by position', () => {
    // Provide items in wrong order
    const items: ScaffoldHashItem[] = [
      { position: 'C03', type: 'test', compound: 'c', dose_uM: 0 },
      { position: 'A01', type: 'test', compound: 'a', dose_uM: 0 },
      { position: 'B02', type: 'test', compound: 'b', dose_uM: 0 },
    ];

    const canonical = canonicalJsonPythonCompatible(items);

    // Should be sorted by position (A01, B02, C03)
    const a01Idx = canonical.indexOf('"position":"A01"');
    const b02Idx = canonical.indexOf('"position":"B02"');
    const c03Idx = canonical.indexOf('"position":"C03"');

    expect(a01Idx).toBeLessThan(b02Idx);
    expect(b02Idx).toBeLessThan(c03Idx);
  });

  test('Special characters are properly escaped', () => {
    const items: ScaffoldHashItem[] = [
      { position: 'A01', type: 'test', compound: 'compound"with"quotes', dose_uM: 0 },
    ];

    const canonical = canonicalJsonPythonCompatible(items);

    // Quotes should be escaped
    expect(canonical).toContain('\\"');
  });

  test('NaN and Infinity are rejected', () => {
    const itemsNaN: ScaffoldHashItem[] = [
      { position: 'A01', type: 'test', compound: 'compound', dose_uM: NaN },
    ];

    expect(() => canonicalJsonPythonCompatible(itemsNaN)).toThrow('Invalid number');

    const itemsInfinity: ScaffoldHashItem[] = [
      { position: 'A01', type: 'test', compound: 'compound', dose_uM: Infinity },
    ];

    expect(() => canonicalJsonPythonCompatible(itemsInfinity)).toThrow('Invalid number');
  });
});

describe('Scaffold Hash Computation', () => {
  test('SHA-256 hash matches Python implementation', () => {
    const items: ScaffoldHashItem[] = [
      { position: 'A02', type: 'vehicle', compound: 'DMSO', dose_uM: 0 },
      { position: 'A05', type: 'ER_mid', compound: 'thapsigargin', dose_uM: 0.1 },
    ];

    const tsCanonical = canonicalJsonPythonCompatible(items);

    // Compute SHA-256 hash in TypeScript
    const crypto = require('crypto');
    const tsHash = crypto.createHash('sha256').update(tsCanonical, 'utf8').digest('hex').slice(0, 16);

    // Compute SHA-256 hash in Python
    const pythonScript = `
import json
import hashlib

items = [
    {"position": "A02", "type": "vehicle", "compound": "DMSO", "dose_uM": 0.0},
    {"position": "A05", "type": "ER_mid", "compound": "thapsigargin", "dose_uM": 0.1},
]

items_sorted = sorted(items, key=lambda x: x['position'])
canonical = json.dumps(items_sorted, sort_keys=True, separators=(',', ':'))
hash_val = hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]
print(hash_val, end='')
`;

    const pyHash = execSync('python3', {
      input: pythonScript,
      encoding: 'utf-8',
    });

    // Hashes MUST match
    expect(tsHash).toBe(pyHash);
  });
});
