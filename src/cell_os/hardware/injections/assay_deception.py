"""
Injection J: Assay Deception (Cells Lie to Assays)

PROBLEM: Assays measure what they're designed to measure, not what you think they measure.

State Variables:
- mitochondrial_health: True mitochondrial function (0-1)
- atp_level: ATP content (can decouple from mito health)
- glycolytic_flux: Glycolysis rate (compensates for mito damage)
- latent_damage: Accumulates silently before manifesting
- inversion_timer: Countdown to sudden collapse
- warburg_activated: Glycolysis preference (cancer-like)

Pathologies Introduced:
- ATP-mito decoupling: High ATP despite damaged mitochondria (glycolysis compensates)
- Late inversions: Cells look healthy (ATP high), then sudden crash
- Latent damage: Damage accumulates invisibly, then manifests
- Warburg effect: Cells prefer glycolysis even with O2 (cancer phenotype)
- False negatives: Assay says "healthy" but cells are dying
- False positives: Assay says "dead" but cells are viable

Exploits Blocked:
- "ATP = health": ATP high doesn't mean mitochondria work
- "Early markers predict outcome": Latent damage invisible early
- "Measurements are ground truth": Assays lie
- "Viability is monotonic": Can look healthy then suddenly crash

Real-World Motivation:
- Mitochondrial toxicity: Drugs damage mitochondria but ATP stays high (glycolysis)
- Warburg effect: Cancer cells prefer glycolysis (aerobic glycolysis)
- Latent cardiotoxicity: Heart drugs look safe initially, then heart failure
- MPTP toxicity: Mitochondrial damage → delayed Parkinson's
- Acetaminophen: Liver damage hours after ingestion (latent)

Philosophy:
What you measure is not what matters. Cells can look healthy while dying,
or look dead while viable. The map is not the territory.
"""

from dataclasses import dataclass
from typing import Dict, Any
import numpy as np
from .base import InjectionState, Injection, InjectionContext


# Constants
GLYCOLYSIS_COMPENSATION_MAX = 0.80  # Glycolysis can provide up to 80% ATP
MITOCHONDRIAL_DAMAGE_RATE = 0.05    # 5% damage per stress event
LATENT_DAMAGE_THRESHOLD = 0.60      # 60% accumulated → inversion
INVERSION_DELAY_H = (4.0, 12.0)     # Hours between threshold and collapse
WARBURG_ACTIVATION_THRESHOLD = 0.30  # Activate glycolysis preference
ATP_DECAY_RATE_H = 0.10             # ATP decays 10% per hour without production
MITO_RECOVERY_TAU_H = 72.0          # Mitochondria recover slowly (3 days)


