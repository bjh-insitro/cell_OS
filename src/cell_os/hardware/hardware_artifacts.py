"""
Hardware-specific artifacts for liquid handling instruments.

Models systematic biases from:
- EL406 8-channel manifold (culture and Cell Painting instruments)
- Certus Flex dispenser (complex plating)

These artifacts create deterministic 2D gradient structures:
- ROW bias: Pin/valve-specific volume and mixing characteristics
- COLUMN bias: Serpentine temporal gradients from processing order
"""

import numpy as np
from typing import Dict, Literal
from src.cell_os.hardware._impl import stable_u32, lognormal_multiplier


def get_hardware_bias(
    plate_id: str,
    batch_id: str,
    well_position: str,
    instrument: Literal['el406_culture', 'el406_cellpainting', 'certus'],
    operation: Literal['plating', 'feeding', 'cell_painting'],
    seed: int,
    tech_noise: Dict,
    cell_line: str = None,
    cell_line_params: Dict = None
) -> Dict[str, float]:
    """
    Calculate deterministic hardware bias for a specific well.

    Combines:
    1. Pin/valve-specific systematic offset (row-dependent)
    2. Serpentine temporal gradient (column-dependent, within-row)
    3. Plate-level temporal drift (row A→P, reagent depletion + thermal)
    4. Uncoupled noise (roughness doesn't perfectly track volume)
    5. Cell line-specific modifiers (attachment, shear sensitivity, robustness)

    Args:
        plate_id: Plate identifier
        batch_id: Batch identifier
        well_position: Well position (e.g., "A1", "P24")
        instrument: Which instrument is being used
        operation: Which operation is being performed
        seed: Random seed for this run
        tech_noise: Technical noise parameters
        cell_line: Cell line name (optional, for cell-specific modifiers)
        cell_line_params: Cell line hardware sensitivity params (optional)

    Returns:
        Dict with bias factors:
        - 'volume_factor': Volume/cell count multiplier (0.95-1.05)
        - 'roughness_factor': Viability impact from mechanical stress (0.92-1.00, plating only)
        - 'temperature_factor': Temperature shock viability loss (0.98-1.00, feeding only)
        - 'combined_factor': Total multiplier for measurements (cell_painting)
    """
    # Parse well position
    try:
        row, col = _parse_well_position(well_position)
    except ValueError:
        # Fallback for non-plate contexts
        return {
            'volume_factor': 1.0,
            'roughness_factor': 1.0,
            'temperature_factor': 1.0,
            'combined_factor': 1.0
        }

    # Get pin/valve number (1-8) from row
    pin_number = _get_pin_from_row(row)

    # Calculate pin/valve-specific systematic offset
    pin_bias = _get_pin_bias(
        instrument=instrument,
        pin_number=pin_number,
        plate_id=plate_id,
        batch_id=batch_id,
        seed=seed,
        tech_noise=tech_noise
    )

    # Calculate serpentine temporal gradient (within each row)
    temporal_bias = _get_temporal_bias(
        row=row,
        col=col,
        operation=operation,
        tech_noise=tech_noise,
        plate_format=384
    )

    # Calculate plate-level drift (row A→P reagent depletion + thermal)
    plate_drift = _get_plate_level_drift(
        row=row,
        operation=operation,
        tech_noise=tech_noise
    )

    # Get cell line-specific hardware sensitivity modifiers
    if cell_line and cell_line_params:
        sensitivity = cell_line_params.get(cell_line, cell_line_params.get('DEFAULT', {}))
        attachment_efficiency = sensitivity.get('attachment_efficiency', 0.90)
        shear_sensitivity = sensitivity.get('shear_sensitivity', 1.0)
        mechanical_robustness = sensitivity.get('mechanical_robustness', 1.0)
        coating_required = sensitivity.get('coating_required', False)
    else:
        # Default values if no cell line specified
        attachment_efficiency = 0.90
        shear_sensitivity = 1.0
        mechanical_robustness = 1.0
        coating_required = False

    # Operation-specific effects
    if operation == 'plating':
        # Calculate coating quality (only for cell lines that require coating)
        coating_quality = _get_coating_quality(
            row=row,
            col=col,
            plate_id=plate_id,
            batch_id=batch_id,
            coating_required=coating_required,
            tech_noise=tech_noise
        )

        # Calculate cell suspension settling (amplifies plate-level drift)
        settling_factor = _get_cell_suspension_settling(
            row=row,
            tech_noise=tech_noise
        )

        # Volume variation affects cell count (pin × temporal × drift × settling × attachment × coating)
        # Attachment efficiency: fraction of cells that successfully attach
        # Coating quality: spatial variation in coating (only for coated cell lines)
        volume_factor = pin_bias * temporal_bias * plate_drift * settling_factor * attachment_efficiency * coating_quality

        # Roughness affects viability (only negative, from mechanical stress)
        # CRITICAL: Add uncoupled noise so roughness doesn't perfectly track volume
        roughness_cv = tech_noise.get('roughness_cv', 0.05)  # 5% CV

        # Pin-specific roughness (coupled with pin volume bias)
        roughness_seed_pin = stable_u32(f"roughness_{instrument}_{pin_number}_{batch_id}")
        roughness_rng_pin = np.random.default_rng(roughness_seed_pin)
        roughness_pin = min(1.0, lognormal_multiplier(roughness_rng_pin, roughness_cv))

        # Well-specific uncoupled roughness (breaks perfect correlation)
        # Uses plate_id + well_position so it's deterministic but independent of volume
        roughness_seed_well = stable_u32(f"roughness_well_{instrument}_{plate_id}_{well_position}")
        roughness_rng_well = np.random.default_rng(roughness_seed_well)
        roughness_uncoupled = min(1.0, lognormal_multiplier(roughness_rng_well, roughness_cv * 0.25))  # 25% of CV for uncoupled

        # Combine: pin roughness (coupled) × uncoupled well roughness × shear sensitivity
        # Shear sensitivity amplifies roughness effects (fragile cells lose more viability)
        roughness_factor = roughness_pin * roughness_uncoupled

        # Apply shear sensitivity (transforms viability loss)
        # High shear_sensitivity (e.g., 2.0 for neurons) → more viability loss
        # Low shear_sensitivity (e.g., 0.7 for U2OS) → less viability loss
        # Convert to viability loss, scale, convert back
        viability_loss = 1.0 - roughness_factor
        viability_loss *= shear_sensitivity
        roughness_factor = 1.0 - viability_loss
        roughness_factor = max(0.5, min(1.0, roughness_factor))  # Clamp to [0.5, 1.0]

        # Early wells in row get less roughness (more time for gentle settling)
        # Use same serpentine logic as temporal_bias
        max_col = 24  # 384-well
        row_index = ord(row) - ord('A')
        is_odd_row = (row_index % 2) == 0

        if is_odd_row:
            # Odd rows: L→R (col 1 is early, col 24 is late)
            normalized_col = (col - 1) / (max_col - 1)
        else:
            # Even rows: R→L (col 24 is early, col 1 is late)
            normalized_col = (max_col - col) / (max_col - 1)

        # Mechanical robustness reduces temporal stress effects
        # Robust cells (mechanical_robustness > 1.0) experience less stress
        # Fragile cells (mechanical_robustness < 1.0) experience more stress
        temporal_stress_penalty = 0.03 * normalized_col / mechanical_robustness  # Scale by robustness
        temporal_roughness = 1.0 - temporal_stress_penalty
        roughness_factor *= temporal_roughness

        return {
            'volume_factor': volume_factor,
            'roughness_factor': roughness_factor,
            'temperature_factor': 1.0,
            'combined_factor': volume_factor
        }

    elif operation == 'feeding':
        # Volume variation affects nutrient availability (pin × temporal × drift)
        volume_factor = pin_bias * temporal_bias * plate_drift

        # Temperature shock from cooling during dispense
        # Early wells in row cool more (processed first, sit longest during row dispense)
        # Use same serpentine logic as temporal_bias
        max_col = 24  # 384-well
        row_index = ord(row) - ord('A')
        is_odd_row = (row_index % 2) == 0

        if is_odd_row:
            # Odd rows: L→R (col 1 is early, col 24 is late)
            normalized_col = (col - 1) / (max_col - 1)
        else:
            # Even rows: R→L (col 24 is early, col 1 is late)
            normalized_col = (max_col - col) / (max_col - 1)

        temperature_shock = 0.01 * (1.0 - normalized_col)  # 0-1% viability loss
        temperature_factor = 1.0 - temperature_shock

        return {
            'volume_factor': volume_factor,
            'roughness_factor': 1.0,
            'temperature_factor': temperature_factor,
            'combined_factor': volume_factor
        }

    elif operation == 'cell_painting':
        # Measurement artifact (affects readout, not biology)
        # Includes reagent depletion and thermal drift across plate
        combined_factor = pin_bias * temporal_bias * plate_drift

        return {
            'volume_factor': 1.0,
            'roughness_factor': 1.0,
            'temperature_factor': 1.0,
            'combined_factor': combined_factor
        }

    else:
        # Unknown operation, return neutral
        return {
            'volume_factor': 1.0,
            'roughness_factor': 1.0,
            'temperature_factor': 1.0,
            'combined_factor': 1.0
        }


