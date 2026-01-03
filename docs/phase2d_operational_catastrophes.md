# Phase 2D: Operational Catastrophes

**Status:** 🚧 Design phase (starting with 2D.1: Contamination)

**Created:** 2025-12-29

---

## Purpose

Add **rare, discrete, provenance-rich operational events** that agents must detect, diagnose, and mitigate.

**Not "random chaos mode"** - these are:
- **Identifiable** (recoverable parameters, predictable from observables)
- **Detectable** (have characteristic signatures in morphology/growth/viability)
- **Provenance-rich** (timestamped, vessel-specific, with known causes)

**Why after Phase 2C:** Trains agents on what actually ruins experiments in real life (ops, instrumentation, contamination) without touching biological semantics.

---

## Event Classes (Minimal Set)

### Phase 2D.1: Contamination Events ← **Start Here**
- **Type:** Vessel-level, discrete, rare
- **Signature:** Abrupt viability collapse OR growth arrest + detectable anomaly
- **Causes:** Bacterial, fungal, or mycoplasma contamination
- **Detection:** pH drift proxy, morphology shift, sudden growth-rate change
- **Parameters:** Contamination rate (per vessel-day), severity, onset delay

### Phase 2D.2: Pipetting Volume Error (Future)
- **Type:** Plate-level, discrete, affects dose spine
- **Signature:** Concentration shifts by multiplier, detectable via controls + spatial structure
- **Causes:** Miscalibration, blockage, air bubble
- **Detection:** Control well deviations, dose-response shift
- **Parameters:** Error rate, multiplier distribution

### Phase 2D.3: Instrument Drift Spike (Future)
- **Type:** Run-level, discrete, affects measurement gain
- **Signature:** Discontinuous jump in signal beyond smooth drift
- **Causes:** PMT voltage spike, temperature shock, detector recalibration
- **Detection:** Calibration well discontinuity, cross-plate comparison
- **Parameters:** Spike rate, magnitude, recovery time

---

## Phase 2D.1: Contamination Events (Detailed Design)

### Overview

**Goal:** Add bacterial/fungal/mycoplasma contamination as a rare, detectable, identifiable event.

**Key properties:**
- **Rare:** ~0.1-1% per vessel over 7-day experiment (realistic lab rate)
- **Discrete:** Event has onset time, then deterministic progression
- **Detectable:** Characteristic signature distinct from compound-induced death
- **Identifiable:** Event rate and severity recoverable from observables

---

### Schema (VesselState Fields)

```python
# Contamination tracking
self.contamination_status = None  # None, "bacterial", "fungal", "mycoplasma"
self.contamination_onset_time = None  # Simulated time when contamination started
self.contamination_severity = 1.0  # Multiplier for growth rate of contaminant

# Contamination-specific death (separate from death_unknown)
self.death_contamination = 0.0  # Cumulative fraction killed by contamination
```

**Why separate from `death_unknown`:**
- `death_unknown` includes known-unknowns (handling mishaps, bubbles, operator error)
- Contamination has **characteristic time course** (onset + progressive death)
- Identifiability requires separating contamination from other ops failures

---

### Config (cell_thalamus_params.yaml Extension)

```yaml
# Phase 2D.1: Contamination events
contamination:
  enabled: true  # Master switch

  # Event rate (Poisson process, per vessel-day)
  rate_per_vessel_day: 0.005  # 0.5% per day = ~3.5% over 7 days

  # Contamination types (multinomial draw when event occurs)
  type_probabilities:
    bacterial: 0.60  # 60% bacterial (fast, aggressive)
    fungal: 0.30     # 30% fungal (medium, visible)
    mycoplasma: 0.10 # 10% mycoplasma (slow, cryptic)

  # Type-specific dynamics
  bacterial:
    onset_delay_h: 12.0  # Time from inoculation to detectable effect (log-normal)
    onset_delay_cv: 0.5
    doubling_time_h: 0.5  # Bacteria grow fast
    death_onset_h: 24.0   # Cell death starts 24h after onset
    max_death_fraction: 0.95  # Nearly total kill

  fungal:
    onset_delay_h: 24.0
    onset_delay_cv: 0.5
    doubling_time_h: 2.0  # Fungi grow slower
    death_onset_h: 48.0
    max_death_fraction: 0.80

  mycoplasma:
    onset_delay_h: 48.0
    onset_delay_cv: 0.5
    doubling_time_h: 8.0  # Mycoplasma very slow
    death_onset_h: 96.0
    max_death_fraction: 0.40  # Chronic, not acute kill

  # Detectable signatures (for diagnosis without labels)
  signature:
    bacterial:
      pH_drift_rate: 0.3  # pH drops fast (acid production)
      morphology_shift: 2.0  # Strong morphology anomaly
      growth_arrest_factor: 0.1  # Cells stop growing

    fungal:
      pH_drift_rate: 0.1
      morphology_shift: 3.0  # Very visible under microscope
      growth_arrest_factor: 0.5

    mycoplasma:
      pH_drift_rate: 0.05  # Subtle pH change
      morphology_shift: 0.5  # Cryptic morphology
      growth_arrest_factor: 0.7  # Partial growth inhibition
```

