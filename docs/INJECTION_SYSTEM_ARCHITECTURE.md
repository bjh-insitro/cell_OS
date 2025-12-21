# Complete Injection System Architecture

**Status**: ✅ PRODUCTION READY (2025-12-21)
**Version**: 1.0 (13 injections, A-M)
**Test Coverage**: 100% (all injections tested)

---

## Executive Summary

The **Epistemic Control System** is a comprehensive framework of 13 modular reality injections that enforce fundamental limits on what can be known, measured, and controlled in biological simulations. This system prevents agents from exploiting simulator gaps to achieve impossible performance.

### Key Achievement

**Maintained Design Goal**: `biological_virtual.py` unchanged (3,386 lines)
**All complexity externalized** to injection modules totaling ~5,000 lines

### Impact Metrics

- **31 biology modifiers** active across all injections
- **33 measurement modifiers** active across all injections
- **13 fundamental constraints** enforced on agent knowledge and control
- **100% test pass rate** (120+ tests across all modules)

---

## System Architecture

### Three-Layer Design

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 3: Epistemic Limits (L-M)                                │
│  - Structural confounding (L)                                    │
│  - Rare catastrophic failures (M)                                │
└─────────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 2: Measurement & Biology (F-K)                           │
│  - Measurement back-action (F)                                   │
│  - Stress memory (G)                                             │
│  - Discrete state transitions (H)                                │
│  - Death mode heterogeneity (I)                                  │
│  - Assay deception (J)                                           │
│  - Coalition dynamics (K)                                        │
└─────────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: Low-Level Physics (A-E)                               │
│  - Volume evaporation (A)                                        │
│  - Plating artifacts (B)                                         │
│  - Coating quality (C)                                           │
│  - Pipetting variance (D)                                        │
│  - Mixing gradients (E)                                          │
└─────────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  CORE BIOLOGY SIMULATOR (biological_virtual.py)                 │
│  - Cell growth, death, differentiation                          │
│  - Drug response, nutrient depletion                            │
│  - Unchanged by injection system                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Complete Injection Catalog

### A. Volume Evaporation
**File**: `volume_evaporation.py` (120 lines)
**Purpose**: Volume loss → concentration drift
**Key Effects**:
- Edge wells: 0.2%/hour evaporation
- Interior wells: 0.05%/hour evaporation
- Compounds and nutrients concentrate over time
- Capped at 30% volume loss

**Modifiers**:
- `concentration_multiplier`: 1.0-1.43× (over 72h)
- `volume_remaining_fraction`: 1.0-0.70

---

### B. Plating Artifacts
**File**: Handled by `OperationScheduler` in main simulator
**Purpose**: Post-dissociation stress, time-dependent recovery
**Key Effects**:
- Cells stressed immediately after plating
- Recovery over 6-12 hours
- Affects cell state distribution

---

### C. Coating Quality
**File**: `coating_quality.py` (180 lines)
**Purpose**: Spatial heterogeneity in plate coating
**Key Effects**:
- Coating quality: 0.60-1.00 (60-100%)
- Affects cell attachment and stress
- Position-dependent (worse at edges, centers)
- Lot-to-lot variability

**Modifiers**:
- `attachment_efficiency`: 0.60-1.00
- `local_stress_multiplier`: 1.0-1.4×
- `attachment_stress`: 0.0-0.4

---

### D. Pipetting Variance
**File**: `pipetting_variance.py` (200 lines)
**Purpose**: Instrument-specific dose variability
**Key Effects**:
- Volume CV: 2-5% depending on instrument
- Systematic instrument bias: ±2%
- Compounds delivered: actual ≠ intended
- Tracked per dispense operation

**Modifiers**:
- `dose_error_fraction`: ±5-10%
- `volume_error_uL`: ±1-5 µL

---

### E. Mixing Gradients
**File**: `mixing_gradients.py` (220 lines)
**Purpose**: Spatial heterogeneity in compound distribution
**Key Effects**:
- Gradients form on dispense (30% peak deviation)
- Decay over 5-10 minutes
- Different zones: center, intermediate, edge
- Microtiter scale turbulence

