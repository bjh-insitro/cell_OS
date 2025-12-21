================================================================================
CAUSALITY TRAP RUN
================================================================================

Compound: test_A_clean (er_stress)
Seed: 42

Schedule:
  t=0: dose=0.0, washout=False, feed=False
  t=1: dose=0.0, washout=False, feed=False
  t=2: dose=1.0, washout=False, feed=False
  t=3: dose=0.0, washout=False, feed=False

================================================================================
BELIEF STATE SNAPSHOTS
================================================================================

t=1 (6.0h):
  Treated: False
  Predicted axis: unknown
  Posterior top_prob: 0.943
  Posterior margin: 0.935
  Nuisance probability: 0.046
  Calibrated confidence: 0.993
  Viability: 0.980
  Actin fold: 1.000
  Mito fold: 1.000
  ER fold: 1.000

t=2 (12.0h):
  Treated: False
  Predicted axis: unknown
  Posterior top_prob: 0.923
  Posterior margin: 0.915
  Nuisance probability: 0.066
  Calibrated confidence: 0.991
  Viability: 0.980
  Actin fold: 1.000
  Mito fold: 1.000
  ER fold: 1.000

t=3 (18.0h):
  Treated: True
  Predicted axis: er_stress
  Posterior top_prob: 1.000
  Posterior margin: 1.000
  Nuisance probability: 0.000
  Calibrated confidence: 0.993
  Viability: 0.794
  Actin fold: 1.000
  Mito fold: 1.112
  ER fold: 1.820

t=4 (24.0h):
  Treated: True
  Predicted axis: er_stress
  Posterior top_prob: 1.000
  Posterior margin: 1.000
  Nuisance probability: 0.000
  Calibrated confidence: 0.992
  Viability: 0.762
  Actin fold: 1.000
  Mito fold: 1.112
  ER fold: 1.873

================================================================================
CAUSALITY CHECK
================================================================================

Pre-treatment (t=0,1):
  t=1: predicted=unknown, posterior=0.943, nuisance=0.046
  t=2: predicted=unknown, posterior=0.923, nuisance=0.066

✓ No premature mechanism detection

Post-treatment (t=3+):
  t=3: predicted=er_stress, posterior=1.000, nuisance=0.000
  t=4: predicted=er_stress, posterior=1.000, nuisance=0.000