@dataclass
class AssayDeceptionState(InjectionState):
    """
    Assay deception state per well.

    Tracks discrepancy between measured signals and true cellular health.
    """
    vessel_id: str

    # Ground truth cellular state
    mitochondrial_health: float = 1.0     # 0-1 (true mito function)
    glycolytic_flux: float = 0.2          # 0-1 (glycolysis rate)
    true_cellular_health: float = 1.0     # 0-1 (combined health)

    # Measured/apparent state (what assays see)
    atp_level: float = 1.0                # 0-1 (total ATP pool)
    nad_nadh_ratio: float = 1.0           # Redox state
    ros_level: float = 0.0                # ROS (mito damage marker)

    # Latent damage (hidden)
    latent_damage_accumulator: float = 0.0  # 0-1 (builds silently)
    inversion_armed: bool = False           # Countdown started
    inversion_timer_h: float = 0.0          # Hours until collapse

    # Metabolic mode
    warburg_activated: bool = False         # Glycolysis preference
    glycolytic_compensation: float = 0.0    # How much glycolysis compensates

    def accumulate_mitochondrial_damage(self, damage: float) -> None:
        """
        Damage mitochondria (may not show in ATP immediately).

        Args:
            damage: Damage magnitude (0-1)
        """
        # Direct mitochondrial damage
        self.mitochondrial_health = max(0.0, self.mitochondrial_health - damage)

        # Increase ROS (visible marker of mito damage)
        self.ros_level = min(1.0, self.ros_level + damage * 0.5)

        # Accumulate latent damage (hidden)
        self.latent_damage_accumulator += damage * 0.3

        # Activate glycolytic compensation if mito damaged
        if self.mitochondrial_health < 0.70:
            self._activate_glycolytic_compensation()

    def _activate_glycolytic_compensation(self) -> None:
        """
        Activate glycolysis to compensate for mitochondrial damage.

        This maintains ATP levels despite damaged mitochondria (deception!).
        """
        # Calculate how much compensation is needed
        mito_deficit = 1.0 - self.mitochondrial_health

        # Glycolysis can compensate up to GLYCOLYSIS_COMPENSATION_MAX
        self.glycolytic_compensation = min(mito_deficit, GLYCOLYSIS_COMPENSATION_MAX)

        # Increase glycolytic flux
        self.glycolytic_flux = min(1.0, self.glycolytic_flux + self.glycolytic_compensation)

        # Check if Warburg effect should activate (cancer-like metabolism)
        if self.glycolytic_flux > WARBURG_ACTIVATION_THRESHOLD:
            self.warburg_activated = True

    def update_atp_level(self, dt_hours: float) -> None:
        """
        Update ATP based on mitochondrial health + glycolytic compensation.

        ATP can stay high even with damaged mitochondria (deception).

        Args:
            dt_hours: Time step (hours)
        """
        # ATP production from mitochondria
        mito_atp_production = self.mitochondrial_health * 0.9  # 90% of ATP normally from mito

        # ATP production from glycolysis (compensation)
        glyco_atp_production = self.glycolytic_flux * 0.5  # Less efficient

        # Total ATP production
        total_atp_production = mito_atp_production + glyco_atp_production

        # ATP consumption (baseline)
        atp_consumption = 0.8

        # Net ATP change
        net_atp = (total_atp_production - atp_consumption) * dt_hours

        # Update ATP level
        self.atp_level = max(0.0, min(1.0, self.atp_level + net_atp))

        # Key deception: ATP can stay high even when mitochondria are damaged!

    def check_inversion_threshold(self, rng: np.random.Generator) -> None:
        """
        Check if latent damage has crossed threshold (trigger inversion).

        Inversion = sudden collapse after appearing healthy.
        """
        if not self.inversion_armed and self.latent_damage_accumulator >= LATENT_DAMAGE_THRESHOLD:
            # Arm inversion (start countdown to collapse)
            self.inversion_armed = True
            min_delay, max_delay = INVERSION_DELAY_H
            self.inversion_timer_h = float(rng.uniform(min_delay, max_delay))

    def advance_inversion_timer(self, dt_hours: float) -> bool:
        """
        Advance inversion timer.

        Returns:
            True if inversion occurred (collapse)
        """
        if self.inversion_armed and self.inversion_timer_h > 0:
            self.inversion_timer_h -= dt_hours

            if self.inversion_timer_h <= 0:
                # INVERSION: Sudden collapse
                self._trigger_inversion()
                return True

        return False

    def _trigger_inversion(self) -> None:
        """
        Execute inversion (sudden collapse of ATP despite appearing healthy).

        This is the "late inversion" - cells looked fine, then crashed.
        """
        # Sudden ATP collapse
        self.atp_level = max(0.0, self.atp_level - 0.80)  # Lose 80% ATP

        # Mitochondrial failure
        self.mitochondrial_health = max(0.0, self.mitochondrial_health - 0.50)

        # ROS spike
        self.ros_level = min(1.0, self.ros_level + 0.60)

        # Glycolysis can't compensate anymore
        self.glycolytic_compensation = 0.0

        self.inversion_armed = False
        self.inversion_timer_h = 0.0

    def recover_mitochondria(self, dt_hours: float) -> None:
        """
        Slowly recover mitochondrial health (if not too damaged).

        Recovery is SLOW (days) compared to damage (minutes-hours).
        """
        if self.mitochondrial_health > 0.1 and not self.inversion_armed:
            # Exponential recovery with long time constant
            recovery_rate = dt_hours / MITO_RECOVERY_TAU_H
            recovery = (1.0 - self.mitochondrial_health) * recovery_rate
            self.mitochondrial_health = min(1.0, self.mitochondrial_health + recovery)

    def get_apparent_health(self) -> float:
        """
        Get apparent health (what assays see).

        Returns:
            Apparent health (0-1) based on ATP
        """
        # Most viability assays measure ATP or metabolic activity
        # They DON'T measure true mitochondrial health
        return self.atp_level

    def get_true_health(self) -> float:
        """
        Get true cellular health.

        Returns:
            True health (0-1) based on mitochondrial health
        """
        # True health depends on mitochondria, not just ATP
        # Glycolytic compensation is temporary and toxic
        return self.mitochondrial_health * (1.0 - self.latent_damage_accumulator * 0.5)

    def get_deception_magnitude(self) -> float:
        """
        Get magnitude of assay deception.

        Returns:
            Gap between apparent and true health (0-1)
        """
        apparent = self.get_apparent_health()
        true = self.get_true_health()
        return abs(apparent - true)

    def check_invariants(self) -> None:
        """Check state is valid."""
        if not (0.0 <= self.mitochondrial_health <= 1.0):
            raise ValueError(f"Invalid mito health: {self.mitochondrial_health}")

        if not (0.0 <= self.atp_level <= 1.0):
            raise ValueError(f"Invalid ATP: {self.atp_level}")

        if not (0.0 <= self.latent_damage_accumulator <= 1.5):
            raise ValueError(f"Invalid latent damage: {self.latent_damage_accumulator}")


