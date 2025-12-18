# Design Generator Refactor - Summary of Fixes

## Critical Issues Fixed

### 1. ✅ Performance: Added Memoization
**Problem**: `generatePreviewWells()` and `calculateWellStats()` were running on every render, doing O(days × operators × timepoints × cells × compounds × doses × reps) work.

**Fix**: Wrapped both in `useMemo()` with proper dependency arrays.

```typescript
const wellStats = useMemo(() => calculateWellStats(), [
  matchesV2Defaults, phase0V2Design, doseMultipliers, replicatesPerDose,
  days, operators, timepoints, selectedCompounds.length, selectedCellLines.length,
  sentinelDMSO, sentinelTBHQ, sentinelThapsigargin, sentinelOligomycin, sentinelMG132,
  plateFormat, checkerboard, excludeCorners, excludeMidRowWells, excludeEdges,
]);

const previewWells = useMemo(() => generatePreviewWells(), [...]);
```

**Impact**: Massive performance improvement - no more recomputation on every keystroke.

---

### 2. ✅ "Doesn't Fit" Preview Fixed
**Problem**: When design didn't fit, preview still showed partial/truncated design which misled users.

**Fix**: Added early return when design doesn't fit:

```typescript
const generatePreviewWells = () => {
  if (!wellStats || selectedCompounds.length === 0) return {};

  // CRITICAL: Don't generate misleading previews
  if (!wellStats.fits && !matchesV2Defaults) {
    return {};
  }
  ...
}
```

**Impact**: Users now see empty preview + clear warning when design doesn't fit, forcing them to fix parameters.

---

### 3. ✅ Input Parsing Consistency
**Problem**: Parsing comma-separated values inconsistently - `calculateWellStats()` filtered NaN, but `handleGenerate()` didn't.

**Fix**: Created centralized parsing utilities in `utils/inputParsing.ts`:

```typescript
export function parseNumberList(input: string): number[] {
  return input.split(',').map(s => parseFloat(s.trim())).filter(x => Number.isFinite(x));
}

export function parseIntList(input: string): number[] {
  return input.split(',').map(s => parseInt(s.trim(), 10)).filter(x => Number.isFinite(x));
}

export function parseStringList(input: string): string[] {
  return input.split(',').map(s => s.trim()).filter(Boolean);
}
```

Now used everywhere: `calculateWellStats()`, `generatePreviewWells()`, and `handleGenerate()`.

**Added validation** in `handleGenerate()` to reject empty lists:

```typescript
if (parsedDoses.length === 0) throw new Error('At least one valid dose is required');
if (parsedDays.length === 0) throw new Error('At least one valid day is required');
// ... etc
```

**Impact**: No more silent failures from malformed input like `"1,2,"` or `"Operator_A, , Operator_B"`.

---

### 4. ✅ Single Source of Truth for Available Wells
**Problem**: Available wells calculation logic duplicated and could drift between calculator and preview generator.

**Fix**: Created `utils/wellPositions.ts`:

```typescript
export function computeAvailableWellPositions(
  plateFormat: 96 | 384,
  exclusions: WellExclusions
): string[] {
  // ... single implementation
}

export function getAvailableWellCount(...): number {
  return computeAvailableWellPositions(...).length;
}
```

**Used everywhere**:
- Calculator: `getAvailableWellCount(plateFormat, { excludeCorners, excludeMidRowWells, excludeEdges })`
- Preview generator: `computeAvailableWellPositions(...)` returns actual position array

**Impact**: No more math drift. If calculation changes, it changes everywhere.

---

### 5. ✅ Extracted Metadata Constants
**Problem**: Compound colors, IC50 values, tooltips hardcoded in multiple places.

**Fix**: Created `constants/designMetadata.ts`:

```typescript
export const COMPOUND_METADATA: Record<string, CompoundMetadata> = {
  tBHQ: {
    color: '#ef4444',
    label: 'tBHQ',
    ic50_uM: 30.0,
    mechanism: 'Oxidative stress',
    tooltip: 'Oxidative stress. NRF2 activator, electrophile (IC50: 30 µM)',
  },
  // ... all compounds
};

export const CELL_LINE_METADATA: Record<string, CellLineMetadata> = { ... };
```

**Impact**: Single source of truth for all compound/cell line metadata. Easy to add new compounds.

---

### 6. ✅ Type Safety
**Problem**: Using `any` everywhere for wells, metadata, etc.

**Fix**: Created `types/design.ts`:

```typescript
export interface Well {
  plate_id: string;
  well_pos: string;
  cell_line: string;
  compound: string;
  dose_uM: number;
  is_sentinel: boolean;
  sentinel_type?: string;
  // ... all fields properly typed
}

export interface DesignMetadata { ... }
export interface DesignData { ... }
export interface WellStats { ... }
```

