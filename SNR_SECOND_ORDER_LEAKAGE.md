# SNR Second-Order Leakage: Red Team Documentation

## What is Second-Order Leakage?

**First-order leakage** is when the agent learns from raw, unmasked measurements below the noise floor (e.g., reading `feature_means["er"] = 0.28` when the threshold is 0.30).

**Second-order leakage** is when the agent learns from *metadata about masking* instead of the masked values themselves. Even when dim channels are properly masked (set to `None`), the agent can still extract treatment information from:

- **Missingness patterns**: `usable_channels`, `masked_channels`, `n_usable`
- **Quality metrics**: `quality_score`, `min_margin`, `min_margin_sigma`
- **Threshold proximity**: How close signals are to `floor + kσ`
- **Spatial patterns**: Edge vs center masking rates due to vignette

## The Four Attack Classes

### 1. Hover Attacks (Threshold-Edge Gaming)

**What it tests:** Can the agent extract directional effects from signals that hover just above or below the threshold?

**Design:**
- All treatments have **IDENTICAL true morphology**
- Signals sit at `floor + (kσ ± ε)` where `ε` is tiny (e.g., 1% of typical signal)
- Some treatments have signals just below threshold, others just above

**What leakage looks like:**
- Agent becomes confident about treatment differences based solely on which channels cleared the threshold
- Agent learns to trust signals from the "barely usable" sliver above threshold

**Countermeasure if failing:**
- Require meaningful margin across **multiple channels** before allowing belief updates
- Don't treat "threshold + 1 LSB" as trustworthy evidence
- Demand consistency: effect should clear threshold in correlated channels, not single channels

---

### 2. Missingness-as-Signal Attacks

**What it tests:** Can the agent predict treatments from the *pattern of which channels are masked*?

**Design:**
- All treatments have **IDENTICAL true morphology** (e.g., null effect)
- Treatment A: All channels bright → `quality_score = 1.0`
- Treatment B: Half channels masked → `quality_score = 0.6`
- Treatment C: All channels dim → `quality_score = 0.0`

**What leakage looks like:**
- Agent classifies treatments based on `usable_channels` or `quality_score`
- Agent uses missingness metadata as a phenotype surrogate

**Countermeasure if failing:**
- Treat missingness as **QC metadata only**, not reward or evidence
- Explicitly randomize or obscure QC summaries at decision time
- Force agent to ignore `quality_score` as a biological signal

---

### 3. QC Proxy Optimization Attacks

**What it tests:** Does the agent optimize measurement quality instead of biological interest?

**Design:**
- All treatments have **IDENTICAL true morphology**
- Treatment A: Minimal margins (signals barely above threshold)
- Treatment B: Comfortable margins (signals well above threshold)
- Treatment C: Huge margins (signals far above threshold)

**What leakage looks like:**
- Agent prefers high-margin treatments (B or C) over low-margin treatments (A)
- Agent treats `min_margin` or `min_margin_sigma` as a reward proxy
- Agent becomes a "measurement optimizer" instead of a scientist

**Countermeasure if failing:**
- Value **information gain conditional on QC**, not QC itself
- QC is a **gate** (pass/fail), not a **prize**
- Explicitly penalize proposals that optimize margins without epistemic justification

---

### 4. Spatial Confounding Attacks

**What it tests:** Does the agent learn "edge is bad" from systematic masking differences?

**Design:**
- All treatments have **IDENTICAL true morphology**
- Center wells: Full signal, all channels usable
- Edge wells: Attenuated by vignette (15% dimmer), some channels masked

**What leakage looks like:**
- Agent avoids edge wells even when the design demands spatial balance
- Agent learns a policy leak: "edge wells are low quality, avoid them"

**Countermeasure if failing:**
- Enforce **balanced spatial allocation** in proposals
- Normalize QC metrics by expected vignette-corrected distribution
- Explicitly budget edge/center wells separately

---

## What Passing These Tests Proves

**If all tests pass (AUC < 0.6):**
- Agent **cannot** predict treatments from QC metadata alone
- Masking is effective at preventing learning from sub-noise regimes
- Agent treats QC as a gate, not a reward

**If tests pass TODAY, that does NOT prove:**
- Agent will never learn to exploit these channels in the future
- Agent's decision logic is correct (only that it's not exploiting this particular leak)
- There are no other second-order leakage channels we haven't tested

---

## What Failing These Tests Means

**If any test fails (AUC ≥ 0.6):**
- Agent **CAN** extract treatment information from QC metadata
- Agent has learned to use missingness, margins, or quality scores as phenotype surrogates
- System is vulnerable to measurement optimization instead of scientific optimization

**What you must do:**
1. **Identify the leak:** Which QC field(s) enable classification?
2. **Patch the agent:** Modify decision logic to treat QC as gate, not reward
3. **Re-run tests:** Verify that AUC drops below threshold
4. **Add regression test:** Ensure future changes don't reintroduce leak

---

## The Uncomfortable Question

**If the agent becomes good at optimizing `quality_score`, would you notice… or would you call it "good experimental design"?**

