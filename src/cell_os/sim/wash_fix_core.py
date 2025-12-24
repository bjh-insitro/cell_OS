"""
Wash and fixation physics: detachment, not death.

Models mechanical cell loss during wash cycles and fixation as:
- Detachment (reduces cell_count)
- Confluence-dependent (U-shaped: fragile at low/high, stable mid-range)
- Edge-amplified (meniscus effects + evaporation history)
- Stochastic per-well variation

NOT modeled as death (cells are removed, not killed in place).
"""
import numpy as np
from typing import Tuple, Optional


def wash_step(
    cell_count: float,
    confluence: float,
    wash_intensity: float = 0.5,
    is_edge: bool = False,
    rng: Optional[np.random.Generator] = None,
    base_loss: float = 0.01,
    shear_coefficient: float = 0.03,
    edge_multiplier: float = 1.3
) -> Tuple[float, float]:
    """
    Compute cell loss from a single wash cycle.

    Wash physically removes cells via aspiration/dispense shear, not death.
    Loss is confluence-dependent:
    - Low confluence (<0.15): weakly attached, fragile
    - Mid-range (0.15-0.85): stable adhesion
    - High confluence (>0.85): sheet detachment risk at high shear

    Args:
        cell_count: Current cell count in well
        confluence: Current confluence (0..1)
        wash_intensity: Wash aggressiveness (0..1, default 0.5 = gentle)
            - 0.0 = ultra-gentle (slow aspiration)
            - 0.5 = standard Cell Painting wash
            - 1.0 = aggressive (fast dispense, high shear)
        is_edge: True if well is on plate edge (higher loss)
        rng: Random number generator (if None, uses global)
        base_loss: Unavoidable loss fraction per wash (default 1%)
        shear_coefficient: Shear-dependent loss scale (default 3%)
        edge_multiplier: Edge well loss multiplier (default 1.3×)

    Returns:
        (new_cell_count, detach_fraction)
            new_cell_count: Updated cell count after detachment
            detach_fraction: Fraction of cells detached (for logging)

    Examples:
        >>> # Mid-confluence, gentle wash, center well
        >>> wash_step(10000, 0.5, wash_intensity=0.3, is_edge=False)
        (9950, 0.005)  # ~0.5% loss (base only, stable adhesion)

        >>> # Low confluence, gentle wash
        >>> wash_step(3000, 0.1, wash_intensity=0.3, is_edge=False)
        (2940, 0.02)  # ~2% loss (fragile adhesion)

        >>> # High confluence, aggressive wash
        >>> wash_step(15000, 0.9, wash_intensity=0.9, is_edge=False)
        (14400, 0.04)  # ~4% loss (sheet detachment risk)

        >>> # Edge well, aggressive
        >>> wash_step(10000, 0.5, wash_intensity=0.8, is_edge=True)
        (9700, 0.03)  # ~3% loss (edge amplification)
    """
    if rng is None:
        rng = np.random.default_rng()

    if cell_count <= 0:
        return 0.0, 0.0

    # 1. Base loss (unavoidable handling)
    loss = base_loss

    # 2. Shear-dependent term (scales with wash intensity)
    shear_loss = shear_coefficient * wash_intensity
    loss += shear_loss

    # 3. Confluence-dependent modulation (U-shaped)
    if confluence < 0.15:
        # Fragile: weakly attached at low density
        fragility_factor = 1.0 + 1.5 * (0.15 - confluence) / 0.15  # Up to 2.5× at conf=0
        loss *= fragility_factor
    elif confluence > 0.85:
        # Sheet risk: high shear can peel confluent monolayers
        if wash_intensity > 0.5:
            sheet_risk = 1.0 + 0.8 * (confluence - 0.85) / 0.15 * (wash_intensity - 0.5) / 0.5
            loss *= sheet_risk

    # 4. Edge amplification (meniscus + evaporation history)
    if is_edge:
        loss *= edge_multiplier

    # 5. Per-well stochastic variation (±20% relative)
    noise_factor = 1.0 + rng.normal(0.0, 0.2)
    loss *= max(0.0, noise_factor)

    # Clip to [0, 1] (can't lose more than 100%)
    loss = np.clip(loss, 0.0, 1.0)

    # Apply loss
    new_cell_count = cell_count * (1.0 - loss)

    return float(new_cell_count), float(loss)