def _parse_well_position(well_position: str) -> tuple[str, int]:
    """Parse well position into row letter and column number.

    Args:
        well_position: e.g., "A1", "P24"

    Returns:
        (row_letter, column_number) e.g., ("A", 1), ("P", 24)
    """
    import re
    match = re.match(r'^([A-P])(\d{1,2})$', well_position)
    if not match:
        raise ValueError(f"Invalid well position: {well_position}")

    row_letter = match.group(1)
    col_number = int(match.group(2))

    return row_letter, col_number


def _get_pin_from_row(row: str) -> int:
    """Map row letter to pin/valve number (1-8).

    8-channel manifold processes rows in groups:
    - Pin 1: rows A, I (8 rows apart)
    - Pin 2: rows B, J
    - Pin 3: rows C, K
    - ...
    - Pin 8: rows H, P

    Args:
        row: Row letter (A-P)

    Returns:
        Pin number (1-8)
    """
    row_index = ord(row) - ord('A')  # 0-15 for A-P
    pin_number = (row_index % 8) + 1  # 1-8

    return pin_number


def _get_serpentine_index(row: str, col: int, plate_format: int = 384) -> int:
    """Calculate processing order index for serpentine pattern.

    Serpentine pattern (8-channel manifold):
    - Odd rows (A,C,E,G,I,K,M,O): Left to right (col 1→24)
    - Even rows (B,D,F,H,J,L,N,P): Right to left (col 24→1)

    Args:
        row: Row letter (A-P)
        col: Column number (1-24 for 384-well)
        plate_format: 384 or 96

    Returns:
        Processing index (0 = first well processed, higher = later)
    """
    row_index = ord(row) - ord('A')  # 0-15 for A-P

    # Determine if odd or even row
    is_odd_row = (row_index % 2) == 0  # A=0 (even index, odd row), B=1 (odd index, even row)

    max_col = 24 if plate_format == 384 else 12

    if is_odd_row:
        # Odd rows: left to right (col 1 is early, col 24 is late)
        col_order = col - 1  # 0-23
    else:
        # Even rows: right to left (col 24 is early, col 1 is late)
        col_order = max_col - col  # Reversed

    # Total processing index
    # Row processing: rows processed in pairs (A,C,E,G,I,K,M,O then B,D,F,H,J,L,N,P)
    # For simplicity, approximate as: row_index * max_col + col_order
    processing_index = row_index * max_col + col_order

    return processing_index


