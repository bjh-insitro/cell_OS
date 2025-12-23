# Re-Validation After Nutrient Depletion Fix

**Date:** 2025-12-22
**Prerequisites:**
- Nutrient depletion bug fixed (commit b241033)
- Shared factors re-enabled (commit 79e2d78)

## What Changed

### Before (Seeds 5000-5200 with diagnostic mode):
- **A549 vehicle wells**: 100% dead (viability=0.088904)
- **HepG2 vehicle wells**: 100% alive (viability=0.98)
- **Vehicle CV**: 42% (bimodal distribution)
- **Channel correlations**: 0.89 (viability_factor global multiplier)
- **Well persistence**: Failed (identity swamped by viability noise)
- **Fingerprints**: Not visible (structure drowned)

### After (Expected with new seeds):
- **All vehicle wells**: Alive (viability ~0.98, tight distribution)
- **Vehicle CV**: 8-12% (realistic instrument noise)
- **Channel correlations**: 0.3-0.5 (per-well biology + stain/focus coupling)
- **Well persistence**: <15% CV (wells maintain identity across runs)
- **Fingerprints**: Visible (stain-like vs focus-like signatures emerge)

## How to Re-Run Validation

### On JupyterHub:
```bash
ssh jh
cd /home/ubuntu/cell_OS

# Pull latest fixes
git pull origin main

# Run with new seeds (avoid 5000-5200 which had diagnostic mode)
bash scripts/run_structured_noise_validation_jh.sh
```

This will run seeds 5000, 5100, 5200 with:
- ✅ Nutrient depletion fixed (A549 survives)
- ✅ Shared factors enabled (plate/day/operator/edge/illumination)
- ✅ Per-well biology (persistent baseline shifts)
- ✅ Stain/focus coupling (weighted channel exponents)

### Validation Script
The validation script checks 4 criteria:
1. **Vehicle CV**: 8-12% (was 42%)
2. **Channel correlations**: ER-Mito, Nucleus-Actin coupling structure
3. **Well persistence**: Same well_id across seeds has <15% CV
4. **Outlier fingerprints**: Stain-like vs focus-like signatures

## Expected Results

### Check 1: Vehicle CV
```
CV_NW_HEPG2_VEH:  CV = 9.5%   ✓ (was 2.3% with diagnostic mode)
CV_NW_A549_VEH:   CV = 10.2%  ✓ (was 42% with dead wells)
CV_NE_HEPG2_VEH:  CV = 8.8%   ✓
CV_NE_A549_VEH:   CV = 9.7%   ✓
```

### Check 2: Channel Correlations
```
ER-Mito correlation:       0.45 ✓ (stain-coupled, both at ~1.0 exponent)
Nucleus-Actin correlation: 0.40 ✓ (focus-coupled, both at ~1.0 exponent)
ER-Nucleus correlation:    0.28 ✓ (weak coupling, 0.5 exponent)
```

### Check 3: Well Persistence
```
Well D8 (A549):
  Seed 5000: morph_er = 185.3
  Seed 5100: morph_er = 192.1
  Seed 5200: morph_er = 188.7
  Within-well CV: 1.8%  ✓ (< 15%)
```

### Check 4: Fingerprints
```
Stain outliers (high):
  Score: +2.5  ✓ (ER↑, Mito↑, RNA↑, Nucleus~, Actin~)

Focus outliers (defocus):
  Score: +2.3  ✓ (Nucleus↓, Actin↓, ER~, Mito~, RNA~)
```

## What Success Looks Like

After validation passes, you should see:

1. **Vehicle CV in realistic range (8-12%)**
   - No more bimodal distributions
   - No more global viability multiplier
   - Structured noise is now the dominant source of variance

2. **Channel correlations reflect coupling structure**
   - Stain-coupled channels (ER/Mito/RNA) move together
   - Focus-coupled channels (Nucleus/Actin) move together
   - Cross-coupling is weak but non-zero

3. **Wells have persistent identity**
   - Same well maintains baseline across runs
   - Within-well variance << between-well variance
   - Agent can learn "this well is always a bit high/low"

4. **Fingerprints are interpretable**
   - Stain failures boost ER/Mito/RNA proportionally
   - Focus failures affect Nucleus/Actin with variance inflation
   - QC system can classify failure modes

## Next Steps After Validation

Once validation passes:

1. **Wire fingerprints into QC ontology**
   - Create `FailureMode` enum (stain, focus, bubble, contamination)
   - Add fingerprint classifier to QC pipeline
   - Enable "earning the gate" epistemic control

2. **Enable agent learning of instrument trust**
   - Agent sees well-to-well baseline variance (8-12%)
   - Agent learns which wells are systematically high/low
   - Agent learns which failure modes are common

3. **Production plate execution**
   - Move from calibration plates to treatment plates
   - Enable biological anchors for dose-response validation
   - Enable contrastive tiles for mechanism discovery

## Troubleshooting

### If A549 still dying:
Check that nutrient depletion fix was applied:
```bash
grep -A3 "Back-calculate start-of-interval" \
  src/cell_os/hardware/stress_mechanisms/nutrient_depletion.py
```
Should see: `viable_cells_t0 = viable_cells_t1 / np.exp(growth_rate * hours)`

### If correlations still at 0.89:
Check that shared factors are re-enabled:
```bash
grep "DIAGNOSTIC_DISABLE_SHARED_FACTORS = " \
  src/cell_os/hardware/assays/cell_painting.py
```
Should see: `DIAGNOSTIC_DISABLE_SHARED_FACTORS = False` (not True)

### If vehicle CV still too low:
Check that per-well biology is keyed correctly:
```bash
grep "well_biology_" src/cell_os/hardware/biological_virtual.py
```
Should see: `well_seed = stable_u32(f"well_biology_{well_position}_{cell_line}")`

## Timeline

- [x] Fix nutrient depletion (commit b241033)
- [x] Re-enable shared factors (commit 79e2d78)
- [x] Document bug and fix (NUTRIENT_DEPLETION_BUG_POSTMORTEM.md)
- [ ] Pull fixes to JH
- [ ] Re-run validation (seeds 5000, 5100, 5200)
- [ ] Analyze results
- [ ] If pass → wire fingerprints into QC
- [ ] If fail → debug remaining issues

Estimated time: ~5 minutes for execution, ~10 minutes for analysis