def fixation_step(
    cell_count: float,
    confluence: float,
    fixation_strength: float = 0.5,
    is_edge: bool = False,
    rng: Optional[np.random.Generator] = None,
    base_loss: float = 0.03,
    shear_coefficient: float = 0.05,
    edge_multiplier: float = 1.4
) -> Tuple[float, float]:
    """
    Compute cell loss from fixation.

    Fixation is a harsher detachment event than wash:
    - Paraformaldehyde/methanol causes some detachment
    - Often includes a final wash step
    - Edge wells suffer more

    After fixation, vessel should be marked as destroyed (no further growth/operations).

    Args:
        cell_count: Current cell count in well
        confluence: Current confluence (0..1)
        fixation_strength: Fixation aggressiveness (0..1, default 0.5)
            - 0.0 = ultra-gentle (methanol, cold)
            - 0.5 = standard paraformaldehyde (4%, RT)
            - 1.0 = harsh (high temp, aggressive wash)
        is_edge: True if well is on plate edge
        rng: Random number generator
        base_loss: Unavoidable loss fraction (default 3%)
        shear_coefficient: Strength-dependent loss scale (default 5%)
        edge_multiplier: Edge well loss multiplier (default 1.4×)

    Returns:
        (new_cell_count, loss_fraction)

    Examples:
        >>> # Standard fixation, mid-confluence
        >>> fixation_step(10000, 0.5, fixation_strength=0.5)
        (9700, 0.03)  # ~3% loss

        >>> # Harsh fixation, low confluence
        >>> fixation_step(3000, 0.1, fixation_strength=0.9)
        (2700, 0.10)  # ~10% loss (fragile + harsh)

        >>> # Edge well
        >>> fixation_step(10000, 0.6, fixation_strength=0.5, is_edge=True)
        (9550, 0.045)  # ~4.5% loss (edge amplified)
    """
    if rng is None:
        rng = np.random.default_rng()

    if cell_count <= 0:
        return 0.0, 0.0

    # 1. Base loss (fixation is harsher than wash)
    loss = base_loss

    # 2. Fixation strength-dependent term
    strength_loss = shear_coefficient * fixation_strength
    loss += strength_loss

    # 3. Confluence-dependent modulation (same U-shape as wash, but stronger)
    if confluence < 0.15:
        # Fragile: 2× to 3× at very low confluence
        fragility_factor = 1.0 + 2.0 * (0.15 - confluence) / 0.15
        loss *= fragility_factor
    elif confluence > 0.85:
        # Sheet risk: fixation can crack dense monolayers
        if fixation_strength > 0.3:
            sheet_risk = 1.0 + 1.0 * (confluence - 0.85) / 0.15 * (fixation_strength - 0.3) / 0.7
            loss *= sheet_risk

    # 4. Edge amplification (worse than wash due to evaporation history)
    if is_edge:
        loss *= edge_multiplier

    # 5. Per-well stochastic variation (±25% relative, higher than wash)
    noise_factor = 1.0 + rng.normal(0.0, 0.25)
    loss *= max(0.0, noise_factor)

    # Clip to [0, 1]
    loss = np.clip(loss, 0.0, 1.0)

    # Apply loss
    new_cell_count = cell_count * (1.0 - loss)

    return float(new_cell_count), float(loss)


