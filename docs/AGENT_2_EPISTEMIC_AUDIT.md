# Agent 2: Epistemic Discipline and Uncertainty Accounting - Audit

**Mission**: Audit how the system represents uncertainty, earns confidence, and refuses action.
**Goal**: Make it harder to lie to itself.

**Status**: Phase 1 - Inventory (No Code Changes)

---

## Phase 1: Deliverable 1.1 - Confidence Map

### Confidence Creation Points

#### 1. MechanismPosterior (mechanism_posterior_v2.py)

**Location**: `compute_mechanism_posterior_v2()` (lines 157-348)

**What it creates**:
- `probabilities`: Dict[Mechanism, float] - Posterior distribution over mechanisms
- `calibrated_confidence`: Optional[float] - Learned P(correct | features)
- `nuisance_probability`: float - P(NUISANCE | observation)

**Nature**: Probabilistic (Bayesian posterior from multivariate normal likelihoods)

**Uncertainty attached**: Yes - full probability distribution over mechanisms

**Can it decrease**:
- **Probabilities**: YES - new evidence can flatten posterior (Agent 2 ambiguity capping also forces decrease)
- **calibrated_confidence**: YES - learned from data, can change
- **nuisance_probability**: YES - depends on nuisance model (mean shifts + variance inflation)

**Issues**:
- ✅ Agent 2 ambiguity capping (lines 229-260): Forces confidence down when `likelihood_gap < GAP_CLEAR`
- ✅ `uncertainty` metric explicit (line 263-266): Monotonic with gap
- ⚠️ **MONOTONICITY TRAP**: `nuisance_probability` only computed once per observation. If nuisance model doesn't update, this can only increase or stay constant within a trajectory. No decay mechanism.

#### 2. BeliefState Gates (beliefs/state.py)

**Location**: Multiple gate fields (lines 111, 122-132)

**What it creates**:
- `noise_sigma_stable`: bool - Noise gate (rel_width ≤ 0.25)
- `ldh_sigma_stable`: bool - LDH assay gate
- `cell_paint_sigma_stable`: bool - Cell Painting gate
- `scrna_sigma_stable`: bool - scRNA gate
- `edge_effect_confident`: bool - Edge effects detected

**Nature**: Categorical (boolean thresholds on continuous metrics)

**Uncertainty attached**: YES - underlying metrics (rel_width, df) tracked

**Can it decrease**:
- **YES** - Gates have explicit loss logic (lines 425-479)
- Hysteresis: enter_threshold=0.25, exit_threshold=0.40
- Drift detection: gate lost if drift_metric ≥ 0.20
- **GOOD**: Symmetric gate_event/gate_loss events emitted

**Issues**:
- ✅ Decreasable confidence (gates can be revoked)
- ✅ Provenance for loss (gate_loss events with evidence)
- ⚠️ **SEQUENTIAL REQUIREMENT**: `noise_gate_streak` (line 116) requires K=3 consecutive stable observations to earn gate. This is GOOD (prevents one lucky batch) but creates asymmetry: earning is harder than losing.

#### 3. BeliefState Calibration Entropy (beliefs/state.py)

**Location**: `calibration_entropy_bits` property (lines 1269-1340)

**What it creates**:
- Heuristic entropy from calibration state (0-11 bits range)

**Nature**: Heuristic (rule-based, not probabilistic)

**Uncertainty attached**: Compositional (sum of component entropies)

**Can it decrease**:
- **YES** - Monotonically decreases as gates are earned
- Compounds: 2.0 → 1.0 → 0.5 (as tested count increases)
- Noise: 2.0 → 0.1 (as gate stabilizes)
- Assays: 3.0 bits available (1.0 per ungated assay)

**Issues**:
- ✅ Decreasable
- ⚠️ **CONFLATION RISK**: Named `entropy` (line 1343) - same name as mechanism_entropy_bits. Docstring warns against conflation but naming is dangerous.
- ⚠️ **HEURISTIC, NOT PROBABILISTIC**: Not derived from information theory, just sum of rule-based components.

#### 4. BeliefState Expected Gain (beliefs/state.py)

**Location**: `estimate_expected_gain()` (lines 1352-1430)

**What it creates**:
- Expected information gain estimate (bits)

**Nature**: Heuristic (template-based rules)

**Uncertainty attached**: No - returns scalar, no variance

