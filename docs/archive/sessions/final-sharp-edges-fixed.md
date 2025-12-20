# Final Sharp Edges Fixed: 2025-01-20

## Three Critical Bugs Caught in Final Review

After achieving epistemic honesty in the main architecture, a detailed review revealed three sharp edges where **silent semantic drift** could still occur. All fixed and tested.

---

## Fix #1: Microtubule Morphology Double-Rendering ⚠️ CRITICAL

### Bug

In `cell_painting_assay`, microtubule compounds had their morphology effects applied **twice**:

1. First: Direct application via `stress_axes['microtubule']['channels']` (line 2224-2227)
2. Second: Latent state application via `transport_dysfunction` → actin (line 2247)

**Result**: Actin signal inflated by `axis_effect * (1 + transport_dysfunction)` instead of just `(1 + transport_dysfunction)`.

This created "stronger than physics" microtubule signatures that didn't match latent state dynamics.

### Fix (biological_virtual.py:2219-2220)

```python
# Microtubule phenotypes are ONLY rendered via transport dysfunction latent state
# (applied below, affects actin). Skip direct axis_effects to avoid double-counting.
if stress_axis == "microtubule":
    continue  # Skip morphology loop, latent state will handle it
```

Now microtubule compounds:
- Skip direct channel effects entirely
- Render morphology ONLY through transport_dysfunction latent state
- Mitotic catastrophe (viability effect) handled separately in _apply_compound_attrition

### Verified By

**test_microtubule_double_counting.py: 2/2 passing**

- Test 1: Actin inflation matches latent-only model exactly (multiplier 1.600 vs expected 1.600)
- Test 2: Microtubule (gated) and ER stress (not gated) work independently

---

## Fix #2: Morphology Potency Inconsistent with Viability Potency ⚠️ CRITICAL

### Bug

`cell_painting_assay` used raw `compound_params['ec50_uM']` from thalamus_params, but `treat_with_compound` computed an **adjusted** `ic50_uM` that includes:

- Cell-line sensitivity (prolif index)
- Run context EC50 modifiers (incubator/batch effects)
- Potency scalar (mechanism coupling strength)

**Result**: Systematic mismatch where:
- Viability says "this dose is potent" (low adjusted IC50)
- Morphology says "meh" (still using baseline IC50)

Or vice versa. This was **not stochastic realism**, it was accidental bypass of declared mechanisms.

### Fix (biological_virtual.py:2214-2240)

```python
# Use adjusted potency from vessel.compound_meta if available (includes cell-line
# sensitivity, run context modifiers, potency_scalar). Falls back to baseline if not.
meta = vessel.compound_meta.get(compound_name)
if meta:
    # Use adjusted values stored during treat_with_compound
    ec50 = meta['ic50_uM']  # Adjusted for cell line, run context, etc.
    hill_slope = meta['hill_slope']
    potency_scalar = meta.get('potency_scalar', 1.0)
else:
    # Fallback to baseline (compound present but not via treat_with_compound)
    ec50 = compound_params['ec50_uM']
    hill_slope = compound_params['hill_slope']
    potency_scalar = 1.0

# Calculate dose response with adjusted parameters
dose_effect = intensity * potency_scalar * (dose_uM ** hill_slope) / (ec50 ** hill_slope + dose_uM ** hill_slope)
```

Now viability and morphology use **same adjusted potency**, creating coherent cross-modality signals.

**Controlled incoherence** (when desired) still comes from explicit sources:
- Run context measurement modifiers (illumination_bias, channel_biases, reader_gain)
- Plating artifacts (post-dissociation stress, clumpiness)
- Pipeline transform (batch-dependent feature extraction)

Not from accidentally bypassing adjusted potency.

### Verified By

Existing tests continue to pass. Morphology now responds to same IC50/potency adjustments as viability.

---

## Fix #3: Passage Conservation Check Added (Fail-Fast)

### Issue

`passage_cells` does stateful transfer (copies all death buckets, latent states, compounds), but didn't verify conservation immediately.

**Risk**: If someone breaks stateful transfer logic later, the bug wouldn't be caught until next `_update_death_mode` call (which might be much later or not at all if vessel not used).

### Fix (biological_virtual.py:1715-1717)

```python
self.vessel_states[target_vessel] = target

# Verify conservation immediately (catch passage accounting bugs early)
# This ensures that if we break stateful transfer logic later, we fail fast
self._update_death_mode(target)
```

Now any passage accounting bug raises `ConservationViolationError` **immediately**, not later when debugging is harder.

### Verified By

**test_mixed_mechanisms_conservation.py** includes passage test (2/2 passing):
- Conservation holds through passage
- Attribution history preserved (death_compound, death_er_stress carry over)
- New passage stress added to death_unknown correctly

---

## Two "Keeper of Honesty" Regression Tests

