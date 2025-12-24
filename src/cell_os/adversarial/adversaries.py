"""
Concrete adversary implementations.

Each adversary injects a specific type of technical artifact that can
masquerade as biology but should be detectable by QC systems.

Design principle: Subtle realism, not cartoon sabotage.
Effect sizes are calibrated to be detectable but plausible.
"""

from dataclasses import dataclass
from typing import Tuple
import numpy as np
from numpy.random import Generator

from ..core.observation import RawWellResult
from .types import get_readout_value, set_readout_value


def parse_well_id(well_id: str) -> Tuple[int, int]:
    """Parse well_id to (row_index, col_index).

    Args:
        well_id: Well identifier like "A1", "B12", "P24"

    Returns:
        Tuple of (row_index, col_index) zero-indexed

    Example:
        >>> parse_well_id("A1")
        (0, 0)
        >>> parse_well_id("P24")
        (15, 23)
    """
    if not well_id or len(well_id) < 2:
        raise ValueError(f"Invalid well_id: {well_id}")

    row_letter = well_id[0].upper()
    try:
        col_num = int(well_id[1:])
    except ValueError:
        raise ValueError(f"Invalid well_id column: {well_id}")

    # Convert row letter to index (A=0, B=1, ..., P=15)
    row_idx = ord(row_letter) - ord('A')
    col_idx = col_num - 1  # Columns are 1-indexed

    return row_idx, col_idx


def infer_plate_geometry(wells: Tuple[RawWellResult, ...]) -> Tuple[int, int]:
    """Infer plate geometry from well positions.

    Args:
        wells: Tuple of raw well results

    Returns:
        Tuple of (n_rows, n_cols)

    Raises:
        ValueError: If geometry cannot be inferred
    """
    if not wells:
        raise ValueError("Cannot infer geometry from empty wells")

    max_row = 0
    max_col = 0

    for well in wells:
        row_idx, col_idx = parse_well_id(well.location.well_id)
        max_row = max(max_row, row_idx)
        max_col = max(max_col, col_idx)

    n_rows = max_row + 1
    n_cols = max_col + 1

    # Validate known formats
    if (n_rows, n_cols) == (8, 12):
        return (8, 12)  # 96-well
    elif (n_rows, n_cols) == (16, 24):
        return (16, 24)  # 384-well
    else:
        # Allow arbitrary geometry but warn
        return (n_rows, n_cols)


@dataclass
class SpatialGradientAdversary:
    """Inject smooth spatial gradient in one measurement channel.

    This mimics technical artifacts like:
    - Temperature gradients across plate
    - Illumination fall-off in imaging
    - Liquid handler drift

    The gradient is smooth (not checkerboard) and should trigger Moran's I detection.

    Attributes:
        target_channel: Measurement key to perturb (e.g., "morphology.nucleus")
        axis: Gradient axis ("row", "column", or "both")
        strength: Effect size as fraction of mean (default: 0.1 = 10% gradient)
        direction: Gradient direction (+1 = increasing, -1 = decreasing)
    """
    target_channel: str = "morphology.nucleus"
    axis: str = "row"  # "row", "column", or "both"
    strength: float = 0.1  # 10% gradient across plate
    direction: int = 1  # +1 or -1

    def apply(
        self,
        wells: Tuple[RawWellResult, ...],
        rng: Generator,
        strength: float = 1.0
    ) -> Tuple[RawWellResult, ...]:
        """Apply spatial gradient to target channel."""
        if not wells:
            return wells

        n_rows, n_cols = infer_plate_geometry(wells)
        effective_strength = self.strength * strength

        # Compute base statistics for calibration
        values = [get_readout_value(w, self.target_channel) for w in wells]
        mean_value = np.mean(values)

        perturbed = []
        for well in wells:
            row_idx, col_idx = parse_well_id(well.location.well_id)

            # Compute normalized position (0 to 1)
            if self.axis == "row":
                position = row_idx / max(1, n_rows - 1)
            elif self.axis == "column":
                position = col_idx / max(1, n_cols - 1)
            elif self.axis == "both":
                # Diagonal gradient
                position = (row_idx / max(1, n_rows - 1) + col_idx / max(1, n_cols - 1)) / 2
            else:
                raise ValueError(f"Unknown axis: {self.axis}")

            # Linear gradient: -strength/2 to +strength/2
            gradient_effect = (position - 0.5) * self.direction * effective_strength
            original_value = get_readout_value(well, self.target_channel)
            perturbed_value = original_value * (1 + gradient_effect)

            perturbed.append(set_readout_value(well, self.target_channel, perturbed_value))

        return tuple(perturbed)


