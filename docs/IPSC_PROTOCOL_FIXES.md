# iPSC Protocol Fixes - Summary

**Date**: 2025-11-29  
**Issue**: iPSC MCB simulations were not using cell line-specific protocols (coating and Accutase dissociation)

## Problem Description

When simulating iPSC Master Cell Bank generation, the system was:
1. **Not coating vessels** before cell seeding (iPSC require laminin/vitronectin coating)
2. **Using Trypsin-EDTA** instead of Accutase for dissociation (iPSC are sensitive and require gentler enzymes)

## Root Cause

The cell line database (`data/cell_lines.yaml`) contained the correct information:
- `coating_required: true`
- `detach_reagent: accutase`
- `dissociation_method: versene` (EDTA-only)

However, the workflow and unit operation code had several issues:
1. **Dataclass vs Dict confusion**: Code was treating `CellLineProfile` dataclass as a dictionary
2. **Hardcoded fallbacks**: Multiple places had hardcoded `if cell_line == "ipsc"` checks
3. **Missing database lookups**: Some methods weren't consulting the cell line database at all

## Files Modified

### 1. `/src/cell_os/unit_ops/protocols.py`
**Lines 53-75**: Fixed `op_thaw()` coating detection logic
- Changed from `profile.get('coating_required', False)` to `profile.coating_required`
- Added proper dissociation reagent extraction from profile
- Now uses `profile.coating` for coating reagent selection
- Now uses `profile.dissociation_method` for dissociation reagent

### 2. `/src/cell_os/unit_ops/parametric.py`
**Lines 78-99**: Updated `op_thaw()` to use cell line database
- Replaced hardcoded iPSC/hESC checks with database lookup
- Added proper media selection from profile
- Fixed coating reagent selection
- Removed duplicate media assignment

### 3. `/src/cell_os/workflows/__init__.py`
**Lines 113-128**: Updated `build_master_cell_bank()` dissociation selection
- Changed from simple `"ipsc" check` to database lookup
- Added proper fallback chain: database → hardcoded → default

**Lines 181-193**: Updated `build_working_cell_bank()` dissociation selection
- Added cell line-specific dissociation method lookup
- Previously was using default "accutase" for all cell lines

### 4. `/dashboard_app/pages/tab_campaign_posh.py`
**Lines 356-364, 486-497**: Added unique widget keys
- Fixed navigation bug where clicking widgets redirected to Mission Control tab
- Added keys: `posh_initial_cells`, `posh_vendor_lot`, `posh_target_vials`, etc.

**Line 519**: Removed problematic `st.rerun()`
- Prevented automatic page refresh that caused tab switching

### 5. `/dashboard_app/app.py`
**Lines 55-57**: Added tab state management
- Initialized `st.session_state.active_tab` for future tab persistence

## Expected Behavior After Fix

When simulating iPSC MCB generation, the system will now:

1. ✅ **Coat vessels** with vitronectin/laminin before seeding
   - Adds coating steps: dispense coating reagent → incubate → aspirate
   
2. ✅ **Use Accutase** (or Versene) for dissociation instead of Trypsin
   - Respects the `dissociation_method` field from cell line database
   
3. ✅ **Use correct media** (mTeSR Plus) instead of DMEM
   - Reads `growth_media` from cell line profile

4. ✅ **Display proper BOM** with iPSC-specific reagents
   - Coating reagent costs included
   - Accutase instead of Trypsin-EDTA in consumables list

## Validation

To verify the fixes work:

```bash
# Run iPSC MCB simulation
python -c "
from cell_os.simulation.mcb_wrapper import simulate_mcb_generation, VendorVialSpec

spec = VendorVialSpec(
    cell_line='iPSC',
    initial_cells=1e6,
    lot_number='TEST-001',
    vial_id='VENDOR-iPSC-001'
)

result = simulate_mcb_generation(spec, target_vials=10)

# Check logs for coating and Accutase mentions
for log in result.logs:
    print(log)
"
```

Expected log output should mention:
- Coating steps (dispense vitronectin, incubate, aspirate)
- Accutase or Versene for dissociation (not Trypsin)

## Cell Line Database Schema

The fixes rely on the following fields in `data/cell_lines.yaml`:

```yaml
iPSC:
  detach_reagent: accutase
  coating:
    reagent: vitronectin
  profile:
    coating_required: true
    coating_reagent: "laminin_521"
    dissociation_method: "versene"  # Ultra-gentle EDTA-only
    media: "mtesr_plus_kit"
```

## Future Improvements

1. **Protocol Resolver**: The code has a `resolver` mechanism that should be used instead of fallback logic
2. **Database Migration**: Consider migrating from YAML to SQLite (`cell_line_db.py`) for better performance
3. **Validation**: Add unit tests to ensure cell line-specific protocols are applied correctly
4. **UI Feedback**: Show coating and dissociation method in dashboard simulation logs

## Related Issues

- Dashboard navigation bug (clicking widgets in POSH Campaign tab)
- Missing unique keys on Streamlit widgets
- Inconsistent cell line profile access (dataclass vs dict)
