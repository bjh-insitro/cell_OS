# Phase 6: Realism Roadmap (Wet Lab Real)

Ranked by realism-per-line-of-code. These are upgrades that make the simulator feel "wet lab real" not just "plausible dynamics."

---

## Priority 1: Volume + Evaporation + Concentration Drift ⭐⭐⭐

**Impact**: Massive realism from small footprint. Makes edge effects principled.

### What to Add to VesselState (biological_virtual.py:~157)

```python
# Volume tracking (first-class state, not proxy)
self.media_volume_uL = 200.0  # 96-well typical working volume
self.initial_volume_uL = 200.0  # For concentration tracking
self.evaporation_rate_uL_per_h = 0.0  # Drawn from run_context, edge-biased

# Derived state
self.media_age_h = 0.0  # Time since last feed (explicit, not inferred)
```

### Injection Points

**1) Initialize in seed_vessel (biological_virtual.py:~1422)**
```python
# After setting vessel_capacity
state.media_volume_uL = kwargs.get('initial_volume_uL', 200.0)
state.initial_volume_uL = state.media_volume_uL

# Sample evaporation rate from run_context + well position
is_edge = self._is_edge_well(vessel_id)
state.evaporation_rate_uL_per_h = self.run_context.get_evaporation_rate(
    well_position=vessel_id,
    is_edge=is_edge
)
```

**2) Update volume in _step_vessel (biological_virtual.py:~1055)**
```python
# After _update_vessel_growth, before death proposals
vessel.media_volume_uL = max(0.0, vessel.media_volume_uL - vessel.evaporation_rate_uL_per_h * hours)
vessel.media_age_h += hours
```

**3) Scale concentrations by volume (biological_virtual.py:~1186)**
```python
# In _apply_compound_attrition, before computing attrition rate
concentration_multiplier = vessel.initial_volume_uL / max(1.0, vessel.media_volume_uL)
effective_dose_uM = dose_uM * concentration_multiplier

# Use effective_dose_uM instead of dose_uM for attrition calculation
```

**4) Feed resets volume + age (biological_virtual.py:~1466)**
```python
# In feed_vessel, after setting nutrient levels
vessel.media_volume_uL = vessel.initial_volume_uL  # Full volume restored
vessel.media_age_h = 0.0
```

**5) Washout dilutes compounds (biological_virtual.py:~1527)**
```python
# In washout_compound, instead of clearing compounds entirely
# Option: dilute by exchange fraction
exchange_fraction = 0.9  # 90% media exchanged
for compound in list(vessel.compounds.keys()):
    vessel.compounds[compound] *= (1.0 - exchange_fraction)
    if vessel.compounds[compound] < 1e-3:  # Below detection limit
        del vessel.compounds[compound]
        vessel.compound_meta.pop(compound, None)
        vessel.compound_start_time.pop(compound, None)
```

**Why It Matters**: Edge wells become "everything concentrates" not just "growth penalty." Spatially correlated artifacts that look like biology.

---

## Priority 2: Plate-Level Correlated Fields ⭐⭐⭐

**Impact**: Critical for RL. Fixes "simulator smell" of independent noise per well.

### What to Add to RunContext (run_context.py:~40)

```python
# Plate-level latent fields (spatially correlated)
self.plate_fields = {
    'temperature_gradient': None,  # Row/column temperature bias
    'illumination_gradient': None,  # Imaging field non-uniformity
    'evaporation_field': None,     # Edge-biased + local variation
    'pipetting_bias': None         # Channel-specific systematic error
}

def get_plate_field_multiplier(self, plate_id: str, well_position: str, field_type: str) -> float:
    """
    Get spatially correlated multiplier for a well position.

    Returns multiplicative factor (1.0 = no effect) that varies smoothly across plate.
    """
    # Parse well position to (row, col)
    row, col = self._parse_well_position(well_position)

    # Lazy initialize field for this plate
    if self.plate_fields[field_type] is None:
        self.plate_fields[field_type] = self._sample_plate_field(field_type, plate_id)

    # Lookup field value at (row, col)
    field = self.plate_fields[field_type][plate_id]
    return field.get_value(row, col)
```

