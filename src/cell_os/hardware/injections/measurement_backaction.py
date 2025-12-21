"""
Injection F: Measurement Back-Action

PROBLEM: Measurements are not passive. They perturb the system.

State Variables:
- cumulative_imaging_stress: Photobleaching and phototoxicity (0-1)
- cumulative_handling_stress: Mechanical perturbation from liquid ops (0-1)
- cells_removed_scRNA: Cells destructively sampled
- measurement_count: Number of observations taken

Pathologies Introduced:
- Imaging causes photobleaching → cells stressed
- Repeated imaging → cumulative phototoxicity
- Wash operations → mechanical stress, trajectory reset
- scRNA sampling → cells removed (destructive)
- Feed operations → trajectory perturbation

Exploits Blocked:
- "Free measurement": Every observation costs something
- "Spam imaging": Photobleaching accumulates
- "Ignore sampling cost": scRNA removes cells from population
- "Measurements don't interact": Cumulative stress compounds

Real-World Motivation:
- Live-cell imaging with fluorophores generates ROS (phototoxicity)
- Repeated exposure to light → photobleaching → signal loss + stress
- Aspirate/dispense → shear stress, cell detachment
- scRNA-seq is destructive (lysed cells)
- Media change resets nutrient gradients (trajectory jump)

Philosophy:
Every question you ask changes the answer to the next question.
"""

from dataclasses import dataclass
from typing import Dict, Any
import numpy as np
from .base import InjectionState, Injection, InjectionContext


# Constants
IMAGING_STRESS_PER_TIMEPOINT = 0.05  # 5% stress per imaging session
IMAGING_PHOTOBLEACHING_RATE = 0.03   # 3% signal loss per imaging
HANDLING_STRESS_PER_OPERATION = 0.02 # 2% stress per liquid handling op
WASH_TRAJECTORY_RESET = 0.15         # 15% of stress state reset by wash
SCRNA_CELLS_REMOVED_FRACTION = 0.001 # 0.1% of population sampled (1000 cells from 1M)

# Stress accumulation decay (cells recover slowly between measurements)
STRESS_RECOVERY_TAU_H = 24.0  # 24h recovery time constant


