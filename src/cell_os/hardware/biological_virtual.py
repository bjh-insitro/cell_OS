"""
Biological Virtual Machine - Core Simulation Engine

A high-fidelity cell culture simulator with rigorous death accounting, realistic noise,
and modular extension points for assays and stress mechanisms.

ARCHITECTURE
============

Core VM (this file):
    • Time advancement & scheduling
    • Vessel operations (seed, feed, passage, treat, washout)
    • Growth dynamics & confluence management
    • Death accounting with conservation law enforcement
    • Parameter loading from database or YAML
    • RNG stream management (biology, assay, operations)

Delegated Subsystems:
    • Assays (src/cell_os/hardware/assays/):
        - CellPaintingAssay - 5-channel morphology
        - LDHViabilityAssay - Scalar readouts (LDH, ATP, UPR, trafficking)
        - ScRNASeqAssay - Single-cell transcriptomics

    • Stress Mechanisms (src/cell_os/hardware/stress_mechanisms/):
        - ERStressMechanism - ER stress dynamics
        - MitoDysfunctionMechanism - Mitochondrial dysfunction
        - TransportDysfunctionMechanism - Cytoskeletal transport
        - NutrientDepletionMechanism - Glucose/glutamine consumption
        - MitoticCatastropheMechanism - Mitotic failure

KEY INVARIANTS
==============
1. Conservation Laws: Σ(all death fields) ≤ 1.0 - viability (strictly enforced)
2. Observer Independence: Assays cannot affect biology (read-only)
3. Competing Risks: Death hazards combine multiplicatively (no double-counting)
4. Epistemic Subpopulations: Subpops are epistemic-only (all sync to vessel viability)

EXTENSION POINTS
================
• Add new assays: Inherit from AssaySimulator, implement measure()
• Add new stress mechanisms: Inherit from StressMechanism, implement update()
• Add new death causes: Add field to TRACKED_DEATH_FIELDS in constants.py

REFERENCES
==========
See also:
    • VesselState - State container for individual vessels
    • InjectionManager - Volume tracking & evaporation
    • RunContext - Batch effects & epistemic drift
    • biology_core - Single source of truth for biology

Last major semantic fixes: 2025-12-20 10:09:11 PST
- Fixed death accounting honesty (death_unknown vs death_unattributed split)
- Fixed conservation violations (hard errors everywhere, no silent renormalization)
- Fixed subpopulation semantics (epistemic-only, viabilities sync)
- Fixed multiplicative noise (lognormal preserves positivity)
- Fixed run-to-run variability (biology invariant, measurements vary, run-seeded technical factors)
- Fixed adversarial honesty (tail-aware hazards, not comforting means)
- Fixed RNG stream separation (count_cells uses assay RNG, observer independence)
- Fixed washout contamination (now actually affects measurements)
"""

import logging
import numpy as np
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from .virtual import VirtualMachine

class ConservationViolationError(Exception):
    """Raised when death accounting violates conservation law."""
    pass

# Import shared biology core (single source of truth)
from ..sim import biology_core

# Import run context for Phase 5B realism layer
from .run_context import RunContext, sample_plating_context, pipeline_transform

# Import InjectionManager for Injection A (Volume + Evaporation)
from .injection_manager import InjectionManager

# Import OperationScheduler for Injection B (Operation Scheduling)
from .operation_scheduler import OperationScheduler

# Logger must be defined before use
logger = logging.getLogger(__name__)

# Import database for parameter loading
try:
    from ..database.repositories.simulation_params import SimulationParamsRepository
    DB_AVAILABLE = True
except ImportError as e:
    raise ImportError(
        "SimulationParamsRepository is required but not available. "
        "Cannot fall back to YAML. Please ensure database dependencies are installed."
    ) from e

# Import assay simulators
from .assays import CellPaintingAssay, LDHViabilityAssay, ScRNASeqAssay

# Import stress mechanism simulators
from .stress_mechanisms import (
    ERStressMechanism,
    MitoDysfunctionMechanism,
    TransportDysfunctionMechanism,
    NutrientDepletionMechanism,
    MitoticCatastropheMechanism,
)


# Import constants from shared module (feature flags and core parameters only)
from .constants import (
    # Feature flags (control which mechanisms are active)
    ENABLE_NUTRIENT_DEPLETION,
    ENABLE_MITOTIC_CATASTROPHE,
    ENABLE_ER_STRESS,
    ENABLE_MITO_DYSFUNCTION,
    ENABLE_TRANSPORT_DYSFUNCTION,
    ENABLE_FEEDING_COSTS,
    ENABLE_INTERVENTION_COSTS,
    # Core parameters (used directly by VM)
    DEFAULT_MEDIA_GLUCOSE_mM,
    DEFAULT_MEDIA_GLUTAMINE_mM,
    DEFAULT_DOUBLING_TIME_H,
    FEEDING_TIME_COST_H,
    FEEDING_CONTAMINATION_RISK,
    WASHOUT_TIME_COST_H,
    WASHOUT_CONTAMINATION_RISK,
    WASHOUT_INTENSITY_RECOVERY_H,
    # Death accounting
    DEATH_EPS,
    TRACKED_DEATH_FIELDS,
)
# Note: Mechanism-specific parameters (ER_STRESS_K_ON, etc.) are now imported
# only by the mechanism modules in stress_mechanisms/


# Import shared utilities
from ._impl import stable_u32, lognormal_multiplier


class VesselState:
    """Tracks the biological state of a vessel."""

    def __init__(self, vessel_id: str, cell_line: str, initial_count: float = 0):
        self.vessel_id = vessel_id
        self.cell_line = cell_line
        self.cell_count = initial_count
        self.viability = 0.98
        self.passage_number = 0
        self.last_passage_time = 0.0
        self.last_feed_time = 0.0
        self.confluence = 0.0
        self.vessel_capacity = 1e7  # Default capacity
        self.seed_time = 0.0
        self.last_update_time = 0.0

        # Compound exposure tracking
        self.compounds = {}  # compound -> dose_uM
        self.compound_start_time = {}  # compound -> simulated_time when applied
        self.compound_meta = {}  # compound -> {ic50, hill_slope, stress_axis}

        # Death accounting (cumulative fractions)
        self.death_compound = 0.0  # Fraction killed by compound attrition
        self.death_confluence = 0.0  # Fraction killed by overconfluence
        self.death_unknown = 0.0  # Fraction killed by KNOWN unknowns (contamination, handling mishaps)
        self.death_unattributed = 0.0  # Fraction killed by UNKNOWN unknowns (numerical residue, missing model)
        self.death_mode = None  # "compound", "confluence", "mixed", "unknown", None

        # Mechanistic biology state
        # Media nutrients (simple scalars). last_feed_time already exists as the clock anchor.
        self.media_glucose_mM = DEFAULT_MEDIA_GLUCOSE_mM
        self.media_glutamine_mM = DEFAULT_MEDIA_GLUTAMINE_mM

        # Per-cell-line kinetics hook (can be overwritten elsewhere if you already do this)
        self.doubling_time_h = DEFAULT_DOUBLING_TIME_H

        # Additional death accounting (cumulative fractions)
        self.death_starvation = 0.0
        self.death_mitotic_catastrophe = 0.0
        self.death_er_stress = 0.0
        self.death_mito_dysfunction = 0.0
        # Fix #9: death_transport_dysfunction is a Phase 2 stub (no hazard in v1)
        # Explicitly excluded from conservation checks and death accounting
        # If you activate transport dysfunction death, you MUST:
        # 1. Add hazard proposal in _update_transport_dysfunction()
        # 2. Include in _commit_step_death() tracked_causes
        # 3. Include in _update_death_mode() tracked_total
        # Until then, this field exists only for schema compatibility
        self.death_transport_dysfunction = 0.0

        # Latent stress states (morphology-first, death-later)
        self.er_stress = 0.0  # ER stress level (0-1)
        self.mito_dysfunction = 0.0  # Mito dysfunction level (0-1)
        self.transport_dysfunction = 0.0  # Transport dysfunction level (0-1)

        # Phase 5: Population heterogeneity (3-bucket model)
        # Keystone fix: prevents overconfident early classification
        # Each subpopulation has shifted IC50 and stress thresholds
        self.subpopulations = {
            'sensitive': {
                'fraction': 0.25,  # 25% of cells are more sensitive
                'ic50_shift': 0.5,  # 50% lower IC50 (more sensitive to compounds)
                'stress_threshold_shift': 0.8,  # Lower death thresholds (die earlier)
                'viability': 0.98,  # Per-subpopulation viability
                'er_stress': 0.0,
                'mito_dysfunction': 0.0,
                'transport_dysfunction': 0.0
            },
            'typical': {
                'fraction': 0.50,  # 50% of cells are typical
                'ic50_shift': 1.0,  # Normal IC50
                'stress_threshold_shift': 1.0,  # Normal death thresholds
                'viability': 0.98,
                'er_stress': 0.0,
                'mito_dysfunction': 0.0,
                'transport_dysfunction': 0.0
            },
            'resistant': {
                'fraction': 0.25,  # 25% of cells are more resistant
                'ic50_shift': 2.0,  # 2× higher IC50 (more resistant to compounds)
                'stress_threshold_shift': 1.2,  # Higher death thresholds (die later)
                'viability': 0.98,
                'er_stress': 0.0,
                'mito_dysfunction': 0.0,
                'transport_dysfunction': 0.0
            }
        }

        # Phase 5B Injection #2: Plating artifacts (time-dependent)
        # Makes early timepoints unreliable for structural reasons
        self.plating_context = None  # Will be set during seed_vessel
        # Fields: post_dissociation_stress, seeding_density_error, clumpiness, tau_recovery_h

        # Intervention tracking (Phase 3: costs for washout/feed)
        self.last_washout_time = None  # Simulated time of last washout (for intensity penalty)
        self.washout_count = 0  # Total washouts performed (for ops cost tracking)
        # Washout contamination artifact (measurement-only, transient)
        self.washout_artifact_until_time = None
        self.washout_artifact_magnitude = 0.0

        # Cross-talk tracking (Phase 4 Option 3: transport → mito coupling)
        self.transport_high_since = None  # Time when transport dysfunction first exceeded threshold (or None)

        # Transient per-step bookkeeping (not persisted across steps)
        # These are intentionally prefixed to signal "internal mechanics"
        # Initialize to None to signal "no step in progress" (set to {} during _step_vessel)
        self._step_hazard_proposals: Optional[Dict[str, float]] = None
        self._step_viability_start: float = 0.0
        self._step_cell_count_start: float = 0.0
        self._step_total_hazard: float = 0.0
        self._step_total_kill: float = 0.0
        # Signal when we had to renormalize ledger (should be ~never)
        self._step_ledger_scale: float = 1.0

    # Phase 5: Properties for weighted mixture values from subpopulations
    @property
    def viability_mixture(self) -> float:
        """Compute viability as weighted mixture of subpopulations."""
        return sum(
            subpop['fraction'] * subpop['viability']
            for subpop in self.subpopulations.values()
        )

    @property
    def er_stress_mixture(self) -> float:
        """Compute ER stress as weighted mixture of subpopulations."""
        return sum(
            subpop['fraction'] * subpop['er_stress']
            for subpop in self.subpopulations.values()
        )

    @property
    def mito_dysfunction_mixture(self) -> float:
        """Compute mito dysfunction as weighted mixture of subpopulations."""
        return sum(
            subpop['fraction'] * subpop['mito_dysfunction']
            for subpop in self.subpopulations.values()
        )

    @property
    def transport_dysfunction_mixture(self) -> float:
        """Compute transport dysfunction as weighted mixture of subpopulations."""
        return sum(
            subpop['fraction'] * subpop['transport_dysfunction']
            for subpop in self.subpopulations.values()
        )

    def get_mixture_width(self, field: str) -> float:
        """
        Compute mixture width (std dev) for a field across subpopulations.

        This is CRITICAL for confidence accounting:
        - Wide mixture → conflicting signals → low confidence
        - Narrow mixture → consistent signals → high confidence

        Args:
            field: 'er_stress', 'mito_dysfunction', or 'transport_dysfunction'

        Returns:
            Standard deviation across subpopulations (weighted)
        """
        values = [subpop[field] for subpop in self.subpopulations.values()]
        fractions = [subpop['fraction'] for subpop in self.subpopulations.values()]

        # Weighted mean
        mean = sum(v * f for v, f in zip(values, fractions))

        # Weighted variance
        variance = sum(f * (v - mean) ** 2 for v, f in zip(values, fractions))

        return float(np.sqrt(variance))

    def get_artifact_inflated_mixture_width(self, field: str, simulated_time: float) -> float:
        """
        Compute mixture width inflated by plating artifacts (Phase 5B Injection #2).

        Early timepoints show wide mixture due to:
        - Biological heterogeneity (subpopulations)
        - Plating artifacts (post-dissociation stress, clumpiness)

        Artifacts decay over time, revealing true biological heterogeneity.

        Args:
            field: 'er_stress', 'mito_dysfunction', or 'transport_dysfunction'
            simulated_time: Current simulated time (for artifact decay)

        Returns:
            Mixture width inflated by time-decaying artifacts
        """
        # Base biological heterogeneity
        base_width = self.get_mixture_width(field)

        # Add plating artifact inflation (decays over time)
        if self.plating_context is not None:
            time_since_seed = simulated_time - self.seed_time
            tau_recovery = self.plating_context['tau_recovery_h']

            # Artifact contribution to apparent heterogeneity
            post_dissoc_stress = self.plating_context['post_dissociation_stress']
            clumpiness = self.plating_context['clumpiness']

            # Combined artifact decays exponentially
            artifact_width = (post_dissoc_stress + clumpiness) * float(
                np.exp(-time_since_seed / tau_recovery)
            )

            # Total width = sqrt(base^2 + artifact^2) (quadrature sum)
            total_width = float(np.sqrt(base_width**2 + artifact_width**2))
            return total_width

        return base_width


