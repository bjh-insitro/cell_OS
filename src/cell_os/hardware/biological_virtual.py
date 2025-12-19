"""
Biological Virtual Machine

Enhanced VirtualMachine with biological state tracking and realistic synthetic data generation.
"""

import time
import logging
import hashlib
import numpy as np
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from .virtual import VirtualMachine

# Death accounting epsilon (for conservation law enforcement)
DEATH_EPS = 1e-9

# Import shared biology core (single source of truth)
from ..sim import biology_core

# Import database for parameter loading
try:
    from ..database.repositories.simulation_params import SimulationParamsRepository
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("SimulationParamsRepository not available, will use YAML fallback")

logger = logging.getLogger(__name__)


###############################################################################
# Mechanism feature flags (keep simple, no config plumbing needed yet)
###############################################################################
ENABLE_NUTRIENT_DEPLETION = True
ENABLE_MITOTIC_CATASTROPHE = True

# Nutrient defaults (DMEM-ish, intentionally coarse)
DEFAULT_MEDIA_GLUCOSE_mM = 25.0
DEFAULT_MEDIA_GLUTAMINE_mM = 4.0

# Nutrient stress thresholds (below these, stress begins)
GLUCOSE_STRESS_THRESHOLD_mM = 5.0
GLUTAMINE_STRESS_THRESHOLD_mM = 1.0

# Max starvation death intensity (per hour) at full depletion
MAX_STARVATION_RATE_PER_H = 0.05

# Mitosis model
DEFAULT_DOUBLING_TIME_H = 24.0

# Feeding costs (prevents "feed every hour" dominant strategy)
ENABLE_FEEDING_COSTS = True
FEEDING_TIME_COST_H = 0.25  # Operator time per feed operation
FEEDING_CONTAMINATION_RISK = 0.002  # 0.2% chance of introducing contamination


