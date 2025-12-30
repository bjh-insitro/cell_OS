# Dose Scout Report

**Compound:** CCCP
**Dose Range:** 0.500–15.0 µM (log-spaced)
**Observation Window:** 0.0–120.0 h

---

## Commitment Fraction by Dose

| Dose (µM) | Wells | Committed | Fraction | Mean Time (h) |
|-----------|-------|-----------|----------|---------------|
| 0.500 | 4.0 | 0.0 | 0.000 | — |
| 0.681 | 4.0 | 0.0 | 0.000 | — |
| 0.928 | 4.0 | 0.0 | 0.000 | — |
| 1.264 | 4.0 | 0.0 | 0.000 | — |
| 1.722 | 4.0 | 0.0 | 0.000 | — |
| 2.346 | 4.0 | 1.0 | 0.250 | 48.0 |
| 3.196 | 4.0 | 1.0 | 0.250 | 48.0 |
| 4.355 | 4.0 | 1.0 | 0.250 | 12.0 |
| 5.933 | 4.0 | 1.0 | 0.250 | 12.0 |
| 8.082 | 4.0 | 1.0 | 0.250 | 48.0 |
| 11.011 | 4.0 | 1.0 | 0.250 | 48.0 |
| 15.000 | 4.0 | 0.0 | 0.000 | — |

---

## Dose Suggestions for Identifiability Suite

### Regime B (Mid Stress, Held-Out Prediction)
**Target:** 10–40% commitment
**Suggested dose:** 5.144 µM ✅
*(6 doses in target range)*

### Regime C (High Stress, Parameter Recovery)
**Target:** 40–80% commitment (need variation for identifiability)
**Fallback dose:** 2.346 µM ⚠️
*(Insufficient doses in target range, consider wider range or higher doses)*

---

## Next Steps

1. Update `configs/calibration/identifiability_2c1.yaml` with suggested doses:
   - Set `regimes.mid_stress_mixed.dose_uM` to Regime B dose
   - Set `regimes.high_stress_event_rich.doses` to Regime C doses
2. Rerun full suite: `python scripts/run_identifiability_suite.py --config ... --out ...`
3. If results are still insufficient, adjust:
   - Hazard parameters in truth block
   - Observation window
   - Number of replicates

---

*Scout report generated: 2025-12-29 16:04:09*