**Can it decrease**:
- **NO** - Monotonic within a given call
- Changes between calls depend on belief state
- ⚠️ **MONOTONICITY TRAP**: Once gates are earned, expected gain from calibration decreases (0.1 bits) but never reverts to high value even if gate is lost later (line 1388 fallback is permanent)

**Issues**:
- ❌ No representation of uncertainty about expected gain
- ❌ No confidence decay mechanism
- ⚠️ Inconsistent with actual realized gain (epistemic debt shows overclaiming is common)

#### 5. GovernanceContract (governance/contract.py)

**Location**: `decide_governance()` (lines 72-148)

**What it creates**:
- `GovernanceAction`: COMMIT | NO_COMMIT | NO_DETECTION
- Blocker set: LOW_POSTERIOR_TOP | HIGH_NUISANCE | BAD_INPUT

**Nature**: Categorical (threshold-based decision)

**Uncertainty attached**: Yes - references input posteriors and thresholds

**Can it decrease**:
- **N/A** - Stateless function (no memory)
- Each call is independent

**Issues**:
- ✅ Pure function, deterministic
- ✅ Explicit blocker reasons
- ⚠️ **THRESHOLD BRITTLENESS**: `commit_posterior_min=0.80` is fixed. No hysteresis for commitment (can flip between COMMIT/NO_COMMIT on small posterior changes).

---

### Confidence Modification Points

#### 1. Ambiguity Capping (mechanism_posterior_v2.py)

**Location**: Lines 242-260

**Modification**:
- If `is_ambiguous` (gap < 0.15), cap `MAX_PROB_AMBIGUOUS = 0.75`
- Redistributes excess probability to other mechanisms

**Epistemic justification**: When mechanisms are similar in morphology space, high confidence is unjustified.

**Can revert**: YES - next observation with clearer separation can restore high confidence

**Issues**:
- ✅ Decreases confidence when appropriate
- ✅ Ambiguity explicitly represented (`is_ambiguous`, `uncertainty`, `likelihood_gap` fields)
- ✅ Guardrail enforced (line 332-334): Prevents reintroduction of dishonesty

#### 2. Calibrated Confidence Learning (mechanism_posterior_v2.py)

**Location**: `calibrate_confidence()` (lines 476-530)

**Modification**:
- Learns mapping from features → P(correct) via isotonic regression or Platt scaling
- Overwrites `calibrated_confidence` field

**Epistemic justification**: Raw posterior probabilities are not calibrated to actual accuracy

**Can revert**: YES - retraining on new data can change calibration