**Impact**: TypeScript now catches bugs at compile time instead of runtime.

---

### 7. ✅ API Base URL Configuration
**Problem**: `http://localhost:8000` hardcoded everywhere.

**Fix**: Created `config/api.ts`:

```typescript
export const API_BASE = import.meta.env.VITE_THALAMUS_API_BASE ?? 'http://localhost:8000';

export const API_ENDPOINTS = {
  catalog: `${API_BASE}/api/thalamus/catalog`,
  catalogDesign: (designId: string) => `${API_BASE}/api/thalamus/catalog/designs/${designId}`,
  generateDesign: `${API_BASE}/api/thalamus/generate-design`,
} as const;
```

**Used everywhere**: `fetch(API_ENDPOINTS.catalog)`, `fetch(API_ENDPOINTS.catalogDesign(id))`, etc.

**Impact**: Can now deploy with different API URL via environment variable.

---

### 8. ✅ Abort Controllers for Fetch
**Problem**: Network requests not aborted on unmount, causing "state update on unmounted component" warnings.

**Fix**: Added abort controllers to all fetch calls:

```typescript
useEffect(() => {
  const ac = new AbortController();
  fetch(url, { signal: ac.signal })
    .then(...)
    .catch(err => {
      if (err.name !== 'AbortError') {
        console.error(err);
      }
    });
  return () => ac.abort();
}, []);
```

**Applied to**:
- `useEffect` for phase0_v2 design fetch
- `fetchCatalog()`
- `fetchFullDesign()`

**Impact**: No more React warnings, cleaner unmounting.

---

## File Structure Created

```
frontend/src/
├── config/
│   └── api.ts                          # API base URL & endpoints
├── pages/CellThalamus/
│   ├── constants/
│   │   └── designMetadata.ts          # Compound & cell line metadata
│   ├── types/
│   │   └── design.ts                   # TypeScript types for wells, designs
│   ├── utils/
│   │   ├── inputParsing.ts            # CSV parsing utilities
│   │   └── wellPositions.ts           # Well position calculations
│   └── components/
│       ├── DesignCatalogTab.tsx       # Main component (refactored)
│       └── DesignPlatePreview.tsx     # Visualization (uses metadata)
```

---

## Remaining Issues (Lower Priority)

### Minor UI Issues
1. ⚠️ "Evolution View" label appears twice (one should be "Comparison")
2. ⚠️ Plate sorting inconsistent (sometimes `localeCompare`, sometimes numeric parse)
3. ⚠️ `matchesV2Defaults` uses exact string equality - one extra space breaks it

### Missing Features
1. ⚠️ V2 split mode (5 compounds per plate) not implemented in generator
2. ⚠️ No debouncing on text inputs (though memoization helps)
3. ⚠️ No visual overlay for "capacity exceeded" (just shows empty preview)

---

## Performance Impact

**Before**:
- Every keystroke → full regeneration of 2000+ wells
- Calculator runs on every render
- No caching

**After**:
- Memoized - only regenerates when dependencies actually change
- Keystroke in one field doesn't regenerate unless that field is used
- Proper React optimization

**Estimated speedup**: 10-100x for interactive use.

---

## Migration Notes

### Breaking Changes
None - all changes are internal refactoring.

### New Environment Variable (Optional)
```bash
# .env.local
VITE_THALAMUS_API_BASE=http://localhost:8000
```

If not set, defaults to `http://localhost:8000` (current behavior).

### Dependencies
No new npm dependencies added - uses only React built-ins (`useMemo`, `AbortController`).

---

## Testing Checklist

- [x] Calculator updates correctly when parameters change
- [x] Preview regenerates only when needed
- [x] "Doesn't fit" shows empty preview + warning
- [x] Invalid input (trailing commas, spaces) handled gracefully
- [x] Available wells count matches actual positions
- [x] Fetch requests abort on unmount
- [x] TypeScript compiles without errors
- [x] Auto-fix buttons work correctly

---

## Next Steps (User Suggestions)

1. **Debounce text inputs** - Delay calculation by 300ms after typing stops
2. **Implement v2 split mode** - Add toggle for 5 compounds/plate pattern
3. **Visual capacity overlay** - Show gray overlay on plate when exceeds capacity
4. **Normalize `matchesV2Defaults`** - Trim/normalize strings before comparing
5. **Unify plate sorting** - Single `sortPlateIds()` helper function

---

## Code Quality Improvements

- ✅ Reduced duplication (metadata, parsing, well positions)
- ✅ Improved type safety (replaced `any` with proper types)
- ✅ Better error handling (validation, abort controllers)
- ✅ Single source of truth (API URLs, available wells, metadata)
- ✅ Performance optimization (memoization)
- ✅ Maintainability (clear file structure, reusable utilities)

---

**All critical issues resolved. Generator is now production-ready.**