### Injection Points

**1) Growth rate modulation (biological_virtual.py:~1157)**
```python
# In _update_vessel_growth, after bio_mods
# Temperature field affects growth rate
temp_multiplier = self.run_context.get_plate_field_multiplier(
    plate_id=kwargs.get('plate_id', 'P1'),
    well_position=vessel.vessel_id,
    field_type='temperature_gradient'
)
context_growth_modifier *= temp_multiplier
```

**2) Evaporation rate (new, as part of Priority 1)**
```python
# In seed_vessel
evap_base = self.run_context.evaporation_base_rate
evap_multiplier = self.run_context.get_plate_field_multiplier(
    plate_id=vessel_id.split('_')[0],  # Extract plate from vessel_id
    well_position=vessel_id,
    field_type='evaporation_field'
)
state.evaporation_rate_uL_per_h = evap_base * evap_multiplier
```

**3) Illumination bias (biological_virtual.py:~2388)**
```python
# In cell_painting_assay, replace scalar illumination_bias with field lookup
illumination_multiplier = self.run_context.get_plate_field_multiplier(
    plate_id=plate_id,
    well_position=well_position,
    field_type='illumination_gradient'
)
total_tech_factor = plate_factor * day_factor * operator_factor * well_factor * edge_factor * illumination_multiplier
```

**Why It Matters**: Wells are no longer independent. Correlated failure modes are the difference between "agent learns science" vs "agent learns RNG trivia."

---

## Priority 3: Waste + pH as Second Stress Axis ⭐⭐

**Impact**: Cheap, powerful. Captures "cells fine until suddenly they weren't."

### What to Add to VesselState (biological_virtual.py:~186)

```python
# Waste accumulation and pH proxy
self.lactate_mM = 0.0  # Waste proxy (increases with viable cell-hours)
self.pH_proxy = 7.4    # Baseline ~7.4, drifts with waste and buffering
```

### Injection Points

**1) Update waste in _step_vessel (biological_virtual.py:~1055)**
```python
# After _update_vessel_growth, alongside nutrient depletion
viable_cells = vessel.cell_count * vessel.viability
lactate_production_rate = viable_cells / 1e7 * 0.5 * hours  # mM per hour
vessel.lactate_mM += lactate_production_rate

# pH drifts with lactate (simple linear model)
# Buffer capacity scales with volume
buffer_capacity = vessel.media_volume_uL / 200.0  # Normalized
vessel.pH_proxy = 7.4 - (vessel.lactate_mM / (10.0 * buffer_capacity))
vessel.pH_proxy = float(np.clip(vessel.pH_proxy, 6.0, 7.8))
```

**2) pH affects growth (biological_virtual.py:~1161)**
```python
# In _update_vessel_growth, modulate effective_growth_rate
pH_stress = max(0.0, (7.0 - vessel.pH_proxy) / 1.0)  # Stress increases below pH 7.0
pH_growth_penalty = 1.0 - min(0.8, pH_stress)  # Up to 80% reduction
effective_growth_rate *= pH_growth_penalty
```

**3) pH proposes death hazard (biological_virtual.py:~1080)**
```python
# In _step_vessel, during death proposal phase
if vessel.pH_proxy < 6.5:  # Acidic stress
    pH_hazard = 0.05 * (6.5 - vessel.pH_proxy)  # 5% per hour per pH unit below 6.5
    self._propose_hazard(vessel, pH_hazard, "death_starvation")  # Or new "death_pH" field
```

**4) Feed resets waste (biological_virtual.py:~1466)**
```python
# In feed_vessel
vessel.lactate_mM = 0.0
vessel.pH_proxy = 7.4
```

**Why It Matters**: Classic "sudden death" without compounds. Media becomes poison.

---

## Priority 4: Seeding Density Error Persists ⭐⭐

**Impact**: Density-dependent sensitivity is real. Makes simulator "less clean."

### Injection Points

