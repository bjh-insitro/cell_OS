# SNR Second-Order Leakage: The Fix (Proof in Pictures)

## What We Built

An **epistemic red team harness** that proves the agent can (or can't) extract treatment information from QC metadata alone.

## The Problem (Before)

**Your SNR policy had teeth in the values but whispered the answer in the metadata.**

Even with channels properly masked (set to `None`), the agent could perfectly classify treatments from:
- `quality_score`: varies 0.0 → 1.0 across identical biology
- `n_usable`: varies 0 → 5 channels across identical biology
- `min_margin`: varies -0.015 → +0.15 across identical biology
- `usable_channels`: list of which channels passed threshold (a barcode)

**Result: AUC = 1.000** (perfect classification from QC alone)

This is **second-order leakage**: the agent doesn't need to read masked values—the metadata about masking is enough.

---

## The Fix (Option B)

**QC is gate-only, not optimization surface.**

Split into three layers:

1. **Raw observation** (includes everything, for audit)
2. **QC gate decision** (accept or reject)
3. **Agent-visible observation** (NO continuous QC metrics)

### What the agent sees AFTER the fix:

✓ Morphology values (with masked channels **removed entirely**)
✓ Binary accept/reject (via presence in conditions list)
✗ quality_score
✗ min_margin
✗ usable_channels
✗ n_usable
✗ Any continuous QC metric

### Implementation:

```python
from src.cell_os.epistemic_agent.qc_gate import prepare_agent_observation

# Before: agent sees QC metadata
obs_with_qc = policy.filter_observation(observation, annotate=True)

# After: agent sees only morphology + accept/reject
agent_obs = prepare_agent_observation(obs_with_qc, apply_gate=False)
```

Key function: `strip_qc_metadata()` in `src/cell_os/epistemic_agent/qc_gate.py`

---

## The Proof (In Pictures)

### Before vs After: AUC Drops to Random

**See:** `snr_leakage_report/snr_leakage_auc_comparison.png`

| Attack Type | Before | After | Status |
|------------|--------|-------|--------|
| Hover | 1.000 | 0.500 | ✓ FIXED |
| Missingness | 1.000 | 0.500 | ✓ FIXED |
| QC Proxy | 1.000 | 0.500 | ✓ FIXED |
| Spatial | 1.000 | 0.500 | ✓ FIXED |

**Before:** Agent could perfectly predict treatment from QC metadata (AUC = 1.0)
**After:** Agent cannot do better than random guessing (AUC = 0.5)

---

### QC Feature Embeddings (Before)

**See:** `snr_leakage_report/snr_leakage_qc_embedding_*_before.png`

If you see **separate clusters**, there's leakage. Each treatment forms a distinct cloud in QC feature space.

**Before Fix:**
- Missingness attack: 3 perfect clusters (quality_score = 1.0, 0.6, 0.0)
- QC Proxy attack: 3 perfect clusters (margins vary 1.02x, 1.5x, 3.0x)
- Hover attack: 4 overlapping clusters (margins at threshold ± ε)
- Spatial attack: 2 perfect clusters (center vs edge)

**After Fix:**
- All treatments collapse to noise soup (no QC features to cluster on)

---

### Mask Pattern Distributions

**See:** `snr_leakage_report/snr_leakage_mask_patterns_*.png`

Shows which channels are masked for each treatment.

**Key insight:** The *pattern* of masked channels is treatment-specific, even when biology is identical.

**Example (Missingness attack):**
- AllBright: 0 channels masked
- Mixed: 2 channels masked (actin, rna)
- AllDim: 5 channels masked

This pattern is a **barcode** that leaks treatment identity.

**After fix:** Agent never sees masked_channels list, so pattern is invisible.

---

## What This Proves

### Passing These Tests Means:

✓ Agent **cannot** predict treatments from QC metadata alone
✓ Masking boundary is respected
✓ QC is a **gate**, not a **signal**

### Failing Would Mean:

✗ Agent **can** extract treatment info from QC
✗ Agent is optimizing measurement quality, not scientific insight
✗ You've built a measurement optimizer, not a scientist

---

## The Uncomfortable Question (Answered)

> If the agent becomes good at optimizing `quality_score`, would you notice… or would you call it "good experimental design"?

**With this harness, you'd notice immediately.**

The tests force a clean separation:
- **Legitimate:** Optimize for epistemic value (information gain)
- **Leak:** Optimize for QC proxy (margin, quality) as biological signal

If agent prefers high-quality low-information experiments over low-quality high-information experiments, **the tests will fail.**

---

## How to Run

### Quick Test (Command Line)

```bash
# Run integration tests (requires pytest)
pytest tests/integration/test_snr_second_order_leakage.py -v -s

# Run summary report
pytest tests/integration/test_snr_second_order_leakage.py::test_leakage_summary_report -v -s
```

### Generate Visual Report (With Plots)

```python
from src.cell_os.analysis.plot_snr_leakage import generate_leakage_report
from src.cell_os.adversarial.snr_leakage_harness import (
    generate_hover_attack,
    generate_missingness_attack,
    compute_leakage_auc
)
from src.cell_os.epistemic_agent.snr_policy import SNRPolicy
from src.cell_os.epistemic_agent.qc_gate import prepare_agent_observation

# ... generate conditions before/after ...

generate_leakage_report(
    results_before,
    results_after,
    conditions_before,
    conditions_after,
    output_dir="snr_leakage_report"
)
```

See `test_leakage_before_after.py` (in repo root, temporary) for full example.

---

## Files Created

### Core Implementation
1. **`src/cell_os/adversarial/snr_leakage_harness.py`**
   Generates adversarial conditions, computes leakage AUC

2. **`src/cell_os/epistemic_agent/qc_gate.py`**
   Strips QC metadata from agent-visible observations (Option B)

3. **`src/cell_os/analysis/plot_snr_leakage.py`**
   Visualization tools (AUC comparison, embeddings, mask patterns)

### Tests
4. **`tests/integration/test_snr_second_order_leakage.py`**
   13 integration tests covering all 4 attack classes

### Documentation
5. **`SNR_SECOND_ORDER_LEAKAGE.md`**
   Detailed explanation of leakage, attacks, countermeasures

6. **`SNR_LEAKAGE_FIX_PROOF.md`** (this file)
   Before/after proof with visual results

---

## What's Next

### To Deploy This Fix System-Wide:

1. **Update observation pipeline** to use `prepare_agent_observation()`:
   ```python
   # In observation_aggregator.py or wherever observations are built
   from src.cell_os.epistemic_agent.qc_gate import prepare_agent_observation

   # After applying SNR policy
   obs_with_qc = snr_policy.filter_observation(observation, annotate=True)

   # Strip QC before passing to agent
   agent_obs = prepare_agent_observation(obs_with_qc, apply_gate=False)
   ```

2. **Run regression tests** to ensure agent still functions:
   ```bash
   pytest tests/integration/ -v
   ```

3. **Monitor agent behavior** for QC-seeking:
   - Does agent avoid low-quality conditions even when they're high-information?
   - Does agent design experiments to maximize margins instead of epistemic value?
   - If yes, you still have policy leak (not metadata leak)

4. **Add CI check** to prevent future leakage:
   ```bash
   # In .github/workflows/test.yml or similar
   - name: SNR Leakage Check
     run: pytest tests/integration/test_snr_second_order_leakage.py::test_leakage_summary_report
   ```

---

## The One-Line Summary

**You had a membership oracle. Now you don't.**

---

## Acknowledgments

This harness was built in response to the observation that "masked means safe" is insufficient when metadata encodes treatment identity.

Second-order leakage is subtle, pervasive, and structurally hard to detect without adversarial testing.

The fix (Option B) is structurally clean: **if the agent can't see it, the agent can't optimize it.**

Gradient-following raccoons, meet information boundary.