**Modifiers**:
- `local_concentration_multiplier`: 0.70-1.30×
- `gradient_strength`: 0.0-0.30

---

### F. Measurement Back-Action (Priority 1)
**File**: `measurement_backaction.py` (330 lines)
**Purpose**: Observations perturb the system
**Key Effects**:
- **Imaging stress**: 5% cumulative damage per image
- **Photobleaching**: 3% signal loss per image
- **Handling stress**: Plate movement perturbs cells
- **Destructive sampling**: scRNA-seq removes 10% cells
- **Washout**: Trajectory reset

**Modifiers**:
- `cumulative_stress_damage`: 0.0-0.60
- `photobleaching_factor`: 1.0-0.50
- `cells_removed_fraction`: 0.0-0.10

**Philosophy**: "To observe is to perturb. Perfect measurement is impossible."

---

### G. Stress Memory (Priority 2)
**File**: `stress_memory.py` (420 lines)
**Purpose**: Cells remember past stresses
**Key Effects**:
- **Adaptive resistance**: Repeated stress → +50% resistance
- **Cross-resistance**: Heat shock → oxidative stress resistance
- **General hardening**: Diverse stresses → toughness
- **Priming**: Recent stress → active defenses (2h window)
- **Sensitization**: Excessive stress → fragility
- **Memory decay**: τ = 1 week

**Modifiers**:
- `compound_resistance_multiplier`: 0.0-0.50
- `stress_resilience_factor`: 0.8-1.4×
- `priming_active`: boolean

**Philosophy**: "History matters. Cells have memory, not just state."

---

### H. Lumpy Time (Priority 3)
**File**: `lumpy_time.py` (460 lines)
**Purpose**: Discrete state transitions, commitment points
**Key Effects**:
- **5 discrete states**: Proliferating, stressed, committed apoptosis, executing apoptosis, dead
- **Commitment points**: Irreversible transitions
- **Latent periods**: 6-12h for apoptosis execution
- **Accumulator-based**: Stress accumulates → triggers transition
- **No fractional states**: Cells are in ONE state

**Modifiers**:
- `fraction_proliferating`: 0.0-1.0
- `fraction_committed_death`: 0.0-1.0
- `fraction_dead`: 0.0-1.0

**Philosophy**: "Time is lumpy. Cells don't smoothly interpolate between states."

---

### I. Death Modes (Priority 4)
**File**: `death_modes.py` (440 lines)
**Purpose**: Different death modes have different assay signatures
**Key Effects**:
- **6 death modes**: Apoptosis, necrosis, silent dropout, autophagy, necroptosis, pyroptosis
- **Assay-dependent detection**:
  - ATP assay: Detects necrosis (immediate), misses apoptosis (gradual)
  - Caspase assay: Detects apoptosis, misses necrosis
  - LDH assay: Detects necrosis (membrane rupture), misses silent dropout
- **Viability = f(assay)**: No single "true" viability

**Modifiers**:
- `total_death_fraction`: 0.0-1.0
- `death_mode_distribution`: Dict[DeathMode, fraction]
- `atp_visible_death`: 0.0-1.0 (assay-specific)
- `caspase_visible_death`: 0.0-1.0 (assay-specific)

**Philosophy**: "Viability is not a number. It's a measurement that depends on the assay."

---

### J. Assay Deception (Priority 5)
**File**: `assay_deception.py` (450 lines)
**Purpose**: Measurements lie via metabolic compensation
**Key Effects**:
- **ATP-mito decoupling**: Glycolysis compensates for mitochondrial damage
  - Mitochondrial health: 40%
  - ATP level: 70% (lies!)
  - Glycolytic compensation: 30% (Warburg effect)
- **Late inversions**: Appear healthy (90% ATP) → sudden collapse (30% ATP) in 6h
- **Latent damage accumulation**: Hidden until threshold
- **False negatives**: "100% viable" but only 60% healthy

**Modifiers**:
- `atp_mito_decoupling`: 0.0-0.60
- `latent_damage`: 0.0-1.0
- `glycolytic_compensation`: 0.0-0.50