class AssayDeceptionInjection(Injection):
    """
    Injection J: Assay Deception (Cells Lie to Assays).

    Makes measurements misleading. Agents must:
    - Recognize that ATP ≠ mitochondrial health
    - Anticipate late inversions (sudden collapse)
    - Understand glycolytic compensation is temporary
    - Know that early markers don't predict late outcome
    - Realize assays can be systematically wrong
    """

    def __init__(self, seed: int = 0):
        """
        Initialize assay deception injection.

        Args:
            seed: RNG seed for stochastic effects
        """
        self.rng = np.random.default_rng(seed + 900)

    def create_state(self, vessel_id: str, context: InjectionContext) -> AssayDeceptionState:
        """
        Create assay deception state for a well.

        Initial state: Healthy mitochondria, ATP high, no deception.
        """
        state = AssayDeceptionState(
            vessel_id=vessel_id,
            mitochondrial_health=1.0,
            glycolytic_flux=0.2,
            true_cellular_health=1.0,
            atp_level=1.0,
            nad_nadh_ratio=1.0,
            ros_level=0.0,
            latent_damage_accumulator=0.0,
            inversion_armed=False,
            inversion_timer_h=0.0,
            warburg_activated=False,
            glycolytic_compensation=0.0,
        )
        return state

    def apply_time_step(self, state: AssayDeceptionState, dt: float, context: InjectionContext) -> None:
        """
        Update ATP levels, check for inversions, allow recovery.

        Args:
            dt: Time step (hours)
        """
        # Update ATP based on metabolism
        state.update_atp_level(dt)

        # Check if inversion should trigger
        state.check_inversion_threshold(self.rng)

        # Advance inversion timer (may trigger collapse)
        inversion_occurred = state.advance_inversion_timer(dt)

        if inversion_occurred:
            # Late inversion event (sudden collapse)
            pass  # State already updated in _trigger_inversion

        # Slow mitochondrial recovery (if not too damaged)
        state.recover_mitochondria(dt)

        # Update true health
        state.true_cellular_health = state.get_true_health()

    def on_event(self, state: AssayDeceptionState, context: InjectionContext) -> None:
        """
        Apply mitochondrial damage from stress events.

        Events:
        - 'mitochondrial_toxin': Direct mito damage
        - 'oxidative_stress': ROS damage to mitochondria
        - 'metabolic_stress': Nutrient deprivation affects mito
        """
        event_type = context.event_type
        params = context.event_params or {}

        if event_type == 'mitochondrial_toxin':
            # Direct mitochondrial damage (will show latent effects)
            damage = params.get('damage', 0.20)
            state.accumulate_mitochondrial_damage(damage)

        elif event_type == 'oxidative_stress':
            # ROS damages mitochondria
            magnitude = params.get('magnitude', 0.15)
            state.accumulate_mitochondrial_damage(magnitude * 0.7)

        elif event_type == 'metabolic_stress':
            # Nutrient stress affects mitochondria
            magnitude = params.get('magnitude', 0.10)
            state.accumulate_mitochondrial_damage(magnitude * 0.5)

        elif event_type == 'dispense':
            # Check if compound is mitotoxic
            compound_conc = params.get('compound_uM', 0.0)
            is_mitotoxic = params.get('mitotoxic', False)

            if is_mitotoxic and compound_conc > 1.0:
                # Mitochondrial toxin (latent damage)
                toxicity = min(compound_conc / 100.0, 0.40)
                state.accumulate_mitochondrial_damage(toxicity)

    def get_biology_modifiers(self, state: AssayDeceptionState, context: InjectionContext) -> Dict[str, Any]:
        """
        True health affects biology (not apparent health).

        Returns:
            Dict with:
            - true_health: Ground truth health
            - viability_multiplier: Based on true health, not ATP
        """
        true_health = state.get_true_health()

        return {
            'true_cellular_health': true_health,
            'viability_multiplier': true_health,
            'mitochondrial_health': state.mitochondrial_health,
        }

    def get_measurement_modifiers(self, state: AssayDeceptionState, context: InjectionContext) -> Dict[str, Any]:
        """
        Assays see apparent health (can be wrong!).

        Returns:
            Dict with assay readouts (deceptive)
        """
        apparent_health = state.get_apparent_health()
        true_health = state.get_true_health()
        deception = state.get_deception_magnitude()

        return {
            'apparent_viability_atp': apparent_health,        # What ATP assay sees
            'true_viability': true_health,                    # Ground truth
            'deception_magnitude': deception,                 # Gap between apparent and true
            'mitochondrial_health_true': state.mitochondrial_health,
            'glycolytic_compensation': state.glycolytic_compensation,
            'warburg_activated': state.warburg_activated,
        }

    def pipeline_transform(self, observation: Dict[str, Any], state: AssayDeceptionState,
                          context: InjectionContext) -> Dict[str, Any]:
        """
        Add assay deception metadata to observations.

        IMPORTANT: Observations show APPARENT health (what assays measure),
        not true health. This is the deception!
        """
        # Add apparent measurements (what assays see)
        observation['atp_content'] = state.atp_level
        observation['ros_level'] = state.ros_level
        observation['nad_nadh_ratio'] = state.nad_nadh_ratio

        # Add metabolic state
        observation['glycolytic_flux'] = state.glycolytic_flux
        observation['warburg_activated'] = state.warburg_activated

        # Add latent damage (invisible to most assays!)
        observation['latent_damage'] = state.latent_damage_accumulator
        observation['inversion_armed'] = state.inversion_armed
        if state.inversion_armed:
            observation['inversion_timer_h'] = state.inversion_timer_h

        # Add deception metrics (for debugging/analysis)
        observation['apparent_viability'] = state.get_apparent_health()
        observation['true_viability_hidden'] = state.get_true_health()
        observation['deception_magnitude'] = state.get_deception_magnitude()

        # Warn if deception is large (assay lying)
        deception = state.get_deception_magnitude()
        if deception > 0.30:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f'assay_deception_{deception:.2f}'
            )

        # Warn if inversion is armed (collapse imminent)
        if state.inversion_armed:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(
                f'late_inversion_armed_{state.inversion_timer_h:.1f}h'
            )

        # Warn if Warburg effect active (cancer-like metabolism)
        if state.warburg_activated:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append('warburg_effect_active')

        return observation