def _get_pin_bias(
    instrument: str,
    pin_number: int,
    plate_id: str,
    batch_id: str,
    seed: int,
    tech_noise: Dict
) -> float:
    """
    Calculate pin/valve-specific systematic bias.

    Each pin has persistent characteristics:
    - Volume offset (dispenses slightly more/less than nominal)
    - Mixing quality (affects staining uniformity, wash efficiency)

    These are DETERMINISTIC (same pin always has same bias) but unique per instrument.

    Args:
        instrument: Which instrument (el406_culture, el406_cellpainting, certus)
        pin_number: Pin/valve number (1-8)
        plate_id: Plate identifier
        batch_id: Batch identifier
        seed: Random seed for run
        tech_noise: Technical noise parameters

    Returns:
        Multiplicative bias factor
    """
    # Get pin CV from tech_noise (how much pin-to-pin variation)
    pin_cv = tech_noise.get('pin_cv', 0.03)  # Default 3% CV between pins

    # Deterministic seed: instrument + pin number
    # This ensures Pin 1 on EL406_Culture always has same characteristic
    # but different from Pin 1 on EL406_CellPainting (different instrument)
    pin_seed = stable_u32(f"pin_bias_{instrument}_{pin_number}_{batch_id}")
    pin_rng = np.random.default_rng(pin_seed)

    # Sample lognormal multiplier
    # Each pin has persistent offset from nominal (1.0)
    pin_bias = lognormal_multiplier(pin_rng, pin_cv)

    return pin_bias


