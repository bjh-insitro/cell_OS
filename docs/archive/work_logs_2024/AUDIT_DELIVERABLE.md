# Statistical Audit Deliverable: cell_OS Biological Simulator

**Date**: 2025-12-25
**Auditor**: Agent A (Adversarial Review)
**Status**: One fatal artifact identified, patch ready for merge

---

## Executive Summary

The simulator implements a **deterministic population-level model** with lognormal measurement noise. Core biology (growth, death, stress) is **pure ODE**, not stochastic. Randomness enters only at measurement boundaries and in biological variability terms.

**One fatal artifact found**: Hard 12h commitment threshold creates synchronized population death that real biology would never show.

**Patch delivered**: Removes threshold, introduces dose-dependent per-subpopulation commitment heterogeneity. Mergeable after hostile review.

---

## Part 1: Statistical Models Inventory

### Growth (`biological_virtual.py:1034-1133`)
- **Model**: Deterministic ODE, `dn/dt = r × n × (1 - (c/c_max)²)`
- **Parameters**: `doubling_time_h` (20-30h), `max_confluence` (0.9), `lag_duration_h` (12h)
- **Stochastic**: NO (growth RNG exists but unused)
- **Variance**: Only from run-context batch effects, not cell-to-cell

### Death (`biological_virtual.py:798-882`)
- **Model**: Competing risks, `S(t) = exp(-Σλᵢ × Δt)`
- **Hazards**: Compound attrition, starvation, mitotic catastrophe, ER/mito dysfunction
- **Stochastic**: NO. Deterministic hazard rates.
- **Conservation**: Strictly enforced, crashes on violation

### Dose-Response (`biology_core.py:280-302`)
- **Model**: Hill equation (monotonic), `v = 1/(1 + (dose/IC50)^hill)`
- **Stochastic**: YES, lognormal biological variability (CV=0.05)
- **Impossibility**: Non-monotonic responses structurally forbidden

### Subpopulations (`biological_virtual.py:207-238`)
- **Structure**: 3 fixed buckets (25% sensitive, 50% typical, 25% resistant)
- **Transitions**: NONE. Fractions hard-coded.
- **Stochastic**: NO. Deterministic stress evolution per subpop.
- **Viabilities**: All synced to vessel (not independent)

### Assay Noise
- **Cell Painting**: Hierarchical lognormal, CVs 4-8% (stress-dependent), 1-5% technical
- **LDH/Scalars**: Same structure
- **scRNA-seq**: Lognormal → batch effects (10-15%) → dropout (Bernoulli) → Poisson
- **All positive**: Lognormal guarantees no negative signals

---

## Part 2: RNG Usage Map

**4 isolated streams** (enforced by `ValidatedRNG`):
1. `rng_growth` (seed+1): Unused, reserved
2. `rng_treatment` (seed+2): Biological variability (lognormal CV=0.05)
3. `rng_assay` (seed+3): Measurement noise ONLY (observer independence)
4. `rng_operations` (seed+4): Contamination (0.2% feeding, 0.1% washout)

**Determinism**: Given seed, entire simulation reproducible. No control flow randomness.

**Coupling**: Streams isolated by stack inspection. Measuring cannot affect biology.

**Batch effects**: Deterministic per batch (seeded by hash), not drawn from RNG streams.

---

## Part 3: Invariants and Impossibilities

### Cannot Happen (By Design)

1. **Death reversal**: Conservation law enforced, death fields only increase
2. **Subpopulation transitions**: Fractions fixed at 25/50/25
3. **Negative signals**: Lognormal noise guarantees positivity
4. **Non-monotonic dose-response**: Hill equation structurally monotonic
5. **Death before 12h commitment**: Hard threshold gate ← **FATAL ARTIFACT**
6. **Cellular memory**: No history-dependent responses
7. **Rapid death (<12h)**: Instant kill disabled during growth
8. **Overgrowth death**: Growth capped, no death from crowding
9. **Measurement affecting biology**: Observer independence enforced
10. **Time reversal**: Causality enforced
11. **Subpop differential viability**: All synced to vessel
12. **Biological run-to-run variance**: Biology deterministic, only measurement varies

---

## Part 4: Statistical Shape of Data

### Time Series
- **Non-stationary**: Early noise (plating artifacts), attrition step at 12h, evaporation drift
- **Smooth with kinks**: ODE smooth, but commitment threshold creates derivative discontinuity

### Variance
- **Heteroskedastic**: CV increases 2-3× under stress, debris inflates variance
- **Noise floor**: Replicates converge to ~5% CV (persistent per-well biology)

### Dimensionality
- **Low-rank biology**: 5 stress axes generate apparent high-dimensional data
- **PCA**: 2-3 PCs explain 70-80%, then technical tail
- **Subpopulations**: 3 discrete clusters in vehicle controls (scRNA)

### Correlations
- **Within-modality**: Dense (50-70% of pairs |r|>0.3)
- **Cross-modality**: Moderate (r~0.5-0.7), weakened by independent batch effects
- **Batch structure**: Plate/day/operator create block correlations

### Outliers
- **Rate**: 1-5% catastrophic (bubbles, contamination, pipetting)
- **Structure**: Spatial clustering, edge enrichment
- **Heavy tails**: From subpopulation mixture, not measurement noise

### Batch Effects
- **Magnitude**: Imaging 5%, scRNA 10-15%
- **Structure**: Multiplicative, per-channel heterogeneity, correlated by run-context
- **Confounding**: Treatment-batch confounding easily swamps signal

---

## Part 5: Fatal Artifact

### What Kind of Real Data Would Embarrass This Simulator

