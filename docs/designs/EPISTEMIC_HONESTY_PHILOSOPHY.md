# Epistemic Honesty: Design Philosophy

## Core Principle

**We are not building a model that explains cells.**
**We are building a world that refuses to lie about what it knows.**

This distinction matters because the end user is an autonomous agent that must act under uncertainty. If the simulator provides false certainty, the agent will learn behaviors that fail catastrophically in reality.

---

## What "Epistemic Honesty" Means

### 1. No Oracle Sensors

Every measurement modality must be fallible.

**Bad**: Imaging has lot/instrument drift, but scalars are magically immune
**Result**: Agent learns "always trust scalars when they disagree"
**Transfer**: Fails (real scalars also drift)

**Good**: Imaging and scalars **both** have correlated lot/instrument drift
**Result**: Agent learns "disagreement is ambiguous, must calibrate"
**Transfer**: Succeeds (agent has experienced correlated failure modes)

### 2. Disagreement is Data, Not Noise

When morphology says "dying" and LDH says "fine," that's not measurement error to average away.

It's one of:
- **Context curse**: Both wrong together (instrument shift affected both)
- **Modality-specific artifact**: One wrong, one right (reagent lot hit one modality)
- **Biology puzzle**: Both right, measuring different things (detachment vs lysis)

The agent must reason about **why** they disagree, not pick a favorite sensor.

### 3. Uncertainty is First-Class Information

Epistemic uncertainty (wide mixture width, conflicting signals, calibration gaps) is not a bug to minimize. It's information the agent must learn to respect.

**Consequence**: Sometimes the correct action is **do nothing**.

Not delay. Not hedge. Literally refuse to intervene because:
- Epistemic state is poisoned (context curse, no calibration)
- Insufficient evidence to distinguish competing hypotheses
- Risk of harm exceeds expected benefit under uncertainty

**This is not policy collapse. This is epistemic integrity.**

---

## How We Enforce Honesty

### Structural Invariants

1. **Observer Independence**: Measurements cannot perturb physics
   - Separate RNG streams (growth, treatment, assay, operations)
   - Assays read latent state, don't modify it
   - count_cells() uses rng_assay, not rng_growth

2. **Conservation Laws**: Death accounting strictly conserved
   - No silent renormalization (hard error if violated)
   - No laundering unknowns into unattributed
   - Passage transfers attribution history (stateful, not reset)

3. **Competing Risks**: Hazards aggregate, survival applies once
   - Hazards proposed independently
   - Combined survival: exp(-Σ hazards × hours)
   - Death allocated proportionally to hazard share

4. **Tail-Aware Hazards**: Respond to sensitive subpops, not comforting means
   - Per-subpop hazards with shifted thresholds
   - Weighted sum by fraction (not mixture mean)
   - Sensitive cells (threshold_shift=0.8) die earlier than resistant (1.2)

### Removed Escape Hatches

#### Before Today's Fixes

- **Instant kill semantics**: Overkilled at low viability (wrong absolute vs fraction)
- **Threshold direction**: Inverted (sensitive died later instead of earlier)
- **Passage discontinuity**: Attribution history lost (death_compound → death_unattributed)
- **Conservation epsilon**: Inconsistent (1e-9 vs 1e-6 vs 1e-5)
- **Scalar oracle**: ATP/LDH immune to run context (agent learns "always trust scalars")

#### After Today's Fixes

All escape hatches closed. No way for system to "feel right while being wrong."

---

## The ρ = 1.0 Problem

### Current State

`reader_gain` (plate reader) and `illumination_bias` (imaging) have **perfect correlation** (ρ=1.0), both derived from same `instrument_shift` latent.

**Pedagogical value**: Teaches agents "independent modalities is a myth, bad days are global"

**Long-term risk**: Becomes its own tell. Agent infers "when imaging cursed, scalars must be cursed too."

### Future Evolution (Phase 6.5)

Introduce **imperfect correlation** (ρ ≈ 0.6-0.8):

```python
# Separate latents with high-but-imperfect correlation
imaging_latent = rng.normal(0, 1)
scalar_latent = ρ * imaging_latent + sqrt(1-ρ²) * rng.normal(0, 1)

illumination_bias = exp(imaging_latent * 0.2)
reader_gain = exp(scalar_latent * 0.2)
```

**Result**: Occasional runs where one modality cursed, other clean (or both cursed independently)

**When to switch**: After agents learn correlation structure during training, before they overgeneralize it

**Critical**: Don't switch too early (won't learn correlation) or too late (will overfit perfect correlation)

---

## The "Do Nothing" Test

### What It Means