---

### RNG Substream (Determinism)

**New RNG:** `rng_operational_events` (separate from biology)

**Why separate:**
- Operational events are **orthogonal** to biological variability
- Enables ablation tests (disable ops, keep biology identical)
- Seed: `rng_operational_events = np.random.default_rng(base_seed + 1000)`

**Sampling:**
```python
# At vessel seeding or start of run
for vessel in vessels:
    # Poisson process: time to next contamination event
    rate_per_h = contamination_rate_per_vessel_day / 24.0
    time_to_event = rng_operational_events.exponential(1.0 / rate_per_h)

    if time_to_event < experiment_duration_h:
        # Event occurs - sample type
        contam_type = rng_operational_events.choice(
            ["bacterial", "fungal", "mycoplasma"],
            p=[0.6, 0.3, 0.1]
        )

        # Sample onset delay (log-normal)
        onset_delay_h = sample_lognormal(
            mean=config[contam_type]['onset_delay_h'],
            cv=config[contam_type]['onset_delay_cv'],
            rng=rng_operational_events
        )

        vessel.contamination_status = contam_type
        vessel.contamination_onset_time = time_to_event + onset_delay_h
        vessel.contamination_severity = 1.0  # Could sample from distribution
```

---

### Integration Points (BiologicalVirtualMachine)

#### 1. Event Sampling (at vessel seeding)

**Where:** `seed_vessel()` - after seeding cells, sample contamination event

**Logic:**
```python
def seed_vessel(...):
    # ... existing seeding logic ...

    # Phase 2D.1: Sample contamination event (if enabled)
    if self.config.get('contamination', {}).get('enabled', False):
        self._sample_contamination_event(vessel)
```

#### 2. Contamination Progression (during advance_time)

**Where:** `_step_vessel()` - after growth, before death proposals

**Logic:**
```python
def _step_vessel(vessel, hours):
    # 1. Growth (existing)
    self._update_growth(vessel, hours)

    # 2. Phase 2D.1: Contamination progression
    if vessel.contamination_status is not None:
        self._progress_contamination(vessel, hours)

    # 3. Death proposals (existing)
    # ... nutrient depletion, compound, confluence ...
```

#### 3. Contamination Death Hazard

**Dynamics:**
```python
def _progress_contamination(vessel, hours):
    """
    Progress contamination and propose death hazard.

    Contamination has three phases:
    1. Latent (before onset): no effect
    2. Growth (onset to death_onset): contaminant grows, cells show stress
    3. Death (after death_onset): progressive cell kill
    """
    if self.simulated_time < vessel.contamination_onset_time:
        return  # Latent phase

    contam_type = vessel.contamination_status
    params = self.config['contamination'][contam_type]

    time_since_onset = self.simulated_time - vessel.contamination_onset_time

    # Phase 2: Growth arrest (before death)
    if time_since_onset < params['death_onset_h']:
        # Cells slow down but don't die yet
        growth_arrest = params['signature']['growth_arrest_factor']
        vessel._contamination_growth_penalty = growth_arrest

        # Morphology shift (detectable anomaly)
        morphology_shift = params['signature']['morphology_shift']
        vessel._contamination_morphology_anomaly = morphology_shift

    # Phase 3: Progressive death
    else:
        time_in_death_phase = time_since_onset - params['death_onset_h']

        # Exponential kill with rate determined by contaminant doubling time
        # Faster doubling = faster kill
        k_death = np.log(2) / params['doubling_time_h']

        # Target death fraction approaches max asymptotically
        target_death = params['max_death_fraction']
        instantaneous_death_fraction = target_death * (1.0 - np.exp(-k_death * time_in_death_phase))

        # Compute incremental death in this step
        # (Need to track cumulative death to avoid double-counting)
        if not hasattr(vessel, '_contamination_cumulative_death'):
            vessel._contamination_cumulative_death = 0.0

        incremental_death = instantaneous_death_fraction - vessel._contamination_cumulative_death
        vessel._contamination_cumulative_death = instantaneous_death_fraction

        # Propose death hazard (will be applied in _commit_step_death)
        if incremental_death > 0:
            # Convert fraction to hazard rate for this step
            survival_this_step = 1.0 - incremental_death
            if survival_this_step > 0:
                hazard_rate = -np.log(survival_this_step) / hours
                self._propose_step_hazard(vessel, hazard_rate, 'death_contamination')
```