def multi_wash_loss(
    cell_count: float,
    confluence: float,
    n_washes: int = 3,
    wash_intensity: float = 0.5,
    is_edge: bool = False,
    rng: Optional[np.random.Generator] = None
) -> Tuple[float, float]:
    """
    Apply multiple wash cycles sequentially.

    Cell Painting typically uses 3-4 washes before fixation.
    Each wash independently detaches cells.

    Args:
        cell_count: Initial cell count
        confluence: Initial confluence (updated after each wash)
        n_washes: Number of wash cycles (default 3)
        wash_intensity: Wash aggressiveness (0..1)
        is_edge: True if edge well
        rng: Random number generator

    Returns:
        (final_cell_count, total_loss_fraction)

    Example:
        >>> # 3 washes, standard intensity
        >>> multi_wash_loss(10000, 0.5, n_washes=3, wash_intensity=0.5)
        (9850, 0.015)  # ~1.5% total loss
    """
    if rng is None:
        rng = np.random.default_rng()

    initial_count = cell_count
    current_confluence = confluence

    for _ in range(n_washes):
        if cell_count <= 0:
            break

        cell_count, _ = wash_step(
            cell_count=cell_count,
            confluence=current_confluence,
            wash_intensity=wash_intensity,
            is_edge=is_edge,
            rng=rng
        )

        # Update confluence (roughly proportional to cell count)
        # This is approximate - exact confluence needs vessel_capacity
        current_confluence *= (cell_count / initial_count) if initial_count > 0 else 0.0

    total_loss = 1.0 - (cell_count / initial_count) if initial_count > 0 else 0.0

    return float(cell_count), float(total_loss)


def validate_loss_monotonicity(loss_fractions: list) -> bool:
    """
    Validate that loss fractions are physically plausible.

    Checks:
    - All losses in [0, 1]
    - Losses never negative (no spontaneous growth during wash)

    Args:
        loss_fractions: List of loss fractions from wash/fixation steps

    Returns:
        True if valid, False otherwise
    """
    for loss in loss_fractions:
        if not (0.0 <= loss <= 1.0):
            return False
    return True


def _confluence_support_factor(confluence: float) -> float:
    """
    Compute confluence-dependent adhesion support.

    Cells at mid-confluence support each other (contact inhibition, gap junctions).
    Lonely cells (low conf) and overcrowded sheets (high conf) are more fragile.

    Args:
        confluence: Current confluence (0..1)

    Returns:
        Support factor (0..1, peak at ~0.5)
    """
    if confluence < 0.15:
        # Lonely cells: poor adhesion
        return 0.5 + 0.5 * (confluence / 0.15)
    elif confluence < 0.85:
        # Sweet spot: stable adhesion
        return 1.0
    else:
        # Overcrowded: sheet stress
        overshoot = (confluence - 0.85) / 0.15
        return 1.0 - 0.3 * overshoot  # Up to 30% penalty


