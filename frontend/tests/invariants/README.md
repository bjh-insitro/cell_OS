# Phase 0 Invariant Test Suite

Systematic mutation testing for Phase 0 founder design invariants.

## Test Strategy

**Goal**: High coverage of failure modes, not exhaustive permutations.

### Test Files

1. **`phase0_mutations.test.ts`** - Deterministic mutation coverage
   - Applies 18 systematic "evil edits" to golden fixture
   - Each mutation targets a specific invariant failure mode
   - Table-driven tests with expected violation types
   - Fast, deterministic, no flakiness

2. **`cross_language_canonical.test.ts`** - Byte-for-byte verification
   - Ensures Python and TypeScript produce identical canonical JSON
   - Tests float formatting (0 -> "0.0", not "0")
   - Tests key ordering (alphabetical: compound, dose_uM, position, type)
   - Tests case preservation (ER_mid not er_mid)
   - Verifies SHA-256 hash matches across languages

3. **`mutators.ts`** - Helper functions for systematic mutations
   - Each mutator applies one specific type of "evil edit"
   - Mutations affect design structure, not random fuzzing
   - Examples: tamper sentinel compound, swap positions, unbalance batches

## Golden Fixture

**Source**: `/data/designs/phase0_founder_v2_regenerated.json`
- 24 plates, 2112 wells
- 672 sentinel wells (28 per plate)
- 1440 experimental wells (60 per plate)
- Fixed scaffold: `phase0_v2_scaffold_v1` (hash: `901ffeb4603019fe`)
- Zero violations (known-good baseline)

## Mutation Coverage

### Scaffold Provenance (6 mutations)
- Missing/wrong policy
- Missing/wrong scaffold hash
- Tamper sentinel compound/dose/type
- Swap sentinel positions

### Scaffold Stability (2 mutations)
- Remove sentinel from first plate
- Diverge scaffold on second plate

### Plate Capacity (2 mutations)
- Add duplicate well
- Add well in excluded corner

### Condition Multiset (2 mutations)
- Remove experimental condition from one timepoint
- Change compound/dose for experimental position

### Sentinel Placement (1 mutation)
- Cluster sentinels in corner

### Batch Balance (2 mutations)
- Unbalance operator across plates
- Unbalance cell line across plates

## Running Tests

```bash
# Run all tests
npm test

# Watch mode
npm run test:watch

# CI mode (fail if no tests)
npm run test:ci

# Run specific test file
npm test tests/invariants/phase0_mutations.test.ts
```

## Test Results

All tests pass (30 tests, 2 files):
- ✅ Cross-language canonical JSON (9 tests)
- ✅ Phase 0 mutations (21 tests)

## Adding New Mutations

1. Add mutator function to `mutators.ts`
2. Add test case to `mutationTests` array in `phase0_mutations.test.ts`
3. Specify expected violation types in `expectOneOf` array

Example:
```typescript
{
  name: 'my new mutation',
  mutator: mutators.mut_my_new_mutation,
  expectOneOf: ['violation_type_1', 'violation_type_2'],
}
```

## Design Principles

1. **Deterministic** - No random fuzzing, reproducible failures
2. **Fast** - All tests run in ~1 second
3. **Focused** - Each mutation targets one failure mode
4. **Documented** - Clear comments explain what each mutation breaks
5. **Maintainable** - Table-driven tests, easy to add new cases

## Why Not Property-Based Testing?

Property-based testing (fast-check) could be added for "weird but plausible" edits,
but the core mutation tests provide better signal-to-noise for catching regressions.

The systematic mutations catch:
- Allocation bugs (wrong scaffold, wrong multiset)
- Labeling bugs (wrong metadata, wrong types)
- Structural bugs (duplicates, missing wells)

Random fuzzing would likely just produce the same violations repeatedly.
