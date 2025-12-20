# Simulator Realism Gap: What Breaks Real Experiments

**Date**: 2024-12-19
**From**: External calibration by skeptical experimentalist
**Question**: Is the simulator useful as a stand-in for reality, or just impressive code?

---

## Current State

**Strong on**: Intrinsic cell biology under controlled conditions
- Latent stress dynamics (ER/mito/transport)
- Competing-risks death model
- Axis-specific compound effects
- Measurement noise and artifacts

**Weak on**: Extrinsic, boring, unfair, human-made things that dominate real lab outcomes

**The uncomfortable truth**:
> Right now, your simulator answers: "What happens if biology behaves according to my mental model?"
>
> The real world asks: "What happens when biology, materials, humans, and logistics collide badly?"

---

## What's Missing (Prioritized by Reality)

### 🔥 Critical (Would Add Now)

#### 1. Population Heterogeneity
**Current**: Single "average cell" per vessel, smooth dynamics, homogeneous response

**Reality**:
- Cell cycle phase heterogeneity dominates outcomes
- Subpopulations die early or late
- Rare resistant cells matter more than averages

**Minimal fix**: 3-5 subpopulations per vessel with different:
- Doubling times
- IC50 shifts
- Stress thresholds
- Asynchronous entry into death

**Why it matters**: Your noise washes out. Real variance persists and accumulates.

**Impact on epistemic control**:
- Classifier sees mixed signatures (some cells dead, some stressed, some fine)
- Death timing becomes stochastic at population level
- Smart policy needs to reason about "fraction at risk" not "average stress"

---

#### 2. Waste Accumulation (Lactate/Ammonia/pH)
**Current**: Nutrients (glucose/glutamine) deplete

**Reality**: Media becomes poison, not just depleted
- Lactate buildup
- Ammonia toxicity
- pH drift
- Osmolarity changes

**Minimal fix**: One scalar `waste_load` (0-1)
- Increases with viable cell metabolism
- Decays only on feed
- Affects growth rate, ER stress baseline, drug sensitivity

**Why it matters**:
- Feeding late can be worse than not feeding
- Creates "mysterious plate effects"
- Feed timing becomes non-trivial tradeoff

**Impact on epistemic control**:
- Feed interventions have non-monotonic effects
- Timing matters beyond just "expose longer"
- Budget constraint (interventions ≤2) becomes more interesting

---

#### 3. History-Dependent Stress Sensitivity
**Current**: Latent stress decays cleanly after washout

**Reality**: Cells remember insults
- Prior ER stress lowers future ER threshold
- Mito damage makes later insults lethal
- Microtubule hits destabilize future divisions

**Minimal fix**: Stress memory (slowly decaying modifier to thresholds or k_on, capped)

**Why it matters**:
- Washout is too clean biologically
- Reality is sticky
- Order effects and path dependence

**Impact on epistemic control**:
- Pulse timing becomes critical (early probe vs late probe different outcomes)
- Washout doesn't fully reset state
- Multi-day experiments have hysteresis

---

### ⚠️ Important (Would Add Soon)

#### 4. Effective Concentration Decay
**Current**: Dose constant until washout

**Reality**:
- Adsorption to plastic
- Degradation
- Precipitation
- Uptake and sequestration
- Protein binding

**Minimal fix**: `effective_concentration(t)` with exponential decay + vessel-dependent adsorption

**Why it matters**:
- Morphology may peak early, death lags
- Washout timing nontrivial (washing out degraded compound is wasteful)
- Time reshapes dose, not just accumulates stress

**Impact on epistemic control**:
- Probe timing optimal point shifts
- Late measurements may miss peak signature
- Dose-response curves become time-dependent

---

#### 5. Assays Fail in Structured Ways
**Current**: Random well failures (independent noise)

**Reality**: Failures correlated with stress, morphology, operator, timing
- Dead cells → segmentation fails nonlinearly
- High actin bundling → nuclei mis-segment
- Late imaging → photobleaching patterns

**Minimal fix**: Failure probability as function of stress level, confluence, morphology extremes

**Why it matters**:
- Selection bias
- Missing-not-at-random data
- Reinforces false conclusions

**Impact on epistemic control**:
- Classifier sees censored data (missing weak signatures more often)
- Confidence estimates wrong (missing data looks like "certain")
- Epistemic uncertainty underestimated

---

### 📋 Nice-to-Have (Future)

#### 6. Shared Environment State
**Current**: Vessels independent

**Reality**:
- Incubator gradients
- Edge effects correlate across plates
- Contamination spreads
- Day-level events

**Fix**: Shared environment state (temperature drift, CO₂, contamination spread)

**Why it matters**: Parallel experiments correlate, "bad days" exist

---

#### 7. Policy-Coupled Human Behavior
**Current**: Operator noise is statistical

**Reality**:
- Operators adapt mid-experiment
- Protocols drift
- Bad plates quietly re-run
- People feed differently when things look bad

**Fix**: Model operator behavior as function of observed state

**Why it matters**: Agent learns strategies that only work if humans behave like RNGs (they don't)

---

#### 8. Senescence and Passage Effects
**Current**: Indefinite proliferation until capped

**Reality**:
- Senescence
- Replicative exhaustion
- Passage-dependent fragility

**Fix**: Passage-dependent growth slowdown and death susceptibility

**Why it matters**: Long timelines or serial passaging

---

## The Three-Thing Threshold

If you add everything above, you'll drown.

If you add **three** things:
1. **Waste accumulation** (media becomes poison)
2. **Population heterogeneity** (variance persists)
3. **History-dependent stress sensitivity** (washout not clean)

You cross a real threshold.

**That's the point where an agent trained here will stop being clever and start being robust.**

---

## Missing Interaction Effects

The biggest realism gap is **interaction between layers**:
- Biology × media (waste changes drug sensitivity)
- Biology × plastic (adsorption changes effective dose)
- Biology × operator (human adapts to observations)
- Assay × stress × timing (failures correlated with biology)

Right now these are independent. In reality they compound.

---

## Questions for Prioritization

**From external reviewer**:
> Tell me what *kind of wrong conclusions* you're most worried about your system making, and I'll tell you which realism knobs matter and which are theater.

**My answer** (to be updated):

I'm most worried about:

1. **Overconfident early classification** (Phase 5)
   - Smart policy classifies at 12h with confidence margin
   - If real signatures are noisier due to population heterogeneity, confidence is wrong
   - Would lead to: premature washout, missed mechanism engagement

2. **Underestimating death variance** (Phase 6A)
   - Beam search prunes on viability < 0.80
   - If real death is stochastic at population level (some cells die, some don't), deterministic rollout is misleading
   - Would lead to: policies that violate 20% budget in practice

3. **Ignoring order effects** (Phase 6A)
   - Beam search explores sequences (dose, washout, re-dose)
   - If stress sensitization exists, early probe weakens cells for later measurements
   - Would lead to: multi-pulse strategies that look good in sim, fail in practice

4. **Missing feed tradeoffs** (Future multi-day)
   - Current: feeding almost always good (resets nutrients)
   - If waste accumulation matters, late feeds can be harmful
   - Would lead to: over-feeding strategies

5. **Treating assay failures as random** (Classifier training)
   - Missing-not-at-random creates systematic bias
   - Would lead to: classifier that's brittle on real censored data

**Which of these should I fix first?**

---

## Status

**Decision needed**: Which realism gaps matter for current Phase 5/6A use case?

Once prioritized, implement minimal fixes (not full realism).

The goal: robust policies that transfer to reality, not perfect simulation.