def wash_step_v2(
    cell_count: float,
    confluence: float,
    wash_intensity: float = 0.5,
    is_edge: bool = False,
    adhesion_strength: float = 0.75,
    adhesion_state: float = 1.0,
    adhesion_heterogeneity: float = 0.3,
    is_fixed: bool = False,
    post_fix_brittleness: float = 0.5,
    rng: Optional[np.random.Generator] = None,
    base_loss: float = 0.01,
    shear_coefficient: float = 0.03,
    edge_multiplier: float = 1.3
) -> Tuple[float, float, float]:
    """
    Compute cell loss from a single wash cycle with stickology.

    Returns separate detachment and debris fractions.
    Pre-fixation: mostly detachment (cells removed cleanly).
    Post-fixation: shifts toward debris (fragments remain, poison imaging).

    Args:
        cell_count: Current cell count in well
        confluence: Current confluence (0..1)
        wash_intensity: Wash aggressiveness (0..1)
        is_edge: True if well is on plate edge
        adhesion_strength: Cell line adhesion strength (0..1, higher = stickier)
        adhesion_state: Dynamic adhesion quality (1.0 = pristine, degrades with handling)
        adhesion_heterogeneity: Spatial adhesion variation (0..1, higher = more edge/spot failures)
        is_fixed: True if cells have been fixed (changes physics)
        post_fix_brittleness: Brittleness after fixation (0..1, higher = more debris)
        rng: Random number generator
        base_loss: Unavoidable loss fraction per wash
        shear_coefficient: Shear-dependent loss scale
        edge_multiplier: Edge well loss multiplier

    Returns:
        (new_cell_count, detach_fraction, debris_fraction)
            new_cell_count: Updated cell count after loss
            detach_fraction: Fraction cleanly detached (removed from well)
            debris_fraction: Fraction fragmented into debris (remains, poisons imaging)

    Examples:
        >>> # Pre-fix, gentle wash, high adhesion
        >>> wash_step_v2(10000, 0.5, 0.3, False, adhesion_strength=0.85, is_fixed=False)
        (9970, 0.003, 0.0)  # ~0.3% detachment, no debris

        >>> # Post-fix, aggressive wash, brittle cells
        >>> wash_step_v2(10000, 0.5, 0.8, False, adhesion_strength=0.75, is_fixed=True, post_fix_brittleness=0.6)
        (9850, 0.005, 0.010)  # ~0.5% detachment, ~1.0% debris (3× more debris)
    """
    if rng is None:
        rng = np.random.default_rng()

    if cell_count <= 0:
        return 0.0, 0.0, 0.0

    # 1. Compute effective adhesion
    confluence_support = _confluence_support_factor(confluence)
    effective_adhesion = adhesion_strength * adhesion_state * confluence_support

    # 2. Base loss from handling
    loss = base_loss

    # 3. Shear-dependent term
    shear_loss = shear_coefficient * wash_intensity
    loss += shear_loss

    # 4. Modulate by adhesion (stronger adhesion = less loss)
    adhesion_penalty = 1.0 - effective_adhesion
    loss *= (0.5 + 0.5 * adhesion_penalty)  # Map [0,1] adhesion to [0.5×, 1.0×] loss

    # 5. Edge amplification (worse with high heterogeneity)
    if is_edge:
        edge_factor = edge_multiplier * (1.0 + 0.5 * adhesion_heterogeneity)
        loss *= edge_factor

    # 6. Confluence-dependent fragility (U-shaped, stronger for low adhesion)
    if confluence < 0.15:
        fragility_factor = 1.0 + (1.5 - 0.5 * effective_adhesion) * (0.15 - confluence) / 0.15
        loss *= fragility_factor
    elif confluence > 0.85:
        if wash_intensity > 0.5:
            sheet_risk = 1.0 + 0.8 * (confluence - 0.85) / 0.15 * (wash_intensity - 0.5) / 0.5
            loss *= sheet_risk

    # Clip to [0, 1]
    loss = np.clip(loss, 0.0, 1.0)

    # 7. Route loss to detachment vs debris based on fixation state
    if not is_fixed:
        # Pre-fix: mostly clean detachment, but rough handling fragments some cells
        # Even gentle aspiration/dispense can fragment weakly-attached cells (5-20% of loss)
        # Higher intensity → more fragmentation (mechanical shear)
        prefixdebris_base = 0.05  # 5% minimum debris (gentle handling)
        prefixdebris_intensity = 0.15 * wash_intensity  # Up to 15% more for aggressive wash
        prefixdebris_ratio = np.clip(prefixdebris_base + prefixdebris_intensity, 0.0, 0.25)

        debris_fraction = loss * prefixdebris_ratio
        detach_fraction = loss * (1.0 - prefixdebris_ratio)
    else:
        # Post-fix: brittleness shifts loss toward debris
        # Debris dominates at high brittleness and intensity
        debris_ratio = post_fix_brittleness * (0.5 + 0.5 * wash_intensity)
        debris_ratio = np.clip(debris_ratio, 0.0, 0.9)  # Cap at 90% debris

        debris_fraction = loss * debris_ratio
        detach_fraction = loss * (1.0 - debris_ratio)

    # 8. Apply loss
    total_loss = detach_fraction + debris_fraction
    new_cell_count = cell_count * (1.0 - total_loss)

    return float(new_cell_count), float(detach_fraction), float(debris_fraction)