**1) Seed with density-scaled confluence (biological_virtual.py:~1432)**
```python
# In seed_vessel, after plating_context sampling
density_error = state.plating_context['seeding_density_error']
state.confluence = (initial_count / capacity) * (1.0 + density_error)
```

**2) Density modulates IC50 (biological_virtual.py:~1728)**
```python
# In treat_with_compound, after computing ic50_uM
density_multiplier = 1.0 + 0.3 * (vessel.confluence - 0.5)  # 30% shift per 0.5 confluence
ic50_uM *= density_multiplier
```

**3) Density affects growth rate (biological_virtual.py:~1161)**
```python
# In _update_vessel_growth
# High density → slower growth (beyond confluence saturation)
density_penalty = 1.0 - 0.1 * max(0.0, vessel.confluence - 0.3)
effective_growth_rate *= density_penalty
```

**Why It Matters**: Stops "too clean" feeling. Density-dependent phenotypes are ubiquitous.

---

## Priority 5: Compound as Concentration in Media ⭐⭐

**Impact**: Makes washout physical, not boolean. Enables realistic intervention policies.

### What to Change in VesselState (biological_virtual.py:~173)

```python
# Change from dict to explicit state
self.compound_conc_uM = {}  # Current concentration (not nominal dose)
self.compound_decay_k_per_h = {}  # Decay rate constant
self.compound_adsorbed_fraction = {}  # Initial plastic binding
```

### Injection Points

**1) Treat sets concentration (biological_virtual.py:~1767)**
```python
# In treat_with_compound, instead of vessel.compounds[compound] = dose_uM
vessel.compound_conc_uM[compound] = dose_uM * (1.0 - adsorption_fraction)
vessel.compound_decay_k_per_h[compound] = compound_params.get('decay_k_per_h', 0.0)
vessel.compound_adsorbed_fraction[compound] = compound_params.get('adsorption_fraction', 0.1)
```

**2) Decay during _step_vessel (biological_virtual.py:~1092)**
```python
# After _apply_compound_attrition
for compound in list(vessel.compound_conc_uM.keys()):
    k = vessel.compound_decay_k_per_h[compound]
    vessel.compound_conc_uM[compound] *= float(np.exp(-k * hours))
    if vessel.compound_conc_uM[compound] < 1e-3:
        del vessel.compound_conc_uM[compound]
```

**3) Feed/washout dilute (biological_virtual.py:~1527)**
```python
# In washout_compound
for compound in list(vessel.compound_conc_uM.keys()):
    vessel.compound_conc_uM[compound] *= (1.0 - exchange_fraction)
```

**Why It Matters**: Washout becomes physical dilution, not magic reset.

---

## Priority 6: Split Death Modes (Attachment vs Lysis) ⭐

**Impact**: Makes morphology not simply "baseline × viability."

### What to Add to VesselState (biological_virtual.py:~163)

```python
# Three-component death state
self.attached_fraction = 1.0   # Cells still on plate
self.live_fraction = 0.98      # Of attached, what fraction is viable
self.debris_level = 0.0        # Lysed material contaminating field
```

### Injection Points

**1) Death modes affect attachment differently (biological_virtual.py:~1395)**
```python
# In _update_death_mode, track attachment vs lysis
if vessel.death_mode == "mitotic":
    # Mitotic catastrophe → detachment
    vessel.attached_fraction *= 0.9
elif vessel.death_mode in ["er_stress", "compound"]:
    # Apoptosis → stays attached initially, becomes debris
    vessel.debris_level += 0.1 * vessel.death_compound
```

**2) Count_cells sees attached only (biological_virtual.py:~1606)**
```python
# In count_cells
measured_count = vessel.cell_count * vessel.attached_fraction
```

**3) Morphology signal includes debris contamination (biological_virtual.py:~2231)**
```python
# In cell_painting_assay, after viability_factor
debris_contamination = 1.0 + 0.5 * vessel.debris_level  # Debris inflates background
for channel in morph:
    morph[channel] *= viability_factor * debris_contamination
```