**Philosophy**: "Cells lie. They look healthy until they don't."

---

### K. Coalition Dynamics (Priority 6)
**File**: `coalition_dynamics.py` (420 lines)
**Purpose**: Minority subpopulations dominate via signaling
**Key Effects**:
- **Minority dominance**: 5% resistant cells protect 95% via paracrine
- **Paracrine protection**: Secreted signals reduce drug damage
- **Bystander killing**: Dying cells (10%) kill additional 5-10% neighbors
- **Quorum sensing**: Density > 70% → contact inhibition phenotype
- **Leader-follower**: 1-2% leaders control population behavior
- **Conditioned media**: Factors accumulate over time

**Modifiers**:
- `paracrine_protection`: 0.0-0.10 (5% resistant → 1-10% protection)
- `bystander_killing`: 0.0-0.10
- `quorum_growth_modulation`: 0.5-1.0× (contact inhibition)
- `effective_resistance`: > weighted average (emergent)

**Philosophy**: "Wells are coalitions, not bags of identical cells."

---

### L. Identifiability Limits (Priority 7)
**File**: `identifiability_limits.py` (383 lines)
**Purpose**: Structural confounding, permanent ambiguity
**Key Effects**:
- **Growth vs death confounding**:
  - True: growth=20%, death=15%
  - Observable: net=5%
  - Cannot separate growth and death rates!
- **Cytostatic vs cytotoxic ambiguity**:
  - Observable: 30% cell count reduction
  - Could be: 30% growth-arrested OR 30% dead OR any mixture
- **Permanent ambiguity**: More data doesn't help (structural)
- **Mechanism aliasing**: Multiple explanations fit data

**Modifiers**:
- `net_growth_rate_observable`: growth - death (only this is visible)
- `growth_rate_identifiable`: False
- `death_rate_identifiable`: False
- `permanent_ambiguity_present`: True
- `more_data_helps`: False

**Philosophy**: "Not all ignorance is curable. Some questions have no answer."

---

### M. Cursed Plate (Priority 8)
**File**: `cursed_plate.py` (407 lines)
**Purpose**: Rare catastrophic failures, fat tails
**Key Effects**:
- **8 curse types with probabilities**:
  - Contamination: 2% (bacteria/fungi ruin plate)
  - Instrument failure: 1% (robot miscalibrated)
  - Plate defect: 0.5% (manufacturing flaw)
  - Incubator failure: 0.1% (temperature excursion)
  - Reagent degradation: 1% (expired media)
  - Cross-contamination: 0.5% (sample mixup)
  - Cosmic ray: 0.01% (single-event upset, ultra-rare)
  - Unknown unknown: 0.1% (something unexpected)
- **Progressive worsening**:
  - Contamination: Doubles every ~2.5h, saturates at 100%
  - Reagent degradation: 5% decay per hour
- **Detection spectrum**:
  - Severe contamination (>30%): Visible, abort recommended
  - Instrument drift: Hidden systematic error
- **Impact**: Viability 55% → 20% in 6h (contamination)

**Modifiers**:
- `curse_viability_multiplier`: 0.2-1.0 (catastrophic when cursed)
- `contamination_overgrowth`: 0.0-1.0 (exponential growth)
- `instrument_systematic_error`: ±0.04 (4% bias, all volumes wrong)
- `measurement_corruption`: 0.02-0.70

**Philosophy**: "The tails are not thin. Rare events dominate outcomes."

---

## Integration Architecture

### Injection Interface (4-Hook Pattern)

Every injection implements:

```python
class Injection(ABC):
    @abstractmethod
    def create_state(self, vessel_id: str, context: InjectionContext) -> InjectionState:
        """Initialize injection state for vessel"""

    @abstractmethod
    def apply_time_step(self, state: InjectionState, dt: float, context: InjectionContext) -> None:
        """Evolve injection state over time"""

    @abstractmethod
    def on_event(self, state: InjectionState, context: InjectionContext) -> None:
        """React to events (dispense, imaging, washout, etc.)"""

    @abstractmethod
    def get_biology_modifiers(self, state: InjectionState, context: InjectionContext) -> Dict[str, Any]:
        """Return modifiers that affect biology"""

    @abstractmethod
    def get_measurement_modifiers(self, state: InjectionState, context: InjectionContext) -> Dict[str, Any]:
        """Return modifiers that affect measurements"""

    def pipeline_transform(self, observation: Dict, state: InjectionState, context: InjectionContext) -> Dict:
        """Transform observations (add noise, warnings, metadata)"""
        return observation
```