This is the hardest part. Some optimization is legitimate:
- "I should use brighter conditions because they're more reliable" → **OK**
- "I should design experiments to maximize expected SNR" → **OK**
- "I should prefer treatments with high `quality_score`" → **NOT OK**

The difference:
- **Legitimate:** Optimize for epistemic value (information gain)
- **Leak:** Optimize for QC proxy (margin, quality) as a biological signal

**How to tell:**
1. Generate two proposals: one with high epistemic value but low margins, one with low epistemic value but high margins
2. See which the agent prefers
3. If agent prefers high-margin low-information, you have a leak

---

## Thresholds and Tuning

**Current thresholds:**
- Hover, Missingness, QC Proxy: `AUC < 0.6` (strict)
- Spatial: `AUC < 0.75` (moderate, some leakage tolerated)

**Why 0.6?**
- Random classifier: AUC = 0.5
- Slightly-better-than-random: AUC = 0.55
- Meaningful classification: AUC ≥ 0.6
- Strong classification: AUC ≥ 0.7

**Why is spatial looser (0.75)?**
- Edge wells **ARE** systematically dimmer (vignette effect)
- Some QC difference is real and unavoidable
- The leak is not "edge is different" but "edge is bad"
- Agent should balance plates, not avoid edge

**Tuning guidance:**
- Start strict (AUC < 0.6)
- If tests fail, patch agent logic
- If tests are flaky (AUC hovers near 0.6), tighten threshold to 0.55
- If spatial is too loose, tighten to 0.7 and enforce balanced allocation

---

## Usage

### Running Tests

```bash
# Run all leakage tests
pytest tests/integration/test_snr_second_order_leakage.py -v -s

# Run specific attack class
pytest tests/integration/test_snr_second_order_leakage.py::test_hover_attack_identical_biology_different_margins -v -s

# Run summary report (all 4 attacks)
pytest tests/integration/test_snr_second_order_leakage.py::test_leakage_summary_report -v -s
```

### Generating Adversarial Conditions

```python
from cell_os.calibration.profile import CalibrationProfile
from cell_os.adversarial.snr_leakage_harness import (
    generate_hover_attack,
    generate_missingness_attack,
    compute_leakage_auc
)

profile = CalibrationProfile("calibration_report.json")

# Generate hover attack
hover_conditions = generate_hover_attack(profile, k=5.0, epsilon=0.01)

# Apply SNR policy
policy = SNRPolicy(profile, threshold_sigma=5.0, strict_mode=False)
filtered_conditions = []
for cond in hover_conditions:
    cond_dict = cond.to_condition_summary()
    obs = {"conditions": [cond_dict]}
    filtered = policy.filter_observation(obs, annotate=True, mask_dim_channels=True)
    filtered_conditions.append(filtered["conditions"][0])

# Check for leakage
auc = compute_leakage_auc(filtered_conditions, qc_features_only=True)
print(f"Leakage AUC: {auc:.3f}")
assert auc < 0.6, f"Leakage detected: {auc:.3f}"
```

---

## Implementation Notes

### Harness Design Principles

1. **Ground truth is known:** Each adversarial condition has `.true_morphology` field
2. **Identical biology, different QC:** The core invariant for all attacks
3. **Realistic signal values:** Use actual calibration profile to compute thresholds
4. **Machine-readable output:** All QC features are numeric (not just warning strings)

### Why AUC?

- **AUC = Area Under ROC Curve** (binary classification metric)
- Measures ability to rank treatments by likelihood
- Robust to class imbalance (works even with 2 vs 2 vs 2 treatments)
- Threshold-independent (doesn't depend on arbitrary cutoff)
- Interpretable: 0.5 = random, 1.0 = perfect

### Limitations of Current Tests

1. **Synthetic conditions:** Real agent loop may behave differently
2. **Small sample size:** Only 2-4 treatments per attack
3. **No temporal drift:** Doesn't test for margin decay over cycles
4. **No agent policy:** Tests QC metadata only, not agent's decision logic

Future work:
- Test with actual agent proposals (not synthetic conditions)
- Larger sample sizes (10+ treatments per attack)
- Temporal attacks (margin decay correlates with treatment)
- Policy-level tests (agent's allocation strategy, not just QC features)

---

## When to Re-Run These Tests

**Always:**
- After modifying SNR policy (threshold, masking logic)
- After changing QC metadata fields (adding new metrics)
- After updating belief update logic (how agent uses observations)

**Conditionally:**
- After agent performance improvements (check if they're measurement optimization)
- After adding new morphology channels (edge artifacts may change)
- After calibration profile changes (floor drift may affect thresholds)

**Never:**
- After unrelated changes (database, UI, hardware abstraction)
- After documentation updates
- After test infrastructure changes (unless they affect this test)

---

## Summary

**These tests answer:** Can the agent cheat by reading QC metadata instead of biology?

**Passing means:** Agent respects the masking boundary. QC is a gate, not a signal.

**Failing means:** Agent is optimizing measurement quality, not scientific insight.

**The real test:** When agent gets good at "experimental design," is it designing for epistemic value or QC scores? Pick B. Force the system to answer in public.