@dataclass
class EdgeEffectAdversary:
    """Inject systematic edge well artifacts.

    This mimics technical artifacts like:
    - Evaporation at plate edges
    - Temperature edge effects
    - Liquid handler positioning errors

    Edge wells show systematic shift relative to center wells.

    Attributes:
        target_channel: Measurement key to perturb
        edge_shift: Fractional shift for edge wells (default: -0.05 = 5% lower)
        corner_boost: Additional shift for corner wells (default: 1.5x)
    """
    target_channel: str = "morphology.nucleus"
    edge_shift: float = -0.05  # 5% lower at edges
    corner_boost: float = 1.5  # Corners get 1.5x effect

    def apply(
        self,
        wells: Tuple[RawWellResult, ...],
        rng: Generator,
        strength: float = 1.0
    ) -> Tuple[RawWellResult, ...]:
        """Apply edge effect to target channel."""
        if not wells:
            return wells

        n_rows, n_cols = infer_plate_geometry(wells)
        effective_shift = self.edge_shift * strength

        perturbed = []
        for well in wells:
            row_idx, col_idx = parse_well_id(well.location.well_id)

            # Detect edge positions
            is_edge_row = row_idx == 0 or row_idx == n_rows - 1
            is_edge_col = col_idx == 0 or col_idx == n_cols - 1
            is_corner = is_edge_row and is_edge_col

            # Compute effect multiplier
            if is_corner:
                effect = effective_shift * self.corner_boost
            elif is_edge_row or is_edge_col:
                effect = effective_shift
            else:
                effect = 0.0

            original_value = get_readout_value(well, self.target_channel)
            perturbed_value = original_value * (1 + effect)

            perturbed.append(set_readout_value(well, self.target_channel, perturbed_value))

        return tuple(perturbed)


@dataclass
class BatchAlignedShiftAdversary:
    """Inject group-wise offsets aligned with experimental conditions.

    This is adversarial because it creates a technical artifact that is
    CORRELATED with the biological variable (compound), making it hard
    to distinguish from real effects.

    Mimics:
    - Batch effects in plate preparation
    - Liquid handler drift during compound addition
    - Time-of-day effects aligned with plate layout

    Attributes:
        target_channel: Measurement key to perturb
        grouping_key: How to group wells ("compound" or "compound_dose")
        shift_scale: Standard deviation of per-group shifts (default: 0.03 = 3%)
    """
    target_channel: str = "morphology.nucleus"
    grouping_key: str = "compound"  # "compound" or "compound_dose"
    shift_scale: float = 0.03  # 3% random shift per group

    def apply(
        self,
        wells: Tuple[RawWellResult, ...],
        rng: Generator,
        strength: float = 1.0
    ) -> Tuple[RawWellResult, ...]:
        """Apply batch-aligned shift to target channel."""
        if not wells:
            return wells

        effective_scale = self.shift_scale * strength

        # Group wells by condition
        groups = {}
        for well in wells:
            if self.grouping_key == "compound":
                key = well.treatment.compound
            elif self.grouping_key == "compound_dose":
                key = (well.treatment.compound, well.treatment.dose_uM)
            else:
                raise ValueError(f"Unknown grouping_key: {self.grouping_key}")

            if key not in groups:
                groups[key] = []
            groups[key].append(well)

        # Assign deterministic shift to each group
        group_shifts = {}
        for group_key in sorted(groups.keys(), key=str):  # Deterministic ordering
            # Use hash of group key to derive deterministic shift
            hash_val = hash(str(group_key)) % (2**31)
            rng_group = np.random.default_rng(hash_val)
            group_shifts[group_key] = rng_group.normal(0, effective_scale)

        # Apply shifts
        perturbed = []
        for well in wells:
            if self.grouping_key == "compound":
                key = well.treatment.compound
            else:
                key = (well.treatment.compound, well.treatment.dose_uM)

            shift = group_shifts[key]
            original_value = get_readout_value(well, self.target_channel)
            perturbed_value = original_value * (1 + shift)

            perturbed.append(set_readout_value(well, self.target_channel, perturbed_value))

        return tuple(perturbed)


@dataclass
class WashLossCorrelationAdversary:
    """Inject apparent wash loss correlated with dose.

    This is adversarial because it creates a technical artifact (cell loss
    during wash steps) that is DOSE-DEPENDENT, mimicking a real biological
    dose-response relationship.

    Mimics:
    - Wash-induced cell detachment correlated with compound toxicity
    - Aspiration artifacts correlated with well position
    - Staining intensity loss at high doses

    The key is that this is a TECHNICAL pathway (cells lost during processing)
    not a biological one (cells dying from compound).

    Attributes:
        target_channel: Measurement key to perturb
        loss_per_log_dose: Fractional loss per log10(dose_uM) (default: 0.02 = 2% per log)
        threshold_dose_uM: Dose below which no loss occurs (default: 0.1)
    """
    target_channel: str = "morphology.nucleus"
    loss_per_log_dose: float = 0.02  # 2% loss per log dose
    threshold_dose_uM: float = 0.1  # No loss below this dose

    def apply(
        self,
        wells: Tuple[RawWellResult, ...],
        rng: Generator,
        strength: float = 1.0
    ) -> Tuple[RawWellResult, ...]:
        """Apply dose-correlated wash loss to target channel."""
        if not wells:
            return wells

        effective_loss = self.loss_per_log_dose * strength

        perturbed = []
        for well in wells:
            dose = well.treatment.dose_uM

            # Compute loss based on log dose
            if dose > self.threshold_dose_uM:
                log_dose = np.log10(dose)
                loss_fraction = log_dose * effective_loss
                # Clamp to reasonable range
                loss_fraction = np.clip(loss_fraction, 0, 0.3)  # Max 30% loss
            else:
                loss_fraction = 0.0

            original_value = get_readout_value(well, self.target_channel)
            perturbed_value = original_value * (1 - loss_fraction)

            perturbed.append(set_readout_value(well, self.target_channel, perturbed_value))

        return tuple(perturbed)