def _get_temporal_bias(
    row: str,
    col: int,
    operation: str,
    tech_noise: Dict,
    plate_format: int = 384
) -> float:
    """
    Calculate serpentine temporal gradient bias WITHIN each row.

    The serpentine pattern creates gradients within rows because wells in the same
    row are processed sequentially with minimal time between them (~5s per well).

    Odd rows (A,C,E,G,I,K,M,O): Process L→R (col 1 early, col 24 late)
    Even rows (B,D,F,H,J,L,N,P): Process R→L (col 24 early, col 1 late)

    For Cell Painting:
    - Early wells in row: Stain longer → higher signal
    - Late wells in row: Stain shorter → lower signal

    For Culture (feeding, plating):
    - Early wells in row: Media/cells sit longer → temperature drop, attachment advantage
    - Late wells in row: Fresher media/cells → less temperature equilibration

    Args:
        row: Row letter (A-P)
        col: Column number (1-24 for 384-well)
        operation: Which operation (plating, feeding, cell_painting)
        tech_noise: Technical noise parameters
        plate_format: 384 or 96

    Returns:
        Multiplicative bias factor
    """
    # Get temporal gradient magnitude from tech_noise
    temporal_cv = tech_noise.get('temporal_gradient_cv', 0.04)  # Default 4% CV within row

    max_col = 24 if plate_format == 384 else 12
    row_index = ord(row) - ord('A')  # 0-15 for A-P
    is_odd_row = (row_index % 2) == 0  # A=0 (even index, odd row)

    # Normalize column position within row to [0, 1]
    if is_odd_row:
        # Odd rows: L→R (col 1 is early, col 24 is late)
        normalized_col = (col - 1) / (max_col - 1)  # 0.0 at col 1, 1.0 at col 24
    else:
        # Even rows: R→L (col 24 is early, col 1 is late)
        normalized_col = (max_col - col) / (max_col - 1)  # 1.0 at col 1, 0.0 at col 24

    # Map to temporal bias
    # Early in row (normalized_col=0): positive bias (e.g., 1.04)
    # Late in row (normalized_col=1): negative bias (e.g., 0.96)
    # Linear gradient from +CV to -CV
    bias_offset = temporal_cv * (1.0 - 2.0 * normalized_col)  # +temporal_cv to -temporal_cv

    temporal_bias = 1.0 + bias_offset

    return temporal_bias


def _get_plate_level_drift(
    row: str,
    operation: str,
    tech_noise: Dict
) -> float:
    """
    Calculate plate-level temporal drift (row A→P).

    As rows are processed sequentially (A, B, C, ... P), later rows experience:
    1. Reagent depletion: Cell suspension becomes less uniform, stain quality degrades
    2. Thermal drift: Plate cools as incubator door is open longer
    3. Operator fatigue: Subtle variations in handling technique

    This creates a gradual ~1-2% decline from first row (A) to last row (P).

    Args:
        row: Row letter (A-P)
        operation: Which operation (plating, feeding, cell_painting)
        tech_noise: Technical noise parameters

    Returns:
        Multiplicative drift factor (typically 0.99-1.00)
    """
    # Get plate-level drift magnitude (default ~0.5% total across 16 rows)
    drift_cv = tech_noise.get('plate_level_drift_cv', 0.005)  # 0.5% total drift

    # Row index: A=0, P=15
    row_index = ord(row) - ord('A')

    # Normalize to [0, 1]
    normalized_row = row_index / 15.0  # 0.0 at row A, 1.0 at row P

    # Linear decline from row A to row P
    # Row A (normalized=0): drift_factor = 1.0 + drift_cv (slightly high)
    # Row P (normalized=1): drift_factor = 1.0 - drift_cv (slightly low)
    drift_offset = drift_cv * (1.0 - 2.0 * normalized_row)  # +drift_cv to -drift_cv

    drift_factor = 1.0 + drift_offset

    return drift_factor