def stable_u32(s: str) -> int:
    """
    Stable deterministic hash for RNG seeding.

    Unlike Python's hash(), this is NOT salted per process, so it gives
    consistent seeds across runs and machines. Critical for reproducibility.

    Args:
        s: String to hash

    Returns:
        Unsigned 32-bit integer suitable for RNG seeding
    """
    return int.from_bytes(hashlib.blake2s(s.encode(), digest_size=4).digest(), "little")


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
        self.transport_dysfunction = 0.0  # Current dysfunction score (0-1)
        self.death_compound = 0.0  # Fraction killed by compound attrition
        self.death_confluence = 0.0  # Fraction killed by overconfluence
        self.death_unknown = 0.0  # Fraction killed by unknown causes (seeding stress, etc.)
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

        # Transient per-step bookkeeping (not persisted across steps)
        # These are intentionally prefixed to signal "internal mechanics"
        self._step_hazard_proposals: Dict[str, float] = {}
        self._step_viability_start: float = 0.0
        self._step_cell_count_start: float = 0.0
        self._step_total_hazard: float = 0.0
        self._step_total_kill: float = 0.0
        # Signal when we had to renormalize ledger (should be ~never)
        self._step_ledger_scale: float = 1.0


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
                 seed: int = 0):
        """
        Initialize BiologicalVirtualMachine.

        Args:
            simulation_speed: Speed multiplier for simulation
            params_file: Path to YAML parameter file
            use_database: Whether to use database for parameters
            seed: RNG seed for reproducibility (default: 0).

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
        self.use_database = use_database and DB_AVAILABLE

        # Split RNG streams for observer independence
        # Each subsystem gets its own RNG so observation doesn't perturb physics
        self.rng_growth = np.random.default_rng(seed + 1)      # Growth and cell count
        self.rng_treatment = np.random.default_rng(seed + 2)   # Treatment variability
        self.rng_assay = np.random.default_rng(seed + 3)       # Assay measurements

        self._load_parameters(params_file)
        self._load_raw_yaml_for_nested_params(params_file)  # Load nested params for CellROX/segmentation
    
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
            "default_ic50": 1.0,
            "default_hill_slope": 1.0,
            "lag_duration_h": 12.0,
            "edge_penalty": 0.15
        }
        
    def advance_time(self, hours: float):
        """Advance simulated time and update all vessel states."""
        self.simulated_time += hours

        for vessel in self.vessel_states.values():
            self._step_vessel(vessel, hours)

    def _apply_survival(self, vessel: VesselState, survival: float, death_field: str, hours: float):
        """
        Proposal-mode survival application.

        Instead of mutating viability/cell_count immediately (which creates implicit ordering
        and makes accounting brittle), convert the survival fraction into a hazard rate over
        this interval and accumulate it into vessel._step_hazard_proposals.

        At the end of _step_vessel, we apply the combined survival once and allocate the realized
        death back to causes proportionally to hazard contribution (competing risks).

        Args:
            vessel: Vessel state
            survival: Survival fraction over this interval (0-1)
            death_field: Which cumulative death field to credit (e.g., "death_starvation")
            hours: Time interval (hours) over which this survival applies
        """
        survival = float(np.clip(survival, 0.0, 1.0))
        hours = float(max(DEATH_EPS, hours))

        # Convert per-interval survival to hazard rate (per hour)
        # survival == 1 → hazard 0
        if survival >= 1.0:
            hazard = 0.0
        elif survival <= 0.0:
            # Treat zero survival as extremely large hazard (still finite for math)
            hazard = 1e9
        else:
            hazard = float(-np.log(survival) / hours)

        # Accumulate hazard proposal for this death cause
        if not hasattr(vessel, "_step_hazard_proposals") or vessel._step_hazard_proposals is None:
            vessel._step_hazard_proposals = {}

        vessel._step_hazard_proposals[death_field] = vessel._step_hazard_proposals.get(death_field, 0.0) + hazard

    def _commit_step_death(self, vessel: VesselState, hours: float):
        """
        Apply combined survival once and update cumulative death buckets proportionally.

        This is where competing-risks semantics happen:
        1. Sum all hazard proposals into total_hazard
        2. Compute combined survival = exp(-total_hazard * hours)
        3. Apply to viability/cell_count once
        4. Allocate realized death to buckets proportionally to hazard share
        5. Enforce conservation law: sum(death_*) <= 1 - viability + epsilon

        Args:
            vessel: Vessel state
            hours: Time interval (hours)
        """
        hours = float(max(DEATH_EPS, hours))
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

        # Conservation: tracked <= total_dead (+eps). If we drift, renormalize tracked.
        total_dead = 1.0 - float(np.clip(vessel.viability, 0.0, 1.0))
        tracked = float(
            max(0.0, vessel.death_compound)
            + max(0.0, vessel.death_starvation)
            + max(0.0, vessel.death_mitotic_catastrophe)
            + max(0.0, vessel.death_confluence)
        )
        if tracked > total_dead + 1e-6:
            scale = float(max(0.0, total_dead) / max(DEATH_EPS, tracked))
            vessel._step_ledger_scale = scale
            vessel.death_compound *= scale
            vessel.death_starvation *= scale
            vessel.death_mitotic_catastrophe *= scale
            vessel.death_confluence *= scale
        else:
            vessel._step_ledger_scale = 1.0

    def _update_nutrient_depletion(self, vessel: VesselState, hours: float):
        """
        Nutrient depletion driven by viable cell load.
        Uses last_feed_time as the reset clock, but maintains explicit nutrient levels.
        """
        # If feeding was never called, we still treat media as aging since seed.
        # last_feed_time already exists; it becomes meaningful with feed_vessel().
        viable_cells = vessel.cell_count * vessel.viability

        # Convert vessel_capacity into a coarse proxy for "media volume"
        # Higher capacity means effectively more media buffering.
        # This keeps the model stable without adding a new volume field everywhere.
        media_buffer = max(1.0, float(vessel.vessel_capacity) / 1e7)  # ~1.0 at default capacity

        # Consumption rates in mM per hour, scaled by viable cell load.
        # These are intentionally simple and tunable.
        # Scaling chosen so depletion happens on multi-day timescales near confluence.
        glucose_drop = (viable_cells / 1e7) * (0.8 / media_buffer) * hours   # mM
        glutamine_drop = (viable_cells / 1e7) * (0.12 / media_buffer) * hours # mM

        vessel.media_glucose_mM = max(0.0, vessel.media_glucose_mM - glucose_drop)
        vessel.media_glutamine_mM = max(0.0, vessel.media_glutamine_mM - glutamine_drop)

        glucose_stress = max(0.0, (GLUCOSE_STRESS_THRESHOLD_mM - vessel.media_glucose_mM) / GLUCOSE_STRESS_THRESHOLD_mM)
        glutamine_stress = max(0.0, (GLUTAMINE_STRESS_THRESHOLD_mM - vessel.media_glutamine_mM) / GLUTAMINE_STRESS_THRESHOLD_mM)
        nutrient_stress = max(glucose_stress, glutamine_stress)

        if nutrient_stress <= 0.0:
            return

        starvation_rate = MAX_STARVATION_RATE_PER_H * nutrient_stress
        survival = float(np.exp(-starvation_rate * hours))
        self._apply_survival(vessel, survival, "death_starvation", hours)

    def _apply_mitotic_catastrophe(self, vessel: VesselState, stress_axis: str, dose_uM: float, ic50_uM: float, hours: float):
        """
        Mitotic catastrophe: only affects dividing cells and only for microtubule-axis stress.
        Implemented as additional death beyond generic attrition.
        """
        if stress_axis != "microtubule":
            return
        viable_cells = vessel.cell_count * vessel.viability
        if viable_cells <= 0:
            return

        dt = max(1e-6, float(getattr(vessel, "doubling_time_h", DEFAULT_DOUBLING_TIME_H)))
        mitosis_rate = float(np.log(2.0) / dt)  # fraction attempting division per hour

        # Fraction attempting mitosis in this interval
        attempting = viable_cells * (1.0 - float(np.exp(-mitosis_rate * hours)))

        # Failure probability is dose-dependent; bounded [0,1]
        ic50 = max(1e-9, float(ic50_uM))
        p_fail = float(dose_uM / (dose_uM + ic50))

        # Convert dead cells to a survival multiplier on the whole population
        dead_cells = attempting * p_fail
        frac_dead = dead_cells / max(1.0, vessel.cell_count)
        survival = float(np.clip(1.0 - frac_dead, 0.0, 1.0))
        self._apply_survival(vessel, survival, "death_mitotic_catastrophe", hours)

    def _step_vessel(self, vessel: VesselState, hours: float):
        """
        Update vessel state over time interval.

        Order matters:
        1. Growth (viable cells only)
        2. Death proposal phase (nutrient depletion, compound attrition, mitotic catastrophe)
        3. Commit death (apply combined survival, allocate to ledgers)
        4. Confluence management (cap growth, no killing)
        5. Update death mode label
        """
        # 1) Growth (viable cells only - dead cells don't grow)
        self._update_vessel_growth(vessel, hours)

        # Begin death proposal phase: initialize per-step hazard proposals AFTER growth
        vessel._step_hazard_proposals = {}
        vessel._step_viability_start = float(np.clip(vessel.viability, 0.0, 1.0))
        vessel._step_cell_count_start = float(max(0.0, vessel.cell_count))
        vessel._step_total_hazard = 0.0
        vessel._step_total_kill = 0.0
        vessel._step_ledger_scale = 1.0

        # 2) Death proposal phase - mechanisms propose hazards without mutating viability
        if ENABLE_NUTRIENT_DEPLETION:
            self._update_nutrient_depletion(vessel, hours)

        self._apply_compound_attrition(vessel, hours)

        # 3) Commit death once (combined survival + proportional allocation)
        self._commit_step_death(vessel, hours)

        # 4) Manage confluence (cap growth, but don't kill cells)
        self._manage_confluence(vessel)

        # 5) Update death mode label and enforce conservation law
        self._update_death_mode(vessel)

        vessel.last_update_time = self.simulated_time
            
    def _update_vessel_growth(self, vessel: VesselState, hours: float):
        """
        Update cell count based on growth model.

        Growth is for viable cells only - dead cells don't grow.
        """
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
        lag_duration = params.get("lag_duration_h", self.defaults.get("lag_duration_h", 12.0))
        time_since_seed = self.simulated_time - vessel.seed_time

        lag_factor = 1.0
        if time_since_seed < lag_duration:
            lag_factor = max(0.0, time_since_seed / lag_duration)

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

        # --- 3. Viability factor ---
        # Scale growth by viability (dead cells don't proliferate)
        viability_factor = max(0.0, vessel.viability)

        # Apply factors
        effective_growth_rate = growth_rate * lag_factor * (1.0 - edge_penalty) * viability_factor

        # Reduce growth as confluence increases
        confluence = vessel.cell_count / vessel.vessel_capacity
        growth_factor = 1.0 - (confluence / max_confluence) ** 2
        growth_factor = max(0, growth_factor)

        # Update count
        vessel.cell_count *= np.exp(effective_growth_rate * hours * growth_factor)
        vessel.confluence = vessel.cell_count / vessel.vessel_capacity
            
    def _apply_compound_attrition(self, vessel: VesselState, hours: float):
        """
        Apply time-dependent compound attrition.

        Uses biology_core for consistent attrition logic with standalone simulation.
        Attrition is "physics" - happens whether you observe it or not (Option 2).
        """
        if not vessel.compounds:
            return

        # Lazy load thalamus params (need for dysfunction computation)
        if not hasattr(self, 'thalamus_params') or self.thalamus_params is None:
            self._load_cell_thalamus_params()

        for compound, dose_uM in vessel.compounds.items():
            if dose_uM <= 0:
                continue

            # Get compound metadata (stored during treat_with_compound)
            meta = vessel.compound_meta.get(compound)
            if not meta:
                logger.warning(f"Missing metadata for compound {compound}, skipping attrition")
                continue

            ic50_uM = meta['ic50_uM']
            hill_slope = meta['hill_slope']
            stress_axis = meta['stress_axis']
            base_ec50 = meta['base_ec50']

            # Time since treatment
            time_since_treatment = self.simulated_time - vessel.compound_start_time.get(compound, self.simulated_time)

            # CRITICAL: Compute dysfunction from EXPOSURE, not cached measurement (Option 2)
            # This makes attrition observer-independent ("physics-based")
            transport_dysfunction = biology_core.compute_transport_dysfunction_from_exposure(
                cell_line=vessel.cell_line,
                compound=compound,
                dose_uM=dose_uM,
                stress_axis=stress_axis,
                base_potency_uM=base_ec50,  # Reference potency scale (base EC50)
                time_since_treatment_h=time_since_treatment,
                params=self.thalamus_params
            )

            # Mechanism-specific add-on: mitotic catastrophe for microtubule stress
            # IMPORTANT: This happens BEFORE attrition check because it's independent
            # (dividing cells can fail mitosis even if they haven't committed to death yet)
            if ENABLE_MITOTIC_CATASTROPHE:
                self._apply_mitotic_catastrophe(
                    vessel=vessel,
                    stress_axis=stress_axis,
                    dose_uM=float(dose_uM),
                    ic50_uM=float(ic50_uM),
                    hours=hours,
                )

            # Compute attrition rate using biology_core (single source of truth)
            attrition_rate = biology_core.compute_attrition_rate(
                cell_line=vessel.cell_line,
                compound=compound,
                dose_uM=dose_uM,
                stress_axis=stress_axis,
                ic50_uM=ic50_uM,
                hill_slope=hill_slope,
                transport_dysfunction=transport_dysfunction,
                time_since_treatment_h=time_since_treatment,
                current_viability=vessel.viability,
                params=self.thalamus_params  # Pass real params, not None
            )

            if attrition_rate <= 0:
                continue

            # Apply attrition over this time interval (exponential survival)
            survival = float(np.exp(-attrition_rate * hours))
            self._apply_survival(vessel, survival, "death_compound", hours)

            logger.debug(
                f"{vessel.vessel_id}: Attrition rate={attrition_rate:.4f}/h, "
                f"dys={transport_dysfunction:.3f}, survival={survival:.3f} over {hours:.1f}h"
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
        - death_confluence: Overconfluence stress

        Unknown death includes:
        - Seeding stress (initial viability < 1.0)
        - Delta tracking errors (numerical precision)
        - Any death not attributable to known causes
        """
        # Compute total death and currently tracked causes
        total_dead = 1.0 - vessel.viability
        tracked_causes = (
            vessel.death_compound
            + vessel.death_starvation
            + vessel.death_mitotic_catastrophe
            + vessel.death_confluence
        )

        # If tracked exceeds total_dead due to numerical drift, renormalize
        # (This should be rare because _commit_step_death already guards it)
        if tracked_causes > total_dead + 1e-6:
            scale = float(max(0.0, total_dead) / max(DEATH_EPS, tracked_causes))
            vessel.death_compound *= scale
            vessel.death_starvation *= scale
            vessel.death_mitotic_catastrophe *= scale
            vessel.death_confluence *= scale
            tracked_causes = (
                vessel.death_compound
                + vessel.death_starvation
                + vessel.death_mitotic_catastrophe
                + vessel.death_confluence
            )

        # Unknown is whatever is left
        vessel.death_unknown = float(max(0.0, total_dead - tracked_causes))

        # Final clamps
        vessel.viability = float(np.clip(vessel.viability, 0.0, 1.0))
        for field in [
            "death_compound",
            "death_starvation",
            "death_mitotic_catastrophe",
            "death_confluence",
            "death_unknown",
        ]:
            setattr(vessel, field, float(np.clip(getattr(vessel, field, 0.0), 0.0, 1.0)))

        # Conservation law (epsilon tolerance)
        total_dead = 1.0 - vessel.viability
        tracked_total = (
            vessel.death_compound
            + vessel.death_starvation
            + vessel.death_mitotic_catastrophe
            + vessel.death_confluence
            + vessel.death_unknown
        )
        if tracked_total > total_dead + 1e-5:
            raise RuntimeError(
                f"Death ledger violates conservation law: "
                f"tracked={tracked_total:.6f} > total_dead={total_dead:.6f} "
                f"(vessel_id={vessel.vessel_id}, compound={vessel.death_compound:.6f}, "
                f"starvation={vessel.death_starvation:.6f}, mitotic={vessel.death_mitotic_catastrophe:.6f}, "
                f"confluence={vessel.death_confluence:.6f}, unknown={vessel.death_unknown:.6f})"
            )

        # Death mode labeling (based on thresholds)
        threshold = 0.05  # 5% death required to label
        # Lower threshold for unknown death if no other causes (seeding stress detection)
        unknown_threshold = 0.01 if vessel.death_compound == 0 and vessel.death_confluence == 0 else threshold

        compound_death = vessel.death_compound > threshold
        starvation_death = vessel.death_starvation > threshold
        mitotic_death = vessel.death_mitotic_catastrophe > threshold
        confluence_death = vessel.death_confluence > threshold
        unknown_death = vessel.death_unknown > unknown_threshold

        # Priority: known causes > unknown > none
        # Count number of active causes
        active_causes = sum([compound_death, starvation_death, mitotic_death, confluence_death])

        if active_causes > 1:
            vessel.death_mode = "mixed"
        elif compound_death:
            vessel.death_mode = "compound"
        elif starvation_death:
            vessel.death_mode = "starvation"
        elif mitotic_death:
            vessel.death_mode = "mitotic"
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
        state.vessel_capacity = capacity
        state.last_passage_time = self.simulated_time
        state.seed_time = self.simulated_time
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
        vessel.media_glucose_mM = float(max(0.0, glucose_mM))
        vessel.media_glutamine_mM = float(max(0.0, glutamine_mM))
        vessel.last_feed_time = self.simulated_time

        result = {
            "status": "success",
            "action": "feed",
            "vessel_id": vessel_id,
            "media_glucose_mM": vessel.media_glucose_mM,
            "media_glutamine_mM": vessel.media_glutamine_mM,
            "time": self.simulated_time,
        }

        if ENABLE_FEEDING_COSTS:
            # Time cost (operator hours)
            result["time_cost_h"] = FEEDING_TIME_COST_H

            # Contamination risk (probabilistic)
            contamination_roll = self.rng_assay.random()
            if contamination_roll < FEEDING_CONTAMINATION_RISK:
                # Small contamination introduces minor death (1-3% viability loss)
                contamination_severity = self.rng_assay.uniform(0.01, 0.03)
                vessel.viability *= (1.0 - contamination_severity)
                vessel.cell_count *= (1.0 - contamination_severity)
                vessel.death_unknown += contamination_severity
                vessel.death_unknown = min(1.0, vessel.death_unknown)
                result["contamination"] = True
                result["contamination_severity"] = contamination_severity
                logger.warning(f"Feeding {vessel_id} introduced contamination ({contamination_severity:.1%} loss)")
            else:
                result["contamination"] = False

        logger.info(f"Fed {vessel_id} (glucose={vessel.media_glucose_mM:.1f}mM, glutamine={vessel.media_glutamine_mM:.1f}mM)")
        return result

    def count_cells(self, sample_loc: str, **kwargs) -> Dict[str, Any]:
        """Count cells with realistic biological variation."""
        vessel_id = kwargs.get("vessel_id", sample_loc)

        if vessel_id not in self.vessel_states:
            # Return default if vessel not tracked
            return super().count_cells(sample_loc, **kwargs)

        vessel = self.vessel_states[vessel_id]

        # Get cell line-specific noise parameters
        params = self.cell_line_params.get(vessel.cell_line, self.defaults)
        count_cv = params.get("cell_count_cv", self.defaults.get("cell_count_cv", 0.10))
        viability_cv = params.get("viability_cv", self.defaults.get("viability_cv", 0.02))

        # Add measurement noise (only if CV > 0)
        measured_count = vessel.cell_count
        if count_cv > 0:
            measured_count *= self.rng_growth.normal(1.0, count_cv)
        measured_count = max(0, measured_count)

        # Viability measurement noise (only if CV > 0)
        measured_viability = vessel.viability
        if viability_cv > 0:
            measured_viability *= self.rng_growth.normal(1.0, viability_cv)
        measured_viability = np.clip(measured_viability, 0.0, 1.0)
        
        self._simulate_delay(0.5)
        
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
        """Simulate cell passaging."""
        if source_vessel not in self.vessel_states:
            logger.warning(f"Source vessel {source_vessel} not found in state tracker")
            return {"status": "error", "message": "Vessel not found"}
            
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
        
        self.vessel_states[target_vessel] = target
        
        # Update source (or remove if fully passaged)
        if split_ratio >= 1.0:
            del self.vessel_states[source_vessel]
        else:
            source.cell_count = cells_transferred
            
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

        # Compute adjusted IC50 using biology_core (single source of truth)
        ic50_uM = biology_core.compute_adjusted_ic50(
            compound=compound,
            cell_line=vessel.cell_line,
            base_ec50=base_ec50,
            stress_axis=stress_axis,
            cell_line_sensitivity=cell_line_sensitivity,
            proliferation_index=biology_core.PROLIF_INDEX.get(vessel.cell_line)
        )

        # Compute instant viability effect (no attrition yet - that's in advance_time)
        viability_effect = biology_core.compute_instant_viability_effect(
            dose_uM=dose_uM,
            ic50_uM=ic50_uM,
            hill_slope=hill_slope
        )

        # Add biological variability (only if biological_cv > 0)
        params = self.cell_line_params.get(vessel.cell_line, self.defaults)
        biological_cv = params.get("biological_cv", self.defaults.get("biological_cv", 0.05))
        if biological_cv > 0:
            viability_effect *= self.rng_treatment.normal(1.0, biological_cv)
            viability_effect = np.clip(viability_effect, 0.0, 1.0)

        # Apply instant effect to vessel state and track death accounting
        prev_viability = vessel.viability
        vessel.viability *= viability_effect
        vessel.cell_count *= viability_effect

        # Track instant compound death (not just attrition!)
        instant_killed = prev_viability - vessel.viability
        vessel.death_compound += instant_killed
        vessel.death_compound = min(1.0, max(0.0, vessel.death_compound))

        # Register exposure for time-dependent attrition
        vessel.compounds[compound] = dose_uM
        vessel.compound_start_time[compound] = self.simulated_time
        vessel.compound_meta[compound] = {
            'ic50_uM': ic50_uM,
            'hill_slope': hill_slope,
            'stress_axis': stress_axis,
            'base_ec50': base_ec50
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
            signal *= self.rng_assay.normal(1.0, cv)

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
            quality *= self.rng_assay.normal(1.0, cv)

        return np.clip(quality, 0.0, 1.0)
    
    def _load_raw_yaml_for_nested_params(self, params_file: Optional[str] = None):
        """Load raw YAML data to access nested parameters."""
        if params_file is None:
            params_file = "data/simulation_parameters.yaml"

        yaml_path = Path(params_file)
        if not yaml_path.exists():
            logger.warning(f"YAML file not found: {params_file}")
            return

        with open(yaml_path, 'r') as f:
            self.raw_yaml_data = yaml.safe_load(f)

    def _apply_well_failure(self, morph: Dict[str, float], well_position: str) -> Optional[Dict]:
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
            well_position: Well position (for deterministic failures)

        Returns:
            Dict with modified morphology and failure_mode, or None if no failure
        """
        if not hasattr(self, 'thalamus_params') or self.thalamus_params is None:
            return None

        tech_noise = self.thalamus_params.get('technical_noise', {})
        failure_rate = tech_noise.get('well_failure_rate', 0.0)

        if failure_rate <= 0:
            return None

        # Deterministic failure based on well position (consistent across runs)
        rng_failure = np.random.default_rng(stable_u32(f"well_failure_{well_position}"))
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
        # Lazy load thalamus params
        if not hasattr(self, 'thalamus_params') or self.thalamus_params is None:
            self._load_cell_thalamus_params()

        if vessel_id not in self.vessel_states:
            logger.warning(f"Vessel {vessel_id} not found")
            return {"status": "error", "message": "Vessel not found"}

        vessel = self.vessel_states[vessel_id]
        cell_line = vessel.cell_line

        # Get baseline morphology for this cell line
        baseline = self.thalamus_params['baseline_morphology'].get(cell_line, {})
        if not baseline:
            logger.warning(f"No baseline morphology for {cell_line}, using A549")
            baseline = self.thalamus_params['baseline_morphology']['A549']

        # Start with baseline
        morph = {
            'er': baseline['er'],
            'mito': baseline['mito'],
            'nucleus': baseline['nucleus'],
            'actin': baseline['actin'],
            'rna': baseline['rna']
        }

        # Apply compound effects via stress axes
        stress_axis = None  # Track the stress axis for transport dysfunction calculation
        for compound_name, dose_uM in vessel.compounds.items():
            if dose_uM == 0:
                continue

            # Look up compound params
            compound_params = self.thalamus_params['compounds'].get(compound_name, {})
            if not compound_params:
                logger.warning(f"Unknown compound for morphology: {compound_name}")
                continue

            stress_axis = compound_params['stress_axis']
            intensity = compound_params['intensity']
            ec50 = compound_params['ec50_uM']
            hill_slope = compound_params['hill_slope']

            # Get stress axis channel effects
            axis_effects = self.thalamus_params['stress_axes'][stress_axis]['channels']

            # Calculate dose response (Hill equation)
            # Effect ranges from 0 (no dose) to intensity (saturating dose)
            dose_effect = intensity * (dose_uM ** hill_slope) / (ec50 ** hill_slope + dose_uM ** hill_slope)

            # Apply to each channel
            for channel, axis_strength in axis_effects.items():
                # Channel response = baseline * (1 + dose_effect * axis_strength)
                # Positive axis_strength increases signal, negative decreases
                morph[channel] *= (1.0 + dose_effect * axis_strength)

            # Special handling for microtubule drugs: morphology disruption precedes viability loss
            # Neurons show cytoskeletal disruption (actin, mito distribution) even when viable
            if stress_axis == 'microtubule':
                # Morphology EC50: Lower than viability EC50 (morphology fails first)
                # Set at 30% of viability EC50 for neurons (transport disruption happens fast)
                morph_ec50_fraction = {
                    'iPSC_NGN2': 0.3,       # Morphology fails at 30% of viability dose
                    'iPSC_Microglia': 0.5,  # Moderate
                    'A549': 1.0,            # Morphology and viability fail together
                    'HepG2': 1.0
                }.get(cell_line, 1.0)

                morph_ec50 = ec50 * morph_ec50_fraction

                # Smooth saturating Hill equation (not sharp min() clamp)
                morph_penalty = dose_uM / (dose_uM + morph_ec50)  # 0 to 1, smooth

                if cell_line == 'iPSC_NGN2':
                    # Neurons: major actin/mito disruption at doses below viability IC50
                    morph['actin'] *= (1.0 - 0.6 * morph_penalty)  # Up to 60% reduction
                    morph['mito'] *= (1.0 - 0.5 * morph_penalty)   # Mito distribution severely disrupted
                elif cell_line == 'iPSC_Microglia':
                    # Microglia: moderate actin disruption (migration/phagocytosis impaired)
                    morph['actin'] *= (1.0 - 0.4 * morph_penalty)

        # CRITICAL: Compute transport dysfunction from STRUCTURAL morphology (before viability scaling)
        # Uses biology_core for consistent dysfunction computation
        # This prevents measurement attenuation (dead cells are dim) from masquerading as
        # structural worsening (cytoskeleton more broken), which would create runaway feedback

        # Keep a copy of structural morphology (before viability scaling) for output
        morph_struct = morph.copy()

        # Compute dysfunction using biology_core (single source of truth)
        # If no compounds, no dysfunction
        if stress_axis is not None:
            transport_dysfunction_score = biology_core.compute_transport_dysfunction_score(
                cell_line=cell_line,
                stress_axis=stress_axis,
                actin_signal=morph['actin'],
                mito_signal=morph['mito'],
                baseline_actin=baseline['actin'],
                baseline_mito=baseline['mito']
            )
        else:
            transport_dysfunction_score = 0.0

        # Store for attrition calculation during advance_time
        vessel.transport_dysfunction = transport_dysfunction_score

        # Apply viability effect (dead cells have reduced signal)
        # This affects MEASUREMENT, not STRUCTURE
        viability_factor = 0.3 + 0.7 * vessel.viability  # Dead cells retain 30% signal
        for channel in morph:
            morph[channel] *= viability_factor

        # Calculate stress level (for dose-dependent noise)
        # Higher stress = higher variability (heterogeneous death timing)
        stress_level = 1.0 - vessel.viability  # 0 (healthy) to 1 (dead)
        stress_multiplier = self.thalamus_params['biological_noise'].get('stress_cv_multiplier', 1.0)
        effective_bio_cv = self.thalamus_params['biological_noise']['cell_line_cv'] * (1.0 + stress_level * (stress_multiplier - 1.0))

        # Add biological noise (dose-dependent, only if CV > 0)
        if effective_bio_cv > 0:
            for channel in morph:
                morph[channel] *= self.rng_assay.normal(1.0, effective_bio_cv)

        # Add technical noise (plate, day, operator effects)
        tech_noise = self.thalamus_params['technical_noise']
        plate_cv = tech_noise['plate_cv']
        day_cv = tech_noise['day_cv']
        operator_cv = tech_noise['operator_cv']
        well_cv = tech_noise['well_cv']
        edge_effect = tech_noise.get('edge_effect', 0.0)

        # Apply technical factors
        # Extract batch information from kwargs if provided
        plate_id = kwargs.get('plate_id', 'P1')
        day = kwargs.get('day', 1)
        operator = kwargs.get('operator', 'OP1')
        well_position = kwargs.get('well_position', 'A1')

        # Consistent batch effects per plate/day/operator (deterministic seeding)
        # Only apply if CV > 0
        plate_factor = 1.0
        if plate_cv > 0:
            rng_plate = np.random.default_rng(stable_u32(f"plate_{plate_id}"))
            plate_factor = rng_plate.normal(1.0, plate_cv)

        day_factor = 1.0
        if day_cv > 0:
            rng_day = np.random.default_rng(stable_u32(f"day_{day}"))
            day_factor = rng_day.normal(1.0, day_cv)

        operator_factor = 1.0
        if operator_cv > 0:
            rng_operator = np.random.default_rng(stable_u32(f"operator_{operator}"))
            operator_factor = rng_operator.normal(1.0, operator_cv)

        # Well factor uses assay RNG (non-deterministic)
        well_factor = 1.0
        if well_cv > 0:
            well_factor = self.rng_assay.normal(1.0, well_cv)

        # Edge effect: wells on plate edges show reduced signal (evaporation, temperature gradient)
        is_edge = self._is_edge_well(well_position)
        edge_factor = (1.0 - edge_effect) if is_edge else 1.0

        total_tech_factor = plate_factor * day_factor * operator_factor * well_factor * edge_factor

        for channel in morph:
            morph[channel] *= total_tech_factor
            morph[channel] = max(0.0, morph[channel])  # No negative signals

        # Apply random well failures (bubbles, contamination, etc.)
        failure_result = self._apply_well_failure(morph, well_position)
        if failure_result:
            morph = failure_result['morphology']
            failure_mode = failure_result['failure_mode']
        else:
            failure_mode = None

        self._simulate_delay(2.0)  # Imaging takes time

        result = {
            "status": "success",
            "action": "cell_painting",
            "vessel_id": vessel_id,
            "cell_line": cell_line,
            "morphology": morph,  # Observed morphology (after viability scaling + noise)
            "morphology_struct": morph_struct,  # Structural morphology (before viability scaling)
            "transport_dysfunction_score": transport_dysfunction_score,
            "death_mode": vessel.death_mode,
            "viability": vessel.viability,
            "timestamp": datetime.now().isoformat()
        }

        if failure_mode:
            result['well_failure'] = failure_mode
            result['qc_flag'] = 'FAIL'

        return result

    def atp_viability_assay(self, vessel_id: str, **kwargs) -> Dict[str, Any]:
        """
        Simulate LDH cytotoxicity assay (orthogonal scalar readout).

        LDH (lactate dehydrogenase) release measures membrane integrity - only rises
        when cells die and membranes rupture. Orthogonal to Cell Painting morphology.

        Key advantages over ATP:
        - Not confounded by mitochondrial dysfunction (CCCP, oligomycin crash ATP but may not kill cells)
        - True cytotoxicity measurement (membrane rupture = cell death)
        - Orthogonal to Cell Painting (supernatant biochemistry vs cellular morphology)

        LDH signal is INVERSELY proportional to viability:
        - High viability (0.95) → Low LDH (from 5% dead cells)
        - Low viability (0.30) → High LDH (from 70% dead cells)

        Args:
            vessel_id: Vessel identifier
            **kwargs: Additional parameters (plate_id, day, operator for technical noise)

        Returns:
            Dict with LDH signal and metadata
        """
        # Lazy load thalamus params
        if not hasattr(self, 'thalamus_params') or self.thalamus_params is None:
            self._load_cell_thalamus_params()

        if vessel_id not in self.vessel_states:
            logger.warning(f"Vessel {vessel_id} not found")
            return {"status": "error", "message": "Vessel not found"}

        vessel = self.vessel_states[vessel_id]
        cell_line = vessel.cell_line

        # Get baseline LDH for this cell line
        # LDH is released by dead/dying cells (inverse of ATP)
        baseline_ldh = self.thalamus_params['baseline_atp'].get(cell_line, 50000.0)  # Keep same param name for backward compat

        # LDH scales with ORIGINAL cell count and DEATH (inverse of viability)
        # High viability (0.95) = low LDH (from 5% dead cells)
        # Low viability (0.30) = high LDH (from 70% dead cells)

        # IMPORTANT: Reconstruct original cell count before death
        # treat_with_compound reduces cell_count proportionally to viability,
        # but LDH is released from ALL dead cells (which remain in well initially)
        if vessel.viability > 0:
            original_cell_count = vessel.cell_count / vessel.viability
        else:
            original_cell_count = vessel.cell_count  # All dead

        cell_count_factor = original_cell_count / 1e6  # Normalize to 1M cells
        death_factor = 1.0 - vessel.viability  # Inverse of viability

        # LDH signal proportional to dead/dying cells
        ldh_signal = baseline_ldh * cell_count_factor * death_factor

        # Calculate stress level (for dose-dependent noise)
        stress_level = 1.0 - vessel.viability  # 0 (healthy) to 1 (dead)
        stress_multiplier = self.thalamus_params['biological_noise'].get('stress_cv_multiplier', 1.0)
        effective_bio_cv = self.thalamus_params['biological_noise']['cell_line_cv'] * (1.0 + stress_level * (stress_multiplier - 1.0))

        # Add biological noise (dose-dependent, only if CV > 0)
        if effective_bio_cv > 0:
            ldh_signal *= self.rng_assay.normal(1.0, effective_bio_cv)

        # Add technical noise (plate, day, operator effects)
        tech_noise = self.thalamus_params['technical_noise']
        plate_cv = tech_noise['plate_cv']
        day_cv = tech_noise['day_cv']
        operator_cv = tech_noise['operator_cv']
        well_cv = tech_noise['well_cv']
        edge_effect = tech_noise.get('edge_effect', 0.0)

        # Extract batch information from kwargs if provided
        plate_id = kwargs.get('plate_id', 'P1')
        day = kwargs.get('day', 1)
        operator = kwargs.get('operator', 'OP1')
        well_position = kwargs.get('well_position', 'A1')

        # Consistent batch effects per plate/day/operator (deterministic seeding)
        # Only apply if CV > 0
        plate_factor = 1.0
        if plate_cv > 0:
            rng_plate = np.random.default_rng(stable_u32(f"plate_{plate_id}"))
            plate_factor = rng_plate.normal(1.0, plate_cv)

        day_factor = 1.0
        if day_cv > 0:
            rng_day = np.random.default_rng(stable_u32(f"day_{day}"))
            day_factor = rng_day.normal(1.0, day_cv)

        operator_factor = 1.0
        if operator_cv > 0:
            rng_operator = np.random.default_rng(stable_u32(f"operator_{operator}"))
            operator_factor = rng_operator.normal(1.0, operator_cv)

        # Well factor uses assay RNG (non-deterministic)
        well_factor = 1.0
        if well_cv > 0:
            well_factor = self.rng_assay.normal(1.0, well_cv)

        # Edge effect: wells on plate edges show reduced signal
        is_edge = self._is_edge_well(well_position)
        edge_factor = (1.0 - edge_effect) if is_edge else 1.0

        total_tech_factor = plate_factor * day_factor * operator_factor * well_factor * edge_factor
        ldh_signal *= total_tech_factor
        ldh_signal = max(0.0, ldh_signal)

        # Apply random well failures (same as morphology)
        # For scalar assays, failures manifest as extreme outliers
        failure_rate = tech_noise.get('well_failure_rate', 0.0)
        if failure_rate > 0:
            rng_failure = np.random.default_rng(stable_u32(f"well_failure_{well_position}"))
            if rng_failure.random() <= failure_rate:
                # Failed well - random extreme value
                ldh_signal *= rng_failure.choice([0.01, 0.05, 0.1, 5.0, 10.0, 20.0])
                failure_mode = 'assay_failure'
                qc_flag = 'FAIL'
            else:
                failure_mode = None
                qc_flag = None
        else:
            failure_mode = None
            qc_flag = None

        self._simulate_delay(0.5)  # LDH assay is quick

        result = {
            "status": "success",
            "action": "ldh_viability",
            "vessel_id": vessel_id,
            "cell_line": cell_line,
            "ldh_signal": ldh_signal,
            "atp_signal": ldh_signal,  # Keep for backward compatibility
            "viability": vessel.viability,
            "cell_count": vessel.cell_count,
            "death_mode": vessel.death_mode,
            "death_compound": vessel.death_compound,
            "death_confluence": vessel.death_confluence,
            "death_unknown": vessel.death_unknown,
            "timestamp": datetime.now().isoformat()
        }

        if failure_mode:
            result['well_failure'] = failure_mode
            result['qc_flag'] = qc_flag

        return result