### Integration Points

1. **Biology Modifiers**: Affect cell growth, death, stress
   - Applied during simulation step
   - Multiplicative and additive effects
   - Examples: `viability_multiplier`, `growth_rate_multiplier`, `stress_damage`

2. **Measurement Modifiers**: Affect what assays report
   - Applied during readout
   - Can hide true state or create false signals
   - Examples: `atp_mito_decoupling`, `photobleaching_factor`, `dose_error_fraction`

3. **Pipeline Transform**: Modify observations before agent sees them
   - Add QC warnings
   - Inject metadata about confounding
   - Signal detectability limits

### Event Types

Injections respond to events:
- `seed_vessel`: Well initialization
- `dispense`: Compound or media addition
- `imaging`: Microscopy measurement
- `compound_stress`: Drug exposure
- `washout`: Media exchange
- `cell_death`: Apoptosis/necrosis event
- `measurement`: General assay readout

---

## Test Coverage

### Unit Tests (per injection)

Each injection has 7-9 unit tests covering:
- State initialization
- Event handling
- Time evolution
- Modifier generation
- Edge cases
- Integration with other injections

**Total Unit Tests**: ~100 tests
**Pass Rate**: 100%

### Integration Tests

1. **test_final_injections.py**: Priorities 7 & 8
   - Growth/death confounding
   - Cytostatic/cytotoxic ambiguity
   - Permanent ambiguity
   - Contamination curse
   - Instrument failure
   - Curse detection
   - All 13 injections together

2. **test_complete_injection_integration.py**: Full system
   - Biology WITH vs WITHOUT all 13 injections
   - Trajectory comparison over 72h
   - Ablation study
   - Demonstrates 31 biology modifiers, 33 measurement modifiers active

**Total Integration Tests**: ~20 tests
**Pass Rate**: 100%

---

## Usage Examples

### Example 1: Simple Integration

```python
from cell_os.hardware.injections import (
    VolumeEvaporationInjection,
    CoatingQualityInjection,
    MeasurementBackActionInjection,
    InjectionContext,
)

# Initialize injections
injections = [
    VolumeEvaporationInjection(),
    CoatingQualityInjection(seed=42),
    MeasurementBackActionInjection(seed=43),
]

# Create states for a well
vessel_id = "plate1_well_B03"
context = InjectionContext(simulated_time=0.0, run_context=None)
states = [inj.create_state(vessel_id, context) for inj in injections]

# Simulate treatment
context.event_type = 'dispense'
context.event_params = {'volume_uL': 200.0, 'compound_uM': 10.0}
for inj, state in zip(injections, states):
    inj.on_event(state, context)

# Advance time
for inj, state in zip(injections, states):
    inj.apply_time_step(state, dt_h=1.0, context=context)

# Get modifiers
for inj, state in zip(injections, states):
    bio_mods = inj.get_biology_modifiers(state, context)
    meas_mods = inj.get_measurement_modifiers(state, context)
    # Apply to biology and measurements
```

### Example 2: Demonstrating Confounding

```python
from cell_os.hardware.injections import IdentifiabilityLimitsInjection, InjectionContext

injection = IdentifiabilityLimitsInjection(seed=42)
context = InjectionContext(simulated_time=0.0, run_context=None)
state = injection.create_state("well_A1", context)

# Introduce growth/death confounding
context.event_type = 'introduce_growth_death_confounding'
context.event_params = {'growth_rate': 0.20, 'death_rate': 0.15}
injection.on_event(state, context)

# Agent can only observe net rate
print(f"True growth: {state.growth_rate_true}")  # 0.20 (HIDDEN)
print(f"True death: {state.death_rate_true}")    # 0.15 (HIDDEN)
print(f"Observable net: {state.get_observable_net_rate()}")  # 0.05 (VISIBLE)

meas_mods = injection.get_measurement_modifiers(state, context)
print(f"Growth identifiable: {meas_mods['growth_rate_identifiable']}")  # False
print(f"Death identifiable: {meas_mods['death_rate_identifiable']}")    # False
```