**Issues**:
- ⚠️ **USAGE UNCLEAR**: Function exists but no evidence of it being called in live code (chooser.py, loop.py don't reference it)
- ⚠️ **FEATURE OBSOLESCENCE**: Uses `nuisance.nuisance_fraction` (line 507) which is DEPRECATED (line 149-154 in mechanism_posterior_v2.py). Will crash if called.
- ❌ Not currently enforced in the system

#### 3. Epistemic Debt Accumulation (epistemic_control.py)

**Location**: `resolve_action()` (lines 237-308)

**Modification**:
- Compares claimed gain vs realized gain
- Accumulates debt (overclaim penalty)
- Applies sandbagging discount (lines 272-290): If agent systematically underclaims, future surprising gains are discounted

**Epistemic justification**: Agent must be honest about expected gains

**Can revert**: YES - debt can be repaid via calibration (lines 436-497)

**Issues**:
- ✅ Decreasable (debt repayment exists)
- ⚠️ **ASYMMETRIC RECOVERY**: Calibration inflation is capped at 1.5× (Agent 3 fix) to prevent deadlock, but this means debt accumulation can be faster than repayment
- ⚠️ **SANDBAGGING DISCOUNT**: `sandbagging_detector` (lines 273-287) prevents gaming via systematic underclaiming. Good, but adds complexity.

#### 4. Gate Revocation (beliefs/state.py)

**Location**: Lines 906-915 (noise gate), similar logic for assay gates

**Modification**:
- If `rel_width ≥ exit_threshold` or `drift_metric ≥ drift_threshold`, gate revoked
- `noise_sigma_stable`: True → False

**Epistemic justification**: Calibration degrades over time (drift, variance inflation)

**Can revert**: YES - recalibration can re-earn gate

**Issues**:
- ✅ Confidence explicitly decreases
- ✅ Provenance via gate_loss events
- ⚠️ **ASSYMETRIC EARNING**: K=3 consecutive stable observations required to EARN, but single violation triggers LOSS. This is conservative (good for safety) but may create churn.

---

### Confidence Consumption Points

#### 1. Template Selection (acquisition/chooser.py)

**Location**: `choose_next()` (lines 628-973)

**What it consumes**:
- `beliefs.noise_sigma_stable` (line 709)
- `beliefs.ldh_sigma_stable`, `beliefs.cell_paint_sigma_stable` (lines 849-924)
- `beliefs.epistemic_insolvent` (line 655)
- Gate states via `_required_gates_for_template()` (line 367)

**Decision impact**: Forces calibration if gates not earned, blocks biology templates

**Issues**:
- ✅ Gates are hard constraints (cannot be bypassed)
- ⚠️ **NO CONFIDENCE GRADIENT**: Decision is binary (gate earned or not). No "soft" selection based on confidence level.
- ⚠️ **EXPENSIVE CALIBRATION BACKDOOR**: `allow_expensive_calibration` flag (line 633) can bypass policy validation (line 403). This is a manual override but creates governance hole.

#### 2. Mechanism Commitment (governance/contract.py)

**Location**: `decide_governance()` (lines 72-148)

**What it consumes**:
- `posterior` (top mechanism probability)
- `nuisance_prob`
- `evidence_strength`

**Decision impact**: COMMIT only if `top_p ≥ 0.80` AND `nuisance ≤ 0.35`

**Issues**:
- ✅ Confidence threshold enforced
- ❌ **NO AMBIGUITY AWARENESS**: GovernanceInputs (line 28-40) does not include `is_ambiguous` or `likelihood_gap` from Agent 2. Ambiguous posteriors could still commit if they meet thresholds.
- ❌ **NO HYSTERESIS**: Commitment can flip on small posterior changes near threshold.

#### 3. Epistemic Debt Refusal (epistemic_control.py)

**Location**: `should_refuse_action()` (lines 499-595)

**What it consumes**:
- `total_debt` (line 534)
- `debt_hard_threshold` (line 504, typically 2.0 bits)
- `is_calibration` flag (line 532)

**Decision impact**: Blocks non-calibration actions if debt > threshold

**Issues**:
- ✅ Hard block enforced
- ✅ Agent 3 deadlock fix (capped calibration inflation)
- ⚠️ **THRESHOLD BRITTLENESS**: 2.0 bits is fixed. No evidence this value is principled (chosen heuristically).

#### 4. Information Gain Estimation (beliefs/state.py → loop.py)

**Location**: `estimate_expected_gain()` called in loop.py:247

**What it consumes**:
- `template_name`
- `n_wells`
- `modalities`
- Belief state (gates, tested compounds, etc.)

**Decision impact**: Used for epistemic debt claim (line 254 in loop.py)

**Issues**:
- ⚠️ **OVERCONFIDENT BY CONSTRUCTION**: Returns scalar expected gain with no variance. Agent claims this value with certainty.
- ❌ **NO CONFIDENCE DECAY**: Expected gain heuristics don't degrade over time even if evidence contradicts them.
- ❌ **SYSTEMATIC OVERCLAIMING**: Epistemic debt accumulation (refusal logs) shows agent consistently overclaims. Expected gain estimates are too optimistic.

---

## Summary of Findings

### Confidence Sources by Type

| Source | Probabilistic | Heuristic | Categorical |
|--------|--------------|-----------|-------------|
| MechanismPosterior.probabilities | ✅ | | |
| MechanismPosterior.nuisance_probability | ✅ | | |
| BeliefState gates | | | ✅ |
| BeliefState.calibration_entropy_bits | | ✅ | |
| BeliefState.estimate_expected_gain | | ✅ | |
| GovernanceDecision | | | ✅ |

### Decreasability

| Confidence Type | Can Decrease? | Evidence |
|-----------------|---------------|----------|
| Mechanism posterior probabilities | ✅ YES | New evidence, ambiguity capping |
| Nuisance probability | ⚠️ PARTIAL | Depends on nuisance model updates (rare) |
| Gate states | ✅ YES | Gate loss events with hysteresis |
| Calibration entropy | ✅ YES | Monotonic with gate earning |
| Expected gain | ❌ NO | Heuristic rules, no decay mechanism |
| Calibrated confidence | ✅ YES (UNUSED) | Would change with retraining, but never called |

### Critical Issues Identified

1. **Expected Gain Overconfidence** (Phase 2 target)
   - File: `beliefs/state.py:1352-1430`
   - Issue: Heuristic returns scalar with no uncertainty, systematically overclaims
   - Evidence: Epistemic debt logs show consistent overclaiming
   - Fix: Add confidence intervals or variance estimates

2. **Governance Ambiguity Blindness** (Phase 2 target)
   - File: `governance/contract.py:28-40`
   - Issue: GovernanceInputs lacks `is_ambiguous` field from Agent 2 posterior
   - Evidence: Ambiguous posteriors (gap < 0.15) can still commit if top_p > 0.80
   - Fix: Add ambiguity field to GovernanceInputs, block commit if ambiguous

3. **Calibrated Confidence Unused** (Phase 4 candidate)
   - File: `mechanism_posterior_v2.py:476-530`
   - Issue: `calibrate_confidence()` exists but never called, uses deprecated field
   - Evidence: No references in chooser.py or loop.py
   - Fix: Remove or fix + integrate into live code

4. **No Confidence Decay** (Phase 3 contract)
   - Multiple locations (expected gain, calibration entropy heuristics)
   - Issue: Confidence estimates don't weaken with age or contradiction
   - Fix: Contract 3.1 - Confidence Must Be Decreasable (with time component)

---

## Phase 1: Deliverable 1.2 - Uncertainty Collapse Audit

### Collapse Point 1: Posterior → argmax (mechanism_posterior_v2.py)

**Location**: Properties `top_mechanism` (line 383) and `top_probability` (line 387)

**What collapses**:
- Full posterior distribution Dict[Mechanism, float]
- Collapsed to: single mechanism + single probability

**Why collapse happens**:
- API convenience: agents need "what to do" not "full distribution"
- Governance contract needs top mechanism for COMMIT decision

**Epistemically justified**: ⚠️ PARTIALLY
- `top_probability` preserves some uncertainty information
- BUT: margin (gap to 2nd place) is lost unless explicitly requested
- `is_ambiguous` flag (Agent 2) partially compensates

**Evidence of harm**:
- If mechanisms have similar probabilities (e.g., 0.42, 0.38, 0.20), argmax picks 0.42 but destroys information that this is ambiguous
- Agent 2 ambiguity capping mitigates this by capping at 0.75, but information is still lost

**Fix**: Property should return (mechanism, probability, margin) tuple, or raise if ambiguous

---

### Collapse Point 2: Pooled Variance → Scalar Sigma (beliefs/state.py)

**Location**: `_update_noise_beliefs()` (lines 798-967)

**What collapses**:
- Per-condition variances (each DMSO replicate group)
- Per-channel variances (actin, mito, ER, etc.)
- Collapsed to: `noise_sigma_hat` (single scalar), `noise_rel_width` (single scalar)

**Why collapse happens**:
- Pooling increases statistical power (more df)
- Chi-square CI on pooled variance is more stable

**Epistemically justified**: ✅ YES
- Pooling is statistically valid (assumes homoskedasticity)
- Uncertainty preserved: `noise_ci_low`, `noise_ci_high`, `noise_rel_width` all tracked
- Per-cycle history maintained: `noise_sigma_cycle_history` (line 855)

**Evidence of harm**: NONE (good collapse)

---

### Collapse Point 3: Continuous Rel-Width → Boolean Gate (beliefs/state.py)

**Location**: Gate decision logic (lines 868-944)

**What collapses**:
- `noise_rel_width`: continuous metric [0, ∞)
- `noise_drift_metric`: continuous metric [0, ∞)
- Collapsed to: `noise_sigma_stable`: boolean {True, False}

**Why collapse happens**:
- Policy needs binary decision ("can I do biology?")
- Hysteresis prevents churn (enter=0.25, exit=0.40)

**Epistemically justified**: ⚠️ PARTIALLY
- Threshold is heuristic (0.25 not derived from information theory)
- Hysteresis is good (prevents flip-flopping)
- BUT: Loses graded information (rel_width=0.26 vs 0.39 both "not stable")
- K-sequential requirement (line 898) adds robustness but increases asymmetry

**Evidence of harm**:
- Near-threshold behavior: agent treats rel_width=0.24 and rel_width=0.10 identically (both "stable")
- No "confidence in gate" metric (boolean hides how far from threshold)

**Fix**: Add confidence gradient: `gate_confidence_distance = (exit_threshold - rel_width) / (exit_threshold - enter_threshold)` ∈ [0, 1]

---

### Collapse Point 4: Expected Gain Heuristics → Scalar (beliefs/state.py)

**Location**: `estimate_expected_gain()` (lines 1352-1430)

**What collapses**:
- Multiple sources of uncertainty:
  - How much will noise CI shrink? (depends on df, current rel_width)
  - Will edge test actually detect edges? (depends on effect size)
  - Will compound be interesting? (depends on mechanism diversity)
- Collapsed to: single scalar "expected gain" in bits

**Why collapse happens**:
- Epistemic debt system needs scalar claim for comparison
- No infrastructure for distributional claims

**Epistemically justified**: ❌ NO
- Heuristic rules (e.g., "first compound = 1.0 bits", line 1401) have no theoretical foundation
- No variance estimate
- No confidence intervals
- Systematically overconfident (epistemic debt logs show overclaiming)

**Evidence of harm**:
- Refusal logs (from Agent 3 debt enforcement) show consistent overclaiming
- Agent claims 0.8 bits for calibration (line 1382) but often realizes ~0.3 bits
- No mechanism to revise estimates based on past prediction errors

**Fix**: Return (mean, variance) or (lower_bound, expected, upper_bound) from expected gain

---

### Collapse Point 5: Multi-Source Nuisance → Single Probability (mechanism_posterior_v2.py)

**Location**: `NuisanceModel.total_var_inflation` (lines 126-134)

**What collapses**:
- `artifact_var` (temporal plating)
- `heterogeneity_var` (biological subpopulations)
- `context_var` (reagent lot, instrument drift)
- `pipeline_var` (segmentation bias)
- `contact_var` (contact pressure model mismatch)
- Collapsed to: single `total_var_inflation` scalar

**Why collapse happens**:
- Multivariate normal likelihood P(x | NUISANCE) needs single covariance
- Additive variance model (Σ = I × total_var_inflation)

**Epistemically justified**: ⚠️ PARTIALLY
- Mathematically sound (variances add for independent sources)
- BUT: Assumes independence (artifact_var and heterogeneity_var may correlate)
- Isotropic assumption (affects all channels equally) may be wrong

**Evidence of harm**:
- Nuisance inflation is isotropic (line 206: `cov_nuis = np.eye(3) * ...`)
- Real nuisance may be anisotropic (e.g., ER channel more sensitive to context than actin)
- Loses information about which nuisance source dominates

**Fix**: Track per-source nuisance probabilities, or at minimum distinguish heterogeneity from non-biological nuisance

---

### Collapse Point 6: Mechanism Likelihoods → Posterior (mechanism_posterior_v2.py)

**Location**: Bayes rule normalization (lines 217-227)

**What collapses**:
- Likelihood values for each mechanism (scale-dependent)
- Collapsed to: normalized posterior probabilities (sum to 1)

**Why collapse happens**:
- Bayes rule requires normalization: P(m|x) = P(x|m)P(m) / Σ P(x|m')P(m')
- Posteriors must be probabilities (sum to 1)

**Epistemically justified**: ✅ YES
- Mathematically correct (Bayes rule)
- Likelihood values (absolute scale) preserved in `likelihood_scores` dict (line 339)
- Agent 2 `likelihood_gap` (line 236) preserves information about separation

**Evidence of harm**: NONE (necessary collapse)

---

### Collapse Point 7: Evidence Distributions → Template Selection (chooser.py)

**Location**: `choose_next()` scoring logic (lines 628-973)

**What collapses**:
- Belief state (gates, entropy, tested compounds, debt)
- Budget constraints
- Template affordability
- Collapsed to: single selected template name + kwargs

**Why collapse happens**:
- System must execute one experiment at a time
- Decision must be made

**Epistemically justified**: ⚠️ PARTIALLY
- Selection logic is deterministic rule-based (no scoring function for "best" template)
- Prioritization: calibration > edge test > biology (lines 806-845)
- BUT: No representation of "confidence in template choice"
- No counterfactual tracking ("what would have been 2nd best?")

**Evidence of harm**:
- DecisionEvent (line 137-156) does not track candidate templates with scores
- Cannot answer: "Was this a clear choice or marginal?"
- Cannot learn from template selection mistakes (no feedback loop)

**Fix**: Add `candidates` list with scores to DecisionEvent (already exists in schema, line 140, but not populated)

---

### Collapse Point 8: Calibration Events → ECE (mechanism_posterior_v2.py)

**Location**: `compute_ece()` (lines 790-851)

**What collapses**:
- List[CalibrationEvent] (confidence, correct pairs)
- Binned by confidence ([0-0.1], [0.1-0.2], ..., [0.9-1.0])
- Collapsed to: single ECE scalar ∈ [0, 1]

**Why collapse happens**:
- ECE is a summary metric for calibration quality
- Single number is easier to threshold/alert on

**Epistemically justified**: ✅ YES
- Standard calibration metric (widely used)
- Binning preserves structure (not just mean)
- Full event history available via `tracker.events` if needed

**Evidence of harm**: NONE (good collapse, purpose-built metric)

---

### Collapse Point 9: Thresholds Without Hysteresis (governance/contract.py)

**Location**: Governance thresholds (lines 44-54), decision logic (lines 72-148)

**What collapses**:
- Continuous posterior probability [0, 1]
- Continuous nuisance probability [0, 1]
- Collapsed to: categorical decision {COMMIT, NO_COMMIT, NO_DETECTION}

**Why collapse happens**:
- System needs binary commitment decision
- No "partial commit" semantics

**Epistemically justified**: ❌ NO
- **NO HYSTERESIS**: Can flip between COMMIT/NO_COMMIT on arbitrarily small posterior changes
- If posterior oscillates around 0.80 threshold: commit, no_commit, commit, no_commit...
- Contrast with gate logic (BeliefState) which has explicit hysteresis (enter=0.25, exit=0.40)

**Evidence of harm**:
- Brittle decision boundary
- No "confidence in commitment" metric
- Cannot answer: "How sure are we about this COMMIT?"

**Fix**: Add hysteresis: commit_enter=0.80, commit_exit=0.75. Once committed, require posterior < 0.75 to revoke.

---

## Summary: Collapse Audit

| Collapse | Location | Justified? | Harm Evidence | Fix Priority |
|----------|----------|------------|---------------|--------------|
| Posterior → argmax | mechanism_posterior_v2.py:383 | ⚠️ Partial | Ambiguity info lost | Medium |
| Pooled variance → sigma | beliefs/state.py:834 | ✅ Yes | None | N/A |
| Rel-width → gate boolean | beliefs/state.py:889 | ⚠️ Partial | Graded confidence lost | Low |
| Expected gain heuristics → scalar | beliefs/state.py:1372 | ❌ No | Systematic overclaiming | **HIGH** |
| Multi-source nuisance → total | mechanism_posterior_v2.py:126 | ⚠️ Partial | Source attribution lost | Medium |
| Likelihoods → posterior | mechanism_posterior_v2.py:217 | ✅ Yes | None | N/A |
| Belief state → template | chooser.py:944 | ⚠️ Partial | No candidate ranking | Medium |
| Events → ECE | mechanism_posterior_v2.py:790 | ✅ Yes | None | N/A |
| Posterior → commit (no hysteresis) | governance/contract.py:109 | ❌ No | Decision flip-flopping | **HIGH** |

### Critical Findings

1. **Expected Gain Overconfidence** (Priority 1)
   - No uncertainty representation
   - Systematically overclaims (proven by debt accumulation)
   - Fix: Add variance estimates or confidence intervals

2. **Governance Commitment Brittleness** (Priority 1)
   - No hysteresis in commit decision
   - Can flip on arbitrarily small posterior changes
   - Fix: Add enter/exit thresholds with hysteresis

3. **Argmax Information Loss** (Priority 2)
   - Top mechanism selected without margin information
   - Ambiguity flag helps but not integrated into governance
   - Fix: Add margin to GovernanceInputs

---

## Next Steps

**Phase 2**: Reproduce failure modes
- Scenario A: Overconfident mechanism posterior (find or construct)
- Scenario B: Debt deadlock (construct with Agent 3 tests as starting point)

**Phase 3**: Define epistemic contracts
- Contract 3.1: Confidence Must Be Decreasable (add decay mechanisms)
- Contract 3.2: Ambiguity Must Be Representable (integrate into governance)
- Contract 3.3: Debt Must Be Repayable (already addressed by Agent 3, verify robustness)

**Phase 4**: Choose ≤2 minimal interventions (≤300 LOC)
- Option A: Posterior uncertainty quantification (already partially done by Agent 2)
- Option B: Debt repayment path (already done by Agent 3, verify)
- Option C: Confidence decay (NEW - add time-based or contradiction-based decay)

**Phase 5**: Write tests that fail
- Overconfidence detection
- Ambiguity handling
- Debt recoverability