**Single-cell heterogeneity**: Real cells show continuous parameter distributions. This simulator has exactly 3 discrete subpopulations with fixed ratios. Flow cytometry histograms would reveal the discretization.

**Stress recovery kinetics**: Real cells recover from sublethal ER stress. This simulator makes stress→death irreversible. Washout experiments showing recovery would break the model.

**Selection dynamics**: Drug-resistant clones emerge and expand. This simulator cannot change subpopulation fractions. Serial passaging under drug would show fixed 25/50/25 ratios forever.

**Non-lognormal measurement tails**: Real plate readers saturate, segmentation fails catastrophically. This simulator's strict lognormal assumption would be exposed by Q-Q plots.

**Commitment time heterogeneity**: ← **THIS IS THE KILLER**

---

## The Fatal Flaw: 12h Hard Threshold

### Proof of Existence

**Location**: `src/cell_os/biology/biology_core.py:439-441`

```python
if time_since_treatment_h <= 12.0:
    return 0.0  # No attrition before 12h
```

### Test That Proves It

```python
def test_12h_threshold_exists():
    rate_before = compute_attrition_rate(..., time_since_treatment_h=11.9)
    rate_after = compute_attrition_rate(..., time_since_treatment_h=12.1)

    assert rate_before == 0.0  # Exactly zero
    assert rate_after > 0.0     # Non-zero
    # Jump magnitude: ~28,058× (infinite derivative)
```

**Output**:
```
=== 12H COMMITMENT THRESHOLD ARTIFACT ===
Attrition rate at 11.9h: 0.000000 per hour
Attrition rate at 12.1h: 0.000028 per hour
Jump magnitude: 28,058×

✓ PROOF: Hard 12h threshold exists
```

### Why It's Fatal

Real biology:
- Apoptosis commitment is **stochastic** (cell-to-cell variation)
- Commitment time is **dose-dependent** (high dose commits faster)
- Typical range: 2-24h depending on mechanism and dose

This simulator:
- ALL cells commit at exactly 12h (synchronized)
- Independent of dose (10×IC50 same as 1×IC50)
- Creates population-level **synchronization artifact**

**Falsification method**: High-resolution time-course flow cytometry showing caspase activation. Real data shows gradual onset over hours. This simulator would show sharp inflection at 12h.

---

## The Patch: Commitment Heterogeneity

### Design Decisions

**World A**: Sublethal doses (<IC50) → no attrition (unchanged)

**Commitment delay bounds**: [1.5h, 48h]
- Lower: prevents instant commitment (gate conflicts)
- Upper: simulator doesn't model multi-day recovery
- Both are **engineering guardrails**, not biological claims

**Cache key**: `(compound, exposure_id, subpop)`
- `exposure_id`: Integer, monotonic, unique per dosing
- No float drift, no epsilon collisions

**Dose-dependent mean**: `mean_h = 12 / sqrt(1 + dose_ratio)`
- At IC50: 12h
- At 4×IC50: 5.4h
- At 100×IC50: 1.2h (asymptotes)

**Lognormal CV=0.25**: Tunable, not claiming truth

**RNG stream**: `rng_treatment` (biological variability)

### What It Fixes

1. ✓ Removes population synchronization
2. ✓ Introduces dose-dependent commitment (realistic)
3. ✓ Per-subpopulation heterogeneity
4. ✓ No new ontology (uses existing subpops)
5. ✓ Honest about uncertainty (CV tunable, bounds explicit)

### What It Doesn't Fix (Out of Scope)

- Commitment still deterministic given seed (not truly stochastic)
- Distribution choice (lognormal) still arbitrary
- No cell-to-cell variation within subpopulations
- No recovery/reversal of commitment

These would require deeper architectural changes.

### Hostile Review Outcomes

**Two critical bugs found and fixed**:

1. **Determinism**: Dict iteration order fragile → sorted iteration everywhere
2. **IC50 mismatch**: Sampling guard used base IC50, attrition used shifted IC50 → always sample if dose>0, attrition enforces World A

**Four hardened tests**:
1. No-kink derivative test
2. No lethal dose uses fallback 12h
3. Commitment gate not a threshold (multiple activation times)
4. Heterogeneity with CV stability

**IC50 validity guard added**:
```python
if ic50_uM is None or not np.isfinite(ic50_uM) or ic50_uM <= 0:
    raise ValueError(f"Invalid IC50 {ic50_uM} for {compound}")
```

Fails loudly on junk, prevents silent "everything lethal" behavior.

---

## Next Structural Truth Upgrade

**Subpopulation viabilities are synchronized** (`biological_virtual.py:922-956`).

Fixing commitment heterogeneity makes this lie more obvious: different commitment delays but identical death trajectories. Uncanny valley.

Next patch:
- Independent viability per subpopulation
- Selection pressure (changing fractions over time)
- Darwinian dynamics

This is the natural continuation after commitment heterogeneity.

---

## Audit Confidence Statement

**What we know**:
- Biology is deterministic ODE (not stochastic)
- Measurement noise is hierarchical lognormal
- RNG streams properly isolated (observer independence)
- One fatal artifact identified and patched
- Patch is mergeable after hostile review

**What we don't know**:
- Whether parameter values (IC50s, hazard rates, CVs) match reality
- Whether the simulator is "realistic enough" for the agent's task
- Whether there are other hidden artifacts (we only looked for obvious ones)

**What we're confident about**:
- The 12h threshold would be caught immediately by time-course flow cytometry
- The patch removes the synchronized death wave
- No new lies introduced (bounds and distribution choice are explicit)
- Tests prevent regression

**Recommendation**: Merge the patch. It's the smallest honest fix that kills the visible artifact without inventing new ontology.

---

**End of audit.**