If the simulator is epistemically honest, agents will eventually encounter situations where:
- Epistemic uncertainty is high (conflicting signals, no calibration)
- Stakes are high (intervention could help or hurt)
- Evidence insufficient to distinguish hypotheses

**Rational action**: Refuse to commit. Wait for data, demand calibration, or terminate run.

### Example Scenario

Agent observes:
- Cell Painting: ER channel elevated, mito channel depressed
- LDH: Moderate elevation (20% above baseline)
- Context: No calibration plate this run

Agent reasoning:
> I cannot distinguish between:
> 1. Tunicamycin 2µM on cursed day (looks severe, is moderate)
> 2. Tunicamycin 5µM on clean day (looks severe, is severe)
>
> Planned intervention (washout at 12h):
> - Case 1: Helps (moderate stress, washout prevents death)
> - Case 2: Ineffective (severe stress, already committed to death)
>
> **Decision**: Refuse intervention until calibration available.

### Why This Is Not Failure

Most RL frameworks call this:
- "Exploration failure"
- "Policy collapse"
- "Risk-averse degenerate strategy"

**It's not. It's the simulator believing itself.**

The agent has learned:
- Measurements lie
- Contexts vary
- Uncertainty matters
- Sometimes the correct action is to admit "I don't know enough to act"

This is **epistemic integrity**, not pathology.

---

## Design Tensions

### 1. Realism vs Learnability

**Realism**: Add every artifact (volume, evaporation, waste, pH, spatial correlation, ...)
**Learnability**: Keep state space tractable for RL

**Resolution**: Prioritize realism-per-line (Phase 6 roadmap). Add artifacts that create **non-identifiable structure** (looks like biology until calibration cost paid).

### 2. Honesty vs Kindness

**Honesty**: Simulator refuses to provide false certainty
**Kindness**: Provide clean signals so agent learns faster

**Resolution**: Choose honesty. False certainty transfers nowhere. Better to learn slowly on hard problems than quickly on lies.

### 3. Correlation Structure vs Overfitting

**High correlation** (ρ=1.0): Teaches "bad days are global"
**Risk**: Becomes tell, agents overfit

**Low correlation** (ρ=0.3): Teaches "modalities independent"
**Risk**: Misses real correlation structure

**Resolution**: Start high (ρ=1.0), decrease gradually (Phase 6.5) to ρ ≈ 0.7. Preserve "mostly correlated" while allowing occasional independence.

---

## Success Metrics

### How to Know This Is Working

1. **Agent refuses unsafe interventions**: "I can't tell if this is severe stress or measurement artifact, waiting for calibration"

2. **Agent learns calibration value**: Explicitly budgets interventions for calibration wells, not just treatment

3. **Agent detects context curse**: "This plate looks weird globally, likely instrument shift, adjusting priors"

4. **Cross-modality reasoning**: "Morphology and LDH disagree, need to reason about why before acting"

5. **Transfer success**: Policies trained in simulator perform well in real wet lab (not just simulated test set)

### How to Know It's Broken

1. **Agent ignores uncertainty**: Always acts, never waits for calibration

2. **Oracle sensor routing**: Agent learns "always trust [modality X]" as dominant strategy

3. **Degenerate exploration**: Agent refuses all interventions (collapsed to "do nothing" always)

4. **Overfitting tells**: Agent exploits simulator-specific quirks (e.g., "ρ=1.0 means perfect prediction")

---

## What This Enables

### Scientific Use Cases

1. **Epistemic control**: Explicitly reason about what you don't know
2. **Calibration-aware policies**: Budget interventions for disambiguation
3. **Context-robust strategies**: Work across batch/lot/instrument variations
4. **Honesty about limits**: Refuse to pretend certainty when uncertain

### Why This Matters for Autonomous Science

Most "autonomous lab" efforts fail not from bad planning, but from **misplaced confidence**.

The system:
- Measures something wrong (context curse, reagent failure, equipment drift)
- Interprets confidently (no uncertainty representation)
- Acts decisively (no calibration, no hedging)
- Produces garbage (cannot distinguish artifact from biology)

This simulator forces:
- Measurement uncertainty into the state
- Calibration cost into the budget
- Epistemic reasoning into the policy
- Honesty about "I don't know" into the interface

That's the difference between an autonomous system that flatters you and one that interrogates you.

---

## One More Thing

The hardest part isn't building this. It's **trusting it** when it says "don't act."

When the agent refuses an intervention because epistemic uncertainty is too high, the temptation will be to call it broken.

It's not broken. It's doing exactly what we built it to do:

**Refuse to lie about what it knows.**

That's rare. Keep it.