@dataclass
class MeasurementBackActionState(InjectionState):
    """
    Measurement back-action state per well.

    Tracks cumulative perturbations from measurements and operations.
    """
    vessel_id: str

    # Imaging stress (photobleaching + phototoxicity)
    cumulative_imaging_stress: float = 0.0  # 0-1 (accumulates with each imaging)
    photobleaching_factor: float = 1.0       # Signal multiplier (degrades with imaging)
    n_imaging_events: int = 0

    # Handling stress (mechanical perturbation)
    cumulative_handling_stress: float = 0.0  # 0-1 (accumulates with liquid ops)
    n_handling_events: int = 0

    # Destructive sampling
    cells_removed_fraction: float = 0.0  # Fraction of population removed by scRNA
    n_scrna_samples: int = 0

    # Trajectory perturbation tracking
    time_since_last_wash: float = 999.0  # Hours since last trajectory reset
    n_wash_events: int = 0

    # Recovery tracking
    time_since_last_measurement: float = 0.0  # For stress recovery

    def get_total_measurement_stress(self) -> float:
        """
        Total stress from all measurement sources.

        Returns:
            Combined stress (0-1), clamped
        """
        total = self.cumulative_imaging_stress + self.cumulative_handling_stress
        return float(np.clip(total, 0.0, 1.0))

    def get_population_fraction_remaining(self) -> float:
        """
        Fraction of original population remaining after destructive sampling.

        Returns:
            Fraction remaining (0-1)
        """
        return 1.0 - self.cells_removed_fraction

    def apply_imaging_stress(self) -> None:
        """Add stress from one imaging session (photobleaching + phototoxicity)."""
        self.cumulative_imaging_stress += IMAGING_STRESS_PER_TIMEPOINT
        self.photobleaching_factor *= (1.0 - IMAGING_PHOTOBLEACHING_RATE)
        self.n_imaging_events += 1
        self.time_since_last_measurement = 0.0

    def apply_handling_stress(self) -> None:
        """Add stress from one liquid handling operation."""
        self.cumulative_handling_stress += HANDLING_STRESS_PER_OPERATION
        self.n_handling_events += 1

    def apply_wash_reset(self) -> None:
        """
        Wash operation resets trajectory (removes some accumulated stress).

        Philosophy: Fresh media partially resets stress state, but not completely.
        Cells remember some of the insult.
        """
        # Partial stress reset
        self.cumulative_handling_stress *= (1.0 - WASH_TRAJECTORY_RESET)
        self.time_since_last_wash = 0.0
        self.n_wash_events += 1

    def apply_scrna_sampling(self, n_cells_sampled: int, population_size: float) -> None:
        """
        Remove cells from population (destructive sampling).

        Args:
            n_cells_sampled: Number of cells lysed for scRNA
            population_size: Current total population
        """
        if population_size > 0:
            fraction_removed = n_cells_sampled / population_size
            self.cells_removed_fraction += fraction_removed
            self.n_scrna_samples += 1

    def apply_stress_recovery(self, dt_hours: float) -> None:
        """
        Cells recover from measurement stress over time.

        Recovery follows exponential decay with 24h time constant.
        """
        self.time_since_last_measurement += dt_hours

        if self.time_since_last_measurement > 0:
            decay_factor = np.exp(-dt_hours / STRESS_RECOVERY_TAU_H)

            # Recovery is slow
            self.cumulative_imaging_stress *= decay_factor
            self.cumulative_handling_stress *= decay_factor

            # Photobleaching doesn't recover (permanent signal loss)
            # photobleaching_factor stays degraded

    def check_invariants(self) -> None:
        """Check stress levels are in valid range."""
        if self.cumulative_imaging_stress < 0:
            raise ValueError(f"Negative imaging stress: {self.cumulative_imaging_stress}")

        if self.cumulative_handling_stress < 0:
            raise ValueError(f"Negative handling stress: {self.cumulative_handling_stress}")

        if not (0 <= self.cells_removed_fraction <= 1.0):
            raise ValueError(f"Invalid cells removed fraction: {self.cells_removed_fraction}")

        if self.photobleaching_factor < 0:
            raise ValueError(f"Negative photobleaching factor: {self.photobleaching_factor}")