---

### Detectable Signatures (No Labels)

**Key:** Contamination must be diagnosable from observables **without accessing `contamination_status` label**.

#### Signature 1: Growth Rate Anomaly

**Before contamination:**
```
cell_count(t) follows exponential growth with doubling_time_h
```

**After contamination onset:**
```
growth_rate *= contamination_growth_arrest_factor
→ Sudden drop in dN/dt detectable via time-series analysis
```

**Detection:** Compare growth rate before/after suspected onset using sliding window.

---

#### Signature 2: Morphology Anomaly

**Implementation:** Add `contamination_morphology_multiplier` to Cell Painting channels

```python
# In observe_morphology():
if vessel.contamination_status is not None:
    anomaly = vessel._contamination_morphology_anomaly

    # Bacterial: diffuse signal increase (bacteria in media)
    # Fungal: extreme signal spikes (hyphae visible)
    # Mycoplasma: subtle texture changes

    for channel in ['er', 'mito', 'nucleus', 'actin', 'rna']:
        observed_value *= (1.0 + anomaly * channel_sensitivity)
```

**Detection:** Outlier detection on morphology variance or cross-channel correlation.

---

#### Signature 3: Viability Time Course

**Characteristic:**
- Compound death: smooth exponential decline from t=0
- Contamination death: **bimodal** - plateau, then sudden drop at `death_onset_h`

**Detection:** Change-point detection on viability(t) time series.

---

### Identifiability Suite (Phase 2D.1 Validation)

**Goal:** Prove contamination rate and type-specific parameters are recoverable from observables.

#### Design (3-Regime)

**Regime A: Contamination-free (control)**
- 96 wells, DMSO, 7 days
- Expected: 0 contamination events (or extremely rare)
- Purpose: Baseline for growth rate, morphology variance

**Regime B: Contamination-enriched (stress test)**
- 96 wells, DMSO, 7 days
- **Increase contamination rate 10×** (to ~5% per day → ~30% over 7 days)
- Purpose: Generate events for parameter fitting

**Regime C: Held-out validation**
- 48 wells, DMSO, 7 days
- Contamination rate at 5× baseline
- Purpose: Predict event count using recovered parameters

#### Inference (No Labels)

**Step 1: Detect contamination events**
- Use change-point detection on viability(t) OR growth rate anomaly
- Flag vessels as "suspected contamination" based on signature
- **Do not access `contamination_status` label**

**Step 2: Classify contamination type**
- Bacterial: fast onset (<24h), aggressive kill (>90%)
- Fungal: medium onset (24-48h), visible morphology spike
- Mycoplasma: slow onset (>48h), partial kill (<50%)
- Use time-to-death and severity to classify

**Step 3: Estimate contamination rate**
- Count detected events in Regime B
- Compute rate = events / (wells × days)
- Correct for detection sensitivity (some events may be missed)

**Step 4: Validate on Regime C**
- Predict event count using estimated rate
- Compare to observed (detected) events
- Acceptance: predicted within ±30% of observed

#### Acceptance Criteria

**Recovery:**
- Contamination rate error <2× truth (log-scale tolerance)
- Type classification accuracy ≥70% (bacterial vs fungal vs mycoplasma)

**Prediction:**
- Held-out event count within ±30%

**No hallucination (ablation):**
- With contamination disabled, detector flags ≤1% false positives

---

### Tests (Contracts)

#### Test 1: Contamination Events Are Rare

```python
def test_contamination_rarity():
    """
    With rate=0.005 per vessel-day, expect ~3.5% over 7 days.

    Run 1000 vessels × 7 days, check empirical rate in [2%, 5%].
    """
    n_contaminated = count_contamination_events(1000, 7.0)
    empirical_rate = n_contaminated / 1000.0

    assert 0.02 <= empirical_rate <= 0.05
```

#### Test 2: Contamination Has Characteristic Time Course

```python
def test_contamination_death_bimodal():
    """
    Contaminated vessel should show plateau → sudden drop.
    Non-contaminated vessel shows smooth exponential.
    """
    vessel_clean = run_vessel(contamination_enabled=False)
    vessel_contam = run_vessel(contamination_enabled=True, force_event=True)

    # Check viability time series
    viability_clean = vessel_clean.viability_history
    viability_contam = vessel_contam.viability_history

    # Clean: monotonic decrease
    assert is_monotonic_decreasing(viability_clean)

    # Contaminated: has change-point
    changepoint_detected = detect_changepoint(viability_contam)
    assert changepoint_detected
```

#### Test 3: RNG Independence