def fixation_step_v2(
    cell_count: float,
    confluence: float,
    fixation_strength: float = 0.6,
    is_edge: bool = False,
    adhesion_strength: float = 0.75,
    adhesion_state: float = 1.0,
    adhesion_heterogeneity: float = 0.3,
    post_fix_brittleness: float = 0.5,
    rng: Optional[np.random.Generator] = None,
    base_loss: float = 0.03,
    shear_coefficient: float = 0.05,
    edge_multiplier: float = 1.4
) -> Tuple[float, float, float, float]:
    """
    Compute cell loss from fixation with stickology.

    Fixation is terminal and changes adhesion physics:
    - May slightly increase adhesion (crosslinking glues cells)
    - Dramatically increases brittleness (fragments easily)

    Returns new adhesion_state along with loss fractions.

    Args:
        cell_count: Current cell count
        confluence: Current confluence (0..1)
        fixation_strength: Fixation aggressiveness (0..1)
        is_edge: True if edge well
        adhesion_strength: Cell line adhesion strength
        adhesion_state: Current adhesion state (will be updated)
        adhesion_heterogeneity: Spatial adhesion variation
        post_fix_brittleness: Brittleness after fixation
        rng: Random number generator
        base_loss: Unavoidable loss fraction
        shear_coefficient: Strength-dependent loss scale
        edge_multiplier: Edge well loss multiplier

    Returns:
        (new_cell_count, detach_fraction, debris_fraction, new_adhesion_state)
            new_cell_count: Updated cell count after fixation
            detach_fraction: Fraction cleanly detached
            debris_fraction: Fraction fragmented into debris
            new_adhesion_state: Updated adhesion state (post-fix plateau)

    Examples:
        >>> # Standard fixation, mid-confluence
        >>> fixation_step_v2(10000, 0.5, 0.6, False, adhesion_strength=0.75)
        (9600, 0.015, 0.025, 0.85)  # ~1.5% detached, ~2.5% debris, adhesion↑ from crosslinking

        >>> # Harsh fixation, brittle cells
        >>> fixation_step_v2(10000, 0.5, 0.9, False, post_fix_brittleness=0.7)
        (9400, 0.010, 0.050, 0.85)  # ~1% detached, ~5% debris (debris dominates)
    """
    if rng is None:
        rng = np.random.default_rng()

    if cell_count <= 0:
        return 0.0, 0.0, 0.0, adhesion_state

    # 1. Compute effective adhesion (pre-fixation)
    confluence_support = _confluence_support_factor(confluence)
    effective_adhesion = adhesion_strength * adhesion_state * confluence_support

    # 2. Base loss from fixation (harsher than wash)
    loss = base_loss

    # 3. Fixation strength-dependent term
    strength_loss = shear_coefficient * fixation_strength
    loss += strength_loss

    # 4. Modulate by adhesion
    adhesion_penalty = 1.0 - effective_adhesion
    loss *= (0.5 + 0.5 * adhesion_penalty)

    # 5. Edge amplification
    if is_edge:
        edge_factor = edge_multiplier * (1.0 + 0.5 * adhesion_heterogeneity)
        loss *= edge_factor

    # 6. Confluence-dependent fragility (stronger than wash)
    if confluence < 0.15:
        fragility_factor = 1.0 + (2.0 - 0.5 * effective_adhesion) * (0.15 - confluence) / 0.15
        loss *= fragility_factor
    elif confluence > 0.85:
        if fixation_strength > 0.3:
            sheet_risk = 1.0 + 1.0 * (confluence - 0.85) / 0.15 * (fixation_strength - 0.3) / 0.7
            loss *= sheet_risk

    # Clip to [0, 1]
    loss = np.clip(loss, 0.0, 1.0)

    # 7. Fixation dramatically shifts toward debris
    # Brittleness determines debris ratio (high brittleness → mostly debris)
    debris_ratio = post_fix_brittleness * (0.6 + 0.4 * fixation_strength)
    debris_ratio = np.clip(debris_ratio, 0.3, 0.95)  # At least 30% debris, up to 95%

    debris_fraction = loss * debris_ratio
    detach_fraction = loss * (1.0 - debris_ratio)

    # 8. Apply loss
    total_loss = detach_fraction + debris_fraction
    new_cell_count = cell_count * (1.0 - total_loss)

    # 9. Update adhesion state (fixation crosslinking may slightly increase adhesion)
    # But set to a plateau value (fixation state is stable)
    glue_bonus = 0.1 * (1.0 - post_fix_brittleness)  # Less brittle = more crosslinking benefit
    new_adhesion_state = min(1.0, adhesion_state * (1.0 + glue_bonus))

    return float(new_cell_count), float(detach_fraction), float(debris_fraction), float(new_adhesion_state)