**Why It Matters**: Death trajectories have signatures. Detachment ≠ lysis ≠ apoptosis.

---

## Priority 7: Growth Depends on Nutrients and pH ⭐

**Impact**: Prevents "starving cells keep trying to grow until death catches them."

### Injection Point

**Already partially implemented** via confluence saturation (biological_virtual.py:~1165).

**Extend** (biological_virtual.py:~1161):
```python
# After effective_growth_rate calculation
nutrient_growth_penalty = min(
    vessel.media_glucose_mM / GLUCOSE_STRESS_THRESHOLD_mM,
    vessel.media_glutamine_mM / GLUTAMINE_STRESS_THRESHOLD_mM
)
nutrient_growth_penalty = float(np.clip(nutrient_growth_penalty, 0.1, 1.0))

effective_growth_rate *= nutrient_growth_penalty
```

**Why It Matters**: Growth and death become coupled through nutrient/pH dynamics.

---

## Priority 8: Substep When Hazard High or Hours Large

**Impact**: Makes trajectories less "algorithmic."

### Injection Point (biological_virtual.py:~1055)

```python
def _step_vessel(self, vessel: VesselState, hours: float):
    # Substep if hours large or hazard high
    if hours > 1.0 or vessel._step_total_hazard > 0.5:
        n_substeps = max(2, int(np.ceil(hours / 0.5)))
        substep_hours = hours / n_substeps
        for _ in range(n_substeps):
            self._step_vessel_single(vessel, substep_hours)
    else:
        self._step_vessel_single(vessel, hours)

def _step_vessel_single(self, vessel: VesselState, hours: float):
    # Current _step_vessel implementation
    ...
```

**Why It Matters**: Nonlinear hazard sigmoids behave correctly over multi-hour steps.

---

## Priority 9: Assay Rendering Pipeline

**Impact**: Imaging and segmentation failures correlated per plate/channel.

### What to Add

- Focus quality (per well, time-varying)
- Staining efficiency (per channel, per batch)
- Segmentation failure probability (tied to clumpiness, debris, confluence)

**Already started** with `_apply_well_failure` (biological_virtual.py:~1966).

**Extend**: Make failures correlated via plate fields.

---

## Priority 10: Operation Delay Jitter

**Impact**: Policies that survive reality, not sim Olympics.

### Injection Point (biological_virtual.py:~1445, 1497)

```python
# In feed_vessel, washout_compound
operation_jitter = self.rng_operations.normal(0, 0.3)  # ±18 minutes
self.simulated_time += max(0, operation_jitter)
```

Or enforce "workday clock" where operations snap to windows.

**Why It Matters**: Real labs don't feed at exactly 12.0h for every plate.

---

## Two Concrete "Next Patches" (Recommended Order)

### Patch A: Volume + Evaporation + Concentration Drift
- Small footprint, massive realism
- Makes edge effects principled
- **Injection points identified above** (lines ~157, ~1055, ~1186, ~1422, ~1466, ~1527)

### Patch B: Plate-Level Correlated Fields
- Critical for RL training
- Correlated failure modes = agent learns science, not RNG trivia
- **Requires RunContext extension** (run_context.py:~40)
- **Injection points**: lines ~1157 (growth), ~2388 (illumination)

---

## Audit: Current Injection Points Won't Break Observer Independence

All injection points preserve:
- **Physics RNG** (growth, decay) uses `rng_growth`, `rng_treatment`, `rng_operations`
- **Assay RNG** (measurement noise) uses `rng_assay`
- **Deterministic batch effects** use stable seeding from `run_context.seed`

Volume/evaporation/waste are **physics state** (deterministic given seed).
Plate fields are **measurement modifiers** (seeded per plate, not per observation).

No observer-dependence introduced.

---

## Next Steps

1. Review injection points for Patch A (volume/evaporation)
2. Design `RunContext.get_plate_field_multiplier()` API for Patch B
3. Implement Patch A first (highest ROI)
4. Then Patch B (critical for RL)
5. Revisit priorities 3-10 after A+B deployed