```python
def test_contamination_rng_independence():
    """
    Contamination events use rng_operational_events.
    Disabling contamination should not change biological RNG sequence.
    """
    # Run with contamination ON
    vm1 = BiologicalVM(seed=42, contamination_enabled=True)
    vessel1 = vm1.seed_vessel(...)
    vm1.advance_time(168.0)  # 7 days

    # Run with contamination OFF
    vm2 = BiologicalVM(seed=42, contamination_enabled=False)
    vessel2 = vm2.seed_vessel(...)
    vm2.advance_time(168.0)

    # Growth, stress, Phase 1/2 REs should be identical
    assert vessel1.cell_count == vessel2.cell_count  # (if no contamination death in vessel1)
    assert vessel1.er_stress == vessel2.er_stress
```

---

### Phase 2D.1 Precondition (Hazard-Mass Analogue)

**Before adding contamination to production:**

**Precondition:** Expected event count in stress-test regime must exceed 10.

**Check:**
```
rate_per_vessel_day = 0.005
n_vessels = 96
duration_days = 7.0

expected_events = rate_per_vessel_day * n_vessels * duration_days
# = 0.005 * 96 * 7 = 3.36

Stress test (10× rate):
expected_events_stress = 10 * 3.36 = 33.6
```

**Gate:** If expected_events_stress < 10, event is too rare to validate. Increase rate or extend duration.

---

### Next: Phase 2D.2 (Pipetting Error)

**After 2D.1 passes identifiability:**

Add pipetting volume error (plate-level, discrete, affects dose spine).

**Key differences:**
- **Spatial:** Affects entire plate or column
- **Signature:** Dose-response shifts detectable via control wells
- **Identifiability:** Recover error rate and multiplier distribution

**Use same discipline:**
- RNG: `rng_operational_events`
- Config: error rate, multiplier params
- Identifiability suite: 3-regime design
- Ablation: no hallucination when disabled

---

## Design Principles (Carried from Phase 2C)

### 1. Provenance-Rich

Every event has:
- Onset time (deterministic given RNG seed)
- Type (bacterial/fungal/mycoplasma)
- Severity (sampled from distribution)
- Progression (deterministic given onset)

**Not "add random noise."** Events are discrete, timestamped, and have known causes.

---

### 2. Detectable Without Labels

Contamination must be diagnosable from:
- Growth rate anomalies
- Morphology shifts
- Viability time course (change-point)

**Agents learn to detect contamination** without peeking at `contamination_status`.

---

### 3. Identifiable

Contamination rate and type-specific parameters are **recoverable** from observables:
- Event rate from detection frequency
- Type classification from onset speed + severity
- Validation on held-out data

**Same rigor as Phase 2C:**
- Precondition check (expected events ≥ 10)
- No-peeking ablation (detector flags <1% when disabled)
- Held-out prediction within ±30%

---

### 4. Rare But Not Negligible

**Calibration:**
- Baseline rate: 0.5% per vessel-day → ~3.5% over 7 days (realistic lab rate)
- Stress test (for identifiability): 5% per vessel-day → ~30% over 7 days
- Production runs: Use baseline rate (rare enough to not dominate)

**Not "every run has contamination."** Most experiments clean, but agents must handle edge cases.

---

## Implementation Checklist (Phase 2D.1)

- [ ] Add `death_contamination`, `contamination_status`, `contamination_onset_time` to VesselState
- [ ] Add contamination config to `cell_thalamus_params.yaml`
- [ ] Create `rng_operational_events` RNG substream
- [ ] Implement `_sample_contamination_event()` in `seed_vessel()`
- [ ] Implement `_progress_contamination()` in `_step_vessel()`
- [ ] Add morphology anomaly to `observe_morphology()`
- [ ] Write tests: rarity, time course, RNG independence
- [ ] Create identifiability suite (3-regime design)
- [ ] Implement contamination detector (no labels)
- [ ] Validate: recovery, prediction, no hallucination
- [ ] Document in `docs/phase2d1_contamination.md`

---

## Files to Create

### Implementation
- `src/cell_os/hardware/operational_events/contamination.py` - Event logic
- `src/cell_os/calibration/contamination_detector.py` - Detection (no labels)

### Configs
- `configs/contamination_baseline.yaml` - Production params (0.5%/day)
- `configs/contamination_stress_test.yaml` - Identifiability (5%/day)

### Tests
- `tests/contracts/test_contamination_rarity.py`
- `tests/contracts/test_contamination_signatures.py`
- `tests/contracts/test_contamination_rng_independence.py`

### Identifiability
- `configs/calibration/identifiability_2d1.yaml` - 3-regime design
- `scripts/run_identifiability_2d1.py` - Suite runner
- `scripts/render_identifiability_report_2d1.py` - Report with detection metrics

---

*Phase 2D.1 uses the same discipline as Phase 2C: provenance-rich, detectable, identifiable, with hard preconditions and no-peeking ablations.*
