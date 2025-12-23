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
    tech_noise: Dict
) -> float:
    """
    Calculate deterministic hardware bias for a specific well.

    Combines:
    1. Pin/valve-specific systematic offset (row-dependent)
    2. Serpentine temporal gradient (column-dependent)

    Args:
        plate_id: Plate identifier
        batch_id: Batch identifier
        well_position: Well position (e.g., "A1", "P24")
        instrument: Which instrument is being used
        operation: Which operation is being performed
        seed: Random seed for this run
        tech_noise: Technical noise parameters

    Returns:
        Multiplicative bias factor (typically 0.90 - 1.10)
    """
    # Parse well position
    row, col = _parse_well_position(well_position)

    # Get pin/valve number (1-8) from row
    pin_number = _get_pin_from_row(row)

    # Get serpentine processing order (temporal gradient)
    processing_index = _get_serpentine_index(row, col, plate_format=384)

    # Calculate pin/valve-specific systematic offset
    pin_bias = _get_pin_bias(
        instrument=instrument,
        pin_number=pin_number,
        plate_id=plate_id,
        batch_id=batch_id,
        seed=seed,
        tech_noise=tech_noise
    )

    # Calculate serpentine temporal gradient
    temporal_bias = _get_temporal_bias(
        processing_index=processing_index,
        operation=operation,
        tech_noise=tech_noise
    )

    # Multiply biases (they compound, not add)
    total_bias = pin_bias * temporal_bias

    return total_bias


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
    processing_index: int,
    operation: str,
    tech_noise: Dict
) -> float:
    """
    Calculate serpentine temporal gradient bias.

    Early wells get processed first, sit longer before next step.
    Late wells get processed last, sit shorter before next step.

    For Cell Painting:
    - Early wells (A1): Stain longer → higher signal
    - Late wells (P24): Stain shorter → lower signal

    For Culture (feeding, plating):
    - Early wells (A1): Media/cells sit longer → temperature drop, attachment advantage
    - Late wells (P24): Fresher media/cells → less temperature equilibration

    Args:
        processing_index: Position in processing order (0 = first)
        operation: Which operation (plating, feeding, cell_painting)
        tech_noise: Technical noise parameters

    Returns:
        Multiplicative bias factor
    """
    # Get temporal gradient magnitude from tech_noise
    temporal_cv = tech_noise.get('temporal_gradient_cv', 0.04)  # Default 4% CV across plate

    # Normalize processing_index to [0, 1]
    # For 384-well: processing_index ranges 0-383
    max_index = 383  # 16 rows × 24 columns - 1
    normalized_index = processing_index / max_index  # 0.0 (first) to 1.0 (last)

    # Map to temporal bias
    # Early wells (index=0): positive bias (e.g., 1.04)
    # Late wells (index=1): negative bias (e.g., 0.96)
    # Linear gradient from +CV to -CV
    bias_offset = temporal_cv * (1.0 - 2.0 * normalized_index)  # +temporal_cv to -temporal_cv

    temporal_bias = 1.0 + bias_offset

    return temporal_bias


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