These tests ensure the simulator stays honest when future changes are made.

### Test 1: test_microtubule_double_counting.py

**Guards against**: Accidentally double-applying morphology effects for mechanisms that have both direct and latent pathways.

**Checks**:
- Actin inflation matches latent-only model (no double-counting)
- Gated (microtubule) and non-gated (ER stress) axes work independently

**Why it matters**: Easy to "just add a morphology effect" without checking if it's already rendered via latent state.

### Test 2: test_mixed_mechanisms_conservation.py

**Guards against**: Violating conservation law when mixing instant events, time-dependent hazards, and passage operations.

**Checks**:
- Conservation holds through: initial imperfect viability → instant kill → multi-step time evolution
- Conservation holds through: stressed vessel → passage → target vessel
- Attribution history preserved (no silent laundering)
- death_unattributed never goes negative
- tracked_known <= total_dead + DEATH_EPS always

**Why it matters**: This is the "if someone just adds a little hazard" detector. Conservation is easy to break accidentally when adding mechanisms.

---

## Remaining Sharp Edges (Documented, Not Fixed)

These are design choices, not bugs. Documented for future reference.

### 1) Death Mode Labels: Threshold-Based on Cumulative Totals

Current: death_mode labels based on which cumulative bucket exceeds 5% threshold.

**Issue**: Early instant kill can lock mode label even if later mechanisms dominate.

**Decision**: Leave as-is. Mode labels are for human debugging, not agent training.

**Future option**: Add recency-weighted mode label or "dominant contributor" computed from deltas.

### 2) Nutrient Depletion: `last_feed_time` Not Used

Current: `last_feed_time` is set but not used to shape any effects.

**Status**: Not a bug, just an "unfinished promise."

**Future extension**: Add media age effects (pH, osmolality, toxin accumulation) that depend on time since feed.

### 3) Washout Artifacts: Multiplicative Stacking

Current: viability attenuation + deterministic washout penalty + stochastic artifact + bio noise + plating artifacts

All multiplicative, creating consistent global dimming signature.

**Suggestion for Phase 6**: Make washout penalties partly channel-specific (actin/nucleus hit more than ER) or depend on plating context (clumpy plates get hit harder).

**Decision**: Defer to Phase 6 realism roadmap.

---

## All Test Suites Passing

- ✓ test_instant_kill_semantics.py: 3/3
- ✓ test_threshold_shift_direction.py: 2/2
- ✓ test_death_accounting_honesty.py: 3/3
- ✓ test_adversarial_honesty.py: 3/3
- ✓ test_semantic_invariants.py: 2/2
- ✓ test_stress_axis_determinism.py: 2/2
- ✓ test_scalar_assay_run_context.py: 4/4
- ✓ test_microtubule_double_counting.py: 2/2 ✓ **NEW**
- ✓ test_mixed_mechanisms_conservation.py: 2/2 ✓ **NEW**

---

## Key Architectural Invariants Now Enforced

1. **No Oracle Sensors**: All modalities fallible (imaging + scalars both have correlated drift)
2. **Competing Risks**: Hazards aggregate, survival applies once, death allocated proportionally
3. **Observer Independence**: Measurements don't perturb physics (separate RNG streams)
4. **Conservation Laws**: Strictly enforced with DEATH_EPS uniform tolerance
5. **Tail-Aware Hazards**: Sensitive subpops drive death (not comforting means)
6. **Instant Kill Semantics**: Fraction of viable killed (no overkill at low viability)
7. **Passage Stateful Transfer**: Attribution history preserved (no laundering)
8. **Threshold Shift Direction**: Sensitive dies earlier, resistant dies later
9. **Cross-Modality Coherence**: Morphology and viability use same adjusted potency
10. **Microtubule Latent-Only**: Transport dysfunction renders morphology (no double-counting)

---

## What This Achieves

The simulator now has **structural integrity** around uncertainty:
- Can't accidentally pretend to know things it doesn't
- Can't provide false certainty through semantic escape hatches
- Can't create systematic biases agents can exploit

When an agent trained in this world refuses to act because epistemic uncertainty is too high, that's not a bug.

**That's the simulator believing itself.**

---

## One Final Note

The way "unknown" is treated as a **credited bucket** and "unattributed" as a **remainder** is intentionally uncomfortable.

Most simulators try to be comforting. They silently renormalize. They hide residuals. They make everything add up nicely.

Comfort is how you get agents that cheat.

This simulator enforces:
- death_unknown: KNOWN unknowns (seeding stress, contamination, passage stress) - explicitly credited
- death_unattributed: UNKNOWN unknowns (numerical residue, missing model) - bookkeeping only

If `death_unattributed` is large, that's **information**. It means:
- "We don't understand what killed these cells"
- Not "let's sweep it under the rug"

That discomfort keeps the system honest.
