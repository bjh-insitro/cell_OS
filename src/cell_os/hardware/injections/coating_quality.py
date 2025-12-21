"""
Injection C: Coating Quality Variation

PROBLEM: Not all wells have perfect surface treatment.

State Variables:
- coating_efficiency: Per-well coating quality (0.7-1.0)
- degradation_rate: How fast coating quality degrades over passages

Pathologies Introduced:
- Poor coating → fewer cells attach (seeding efficiency drops)
- Poor coating → slower cell growth (cells sense bad substrate)
- Poor coating → baseline stress (cells don't like bad surface)
- Coating degrades over time (old plates worse than new)

Exploits Blocked:
- "Assume uniform well quality": Wells vary systematically
- "Ignore substrate effects": Substrate quality affects biology
- "Perfect adhesion": Some cells don't stick

Real-World Motivation:
- Plasma treatment quality varies well-to-well
- Old plates have degraded coating
- Edge wells sometimes have poorer coating (manufacturing artifacts)
- Hydrophobic wells vs hydrophilic wells
"""

from dataclasses import dataclass
from typing import Dict, Any
import numpy as np
from .base import InjectionState, Injection, InjectionContext


# Constants
COATING_MEAN = 0.90  # Average coating efficiency
COATING_STD = 0.08   # Well-to-well variation (±8%)
COATING_MIN = 0.70   # Minimum viable coating
COATING_MAX = 1.00   # Perfect coating

# Edge wells have slightly worse coating (manufacturing artifact)
EDGE_COATING_PENALTY = 0.05  # 5% worse on average

# Coating degrades over time (old plates)
COATING_DEGRADATION_PER_PASSAGE = 0.02  # 2% per passage


@dataclass
class CoatingQualityState(InjectionState):
    """
    Per-well coating quality state.

    Coating quality affects:
    - Attachment rate (how many cells stick during seeding)
    - Growth rate (cells on poor substrate grow slower)
    - Baseline stress (cells sense substrate quality)
    """
    vessel_id: str

    # Core state
    coating_efficiency: float = 0.90  # 0.7-1.0 (70-100% perfect coating)

    # Metadata
    is_edge_well: bool = False
    passage_number: int = 0  # Plate passage (not cell passage)

    # Derived stress
    _substrate_stress_cache: float = 0.0

    def get_attachment_rate_multiplier(self) -> float:
        """
        How coating quality affects cell attachment during seeding.

        Poor coating → fewer cells stick.

        Returns:
            Multiplier for seeding efficiency (0.7-1.0)
        """
        return self.coating_efficiency

    def get_growth_rate_multiplier(self) -> float:
        """
        How coating quality affects cell growth.

        Cells on poor substrate grow slower (don't like the surface).

        Returns:
            Multiplier for growth rate (0.85-1.0)
        """
        # Growth is less sensitive than attachment
        # Even poor coating (0.7) only reduces growth to 0.85
        return 0.85 + 0.15 * self.coating_efficiency

    def get_substrate_stress(self) -> float:
        """
        Baseline stress from poor substrate quality.

        Cells sense substrate properties (stiffness, chemistry).
        Poor coating → mild chronic stress.

        Returns:
            Baseline stress (0-0.2)
        """
        # Poor coating (0.7) → 0.06 stress
        # Perfect coating (1.0) → 0.0 stress
        substrate_stress = (1.0 - self.coating_efficiency) * 0.2
        return float(np.clip(substrate_stress, 0.0, 0.2))

    def degrade_coating(self, passages: int = 1) -> None:
        """
        Degrade coating quality over passages (old plates).

        Args:
            passages: Number of passages to age
        """
        self.passage_number += passages
        degradation = COATING_DEGRADATION_PER_PASSAGE * passages
        self.coating_efficiency = max(COATING_MIN, self.coating_efficiency - degradation)

    def check_invariants(self) -> None:
        """Check coating quality is in valid range."""
        if not (COATING_MIN <= self.coating_efficiency <= COATING_MAX):
            raise ValueError(
                f"Coating efficiency out of range: {self.coating_efficiency:.3f} "
                f"(valid: {COATING_MIN}-{COATING_MAX})"
            )