def _get_coating_quality(
    row: str,
    col: int,
    plate_id: str,
    batch_id: str,
    coating_required: bool,
    tech_noise: Dict
) -> float:
    """
    Calculate plate coating quality variation (2D spatial gradient).

    For cell lines that require coating (neurons, primary cells), the coating quality
    isn't uniform across the plate. This creates a plate-specific spatial pattern:
    - Robot arm path creates gradients (spray coating)
    - Incubation time varies (edges dry differently)
    - Coating lot variation affects entire plate

    This is INDEPENDENT of hardware artifacts (pin biases, serpentine).
    It's a third spatial structure for agent to learn.

    Args:
        row: Row letter (A-P)
        col: Column number (1-24)
        plate_id: Plate identifier (for plate-specific coating pattern)
        batch_id: Batch identifier
        coating_required: Does this cell line need coating?
        tech_noise: Technical noise parameters

    Returns:
        Multiplicative coating quality factor (typically 0.92-1.08 for coated)
    """
    # If coating not required, no coating effect
    if not coating_required:
        return 1.0

    # Get coating quality CV from tech_noise
    coating_cv = tech_noise.get('coating_quality_cv', 0.08)  # Default 8% CV

    # Create plate-specific deterministic 2D gradient
    # Use plate_id + batch_id for deterministic seeding (same plate = same coating pattern)
    coating_seed = stable_u32(f"coating_{plate_id}_{batch_id}")
    coating_rng = np.random.default_rng(coating_seed)

    # Sample plate-specific gradient parameters
    # These define the direction and magnitude of the coating gradient
    gradient_x = coating_rng.normal(0.0, coating_cv)  # Left-right gradient strength
    gradient_y = coating_rng.normal(0.0, coating_cv)  # Top-bottom gradient strength
    center_offset = coating_rng.normal(0.0, coating_cv * 0.5)  # Baseline offset

    # Normalize well position to [-0.5, 0.5] (center = 0)
    row_index = ord(row) - ord('A')  # 0-15
    normalized_row = (row_index / 15.0) - 0.5  # -0.5 to +0.5

    normalized_col = ((col - 1) / 23.0) - 0.5  # -0.5 to +0.5

    # 2D linear gradient
    coating_offset = center_offset + (gradient_x * normalized_col) + (gradient_y * normalized_row)

    coating_quality = 1.0 + coating_offset

    # Clamp to reasonable range [0.85, 1.15]
    coating_quality = float(np.clip(coating_quality, 0.85, 1.15))

    return coating_quality


def _get_cell_suspension_settling(
    row: str,
    tech_noise: Dict
) -> float:
    """
    Calculate cell suspension settling effect during plating.

    During plating (~20 min for 384 wells), cells settle in the reservoir:
    - Early rows: well-mixed suspension → slightly higher concentration
    - Late rows: cells have settled → slightly lower concentration

    This amplifies the existing plate-level drift (reagent depletion + thermal).

    Args:
        row: Row letter (A-P)
        tech_noise: Technical noise parameters

    Returns:
        Multiplicative settling factor (typically 0.96-1.04)
    """
    # Get settling CV from tech_noise
    settling_cv = tech_noise.get('cell_suspension_settling_cv', 0.04)  # Default 4% CV

    # Row index: A=0, P=15
    row_index = ord(row) - ord('A')

    # Normalize to [0, 1]
    normalized_row = row_index / 15.0  # 0.0 at row A, 1.0 at row P

    # Linear decline from row A to row P (cells settle out)
    # Row A (early): settling_factor = 1.0 + settling_cv (more cells)
    # Row P (late): settling_factor = 1.0 - settling_cv (fewer cells)
    settling_offset = settling_cv * (1.0 - 2.0 * normalized_row)  # +settling_cv to -settling_cv

    settling_factor = 1.0 + settling_offset

    return settling_factor


# Example usage in cell_painting.py:
"""
In _apply_technical_noise(), after line 494:

# Hardware artifacts (pin bias + serpentine temporal gradient)
from src.cell_os.hardware.hardware_artifacts import get_hardware_bias

# Determine which instrument is being used
if operation_type == 'cell_painting':
    instrument = 'el406_cellpainting'
elif operation_type == 'feeding':
    instrument = 'el406_culture'
elif operation_type == 'plating':
    # Check if complex plate map
    if is_complex_plate_map(plate_id):
        instrument = 'certus'
    else:
        instrument = 'el406_culture'

hardware_bias = get_hardware_bias(
    plate_id=plate_id,
    batch_id=batch_id,
    well_position=well_position,
    instrument=instrument,
    operation=operation_type,
    seed=self.vm.run_context.seed,
    tech_noise=tech_noise
)

# Apply hardware bias to all channels (affects entire well)
for channel in morph:
    morph[channel] *= hardware_bias
"""
