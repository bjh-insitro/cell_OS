# SNR Second-Order Leakage: Visual Proof

This directory contains visual proof that QC metadata stripping eliminates second-order leakage.

## What You're Looking At

### 1. AUC Comparison (`snr_leakage_auc_comparison.png`)

**The smoking gun.**

- **Red bars (Before):** AUC = 1.0 → Agent can perfectly predict treatment from QC metadata alone
- **Green bars (After):** AUC = 0.5 → Agent cannot do better than random guessing

All 4 attack types drop from perfect leakage to random performance.

---

### 2. QC Embeddings (`snr_leakage_qc_embedding_*_before.png`)

**What leakage looks like in feature space.**

Each plot shows PCA projection of QC-only features:
- Points are colored by treatment
- If you see **separate clusters** → leakage
- If you see **noise soup** → no leakage

**Before fix:** Perfect separation (different clouds per treatment)
**After fix:** Not shown (no QC features left to embed)

---

### 3. Mask Patterns (`snr_leakage_mask_patterns_*.png`)

**The barcode effect.**

Shows which channels are masked for each treatment:
- **Missingness attack:** 0 masked (AllBright) vs 2 masked (Mixed) vs 5 masked (AllDim)
- **Spatial attack:** 0 masked (Center) vs 2-3 masked (Edge)

The *pattern* of masked channels is treatment-specific, even when biology is identical.

This pattern acts as a **membership oracle** if exposed to the agent.

---

## How to Regenerate

```bash
python scripts/run_snr_leakage_check.py --output-dir snr_leakage_report
```

---

## What This Proves

✓ **Before:** QC metadata (quality_score, margins, usable_channels) leaked treatment identity
✓ **After:** QC stripping eliminates leakage (AUC drops to random)
✓ **Fix works:** Agent cannot extract treatment from QC alone

---

## What This Doesn't Prove

✗ Agent's decision logic is correct (only that it's not exploiting this leak)
✗ There are no other leakage channels we haven't tested
✗ Agent won't try to optimize QC in the future (requires policy-level monitoring)

---

## The Fix

**File:** `src/cell_os/epistemic_agent/qc_gate.py`

```python
from src.cell_os.epistemic_agent.qc_gate import prepare_agent_observation

# Strip QC metadata before passing to agent
agent_obs = prepare_agent_observation(obs_with_qc, apply_gate=False)
```

**Key idea:** If the agent can't see it, the agent can't optimize it.

---

## The One-Line Summary

**You had a membership oracle. Now you don't.**

Gradient-following raccoons, meet information boundary.