class CoatingQualityInjection(Injection):
    """
    Injection C: Per-well coating quality variation.

    Makes substrate properties matter. Agents must:
    - Account for well-to-well variation
    - Recognize edge effects (worse coating)
    - Plan for coating degradation over time
    """

    def __init__(self, seed: int = 0):
        """
        Initialize coating quality injection.

        Args:
            seed: RNG seed for reproducibility
        """
        self.rng = np.random.default_rng(seed + 200)  # Offset from other RNGs

    def create_state(self, vessel_id: str, context: InjectionContext) -> CoatingQualityState:
        """
        Sample coating quality for a new well.

        Coating quality varies well-to-well due to manufacturing.
        Edge wells tend to be slightly worse.
        """
        # Base coating quality (normal distribution, clipped)
        base_coating = self.rng.normal(loc=COATING_MEAN, scale=COATING_STD)
        base_coating = float(np.clip(base_coating, COATING_MIN, COATING_MAX))

        # Detect edge wells (if position provided)
        is_edge = False
        if context.well_position is not None:
            is_edge = self._is_edge_well(context.well_position)

        # Edge penalty
        if is_edge:
            base_coating -= EDGE_COATING_PENALTY
            base_coating = max(COATING_MIN, base_coating)

        state = CoatingQualityState(
            vessel_id=vessel_id,
            coating_efficiency=base_coating,
            is_edge_well=is_edge,
            passage_number=0
        )

        return state

    def apply_time_step(self, state: CoatingQualityState, dt: float, context: InjectionContext) -> None:
        """
        Coating quality doesn't change passively over time.

        Only degrades when plate is re-used (handled in on_event).
        """
        pass

    def on_event(self, state: CoatingQualityState, context: InjectionContext) -> None:
        """
        Handle events that affect coating quality.

        Events:
        - 'passage_plate': Plate is washed and re-used (coating degrades)
        """
        event_type = context.event_type

        if event_type == 'passage_plate':
            # Plate is re-used, coating degrades
            state.degrade_coating(passages=1)

    def get_biology_modifiers(self, state: CoatingQualityState, context: InjectionContext) -> Dict[str, Any]:
        """
        How coating quality affects biology.

        Returns:
            Dict with:
            - attachment_rate_multiplier: Affects seeding efficiency
            - growth_rate_multiplier: Affects proliferation rate
            - substrate_stress: Baseline stress from poor surface
        """
        return {
            'attachment_rate_multiplier': state.get_attachment_rate_multiplier(),
            'growth_rate_multiplier': state.get_growth_rate_multiplier(),
            'substrate_stress': state.get_substrate_stress(),
        }

    def get_measurement_modifiers(self, state: CoatingQualityState, context: InjectionContext) -> Dict[str, Any]:
        """
        Coating quality can affect imaging.

        Very poor coating → cells detach → segmentation problems.
        """
        # Below 75% coating, segmentation starts to degrade
        if state.coating_efficiency < 0.75:
            segmentation_quality = state.coating_efficiency / 0.75
        else:
            segmentation_quality = 1.0

        return {
            'segmentation_quality_coating': segmentation_quality,
        }

    def pipeline_transform(self, observation: Dict[str, Any], state: CoatingQualityState,
                          context: InjectionContext) -> Dict[str, Any]:
        """
        Add coating quality metadata to observations.
        """
        observation['coating_efficiency'] = state.coating_efficiency
        observation['is_edge_well'] = state.is_edge_well
        observation['plate_passage'] = state.passage_number

        # Flag wells with very poor coating
        if state.coating_efficiency < 0.75:
            if 'qc_warnings' not in observation:
                observation['qc_warnings'] = []
            observation['qc_warnings'].append(f'poor_coating_{state.coating_efficiency:.2f}')

        return observation

    @staticmethod
    def _is_edge_well(well_position: str, plate_format: int = 96) -> bool:
        """Detect if well is on plate edge (reuse logic from evaporation)."""
        import re
        match = re.search(r'([A-P])(\d{1,2})$', well_position)
        if not match:
            return False

        row = match.group(1)
        col = int(match.group(2))

        if plate_format == 96:
            edge_rows = ['A', 'H']
            edge_cols = [1, 12]
            return row in edge_rows or col in edge_cols
        elif plate_format == 384:
            edge_rows = ['A', 'P']
            edge_cols = [1, 24]
            return row in edge_rows or col in edge_cols

        return False