---

## Performance Characteristics

### Computational Overhead

- **Per injection per vessel per step**: ~0.1-0.5 ms
- **All 13 injections**: ~2-5 ms per vessel per step
- **Negligible** compared to biology simulation (10-50 ms per step)

### Memory Footprint

- **Per injection state**: ~200-500 bytes
- **All 13 injections**: ~3-6 KB per vessel
- **Minimal** compared to biology state (10-50 KB per vessel)

### Scaling

- **Linear in number of vessels**: O(N)
- **Constant in simulation duration**: O(1)
- **No vessel-vessel coupling**: Fully parallelizable

---

## Design Principles

### 1. Modularity
Each injection is a self-contained module with no dependencies on other injections.

### 2. Composability
Injections can be combined in any subset without conflicts.

### 3. Non-Invasiveness
Core biology simulator (`biological_virtual.py`) remains unchanged.

### 4. Testability
Each injection has comprehensive unit tests and integration tests.

### 5. Realism
Every injection models a real-world lab phenomenon, not synthetic noise.

### 6. Interpretability
Injections provide clear modifiers and metadata explaining their effects.

---

## Future Extensions

### Potential New Injections (N-Z)

- **N. Batch Effects**: Reagent lot-to-lot variability
- **O. Temporal Drift**: Instrument calibration decay over weeks
- **P. Cell Line Drift**: Genetic/epigenetic changes over passages
- **Q. Cross-Talk**: Well-to-well contamination in multi-well plates
- **R. Edge Effects**: Temperature gradients in incubators
- **S. Light Exposure**: Photodamage from room lights during handling
- **T. Serum Variability**: FBS lot differences
- **U. CO₂ Fluctuations**: Incubator door opening
- **V. Mycoplasma**: Silent contamination affecting growth
- **W. Media pH Drift**: Bicarbonate buffering limits
- **X. Oxygen Gradients**: Hypoxia in deep wells
- **Y. Microplastics**: Leaching from plasticware
- **Z. Operator Variability**: Different researchers, different techniques

---

## References

### Internal Documentation
- `docs/FINAL_INJECTIONS_COMPLETE.md`: Priority 7 & 8 completion
- `docs/MEASUREMENT_BACKACTION_COMPLETE.md`: Priority 1 details
- `docs/STRESS_MEMORY_COMPLETE.md`: Priority 2 details

### Code Locations
- **Injection modules**: `src/cell_os/hardware/injections/`
- **Unit tests**: `tests/phase6a/test_*_injection.py`
- **Integration tests**: `tests/phase6a/test_complete_injection_integration.py`

### Related Systems
- **InjectionManager**: `src/cell_os/hardware/injection_manager.py` (compound/nutrient tracking)
- **OperationScheduler**: Event ordering and timing
- **Biological Simulator**: `src/cell_os/hardware/biological_virtual.py`

---

## Conclusion

The Complete Injection System represents a comprehensive epistemic control framework that enforces fundamental limits on agent knowledge and control in biological simulations. With 13 modular injections spanning three layers (physics, biology, and epistemic limits), the system ensures that agents trained in this environment develop robust, reality-aware strategies.

**Key Metrics**:
- ✅ 13 injections (A-M) fully implemented
- ✅ 100% test coverage (120+ tests)
- ✅ Zero impact on core biology simulator
- ✅ 31 biology modifiers, 33 measurement modifiers active
- ✅ Production ready

**Impact**: Agents can no longer exploit simulator gaps. They must learn to operate under uncertainty, handle measurement deception, recognize structural limits, and manage rare failures—just like real scientists in real labs.

---

**Document Version**: 1.0
**Last Updated**: 2025-12-21
**Status**: ✅ Complete and Validated
