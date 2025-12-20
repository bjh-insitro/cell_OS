# Realism Priority Order: What Actually Changes Agent Behavior

**Date**: 2024-12-19
**Source**: Design review with experimentalist
**Question**: Which realism knobs matter vs theater?

---

## The Keystone Insight

> **If you do not fix heterogeneity, every other fix lies to you.**

Everything else only matters *after* you stop letting population averages masquerade as certainty.

---

## Priority Order (What Actually Changes Outcomes)

### 1. 🔴 Population Heterogeneity (KEYSTONE - Fix First)

**Why it's the highest damage failure**:

Current sim (Phase 5):
- Clean, smooth morphology trajectories
- Monotonic latent stress curves
- Narrow confidence intervals

Agent learns:
> "If the mean looks clean at 12h, I'm safe."

Real wells:
- Some cells at S≈0.7 (highly stressed)
- Some untouched
- Mean hides bimodal distribution

**Result**: Agent is not wrong, it's **overconfident because world is artificially unimodal**.

**Not a simulator realism issue. This is an epistemic geometry issue.**

**Fixes**:
- #1 Overconfident early classification
- #2 Death variance underestimation (variance emerges naturally from which subpopulation tips first)

**Without this**: Every other fix is cosmetic.

**Verdict**:
- ✔️ Real
- ✔️ Highest leverage
- ✔️ Fix first

---

### 2. ✅ Let Variance Emerge (Don't Bolt It On)

**Key insight**:
> Death variance is not random. It is conditional on hidden state.

**Wrong approach**: Add noise/CV inflation/dropout to deterministic model

**Right approach**: Add heterogeneity, variance falls out naturally
- Which subpopulation tips first?
- Fragile policies lose dominance without hacking penalties
- Beam search sees risk correctly

**Verdict**:
- ✔️ Real
- ❌ Do not fix separately
- ➡️ Emerges automatically from #1

---

### 3. 📊 Confidence Accounting for Mixture Width (Not Mean)

**This is a classifier change, not a biology change.**

Current: Confidence = separation margin between top two axes (scalar)

With heterogeneity: Confidence must reflect mixture width
- If subpopulations give conflicting signals, confidence collapses naturally
- Washout becomes risky earlier
- Beam search stops pruning "ugly but informative" paths

**Verdict**:
- ✔️ Real
- ➡️ Implement after #1

---

### 4. 🔗 History Dependence at Subpopulation Level

**The uncomfortable truth**:
> Order effects are fake in a homogeneous world and unavoidable in a heterogeneous one.

At 12-24h timescales:
- Order effects are **second-order** without heterogeneity
- Early pulse selectively damages sensitive subpopulation
- Late pulse hits skewed population → toxicity jumps nonlinearly

**If implemented now**: Agent learns order effects in fake, averaged way (overfits simulator quirks)

**If implemented after heterogeneity**: Emerges naturally

**Minimal future hook**:
- Stress history lowers thresholds for a subpopulation (not globally)

**Verdict**:
- ✔️ Real
- ❌ Not first-order without heterogeneity
- ➡️ Enable after #1

---

### 5. 🕒 Waste + Feed Tradeoffs (Multi-Day Only)

**At 48h**:
- Waste is low
- Late feeding rarely catastrophic
- Osmotic shock is edge-case

**At 96-120h**:
- Feeding becomes dominant intervention
- "Rescue feeds" absolutely kill experiments

**Minimal placeholder** (for later):
- Waste scalar
- Feeding reduces waste partially, not fully
- High waste + feed = transient stress spike

**Verdict**:
- ✔️ Real
- 🕒 Defer until multi-day policies

---

### 6. 🧊 Structured Assay Failures (Low Leverage)

**Affects**:
- Classifier calibration
- Uncertainty estimation quality

**Does NOT drive**:
- Catastrophic policy decisions (not yet)

**Important later. Not a blocker now.**

**Verdict**:
- ✔️ Real
- 🧊 Low leverage for Phase 5/6A

---

## What Changes Downstream (After Heterogeneity)

### Before (Current):
- Agent: "Mean looks clean at 12h → commit to washout"
- Confidence: 0.20 (based on axis separation)
- Beam search: Prunes alternatives with viability 0.82 ("too risky")

### After (With Heterogeneity):
- Agent: "Mean clean but mixture wide → uncertain"
- Confidence: 0.08 (mixture width collapses margin)
- Beam search: Prefers delayed commitment
- Smart early washout policies evaporate (half of them)
- Epistemic control becomes conservative in the **right** way

**That's when simulator stops being clever and starts being honest.**

---

## Implementation Order

### Phase 5/6A Realism (What Actually Matters):

1. **Population heterogeneity** (keystone)
   - 3-bucket subpopulation model
   - Make morphology and viability mixtures, not scalars

2. **Heterogeneity-driven variance** (emergent)
   - Do not add variance explicitly
   - Let it fall out from subpopulation dynamics

3. **Confidence accounting** (classifier change)
   - Reflect mixture width, not mean
   - Margin collapses when subpopulations disagree

4. **History dependence** (subpopulation-level)
   - Only after heterogeneity exists
   - Stress lowers thresholds for sensitive fraction

5. **Waste + feed** (multi-day only)
   - Only when going beyond 48h

**Everything else is theater until these are in.**

---

## The Test

After adding heterogeneity, re-run Phase 5 benchmarks:

**Expected changes**:
- Confidence margins collapse (0.20 → 0.08)
- Half of "smart" early washout policies disappear
- Beam search starts preferring delayed commitment
- Death variance increases (some runs over budget)
- Epistemic control looks conservative (correct behavior)

**If this doesn't happen**: Heterogeneity implementation is wrong.

---

## Next Step

Sketch **minimal heterogeneity implementation**:
- 3-bucket subpopulation model in `VesselState`
- ~50 lines of code
- 80% of benefit

Then:
1. Implement
2. Re-run Phase 5 benchmarks
3. Watch confidence collapse
4. Decide if explicit order-effect code even needed

---

## Credit

Design review and priority calibration: External experimentalist (2024-12-19).

**Key quote**:
> "Order effects are fake in a homogeneous world and unavoidable in a heterogeneous one."