class BiologicalVirtualMachine(VirtualMachine):
    """
    Enhanced VirtualMachine with biological simulation capabilities.

    Features:
    - Cell growth modeling (exponential with saturation)
    - Viability dynamics (confluence-dependent)
    - Passage tracking
    - Compound treatment effects
    - Realistic noise injection
    - Data-driven parameters from YAML
    """

    def __init__(self, simulation_speed: float = 1.0,
                 params_file: Optional[str] = None,
                 use_database: bool = True,
                 seed: int = 0,
                 run_context: Optional[RunContext] = None):
        """
        Initialize BiologicalVirtualMachine.

        Args:
            simulation_speed: Speed multiplier for simulation
            params_file: Path to YAML parameter file
            use_database: Whether to use database for parameters
            seed: RNG seed for reproducibility (default: 0).
            run_context: Optional RunContext for Phase 5B realism layer.
                         If None, samples a new context from seed.

                  Seed contract:
                  - seed=0 → Fully deterministic (physics + measurements)
                  - seed=N → Independent run with seed N
                  - ALWAYS pass explicitly (never rely on random seed)

                  Future extension: Support separate seed_physics and seed_assay
                  for "deterministic physics, stochastic measurements" use case.
                  Never hack around this by conditionally consuming RNG.
        """
        super().__init__(simulation_speed=simulation_speed)
        self.vessel_states: Dict[str, VesselState] = {}
        self.simulated_time = 0.0
        self.use_database = use_database

        # Phase 5B: Sample run context if not provided
        # This injects correlated batch/lot/instrument effects
        if run_context is None:
            run_context = RunContext.sample(seed + 100)  # Offset seed for context
        self.run_context = run_context

        # Epistemic control: Track information gain claims vs reality
        # Creates pressure toward calibrated justifications
        try:
            from cell_os.epistemic_control import EpistemicController
            self.epistemic_controller = EpistemicController()
        except ImportError:
            self.epistemic_controller = None  # Graceful degradation if not available

        # Split RNG streams for observer independence
        # Each subsystem gets its own RNG so observation doesn't perturb physics
        # Agent 1: Wrap with ValidatedRNG to enforce stream partitioning
        from .rng_guard import ValidatedRNG

        # Growth RNG: Currently unused (growth is deterministic)
        # Reserved for future stochastic growth models (division timing, lag variability)
        self.rng_growth = ValidatedRNG(
            np.random.default_rng(seed + 1),
            stream_name="growth",
            allowed_patterns={"_update_vessel_growth", "_divide", "_seed"},
            enforce=True
        )

        # Treatment RNG: Biological variability in compound effects
        self.rng_treatment = ValidatedRNG(
            np.random.default_rng(seed + 2),
            stream_name="treatment",
            allowed_patterns={"_apply_compound", "_attrition", "_treatment", "_compute_viability", "lognormal_multiplier"},
            enforce=True
        )

        # Assay RNG: Measurement noise only (must not affect biology)
        self.rng_assay = ValidatedRNG(
            np.random.default_rng(seed + 3),
            stream_name="assay",
            allowed_patterns={"measure", "count_cells", "_measure_", "_compute_readouts", "lognormal_multiplier", "add_noise", "simulate_scrna_counts", "_sample_library_sizes", "_sample_gene_expression"},
            enforce=True
        )

        # Operations RNG: Operational randomness (contamination, errors)
        self.rng_operations = ValidatedRNG(
            np.random.default_rng(seed + 4),
            stream_name="operations",
            allowed_patterns={"feed", "washout", "_contamination", "_add_media"},
            enforce=True
        )

        # Injection A: Initialize InjectionManager (authoritative concentration spine)
        self.injection_mgr = InjectionManager(is_edge_well_fn=self._is_edge_well)

        # Injection B: Initialize OperationScheduler (deterministic event ordering)
        self.scheduler = OperationScheduler()

        self._load_parameters(params_file)
        self._load_raw_yaml_for_nested_params(params_file)  # Load nested params for CellROX/segmentation

        # Initialize assay simulators
        self._cell_painting_assay = CellPaintingAssay(self)
        self._ldh_viability_assay = LDHViabilityAssay(self)
        self._scrna_seq_assay = ScRNASeqAssay(self)

        # Initialize stress mechanism simulators
        self._er_stress = ERStressMechanism(self)
        self._mito_dysfunction = MitoDysfunctionMechanism(self)
        self._transport_dysfunction = TransportDysfunctionMechanism(self)
        self._nutrient_depletion = NutrientDepletionMechanism(self)
        self._mitotic_catastrophe = MitoticCatastropheMechanism(self)
    
    def _load_parameters(self, params_file: Optional[str] = None):
        """Load simulation parameters from database or YAML file."""
        
        # Try database first if enabled
        if self.use_database:
            try:
                db = SimulationParamsRepository()
                logger.info("Loading parameters from database")
                
                # Load cell line parameters
                self.cell_line_params = {}
                for cell_line_id in db.get_all_cell_lines():
                    params = db.get_cell_line_params(cell_line_id)
                    if params:
                        self.cell_line_params[cell_line_id] = {
                            'doubling_time_h': params.doubling_time_h,
                            'max_confluence': params.max_confluence,
                            'max_passage': params.max_passage,
                            'senescence_rate': params.senescence_rate,
                            'seeding_efficiency': params.seeding_efficiency,
                            'passage_stress': params.passage_stress,
                            'cell_count_cv': params.cell_count_cv,
                            'viability_cv': params.viability_cv,
                            'biological_cv': params.biological_cv,
                            'coating_required': params.coating_required
                        }
                
                # Load compound sensitivity
                self.compound_sensitivity = {}
                for compound in db.get_all_compounds():
                    self.compound_sensitivity[compound] = {}
                    for cell_line_id in db.get_all_cell_lines():
                        sensitivity = db.get_compound_sensitivity(compound, cell_line_id)
                        if sensitivity:
                            self.compound_sensitivity[compound][cell_line_id] = sensitivity.ic50_um
                            if 'hill_slope' not in self.compound_sensitivity[compound]:
                                self.compound_sensitivity[compound]['hill_slope'] = sensitivity.hill_slope

                # Drop compounds that never returned any sensitivity rows so we can
                # detect incomplete databases and fall back to YAML fixtures.
                self.compound_sensitivity = {
                    compound: data
                    for compound, data in self.compound_sensitivity.items()
                    if any(key != 'hill_slope' for key in data.keys())
                }
                
                # Load defaults
                self.defaults = {}
                for param_name in ['doubling_time_h', 'max_confluence', 'max_passage', 
                                  'senescence_rate', 'seeding_efficiency', 'passage_stress',
                                  'cell_count_cv', 'viability_cv', 'biological_cv',
                                  'default_ic50', 'default_hill_slope']:
                    value = db.get_default_param(param_name)
                    if value is not None:
                        self.defaults[param_name] = value
                
                has_defaults = bool(self.defaults)
                if self.cell_line_params and self.compound_sensitivity and has_defaults:
                    logger.info("Loaded parameters from database")
                    logger.info(f"  Cell lines: {len(self.cell_line_params)}")
                    logger.info(f"  Compounds: {len(self.compound_sensitivity)}")
                    return

                logger.warning(
                    "Simulation parameter database is missing data "
                    "(cell_lines=%s, compounds=%s, defaults=%s); "
                    "falling back to YAML",
                    len(self.cell_line_params),
                    len(self.compound_sensitivity),
                    len(self.defaults),
                )
                
            except Exception as e:
                logger.warning(f"Failed to load from database: {e}, falling back to YAML")
        
        # Fallback to YAML
        if params_file is None:
            # Default to data/simulation_parameters.yaml
            params_file = Path(__file__).parent.parent.parent.parent / "data" / "simulation_parameters.yaml"
        
        try:
            with open(params_file, 'r') as f:
                params = yaml.safe_load(f)
                
            self.cell_line_params = params.get('cell_lines', {})
            self.compound_sensitivity = params.get('compound_sensitivity', {})
            self.defaults = params.get('defaults', {})
            
            logger.info(f"Loaded simulation parameters from {params_file}")
            logger.info(f"  Cell lines: {len(self.cell_line_params)}")
            logger.info(f"  Compounds: {len(self.compound_sensitivity)}")
            
        except FileNotFoundError:
            logger.warning(f"Parameters file not found: {params_file}, using defaults")
            self._use_default_parameters()
            
    def _use_default_parameters(self):
        """Fallback to hardcoded parameters if YAML not found."""
        self.cell_line_params = {
            "HEK293T": {"doubling_time_h": 24.0, "max_confluence": 0.9},
            "HeLa": {"doubling_time_h": 20.0, "max_confluence": 0.85},
            "Jurkat": {"doubling_time_h": 18.0, "max_confluence": 1.0},
        }
        self.compound_sensitivity = {
            "staurosporine": {"HEK293T": 0.05, "HeLa": 0.08, "hill_slope": 1.2},
            "tunicamycin": {"HEK293T": 0.80, "HeLa": 0.60, "hill_slope": 1.0},
        }
        self.defaults = {
            "doubling_time_h": 24.0,
            "max_confluence": 0.9,
            "default_ic50": 1.0,
            "default_hill_slope": 1.0,
            "lag_duration_h": 12.0,
            "edge_penalty": 0.15
        }
        
    def flush_operations_now(self):
        """
        Deliver all pending operations at current simulated time.

        This is the ONLY supported way to force delivery without advancing time.
        Most code should use advance_time(dt) instead, which delivers at boundaries.

        Use cases:
        - After seed_vessel (new entity needs immediate concentrations)
        - Explicit "deliver now" for testing or special scenarios
        - Equivalent to advance_time(0.0) but more explicit

        Contract:
        - Flushes events with scheduled_time_h <= simulated_time
        - Events batch and execute in deterministic order (time, priority, event_id)
        - Does NOT advance simulated_time
        """
        if self.scheduler is not None:
            self.scheduler.flush_due_events(now_h=float(self.simulated_time), injection_mgr=self.injection_mgr)

    def advance_time(self, hours: float):
        """
        Advance simulated time and update all vessel states.

        TEMPORAL CONTRACT (the constitution for time semantics):
        =========================================================
        1. Biology integrates over [t0, t1) using state AS-OF t0
           - All "time since X" calculations use t0 (start of interval)
           - Growth, attrition, decay use t0 as reference time

        2. Stateful spines (authoritative concentrations) stamped at t1
           - InjectionManager updates (depletion, evaporation) belong at END of interval
           - Results represent "state after integrating over [t0, t1)"

        3. Clock advances to t1 AFTER biology completes
           - During vessel stepping: self.simulated_time = t0
           - After vessel stepping: self.simulated_time = t1

        4. Measurements taken at t1 (after advance_time returns)
           - Assays read self.simulated_time which is t1 post-advance
           - This is "readout after interval of biology"

        Interval semantics: left-closed [t0, t0+dt)
        - Events scheduled at t0 are delivered before physics (affect the interval)
        - Physics runs over [t0, t0+dt) with concentrations from delivered events
        - Clock advances to t0+dt after physics completes

        Special case: If hours <= 0, ONLY flush events (no physics, no clock advance).
        This is the explicit "deliver now" semantic (same as flush_operations_now).

        Args:
            hours: Time interval to simulate (hours)
        """
        hours = float(hours)

        # 1. Deliver events scheduled at current time (before physics)
        self.flush_operations_now()

        # Special case: Zero time means zero physics
        # Still step vessels (for mirroring), but skip evaporation and clock advance
        if hours <= 0:
            # Mirror concentrations without physics
            for vessel in self.vessel_states.values():
                self._step_vessel(vessel, 0.0)  # hours=0 triggers no-ops in physics
            return

        t0 = float(self.simulated_time)
        t1 = t0 + hours

        # 2. Apply physics over interval [t0, t1) using delivered concentrations
        if self.injection_mgr is not None:
            self.injection_mgr.step(dt_h=hours, now_h=t1)

        # 3. Step vessels over interval (mirror from InjectionManager, run biology)
        # CRITICAL: Keep simulated_time at t0 during stepping so "time since X" calculations
        # use START of interval, not end. This preserves [t0, t1) semantics.
        for vessel in self.vessel_states.values():
            self._step_vessel(vessel, hours)

        # 4. Advance clock to end of interval (AFTER vessel stepping)
        # Agent 1: Assert time monotonicity (fundamental causality invariant)
        assert t1 >= t0, (
            f"TIME MONOTONICITY VIOLATION: simulated_time would decrease!\n"
            f"  t0 (before): {t0:.6f}h\n"
            f"  t1 (after):  {t1:.6f}h\n"
            f"  hours (input): {hours:.6f}h\n"
            f"Time must never decrease (violates causality)."
        )
        self.simulated_time = t1

    def _propose_hazard(self, vessel: VesselState, hazard_per_h: float, death_field: str):
        """
        Directly propose a hazard rate (deaths per hour) for a death cause.

        This is the preferred interface for mechanisms that naturally compute rates.
        Skips the exp(-rate*hours) → ln(survival)/hours roundtrip.

        Args:
            vessel: Vessel state
            hazard_per_h: Hazard rate (deaths per hour, >= 0)
            death_field: Which cumulative death field to credit (must be in TRACKED_DEATH_FIELDS)

        Raises:
            ValueError: If death_field is not in TRACKED_DEATH_FIELDS (catches typos)
        """
        # Validate death_field against allowlist (catches typos like "death_mito_disfunction")
        if death_field not in TRACKED_DEATH_FIELDS:
            raise ValueError(
                f"Unknown death_field '{death_field}' in _propose_hazard. "
                f"Must be one of: {sorted(TRACKED_DEATH_FIELDS)}. "
                f"If this is a new field, add it to TRACKED_DEATH_FIELDS and conservation checks."
            )

        hazard = float(max(0.0, hazard_per_h))
        if not hasattr(vessel, "_step_hazard_proposals") or vessel._step_hazard_proposals is None:
            vessel._step_hazard_proposals = {}
        vessel._step_hazard_proposals[death_field] = vessel._step_hazard_proposals.get(death_field, 0.0) + hazard

    def _apply_instant_kill(self, vessel: VesselState, kill_fraction: float, death_field: str):
        """
        Apply instant kill event while maintaining death accounting conservation.

        This is for out-of-band "instant" events (treatment instant effect, contamination)
        that bypass the normal _commit_step_death() machinery. Ensures ledgers and
        subpopulations stay synchronized.

        GUARDRAIL: Cannot be called during hazard proposal/commit phase (_step_vessel).
        If you need to kill during a step, use _propose_hazard instead.

        Args:
            vessel: Vessel state
            kill_fraction: Fraction of viable cells to kill (0-1).
                          If viability=0.8 and kill_fraction=0.5, we kill 50% of viable cells,
                          so realized_kill = 0.8 * 0.5 = 0.4, and new viability = 0.4.
            death_field: Which death ledger to credit (e.g., "death_compound", "death_unknown")

        Raises:
            RuntimeError: If called during hazard proposal/commit phase
        """
        # Guardrail: prevent instant kill during proposal/commit phase (would violate conservation)
        if hasattr(vessel, '_step_hazard_proposals') and vessel._step_hazard_proposals is not None:
            raise RuntimeError(
                f"Cannot apply instant kill to {vessel.vessel_id} during hazard proposal/commit phase. "
                f"Use _propose_hazard instead to add death causes during _step_vessel."
            )

        # Validate death_field against allowlist (same as _propose_hazard)
        if death_field not in TRACKED_DEATH_FIELDS:
            raise ValueError(
                f"Unknown death_field '{death_field}' in _apply_instant_kill. "
                f"Must be one of: {sorted(TRACKED_DEATH_FIELDS)}. "
                f"If this is a new field, add it to TRACKED_DEATH_FIELDS and conservation checks."
            )

        # Clip kill fraction to [0, 1]
        kill_fraction = float(np.clip(kill_fraction, 0.0, 1.0))

        v0 = float(np.clip(vessel.viability, 0.0, 1.0))

        if v0 <= DEATH_EPS or kill_fraction <= DEATH_EPS:
            return

        # Apply kill as fraction of viable: v1 = v0 * (1 - kill_fraction)
        v1 = float(np.clip(v0 * (1.0 - kill_fraction), 0.0, 1.0))
        realized_kill = v0 - v1

        vessel.viability = v1

        # Scale cell count proportionally
        if v0 > DEATH_EPS:
            vessel.cell_count *= (v1 / v0)

        # Credit death ledger with realized kill (not input kill_fraction)
        current_ledger = getattr(vessel, death_field, 0.0)
        setattr(vessel, death_field, float(np.clip(current_ledger + realized_kill, 0.0, 1.0)))

        # Sync subpops to vessel (epistemic-only model)
        # Don't try to "distribute" kill - just sync viabilities
        for subpop in vessel.subpopulations.values():
            subpop['viability'] = vessel.viability

        # Update confluence (instant kills reduce cell count, so confluence should drop)
        vessel.confluence = vessel.cell_count / vessel.vessel_capacity

    def _commit_step_death(self, vessel: VesselState, hours: float):
        """
        Apply combined survival once and update cumulative death buckets proportionally.

        This is where competing-risks semantics happen:
        1. Sum all hazard proposals into total_hazard
        2. Compute combined survival = exp(-total_hazard * hours)
        3. Apply to viability/cell_count once
        4. Allocate realized death to buckets proportionally to hazard share
        5. Enforce conservation law: sum(death_*) <= 1 - viability + epsilon

        Special case: If hours <= 0, this is a no-op (zero time = zero physics).
        Proposals are recorded but not applied.

        Args:
            vessel: Vessel state
            hours: Time interval (hours)
        """
        hours = float(hours)

        # Zero time means zero physics (no death, no ledger updates)
        if hours <= 0:
            vessel._step_total_hazard = 0.0
            vessel._step_total_kill = 0.0
            vessel._step_ledger_scale = 1.0
            return

        hazards = vessel._step_hazard_proposals or {}

        # Sum hazard contributions (per hour)
        total_hazard = float(sum(max(0.0, h) for h in hazards.values()))
        vessel._step_total_hazard = total_hazard

        v0 = float(np.clip(vessel._step_viability_start, 0.0, 1.0))
        c0 = float(max(0.0, vessel._step_cell_count_start))

        if total_hazard <= DEATH_EPS or v0 <= DEATH_EPS:
            # No proposed death this step
            vessel.viability = v0
            vessel.cell_count = c0
            vessel._step_total_kill = 0.0
            vessel._step_ledger_scale = 1.0
            return

        # Combined survival from competing risks
        survival_total = float(np.exp(-total_hazard * hours))
        v1 = float(np.clip(v0 * survival_total, 0.0, 1.0))
        c1 = float(max(0.0, c0 * survival_total))

        vessel.viability = v1
        vessel.cell_count = c1

        # Agent 1: Assert non-negative counts (fundamental physical invariant)
        assert 0.0 <= vessel.viability <= 1.0, (
            f"NON-NEGATIVE INVARIANT VIOLATION: viability out of bounds!\n"
            f"  vessel_id: {vessel.vessel_id}\n"
            f"  viability: {vessel.viability:.10f}\n"
            f"  Expected: [0.0, 1.0]\n"
            f"Viability must be a valid fraction."
        )
        assert vessel.cell_count >= 0.0, (
            f"NON-NEGATIVE INVARIANT VIOLATION: negative cell count!\n"
            f"  vessel_id: {vessel.vessel_id}\n"
            f"  cell_count: {vessel.cell_count:.2f}\n"
            f"Cell count must be non-negative."
        )

        kill_total = float(max(0.0, v0 - v1))
        vessel._step_total_kill = kill_total

        # Allocate realized kill across causes in proportion to hazard share
        for field, h in hazards.items():
            h = float(max(0.0, h))
            if h <= 0.0:
                continue
            share = h / total_hazard
            d = kill_total * share
            current = getattr(vessel, field, 0.0)
            setattr(vessel, field, float(np.clip(current + d, 0.0, 1.0)))

        # Conservation enforcement (call shared assertion method)
        self._assert_conservation(vessel, gate="_commit_step_death")

        vessel._step_ledger_scale = 1.0  # Always 1.0 (no renormalization)

    def _assert_conservation(self, vessel: VesselState, gate: str = "unknown"):
        """
        Assert conservation law: sum(death_*) <= 1 - viability + epsilon.

        This catches:
        - Viability drift without death accounting
        - Cell_count changes without proper survival application
        - Death field overcrediting

        Args:
            vessel: Vessel to check
            gate: Name of calling function (for error messages)

        Raises:
            ConservationViolationError if conservation violated beyond DEATH_EPS
        """
        total_dead = 1.0 - float(np.clip(vessel.viability, 0.0, 1.0))
        credited = float(
            max(0.0, vessel.death_compound)
            + max(0.0, vessel.death_starvation)
            + max(0.0, vessel.death_mitotic_catastrophe)
            + max(0.0, vessel.death_er_stress)
            + max(0.0, vessel.death_mito_dysfunction)
            + max(0.0, vessel.death_confluence)
            + max(0.0, vessel.death_unknown)  # Include known unknowns (seeding stress, contamination)
        )

        if credited > total_dead + DEATH_EPS:
            raise ConservationViolationError(
                f"Ledger overflow in {gate}: credited={credited:.9f} > total_dead={total_dead:.9f}\n"
                f"  vessel_id={vessel.vessel_id}\n"
                f"  viability={vessel.viability:.6f}, total_dead={total_dead:.6f}\n"
                f"  compound={vessel.death_compound:.9f}, starvation={vessel.death_starvation:.9f}, "
                f"mitotic={vessel.death_mitotic_catastrophe:.9f}, er={vessel.death_er_stress:.9f}, "
                f"mito={vessel.death_mito_dysfunction:.9f}, confluence={vessel.death_confluence:.9f}, "
                f"unknown={vessel.death_unknown:.9f}\n"
                f"This is a simulator bug, not user error. Cannot be silently renormalized."
            )

    def _sync_subpopulation_viabilities(self, vessel: VesselState):
        """
        Phase 5: Sync subpopulation viabilities to vessel viability (epistemic-only model).

        SEMANTIC MODEL (corrected from previous broken implementation):
        - Subpopulations represent PARAMETER UNCERTAINTY, not separate physical populations
        - Each subpop has shifted IC50 and stress thresholds that affect latent state evolution
        - Subpop LATENT STATES (er_stress, mito_dysfunction) evolve independently with shifted params
        - Subpop VIABILITIES are currently synced to vessel (not independently computed)

        Mixture width of LATENT STATES drives confidence:
        - Wide mixture → conflicting signals → low confidence
        - Narrow mixture → consistent signals → high confidence

        TODO(Phase 6): Implement proper epistemic projections
        - Compute subpop viabilities as "what would vessel viability be if everyone had these parameters?"
        - This requires tracking subpop-specific hazards during proposal phase
        - Then subpop viabilities become counterfactual projections, not physics
        - For now, we sync them to avoid the semantic break of "post-hoc synthetic death"
        """
        # Simple sync: all subpops have same viability as vessel
        # This is honest: we're not pretending to model subpop-specific death yet
        for subpop in vessel.subpopulations.values():
            subpop['viability'] = vessel.viability

        # Verify mixture equals vessel (should be exact by construction)
        mixture = vessel.viability_mixture
        if abs(mixture - vessel.viability) > 1e-9:
            logger.error(
                f"Subpop sync failed: vessel={vessel.viability:.9f}, mixture={mixture:.9f}. "
                f"This should never happen with sync-only model."
            )
            # Force sync
            for subpop in vessel.subpopulations.values():
                subpop['viability'] = vessel.viability

    def _step_vessel(self, vessel: VesselState, hours: float):
        """
        Update vessel state over time interval.

        Order matters:
        0. Mirror evaporated concentrations (evaporation already applied globally in advance_time)
        1. Growth (viable cells only)
        2. Death proposal phase (nutrient depletion, compound attrition, mitotic catastrophe)
        3. Commit death (apply combined survival, allocate to ledgers)
        4. Confluence management (cap growth, no killing)
        5. Update death mode label
        6. Clean up per-step bookkeeping (signals that step is complete)
        """
        # 0) Mirror the authoritative concentrations into VesselState (evaporation already applied)
        if self.injection_mgr is not None and self.injection_mgr.has_vessel(vessel.vessel_id):
            vessel.compounds = self.injection_mgr.get_all_compounds_uM(vessel.vessel_id)
            vessel.media_glucose_mM = self.injection_mgr.get_nutrient_conc_mM(vessel.vessel_id, "glucose")
            vessel.media_glutamine_mM = self.injection_mgr.get_nutrient_conc_mM(vessel.vessel_id, "glutamine")

        # 1) Growth (viable cells only - dead cells don't grow)
        self._update_vessel_growth(vessel, hours)

        # 1b) Update contact pressure (lagged state, responds to confluence)
        self._update_contact_pressure(vessel, hours)

        # Begin death proposal phase: initialize per-step hazard proposals AFTER growth
        vessel._step_hazard_proposals = {}
        vessel._step_viability_start = float(np.clip(vessel.viability, 0.0, 1.0))
        vessel._step_cell_count_start = float(max(0.0, vessel.cell_count))
        vessel._step_total_hazard = 0.0
        vessel._step_total_kill = 0.0
        vessel._step_ledger_scale = 1.0

        # 2) Death proposal phase - mechanisms propose hazards without mutating viability
        # IMPORTANT: Transport dysfunction must update BEFORE mito dysfunction
        # so that cross-talk coupling sees current transport state
        if ENABLE_NUTRIENT_DEPLETION:
            self._nutrient_depletion.update(vessel, hours)

        if ENABLE_ER_STRESS:
            self._er_stress.update(vessel, hours)

        if ENABLE_TRANSPORT_DYSFUNCTION:
            self._transport_dysfunction.update(vessel, hours)

        if ENABLE_MITO_DYSFUNCTION:
            self._mito_dysfunction.update(vessel, hours)

        self._apply_compound_attrition(vessel, hours)

        # 3) Commit death once (combined survival + proportional allocation)
        self._commit_step_death(vessel, hours)

        # 3b) Phase 5: Sync subpop viabilities to vessel (epistemic-only model)
        # TODO(Phase 6): Implement proper subpop-specific hazards
        # Current approach: subpops represent parameter uncertainty, not separate populations
        # So their viabilities are projections, not independent physics
        self._sync_subpopulation_viabilities(vessel)

        # 4) Manage confluence (cap growth, but don't kill cells)
        self._manage_confluence(vessel)

        # 5) Update death mode label and enforce conservation law
        self._update_death_mode(vessel)

        # CRITICAL: Record END of interval time, not start
        # We simulated physics over [t0, t1), so "last update" should be t1
        vessel.last_update_time = float(self.simulated_time + hours)

        # 6) Clean up per-step bookkeeping (signals that step is complete)
        # This allows instant_kill to be called safely outside of _step_vessel
        vessel._step_hazard_proposals = None
            
    def _update_vessel_growth(self, vessel: VesselState, hours: float):
        """
        Update cell count based on growth model.

        Growth is for viable cells only - dead cells don't grow.
        """
        if hours <= 0:
            return  # Zero time → zero growth (no phantom effects)

        if vessel.cell_count == 0:
            return

        # Dead cells don't grow
        if vessel.viability <= 0.01:
            return

        # Get cell line parameters with fallback to defaults
        params = self.cell_line_params.get(vessel.cell_line, self.defaults)
        doubling_time = params.get("doubling_time_h", self.defaults.get("doubling_time_h", 24.0))
        max_confluence = params.get("max_confluence", self.defaults.get("max_confluence", 0.9))

        # Exponential growth with confluence-dependent saturation
        growth_rate = np.log(2) / doubling_time

        # --- 1. Lag Phase Dynamics ---
        # Growth ramps up linearly over lag_duration_h
        # CRITICAL: Use interval-integrated lag factor to avoid step-size dependence
        lag_duration = params.get("lag_duration_h", self.defaults.get("lag_duration_h", 12.0))
        time_since_seed_start = self.simulated_time - vessel.seed_time

        # Import at function level to avoid circular dependency
        from ..sim import biology_core
        lag_factor = biology_core.mean_lag_factor_over_interval(
            time_since_seed_start_h=time_since_seed_start,
            dt_h=hours,
            lag_duration_h=lag_duration
        )

        # --- 2. Spatial Edge Effects ---
        # Penalty for edge wells (evaporation/temp gradients)
        edge_penalty = 0.0
        # Extract well position from vessel_id (e.g., 'Plate1_A01' -> 'A01')
        import re
        well_match = re.search(r'([A-P]\d{1,2})$', vessel.vessel_id)
        well_position = well_match.group(1) if well_match else vessel.vessel_id
        is_edge = self._is_edge_well(well_position)
        if is_edge:
            edge_penalty = params.get("edge_penalty", self.defaults.get("edge_penalty", 0.15))

        # --- 3. Phase 5B: Run context growth rate modifier (incubator effects) ---
        bio_mods = self.run_context.get_biology_modifiers()
        context_growth_modifier = bio_mods['growth_rate_multiplier']

        # --- 4. Contact Inhibition (Biology Feedback) ---
        # High contact pressure slows cell cycle (G1 arrest, YAP/TAZ inactivation)
        # This is BIOLOGY FEEDBACK, not just measurement bias
        # Conservative: 20% growth penalty at full pressure (p=1.0)
        contact_pressure = float(np.clip(getattr(vessel, "contact_pressure", 0.0), 0.0, 1.0))
        contact_inhibition_factor = 1.0 - (0.20 * contact_pressure)  # 1.0 at p=0, 0.8 at p=1

        # Apply factors (NO viability_factor - death already updated cell_count)
        effective_growth_rate = growth_rate * lag_factor * (1.0 - edge_penalty) * context_growth_modifier * contact_inhibition_factor

        # --- 5. Confluence Saturation (Interval-Integrated) ---
        # Use predictor-corrector to approximate interval-average saturation
        # This removes dt-dependence from crossing the saturation nonlinearity
        cap = max(vessel.vessel_capacity, 1.0)
        n0 = float(vessel.cell_count)

        def _sat_factor(confluence: float) -> float:
            """Saturation factor: 1.0 at low confluence, 0.0 at capacity."""
            gf = 1.0 - (confluence / max_confluence) ** 2
            return float(max(0.0, min(1.0, gf)))

        # Start-of-interval saturation
        c0 = n0 / cap
        gf0 = _sat_factor(c0)

        # Predictor: assume gf0 holds over interval
        n1_pred = n0 * np.exp(effective_growth_rate * hours * gf0)
        c1_pred = n1_pred / cap
        gf1 = _sat_factor(c1_pred)

        # Interval-average saturation (trapezoid rule in saturation-space)
        gf_mean = 0.5 * (gf0 + gf1)

        # Corrected update using interval-average saturation
        vessel.cell_count = n0 * np.exp(effective_growth_rate * hours * gf_mean)

        # Agent 1: Assert non-negative count after growth
        assert vessel.cell_count >= 0.0, (
            f"NON-NEGATIVE INVARIANT VIOLATION: negative cell count after growth!\n"
            f"  vessel_id: {vessel.vessel_id}\n"
            f"  cell_count: {vessel.cell_count:.2f}\n"
            f"Growth should never produce negative counts."
        )

        # Update confluence diagnostic
        vessel.confluence = vessel.cell_count / cap
            
    def _apply_compound_attrition(self, vessel: VesselState, hours: float):
        """
        Apply time-dependent compound attrition.

        Uses biology_core for consistent attrition logic with standalone simulation.
        Attrition is "physics" - happens whether you observe it or not (Option 2).
        """
        # Authoritative: InjectionManager
        compounds_snapshot = None
        if self.injection_mgr is not None and self.injection_mgr.has_vessel(vessel.vessel_id):
            compounds_snapshot = self.injection_mgr.get_all_compounds_uM(vessel.vessel_id)
        else:
            compounds_snapshot = vessel.compounds

        if not compounds_snapshot:
            return

        # Lazy load thalamus params (need for dysfunction computation)
        if not hasattr(self, 'thalamus_params') or self.thalamus_params is None:
            self._load_cell_thalamus_params()

        for compound, dose_uM in compounds_snapshot.items():
            if dose_uM <= 0:
                continue

            # DEBUG: Log concentration being used for attrition
            logger.debug(f"_apply_compound_attrition: {vessel.vessel_id} {compound} dose_uM={dose_uM:.3f}")

            # Get compound metadata (stored during treat_with_compound)
            meta = vessel.compound_meta.get(compound)
            if not meta:
                logger.warning(f"Missing metadata for compound {compound}, skipping attrition")
                continue

            ic50_uM = meta['ic50_uM']
            hill_slope = meta['hill_slope']
            stress_axis = meta['stress_axis']
            base_ec50 = meta['base_ec50']

            # Time since treatment at START of interval (t0)
            time_since_treatment_start = self.simulated_time - vessel.compound_start_time.get(compound, self.simulated_time)

            # CRITICAL: Compute dysfunction from EXPOSURE, not cached measurement (Option 2)
            # This makes attrition observer-independent ("physics-based")
            transport_dysfunction = biology_core.compute_transport_dysfunction_from_exposure(
                cell_line=vessel.cell_line,
                compound=compound,
                dose_uM=dose_uM,
                stress_axis=stress_axis,
                base_potency_uM=base_ec50,  # Reference potency scale (base EC50)
                time_since_treatment_h=time_since_treatment_start,
                params=self.thalamus_params
            )

            # Mechanism-specific add-on: mitotic catastrophe for microtubule stress
            # IMPORTANT: This happens BEFORE attrition check because it's independent
            # (dividing cells can fail mitosis even if they haven't committed to death yet)
            if ENABLE_MITOTIC_CATASTROPHE:
                self._mitotic_catastrophe.apply(
                    vessel=vessel,
                    stress_axis=stress_axis,
                    dose_uM=float(dose_uM),
                    ic50_uM=float(ic50_uM),
                    hours=hours,
                )

            # Compute attrition rate using interval-integrated biology_core (single source of truth)
            # CRITICAL: Use interval_mean to properly integrate 12h commitment threshold
            attrition_rate = biology_core.compute_attrition_rate_interval_mean(
                cell_line=vessel.cell_line,
                compound=compound,
                dose_uM=dose_uM,
                stress_axis=stress_axis,
                ic50_uM=ic50_uM,
                hill_slope=hill_slope,
                transport_dysfunction=transport_dysfunction,
                time_since_treatment_start_h=time_since_treatment_start,
                dt_h=hours,
                current_viability=vessel.viability,
                params=self.thalamus_params
            )

            # Phase 5: Apply toxicity_scalar to death rates
            toxicity_scalar = meta.get('toxicity_scalar', 1.0)
            attrition_rate *= toxicity_scalar

            if attrition_rate <= 0:
                continue

            # Propose attrition hazard (deaths per hour)
            self._propose_hazard(vessel, attrition_rate, "death_compound")

            logger.debug(
                f"{vessel.vessel_id}: Attrition hazard={attrition_rate:.4f}/h, "
                f"dys={transport_dysfunction:.3f}"
            )

    def _manage_confluence(self, vessel: VesselState):
        """
        Manage over-confluence by capping growth.

        For Phase 0: Do NOT kill cells from overconfluence (prevents "logistics death"
        masquerading as "compound death"). Instead, cap cell count at max confluence.

        If you want confluence death for specific scenarios, opt into it explicitly.
        """
        params = self.cell_line_params.get(vessel.cell_line, self.defaults)
        max_confluence = params.get("max_confluence", self.defaults.get("max_confluence", 0.9))

        if vessel.confluence > max_confluence:
            # Cap growth at max confluence (cells contact-inhibit)
            vessel.cell_count = max_confluence * vessel.vessel_capacity
            vessel.confluence = max_confluence

            # If you enabled confluence death, track it and cap
            # vessel.death_confluence = min(1.0, max(0.0, vessel.death_confluence))

            logger.debug(f"{vessel.vessel_id}: Confluence capped at {max_confluence:.1%}")

    def _update_death_mode(self, vessel: VesselState):
        """
        Update death mode label and enforce conservation law.

        Enforces complete accounting: sum of all death causes = 1 - viability (+epsilon)

        Known death causes:
        - death_compound: Instant viability effect + attrition
        - death_starvation: Nutrient depletion
        - death_mitotic_catastrophe: Mitotic failure under microtubule stress
        - death_er_stress: ER stress accumulation
        - death_mito_dysfunction: Mitochondrial dysfunction
        - death_confluence: Overconfluence stress

        Unknown death includes:
        - Seeding stress (initial viability < 1.0)
        - Delta tracking errors (numerical precision)
        - Any death not attributable to known causes
        """
        # ENFORCE CONSERVATION STRICTLY (no silent laundering)

        # 1. Check for negative viability (impossible)
        if vessel.viability < -DEATH_EPS:
            raise ConservationViolationError(
                f"Negative viability detected: {vessel.viability:.6f} "
                f"(vessel_id={vessel.vessel_id}). This is impossible and indicates a bug."
            )

        # Clamp viability to [0,1] (only for numerical noise near boundaries)
        vessel.viability = float(np.clip(vessel.viability, 0.0, 1.0))

        # Compute total death and currently tracked causes
        total_dead = 1.0 - vessel.viability

        # Tracked KNOWN causes (including credited unknowns like contamination)
        tracked_known = (
            vessel.death_compound
            + vessel.death_starvation
            + vessel.death_mitotic_catastrophe
            + vessel.death_er_stress
            + vessel.death_mito_dysfunction
            + vessel.death_confluence
            + vessel.death_unknown  # KNOWN unknowns (explicitly credited)
        )

        # 2. Check for ledger overflow (tracked > total_dead)
        # This means death was over-credited somewhere - NOT ALLOWED
        # Use DEATH_EPS for strict conservation
        if tracked_known > total_dead + DEATH_EPS:
            raise ConservationViolationError(
                f"Death ledger overflow: tracked={tracked_known:.6f} > total_dead={total_dead:.6f} "
                f"(vessel_id={vessel.vessel_id})\n"
                f"  compound={vessel.death_compound:.6f}, starvation={vessel.death_starvation:.6f}, "
                f"  mitotic={vessel.death_mitotic_catastrophe:.6f}, er_stress={vessel.death_er_stress:.6f}, "
                f"  mito={vessel.death_mito_dysfunction:.6f}, confluence={vessel.death_confluence:.6f}, "
                f"  unknown={vessel.death_unknown:.6f}\n"
                f"This violation cannot be silently renormalized."
            )

        # Unattributed is whatever is left (numerical residue or missing model)
        # This is NOT a credited bucket - it's bookkeeping only
        vessel.death_unattributed = float(max(0.0, total_dead - tracked_known))
        for field in [
            "death_compound",
            "death_starvation",
            "death_mitotic_catastrophe",
            "death_er_stress",
            "death_mito_dysfunction",
            "death_confluence",
            "death_unknown",
        ]:
            setattr(vessel, field, float(np.clip(getattr(vessel, field, 0.0), 0.0, 1.0)))

        # Conservation law (epsilon tolerance)
        # Use DEATH_EPS for strict, consistent conservation enforcement
        total_dead = 1.0 - vessel.viability
        tracked_total = (
            vessel.death_compound
            + vessel.death_starvation
            + vessel.death_mitotic_catastrophe
            + vessel.death_er_stress
            + vessel.death_mito_dysfunction
            + vessel.death_confluence
            + vessel.death_unknown
            + vessel.death_unattributed
        )
        if tracked_total > total_dead + DEATH_EPS:
            raise ConservationViolationError(
                f"Death ledger violates conservation law after clamping: "
                f"tracked={tracked_total:.6f} > total_dead={total_dead:.6f} "
                f"(vessel_id={vessel.vessel_id}, compound={vessel.death_compound:.6f}, "
                f"starvation={vessel.death_starvation:.6f}, mitotic={vessel.death_mitotic_catastrophe:.6f}, "
                f"er_stress={vessel.death_er_stress:.6f}, mito={vessel.death_mito_dysfunction:.6f}, "
                f"confluence={vessel.death_confluence:.6f}, unknown={vessel.death_unknown:.6f}, "
                f"unattributed={vessel.death_unattributed:.6f})"
            )

        # Death mode labeling (based on thresholds)
        threshold = 0.05  # 5% death required to label
        # Lower threshold for unknown death if no other causes (seeding stress detection)
        unknown_threshold = 0.01 if vessel.death_compound == 0 and vessel.death_confluence == 0 else threshold

        compound_death = vessel.death_compound > threshold
        starvation_death = vessel.death_starvation > threshold
        mitotic_death = vessel.death_mitotic_catastrophe > threshold
        er_stress_death = vessel.death_er_stress > threshold
        mito_dysfunction_death = vessel.death_mito_dysfunction > threshold
        confluence_death = vessel.death_confluence > threshold
        unknown_death = vessel.death_unknown > unknown_threshold

        # Priority: known causes > unknown > none
        # Count number of active causes
        active_causes = sum([compound_death, starvation_death, mitotic_death, er_stress_death, mito_dysfunction_death, confluence_death])

        if active_causes > 1:
            vessel.death_mode = "mixed"
        elif compound_death:
            vessel.death_mode = "compound"
        elif starvation_death:
            vessel.death_mode = "starvation"
        elif mitotic_death:
            vessel.death_mode = "mitotic"
        elif er_stress_death:
            vessel.death_mode = "er_stress"
        elif mito_dysfunction_death:
            vessel.death_mode = "mito_dysfunction"
        elif confluence_death:
            vessel.death_mode = "confluence"
        elif unknown_death:
            vessel.death_mode = "unknown"
        elif vessel.viability < 0.5:
            # Significant death but nothing exceeds threshold (accounting bug)
            vessel.death_mode = "unknown"
        else:
            vessel.death_mode = None  # Still healthy
            
    def seed_vessel(self, vessel_id: str, cell_line: str, initial_count: float, capacity: float = 1e7, initial_viability: float = None):
        """Initialize a vessel with cells.

        Args:
            vessel_id: Vessel identifier
            cell_line: Cell line name
            initial_count: Initial cell count
            capacity: Vessel capacity
            initial_viability: Override initial viability (default: 0.98 for realistic seeding stress)
        """
        state = VesselState(vessel_id, cell_line, initial_count)
        if initial_viability is not None:
            state.viability = initial_viability

        # Credit seeding stress to death_unknown (known operational artifact)
        seeding_stress_death = 1.0 - state.viability
        if seeding_stress_death > DEATH_EPS:
            state.death_unknown = seeding_stress_death

        state.vessel_capacity = capacity
        state.last_passage_time = self.simulated_time
        state.seed_time = self.simulated_time

        # Phase 5B Injection #2: Sample plating context (post-dissociation stress)
        # Creates time-dependent artifacts that make early timepoints unreliable
        # Seed deterministically from run context + vessel_id (NOT simulated_time, which creates discontinuities)
        plating_seed = stable_u32(f"plating_{self.run_context.seed}_{vessel_id}")
        state.plating_context = sample_plating_context(plating_seed)

        # Injection A+B: seed event establishes initial exposure state
        self.scheduler.submit_intent(
            vessel_id=vessel_id,
            event_type="SEED_VESSEL",
            requested_time_h=float(self.simulated_time),
            payload={
                "initial_nutrients_mM": {
                    "glucose": float(DEFAULT_MEDIA_GLUCOSE_mM),
                    "glutamine": float(DEFAULT_MEDIA_GLUTAMINE_mM),
                }
            },
        )
        # Seed requires immediate delivery (entity creation, not mutation)
        self.flush_operations_now()

        # Mirror InjectionManager -> VesselState fields (back-compat)
        state.media_glucose_mM = self.injection_mgr.get_nutrient_conc_mM(vessel_id, "glucose")
        state.media_glutamine_mM = self.injection_mgr.get_nutrient_conc_mM(vessel_id, "glutamine")
        state.compounds = self.injection_mgr.get_all_compounds_uM(vessel_id)

        # Update death mode to complete accounting (seeding stress → unknown → unattributed residue)
        self._update_death_mode(state)

        self.vessel_states[vessel_id] = state
        logger.info(f"Seeded {vessel_id} with {initial_count:.2e} {cell_line} cells (viability={state.viability:.1%})")

    def feed_vessel(
        self,
        vessel_id: str,
        glucose_mM: float = DEFAULT_MEDIA_GLUCOSE_mM,
        glutamine_mM: float = DEFAULT_MEDIA_GLUTAMINE_mM,
    ) -> Dict[str, Any]:
        """
        Media change / feed: resets nutrient levels and last_feed_time.

        Costs (if ENABLE_FEEDING_COSTS=True):
        - Time: Consumes FEEDING_TIME_COST_H operator hours
        - Contamination risk: Small probability of introducing contamination (death_unknown bump)

        These costs prevent "feed every hour" from being a dominant strategy.
        """
        if vessel_id not in self.vessel_states:
            return {"status": "error", "message": "Vessel not found", "vessel_id": vessel_id}

        vessel = self.vessel_states[vessel_id]

        # Injection A+B: feed event updates nutrient concentrations in spine
        self.scheduler.submit_intent(
            vessel_id=vessel_id,
            event_type="FEED_VESSEL",
            requested_time_h=float(self.simulated_time),
            payload={
                "nutrients_mM": {
                    "glucose": float(max(0.0, glucose_mM)),
                    "glutamine": float(max(0.0, glutamine_mM)),
                }
            },
        )
        # Deliver immediately so logging is honest (operations feel immediate)
        self.flush_operations_now()
        # Mirror spine -> vessel fields for logging
        vessel.media_glucose_mM = self.injection_mgr.get_nutrient_conc_mM(vessel_id, "glucose")
        vessel.media_glutamine_mM = self.injection_mgr.get_nutrient_conc_mM(vessel_id, "glutamine")

        vessel.last_feed_time = self.simulated_time

        # Return realized values (event delivered immediately)
        result = {
            "status": "success",
            "action": "feed",
            "vessel_id": vessel_id,
            "media_glucose_mM": vessel.media_glucose_mM,  # Realized value (delivered)
            "media_glutamine_mM": vessel.media_glutamine_mM,  # Realized value (delivered)
            "time": self.simulated_time,
        }

        if ENABLE_FEEDING_COSTS:
            # Time cost (operator hours)
            result["time_cost_h"] = FEEDING_TIME_COST_H

            # Contamination risk (probabilistic)
            # Fix #8: Use operations RNG, not assay RNG (observer independence)
            contamination_roll = self.rng_operations.random()
            if contamination_roll < FEEDING_CONTAMINATION_RISK:
                # Small contamination introduces minor death (1-3% viability loss)
                contamination_severity = self.rng_operations.uniform(0.01, 0.03)
                self._apply_instant_kill(vessel, contamination_severity, "death_unknown")
                result["contamination"] = True
                result["contamination_severity"] = contamination_severity
                logger.warning(f"Feeding {vessel_id} introduced contamination ({contamination_severity:.1%} loss)")
            else:
                result["contamination"] = False

        logger.info(f"Fed {vessel_id} (glucose={vessel.media_glucose_mM:.1f}mM, glutamine={vessel.media_glutamine_mM:.1f}mM)")
        return result

    def washout_compound(self, vessel_id: str, compound: Optional[str] = None) -> Dict[str, Any]:
        """
        Remove compound(s) from vessel (media change / washout).

        Enables intervention policies like pulse dosing, compound removal, etc.
        Latent states (ER stress, etc.) will decay naturally after washout.

        Costs (if ENABLE_INTERVENTION_COSTS=True):
        - Time: Consumes WASHOUT_TIME_COST_H operator hours
        - Contamination risk: Small probability of intensity drop (measurement artifact)
        - Intensity penalty: Deterministic 5% signal drop for 12h (handling stress)

        IMPORTANT: Washout does NOT directly affect latent states (er_stress, mito_dysfunction,
        transport_dysfunction). Recovery comes from natural decay dynamics (k_off terms).
        Washout only removes compounds and adds intervention costs.

        Args:
            vessel_id: Vessel identifier
            compound: Specific compound to remove, or None to remove all compounds

        Returns:
            Dict with status, removed compounds, and cost metadata
        """
        if vessel_id not in self.vessel_states:
            return {"status": "error", "message": "Vessel not found", "vessel_id": vessel_id}

        vessel = self.vessel_states[vessel_id]

        # Determine removed set based on current state (before event delivery)
        if compound is None:
            removed = list(vessel.compounds.keys())
        else:
            if compound not in vessel.compounds:
                return {
                    "status": "error",
                    "message": f"Compound {compound} not present in vessel",
                    "vessel_id": vessel_id
                }
            removed = [compound]

        # Injection A+B: authoritative washout event
        self.scheduler.submit_intent(
            vessel_id=vessel_id,
            event_type="WASHOUT_COMPOUND",
            requested_time_h=float(self.simulated_time),
            payload={
                "compound": (None if compound is None else str(compound))
            },
        )
        # Deliver immediately so logging is honest (operations feel immediate)
        self.flush_operations_now()
        # Mirror spine -> vessel fields for logging
        vessel.compounds = self.injection_mgr.get_all_compounds_uM(vessel_id)

        logger.info(f"Washed out {('all compounds' if compound is None else compound)} from {vessel_id}")

        # Track washout for intervention costs
        vessel.last_washout_time = self.simulated_time
        vessel.washout_count += 1

        result = {
            "status": "success",
            "action": "washout",
            "vessel_id": vessel_id,
            "removed_compounds": removed,
            "time": self.simulated_time,
        }

        # Apply intervention costs (Phase 3)
        if ENABLE_INTERVENTION_COSTS:
            # Time cost (operator hours)
            result["time_cost_h"] = WASHOUT_TIME_COST_H

            # Contamination risk (intensity hit, NOT viability hit)
            # This is a measurement artifact, not biological damage
            # Fix #8: Use operations RNG (washout is an operation, not a measurement)
            contamination_roll = self.rng_operations.random()
            if contamination_roll < WASHOUT_CONTAMINATION_RISK:
                # Set transient measurement artifact (5-10% intensity drop for 12h)
                vessel.washout_artifact_until_time = self.simulated_time + WASHOUT_INTENSITY_RECOVERY_H
                vessel.washout_artifact_magnitude = float(self.rng_operations.uniform(0.05, 0.10))
                result["contamination_event"] = True
                result["artifact_magnitude"] = vessel.washout_artifact_magnitude
                logger.warning(f"Washout contamination event in {vessel_id} ({vessel.washout_artifact_magnitude:.1%} intensity artifact)")
            else:
                result["contamination_event"] = False

            # Deterministic intensity penalty (handling stress)
            # Cells are disturbed by media change → measurement noise for next 12h
            result["intensity_penalty_applied"] = True
            logger.debug(f"Washout intensity penalty applied to {vessel_id} (recovers over {WASHOUT_INTENSITY_RECOVERY_H}h)")
        else:
            result["contamination_event"] = False
            result["intensity_penalty_applied"] = False

        self._simulate_delay(0.5)  # Media change takes time

        return result

    def count_cells(self, sample_loc: str, **kwargs) -> Dict[str, Any]:
        """Count cells with realistic biological variation."""
        vessel_id = kwargs.get("vessel_id", sample_loc)

        if vessel_id not in self.vessel_states:
            # Return default if vessel not tracked
            return super().count_cells(sample_loc, **kwargs)

        vessel = self.vessel_states[vessel_id]

        # Agent 1: Lock measurement purity - capture state before measurement
        state_before = (vessel.cell_count, vessel.viability, vessel.confluence)

        # Get cell line-specific noise parameters
        params = self.cell_line_params.get(vessel.cell_line, self.defaults)
        count_cv = params.get("cell_count_cv", self.defaults.get("cell_count_cv", 0.10))
        viability_cv = params.get("viability_cv", self.defaults.get("viability_cv", 0.02))

        # Add measurement noise (only if CV > 0)
        # Fix: Use assay RNG, not growth RNG (observer independence)
        measured_count = vessel.cell_count
        if count_cv > 0:
            measured_count *= lognormal_multiplier(self.rng_assay, count_cv)
        measured_count = max(0, measured_count)

        # Viability measurement noise (only if CV > 0)
        measured_viability = vessel.viability
        if viability_cv > 0:
            measured_viability *= lognormal_multiplier(self.rng_assay, viability_cv)
        measured_viability = np.clip(measured_viability, 0.0, 1.0)

        self._simulate_delay(0.5)

        # Agent 1: Assert measurement did not perturb biological state
        state_after = (vessel.cell_count, vessel.viability, vessel.confluence)
        assert state_before == state_after, (
            f"MEASUREMENT PURITY VIOLATION: count_cells() mutated vessel state!\n"
            f"  Before: count={state_before[0]:.2f}, via={state_before[1]:.6f}, conf={state_before[2]:.4f}\n"
            f"  After:  count={state_after[0]:.2f}, via={state_after[1]:.6f}, conf={state_after[2]:.4f}\n"
            f"Measurement functions must be read-only. Observer independence violated."
        )

        return {
            "status": "success",
            "action": "count_cells",
            "count": measured_count,
            "viability": measured_viability,
            "concentration": measured_count / 1.0,  # Assume 1mL sample
            "confluence": vessel.confluence,
            "passage_number": vessel.passage_number,
            "vessel_id": vessel_id,
            "timestamp": datetime.now().isoformat()
        }
        
    def passage_cells(self, source_vessel: str, target_vessel: str, split_ratio: float = 4.0, **kwargs) -> Dict[str, Any]:
        """Simulate cell passaging.

        split_ratio is a divisor: cells_transferred = source.cell_count / split_ratio
        - split_ratio < 1.0: ERROR (would mint cells)
        - split_ratio == 1.0: transfer all cells (source deleted)
        - split_ratio > 1.0: transfer fraction 1/split_ratio
        """
        if source_vessel not in self.vessel_states:
            logger.warning(f"Source vessel {source_vessel} not found in state tracker")
            return {"status": "error", "message": "Vessel not found"}

        # Guard against cell minting
        if split_ratio < 1.0:
            raise ValueError(
                f"split_ratio must be >= 1.0 (got {split_ratio}). "
                f"split_ratio < 1.0 would transfer more cells than exist (cell minting). "
                f"Use split_ratio=1.0 to transfer all cells."
            )

        source = self.vessel_states[source_vessel]

        # Calculate cells transferred
        cells_transferred = source.cell_count / split_ratio
        
        # Get cell line-specific passage stress
        params = self.cell_line_params.get(source.cell_line, self.defaults)
        passage_stress = params.get("passage_stress", self.defaults.get("passage_stress", 0.02))
        
        # Passage stress reduces viability slightly
        new_viability = source.viability * (1.0 - passage_stress)
        
        # Create new vessel state
        target_capacity = kwargs.get("target_capacity", source.vessel_capacity)
        target = VesselState(target_vessel, source.cell_line, cells_transferred)
        target.viability = new_viability
        target.passage_number = source.passage_number + 1
        target.last_passage_time = self.simulated_time
        target.vessel_capacity = target_capacity

        # Fix: Reset clocks for new vessel (passage is like seeding)
        target.seed_time = self.simulated_time
        target.last_update_time = self.simulated_time
        target.last_feed_time = self.simulated_time

        # Fix: Resample plating context (dissociation creates plating stress)
        plating_seed = stable_u32(f"plating_{self.run_context.seed}_{target_vessel}")
        target.plating_context = sample_plating_context(plating_seed)

        # Stateful transfer: carry over death buckets to preserve attribution history
        # Passaging is a population transfer operation, not a reset
        target.death_compound = source.death_compound
        target.death_starvation = source.death_starvation
        target.death_mitotic_catastrophe = source.death_mitotic_catastrophe
        target.death_er_stress = source.death_er_stress
        target.death_mito_dysfunction = source.death_mito_dysfunction
        target.death_confluence = source.death_confluence
        target.death_unknown = source.death_unknown

        # Add new passage stress to death_unknown
        passage_death = source.viability * passage_stress
        if passage_death > DEATH_EPS:
            target.death_unknown += passage_death

        # Carry over latent stress states (cells remember their stress history)
        target.er_stress = source.er_stress
        target.mito_dysfunction = source.mito_dysfunction
        target.transport_dysfunction = source.transport_dysfunction
        target.transport_high_since = source.transport_high_since

        # Carry over compound exposure (compounds don't vanish during passage unless washed)
        target.compounds = source.compounds.copy()
        target.compound_meta = source.compound_meta.copy()
        target.compound_start_time = source.compound_start_time.copy()

        # Copy subpopulation states (heterogeneity persists through passage)
        for subpop_name in target.subpopulations.keys():
            if subpop_name in source.subpopulations:
                target.subpopulations[subpop_name]['viability'] = source.subpopulations[subpop_name]['viability']
                target.subpopulations[subpop_name]['er_stress'] = source.subpopulations[subpop_name]['er_stress']
                target.subpopulations[subpop_name]['mito_dysfunction'] = source.subpopulations[subpop_name]['mito_dysfunction']
                target.subpopulations[subpop_name]['transport_dysfunction'] = source.subpopulations[subpop_name]['transport_dysfunction']

        self.vessel_states[target_vessel] = target

        # Verify conservation immediately (catch passage accounting bugs early)
        # This ensures that if we break stateful transfer logic later, we fail fast
        self._update_death_mode(target)
        self._assert_conservation(target, gate="passage_cells")

        # Update source (or remove if fully passaged)
        if split_ratio == 1.0:
            # Full passage: delete source vessel
            del self.vessel_states[source_vessel]
        elif split_ratio > 1.0:
            # Partial passage: subtract transferred cells from source
            source.cell_count -= cells_transferred
            
        self._simulate_delay(2.0)
        
        logger.info(f"Passaged {source_vessel} -> {target_vessel} (1:{split_ratio})")
        
        return {
            "status": "success",
            "action": "passage",
            "cells_transferred": cells_transferred,
            "target_viability": new_viability,
            "passage_number": target.passage_number
        }
        
    def treat_with_compound(self, vessel_id: str, compound: str, dose_uM: float, **kwargs) -> Dict[str, Any]:
        """
        Register compound exposure and apply instant viability effect.

        Time-dependent attrition is applied during advance_time(), not here.
        This prevents treatment from being "observer-dependent" (attrition is physics, not measurement).
        """
        if vessel_id not in self.vessel_states:
            logger.warning(f"Vessel {vessel_id} not found")
            return {"status": "error", "message": "Vessel not found"}

        vessel = self.vessel_states[vessel_id]

        # Lazy load thalamus params (for compound definitions)
        if not hasattr(self, 'thalamus_params') or self.thalamus_params is None:
            self._load_cell_thalamus_params()

        # Get compound parameters - FAIL LOUDLY if missing
        compound_params = self.thalamus_params.get('compounds', {}).get(compound)
        if not compound_params:
            raise KeyError(
                f"Unknown compound '{compound}' in thalamus_params. "
                f"Available compounds: {list(self.thalamus_params.get('compounds', {}).keys())}"
            )

        base_ec50 = compound_params['ec50_uM']
        hill_slope = compound_params['hill_slope']
        stress_axis = compound_params['stress_axis']

        # Get cell-line-specific IC50 sensitivity (if exists)
        cell_line_sensitivity = self.thalamus_params.get('cell_line_sensitivity', {})

        # Phase 5: Extract potency and toxicity scalars early (before computing effects)
        potency_scalar = float(kwargs.get('potency_scalar', 1.0))
        toxicity_scalar = float(kwargs.get('toxicity_scalar', 1.0))

        # Compute adjusted IC50 using biology_core (single source of truth)
        ic50_uM = biology_core.compute_adjusted_ic50(
            compound=compound,
            cell_line=vessel.cell_line,
            base_ec50=base_ec50,
            stress_axis=stress_axis,
            cell_line_sensitivity=cell_line_sensitivity,
            proliferation_index=biology_core.PROLIF_INDEX.get(vessel.cell_line)
        )

        # Phase 5B: Apply run context EC50 modifier (incubator/lot effects)
        bio_mods = self.run_context.get_biology_modifiers()
        ic50_uM *= bio_mods['ec50_multiplier']

        # Compute instant viability effect (no attrition yet - that's in advance_time)
        viability_effect = biology_core.compute_instant_viability_effect(
            dose_uM=dose_uM,
            ic50_uM=ic50_uM,
            hill_slope=hill_slope
        )

        # Phase 5: Apply toxicity_scalar to instant viability effect
        # Convert viability to death, scale, convert back
        instant_death_fraction = 1.0 - viability_effect
        instant_death_fraction *= toxicity_scalar
        viability_effect = 1.0 - instant_death_fraction
        viability_effect = float(np.clip(viability_effect, 0.0, 1.0))

        # Add biological variability (only if biological_cv > 0)
        params = self.cell_line_params.get(vessel.cell_line, self.defaults)
        biological_cv = params.get("biological_cv", self.defaults.get("biological_cv", 0.05))
        if biological_cv > 0:
            viability_effect *= lognormal_multiplier(self.rng_treatment, biological_cv)
            viability_effect = np.clip(viability_effect, 0.0, 1.0)

        # Injection A+B: authoritative exposure event
        # CRITICAL: Deliver exposure BEFORE instant kill to maintain causality
        # (cells can't die from a compound that doesn't exist in the spine yet)
        self.scheduler.submit_intent(
            vessel_id=vessel_id,
            event_type="TREAT_COMPOUND",
            requested_time_h=float(self.simulated_time),
            payload={
                "compound": str(compound),
                "dose_uM": float(dose_uM),
            },
        )
        # Deliver immediately so exposure exists in spine before instant kill
        self.flush_operations_now()
        # Mirror spine -> vessel fields for logging
        vessel.compounds = self.injection_mgr.get_all_compounds_uM(vessel_id)

        # Track compound start time for time_since_treatment calculations
        vessel.compound_start_time[compound] = self.simulated_time

        # Apply instant effect using conserved helper (maintains death accounting + subpop sync)
        # NOW compound exists in authoritative spine, so instant kill is causally consistent
        instant_death_fraction_applied = 1.0 - viability_effect

        # CRITICAL: For microtubule drugs on dividing cells, instant effect is division-linked
        # Credit to death_mitotic_catastrophe (not death_compound) to avoid double-attribution
        # For non-dividing cells or other stress axes, use death_compound
        if stress_axis == 'microtubule':
            prolif_index = biology_core.PROLIF_INDEX.get(vessel.cell_line, 1.0)
            if prolif_index >= 0.3:  # Dividing cells (same threshold as _apply_mitotic_catastrophe)
                death_field = "death_mitotic_catastrophe"
            else:
                death_field = "death_compound"  # Non-dividing (neurons) - transport collapse
        else:
            death_field = "death_compound"  # All other stress axes

        self._apply_instant_kill(vessel, instant_death_fraction_applied, death_field)

        # Phase 5: Store potency and toxicity scalars in metadata (already extracted above)
        vessel.compound_meta[compound] = {
            'ic50_uM': ic50_uM,
            'hill_slope': hill_slope,
            'stress_axis': stress_axis,
            'base_ec50': base_ec50,
            'potency_scalar': potency_scalar,  # Scales k_on for latent induction
            'toxicity_scalar': toxicity_scalar  # Scales death rates
        }

        self._simulate_delay(0.5)

        logger.info(f"Treated {vessel_id} with {dose_uM}μM {compound} (instant viability: {vessel.viability:.2f}, IC50={ic50_uM:.2f}µM)")

        return {
            "status": "success",
            "action": "treat",
            "compound": compound,
            "dose_uM": dose_uM,
            "viability_effect": viability_effect,
            "current_viability": vessel.viability,
            "ic50_uM": ic50_uM,
            "hill_slope": hill_slope,
            "stress_axis": stress_axis
        }
        
    def incubate(self, duration_seconds: float, temperature_c: float, **kwargs) -> Dict[str, Any]:
        """Simulate incubation with cell growth."""
        hours = duration_seconds / 3600.0
        
        # Advance time for all vessels
        self.advance_time(hours)
        
        # Fast-forward simulation time
        self._simulate_delay(0.5)
        
        logger.info(f"Incubated for {hours:.1f}h at {temperature_c}°C (simulated time: {self.simulated_time:.1f}h)")
        
        return {
            "status": "success",
            "action": "incubate",
            "duration_h": hours,
            "simulated_time_h": self.simulated_time,
            "vessels_updated": len(self.vessel_states)
        }
        
    def get_vessel_state(self, vessel_id: str) -> Optional[Dict[str, Any]]:
        """Get current state of a vessel."""
        if vessel_id not in self.vessel_states:
            return None

        vessel = self.vessel_states[vessel_id]
        return {
            "vessel_id": vessel.vessel_id,
            "cell_line": vessel.cell_line,
            "cell_count": vessel.cell_count,
            "viability": vessel.viability,
            "confluence": vessel.confluence,
            "passage_number": vessel.passage_number,
            "compounds": vessel.compounds
        }

    def get_rng_audit(self, reset: bool = True) -> Dict[str, int]:
        """Get RNG stream call counts for audit (Agent 1: Task 1.2).

        Returns call counts for each RNG stream since last audit.
        This enables detection of stream contamination (e.g., growth RNG
        called during measurement).

        Args:
            reset: If True, resets call counts to zero after reading

        Returns:
            Dict with keys: growth_calls, treatment_calls, assay_calls, operations_calls

        Usage in loop:
            # After each cycle
            audit = world.hardware.get_rng_audit(reset=True)
            append_diagnostics({"event": "rng_stream_audit", **audit})
        """
        audit = {
            "growth_calls": self.rng_growth.call_count,
            "treatment_calls": self.rng_treatment.call_count,
            "assay_calls": self.rng_assay.call_count,
            "operations_calls": self.rng_operations.call_count,
        }

        if reset:
            self.rng_growth.reset_call_count()
            self.rng_treatment.reset_call_count()
            self.rng_assay.reset_call_count()
            self.rng_operations.reset_call_count()

        return audit

    def simulate_cellrox_signal(self, vessel_id: str, compound: str, dose_uM: float) -> float:
        """
        Simulate CellROX oxidative stress signal.
        
        Uses a Hill equation to model ROS-dependent fluorescence increase.
        
        Args:
            vessel_id: Vessel identifier
            compound: Compound name (e.g., "tbhp")
            dose_uM: Compound concentration in µM
            
        Returns:
            CellROX fluorescence signal (arbitrary units)
        """
        if vessel_id not in self.vessel_states:
            logger.warning(f"Vessel {vessel_id} not found")
            return 0.0
        
        vessel = self.vessel_states[vessel_id]
        cell_line = vessel.cell_line
        
        # Get CellROX parameters from YAML (nested under compound)
        cellrox_params = None
        if compound in self.compound_sensitivity:
            # Check if we have the full YAML data with cellrox_params
            if hasattr(self, 'raw_yaml_data'):
                compound_data = self.raw_yaml_data.get('compound_sensitivity', {}).get(compound, {})
                cellrox_params = compound_data.get('cellrox_params', {}).get(cell_line, {})
        
        # Fallback to defaults if not found
        if not cellrox_params:
            logger.warning(f"No CellROX params for {compound} + {cell_line}, using defaults")
            cellrox_params = {
                'ec50_uM': 50.0,
                'max_fold': 5.0,
                'baseline': 100.0,
                'hill_slope': 1.8
            }
        
        ec50 = cellrox_params.get('ec50_uM', 50.0)
        max_fold = cellrox_params.get('max_fold', 5.0)
        baseline = cellrox_params.get('baseline', 100.0)
        hill_slope = cellrox_params.get('hill_slope', 1.8)
        
        # Hill equation for signal increase
        # signal = baseline * (1 + (max_fold - 1) * dose^h / (EC50^h + dose^h))
        if dose_uM <= 0:
            signal = baseline
        else:
            fold_increase = (dose_uM ** hill_slope) / (ec50 ** hill_slope + dose_uM ** hill_slope)
            signal = baseline * (1.0 + (max_fold - 1.0) * fold_increase)
        
        # Add biological noise (only if CV > 0)
        cv = self.cell_line_params.get(cell_line, {}).get('biological_cv', 0.05)
        if cv > 0:
            signal *= lognormal_multiplier(self.rng_assay, cv)

        return max(0.0, signal)
    
    def simulate_segmentation_quality(self, vessel_id: str, compound: str, dose_uM: float) -> float:
        """
        Simulate cell segmentation quality.
        
        High doses of oxidative stress cause cell rounding and death,
        reducing segmentation quality.
        
        Args:
            vessel_id: Vessel identifier
            compound: Compound name (e.g., "tbhp")
            dose_uM: Compound concentration in µM
            
        Returns:
            Segmentation quality (0.0 to 1.0, where 1.0 is perfect)
        """
        if vessel_id not in self.vessel_states:
            logger.warning(f"Vessel {vessel_id} not found")
            return 0.0
        
        vessel = self.vessel_states[vessel_id]
        cell_line = vessel.cell_line
        
        # Get segmentation parameters from YAML (nested under compound)
        seg_params = None
        if compound in self.compound_sensitivity:
            # Check if we have the full YAML data with segmentation_params
            if hasattr(self, 'raw_yaml_data'):
                compound_data = self.raw_yaml_data.get('compound_sensitivity', {}).get(compound, {})
                seg_params = compound_data.get('segmentation_params', {}).get(cell_line, {})
        
        # Fallback to defaults if not found
        if not seg_params:
            logger.warning(f"No segmentation params for {compound} + {cell_line}, using defaults")
            seg_params = {
                'degradation_ic50_uM': 200.0,
                'min_quality': 0.3,
                'hill_slope': 2.5
            }
        
        degradation_ic50 = seg_params.get('degradation_ic50_uM', 200.0)
        min_quality = seg_params.get('min_quality', 0.3)
        hill_slope = seg_params.get('hill_slope', 2.5)
        
        # Inverse Hill equation for quality degradation
        # quality = min_quality + (1 - min_quality) * IC50^h / (IC50^h + dose^h)
        if dose_uM <= 0:
            quality = 1.0
        else:
            degradation_factor = (degradation_ic50 ** hill_slope) / (degradation_ic50 ** hill_slope + dose_uM ** hill_slope)
            quality = min_quality + (1.0 - min_quality) * degradation_factor
        
        # Also factor in viability (dead cells are hard to segment)
        quality *= vessel.viability

        # Add noise (only if CV > 0)
        cv = 0.05  # 5% CV for segmentation quality
        if cv > 0:
            quality *= lognormal_multiplier(self.rng_assay, cv)

        return np.clip(quality, 0.0, 1.0)
    
    def _load_raw_yaml_for_nested_params(self, params_file: Optional[str] = None):
        """Load raw YAML data to access nested parameters."""
        if params_file is None:
            # Use same default path resolution as _load_parameters()
            params_file = Path(__file__).parent.parent.parent.parent / "data" / "simulation_parameters.yaml"

        yaml_path = Path(params_file)
        if not yaml_path.exists():
            logger.warning(f"YAML file not found: {params_file}")
            return

        with open(yaml_path, 'r') as f:
            self.raw_yaml_data = yaml.safe_load(f)

    def _apply_well_failure(self, morph: Dict[str, float], well_position: str, plate_id: str = "P1", batch_id: str = "batch_default") -> Optional[Dict]:
        """
        Apply random well failures (bubbles, contamination, pipetting errors).

        In real HCS, ~1-5% of wells randomly fail for various reasons:
        - Bubbles (imaging failure)
        - Contamination (bacteria/yeast)
        - Pipetting errors (wrong volume)
        - Staining failures (antibody didn't work)
        - Cross-contamination (neighboring well)

        Args:
            morph: Original morphology dict
            well_position: Well position
            plate_id: Plate identifier (for batch-specific failures)
            batch_id: Batch identifier (for run-specific failures)

        Returns:
            Dict with modified morphology and failure_mode, or None if no failure
        """
        if not hasattr(self, 'thalamus_params') or self.thalamus_params is None:
            return None

        tech_noise = self.thalamus_params.get('technical_noise', {})
        failure_rate = tech_noise.get('well_failure_rate', 0.0)

        if failure_rate <= 0:
            return None

        # Seed failures by run context + plate + well (so failures vary across runs, not cosmic well curses)
        rng_failure = np.random.default_rng(stable_u32(f"well_failure_{self.run_context.seed}_{batch_id}_{plate_id}_{well_position}"))
        if rng_failure.random() > failure_rate:
            return None

        # Select failure mode
        failure_modes = self.thalamus_params.get('well_failure_modes', {})
        if not failure_modes:
            return None

        # Build probability distribution
        modes = list(failure_modes.keys())
        probs = [failure_modes[mode].get('probability', 0.0) for mode in modes]
        total_prob = sum(probs)
        if total_prob <= 0:
            return None

        probs = [p / total_prob for p in probs]  # Normalize
        selected_mode = rng_failure.choice(modes, p=probs)
        effect = failure_modes[selected_mode].get('effect', 'no_signal')

        # Apply failure effect
        failed_morph = morph.copy()

        if effect == 'no_signal':
            # Bubble in well → imaging fails → near-zero signal
            for channel in failed_morph:
                failed_morph[channel] = rng_failure.uniform(0.1, 2.0)  # Background noise only

        elif effect == 'outlier_high':
            # Contamination (bacteria/yeast) → abnormally high signal
            for channel in failed_morph:
                failed_morph[channel] *= rng_failure.uniform(5.0, 20.0)  # 5-20× higher

        elif effect == 'outlier_low':
            # Pipetting error → wrong volume → low cell count
            for channel in failed_morph:
                failed_morph[channel] *= rng_failure.uniform(0.05, 0.3)  # 5-30% of normal

        elif effect == 'partial_signal':
            # Staining failure → some channels fail, others OK
            failed_channels = rng_failure.choice(
                list(failed_morph.keys()),
                size=rng_failure.integers(1, len(failed_morph)),
                replace=False
            )
            for channel in failed_channels:
                failed_morph[channel] = rng_failure.uniform(0.1, 2.0)

        elif effect == 'mixed_signal':
            # Cross-contamination → mix of this well and neighbor
            mix_ratio = rng_failure.uniform(0.3, 0.7)  # 30-70% contamination
            for channel in failed_morph:
                neighbor_signal = failed_morph[channel] * rng_failure.uniform(0.5, 2.0)
                failed_morph[channel] = mix_ratio * failed_morph[channel] + (1 - mix_ratio) * neighbor_signal

        return {
            'morphology': failed_morph,
            'failure_mode': selected_mode,
            'effect': effect
        }

    def _is_edge_well(self, well_position: str, plate_format: int = 96) -> bool:
        """
        Detect if a well is on the edge of a plate (evaporation/temperature artifacts).

        Args:
            well_position: Well position like 'A1', 'H12', or 'Plate1_A01'
            plate_format: 96 or 384

        Returns:
            True if well is on edge (row A or H, column 1 or 12 for 96-well)
        """
        if not well_position:
            return False

        # Extract well position from formats like "Plate1_A01" or just "A01"
        import re
        match = re.search(r'([A-P])(\d{1,2})$', well_position)
        if not match:
            return False

        row = match.group(1)
        col = int(match.group(2))

        if plate_format == 96:
            # 96-well: 8 rows (A-H), 12 columns (1-12)
            edge_rows = ['A', 'H']
            edge_cols = [1, 12]
            return row in edge_rows or col in edge_cols
        elif plate_format == 384:
            # 384-well: 16 rows (A-P), 24 columns (1-24)
            edge_rows = ['A', 'P']
            edge_cols = [1, 24]
            return row in edge_rows or col in edge_cols
        else:
            return False

    def _load_cell_thalamus_params(self):
        """Load Cell Thalamus parameters for morphology simulation."""
        thalamus_params_file = Path(__file__).parent.parent.parent.parent / "data" / "cell_thalamus_params.yaml"

        if not thalamus_params_file.exists():
            logger.warning(f"Cell Thalamus params not found: {thalamus_params_file}")
            self.thalamus_params = None
            return

        with open(thalamus_params_file, 'r') as f:
            self.thalamus_params = yaml.safe_load(f)

        logger.info("Loaded Cell Thalamus parameters")

    def cell_painting_assay(self, vessel_id: str, **kwargs) -> Dict[str, Any]:
        """
        Simulate Cell Painting morphology assay.

        MEASUREMENT TIMING: This assay reads at t_measure = self.simulated_time,
        which is t1 after advance_time() returns. This represents "readout after
        interval of biology." All time-dependent artifacts (washout, plating)
        use t_measure as reference.

        Returns 5-channel morphology features:
        - ER (endoplasmic reticulum)
        - Mito (mitochondria)
        - Nucleus (nuclear morphology)
        - Actin (cytoskeleton)
        - RNA (translation sites)

        Args:
            vessel_id: Vessel identifier
            **kwargs: Additional parameters (plate_id, day, operator for technical noise)

        Returns:
            Dict with channel values and metadata
        """
        if vessel_id not in self.vessel_states:
            logger.warning(f"Vessel {vessel_id} not found")
            return {"status": "error", "message": "Vessel not found"}
        return self._cell_painting_assay.measure(self.vessel_states[vessel_id], **kwargs)

    def atp_viability_assay(self, vessel_id: str, **kwargs) -> Dict[str, Any]:
        """
        Simulate LDH cytotoxicity assay (orthogonal scalar readout).

        Returns LDH, ATP, UPR, and trafficking marker signals.

        Args:
            vessel_id: Vessel identifier
            **kwargs: Additional parameters (plate_id, day, operator, well_position)

        Returns:
            Dict with scalar readouts and metadata
        """
        if vessel_id not in self.vessel_states:
            logger.warning(f"Vessel {vessel_id} not found")
            return {"status": "error", "message": "Vessel not found"}
        return self._ldh_viability_assay.measure(self.vessel_states[vessel_id], **kwargs)

    def scrna_seq_assay(
        self,
        vessel_id: str,
        n_cells: int = 1000,
        *,
        batch_id: Optional[str] = None,
        params_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Simulate single-cell RNA-seq assay.

        Returns UMI count matrix with realistic batch effects and technical noise.

        Args:
            vessel_id: Vessel identifier
            n_cells: Number of cells to profile (default 1000)
            batch_id: Optional batch identifier for batch effects
            params_path: Optional path to scrna_seq_params.yaml

        Returns:
            Dict with counts, metadata, and run information
        """
        if vessel_id not in self.vessel_states:
            logger.warning(f"Vessel {vessel_id} not found")
            return {"status": "error", "message": "Vessel not found"}
        return self._scrna_seq_assay.measure(
            self.vessel_states[vessel_id],
            n_cells=n_cells,
            batch_id=batch_id,
            params_path=params_path
        )

    def _update_contact_pressure(self, vessel: VesselState, dt_h: float):
        """
        Update contact pressure latent state based on confluence.

        Pressure is a lagged, bounded state that mediates confluence effects on
        biology and measurements. This prevents step-size artifacts from hard
        confluence thresholds.

        Parameters (hardcoded for now, can be moved to cell_line_params later):
            c0: Confluence midpoint (0.75)
            width: Sigmoid width (0.08)
            tau_h: Time constant for lag (12.0h)

        Contract:
        - contact_pressure ∈ [0, 1] (hard clamped)
        - Converges to steady-state independent of dt (first-order relaxation)
        - Zero time → zero update (no phantom effects)
        """
        if dt_h <= 0:
            return  # No update for zero-time steps

        # Sigmoid parameters (can be moved to cell_line_params later)
        c0 = 0.75
        width = 0.08
        tau_h = 12.0

        # Current confluence (can exceed 1.0)
        c = vessel.cell_count / max(vessel.vessel_capacity, 1.0)

        # Store confluence for debugging (already computed elsewhere, but explicit here)
        vessel.confluence = float(c)

        # Instantaneous pressure in [0, 1] via sigmoid
        x = (c - c0) / max(width, 1e-6)
        p_inst = 1.0 / (1.0 + np.exp(-x))

        # Lagged state update (first-order relaxation)
        p_current = getattr(vessel, "contact_pressure", 0.0)
        alpha = 1.0 - np.exp(-dt_h / max(tau_h, 1e-6))
        vessel.contact_pressure = float(np.clip(p_current + alpha * (p_inst - p_current), 0.0, 1.0))

    def _apply_confluence_morphology_bias(self, morph: Dict[str, float], p: float) -> Dict[str, float]:
        """
        Apply contact pressure-dependent morphology bias.

        This is a MEASUREMENT CONFOUNDER, not a biological mechanism. High confluence
        creates predictable, systematic shifts in morphology channels independent of
        compound mechanism. This forces agents to control for density or suffer false
        mechanism attribution.

        Effects are:
        - Nucleus: compression (-8%)
        - Actin: reorganization (+10%)
        - ER: mild crowding stress appearance (+6%)
        - Mito: texture/segmentation changes (-5%)
        - RNA: signal reduction (-4%)

        These coefficients are placeholders - tune later against real Cell Painting
        density curves.

        Args:
            morph: Channel dict {channel: value}
            p: Contact pressure [0, 1]

        Returns:
            Modified morph dict

        Contract:
        - Deterministic (no RNG)
        - Monotonic (higher p → consistent direction per channel)
        - Bounded (coefficients control max shift)
        """
        # Bounded, monotonic, channel-specific shifts
        shifts = {
            "nucleus": -0.08,
            "actin": +0.10,
            "er": +0.06,
            "mito": -0.05,
            "rna": -0.04,
        }

        out = dict(morph)
        for channel, coeff in shifts.items():
            if channel in out:
                out[channel] = out[channel] * (1.0 + coeff * p)

        return out