class MeasurementBackActionInjection(Injection):
    """
    Injection F: Measurement back-action.

    Makes measurement non-passive. Agents must:
    - Account for photobleaching and phototoxicity from imaging
    - Recognize that liquid handling perturbs trajectories
    - Understand scRNA is destructive (can't re-sample same cells)
    - Balance information gain vs measurement cost
    """

    def __init__(self, seed: int = 0):
        """
        Initialize measurement back-action injection.

        Args:
            seed: RNG seed (unused for now, reserved for stochastic effects)
        """
        self.rng = np.random.default_rng(seed + 500)

    def create_state(self, vessel_id: str, context: InjectionContext) -> MeasurementBackActionState:
        """
        Create measurement back-action state for a well.

        Initial state: pristine (no measurements yet).
        """
        return MeasurementBackActionState(
            vessel_id=vessel_id,
            cumulative_imaging_stress=0.0,
            photobleaching_factor=1.0,
            cumulative_handling_stress=0.0,
            cells_removed_fraction=0.0,
            n_imaging_events=0,
            n_handling_events=0,
            n_scrna_samples=0,
            time_since_last_wash=999.0,
            time_since_last_measurement=0.0,
        )

    def apply_time_step(self, state: MeasurementBackActionState, dt: float, context: InjectionContext) -> None:
        """
        Apply stress recovery over time.

        Cells slowly recover from measurement stress between observations.
        """
        state.apply_stress_recovery(dt)
        state.time_since_last_wash += dt

    def on_event(self, state: MeasurementBackActionState, context: InjectionContext) -> None:
        """
        Apply back-action effects for measurement and operation events.

        Events:
        - 'measure_imaging': Cell painting, fluorescence microscopy
        - 'measure_scrna': scRNA-seq (destructive)
        - 'aspirate': Liquid removal (handling stress)
        - 'dispense': Liquid addition (handling stress)
        - 'feed': Media change (handling stress + trajectory reset)
        - 'washout': Aggressive media change (handling stress + trajectory reset)
        """
        event_type = context.event_type
        params = context.event_params or {}

        if event_type == 'measure_imaging':
            # Imaging causes photobleaching + phototoxicity
            state.apply_imaging_stress()

        elif event_type == 'measure_scrna':
            # scRNA is destructive (removes cells from population)
            n_cells = params.get('n_cells', 1000)
            population_size = params.get('population_size', 1e6)
            state.apply_scrna_sampling(n_cells, population_size)

            # Also counts as handling stress (cell lysis, plate shaking)
            state.apply_handling_stress()

        elif event_type in ['aspirate', 'dispense']:
            # Liquid handling causes mechanical stress
            state.apply_handling_stress()

        elif event_type == 'feed':
            # Media change: handling stress + partial trajectory reset
            state.apply_handling_stress()
            state.apply_wash_reset()

        elif event_type == 'washout':
            # Aggressive wash: more handling stress + trajectory reset
            state.apply_handling_stress()
            state.apply_handling_stress()  # Double stress for aggressive wash
            state.apply_wash_reset()

    def get_biology_modifiers(self, state: MeasurementBackActionState, context: InjectionContext) -> Dict[str, Any]:
        """
        Measurement stress affects biology.

        Returns:
            Dict with:
            - measurement_stress: Baseline stress from cumulative measurements
            - population_multiplier: Reduces cell count (scRNA sampling)
        """
        total_stress = state.get_total_measurement_stress()
        population_mult = state.get_population_fraction_remaining()

        return {
            'measurement_stress': total_stress * 0.3,  # Up to 30% stress
            'population_multiplier': population_mult,
        }

    def get_measurement_modifiers(self, state: MeasurementBackActionState, context: InjectionContext) -> Dict[str, Any]:
        """
        Back-action affects future measurements.

        Returns:
            Dict with:
            - photobleaching_factor: Signal multiplier for imaging (degrades)
            - measurement_noise_multiplier: Stressed cells noisier
        """
        # Photobleaching reduces signal
        photobleach_mult = state.photobleaching_factor

        # Stressed cells have noisier measurements
        total_stress = state.get_total_measurement_stress()
        noise_mult = 1.0 + total_stress * 0.5  # Up to 50% more noise

        return {
            'photobleaching_signal_multiplier': photobleach_mult,
            'measurement_noise_multiplier': noise_mult,
        }

    def pipeline_transform(self, observation: Dict[str, Any], state: MeasurementBackActionState,
                          context: InjectionContext) -> Dict[str, Any]:
        """
        Add measurement back-action metadata to observations.
        """
        observation['measurement_imaging_stress'] = state.cumulative_imaging_stress
        observation['measurement_handling_stress'] = state.cumulative_handling_stress
        observation['measurement_total_stress'] = state.get_total_measurement_stress()
        observation['photobleaching_factor'] = state.photobleaching_factor
        observation['cells_removed_fraction'] = state.cells_removed_fraction
        observation['n_imaging_events'] = state.n_imaging_events
        observation['n_handling_events'] = state.n_handling_events
        observation['n_scrna_samples'] = state.n_scrna_samples

        # Warn if measurement stress is high
        if state.get_total_measurement_stress() > 0.3:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f'high_measurement_stress_{state.get_total_measurement_stress():.2f}'
            )

        # Warn if photobleaching is significant
        if state.photobleaching_factor < 0.8:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f'photobleaching_{state.photobleaching_factor:.2f}'
            )

        return observation
