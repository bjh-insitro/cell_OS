"""
Canonical condition keys: eliminate aggregation races from floating-point noise.

PROBLEM:
- Dose 1.000 µM vs 1.001 µM → different dictionary keys → replicate splitting
- Time 24.0h vs 24.01h → different keys → spurious CI widening
- Float arithmetic → nondeterministic grouping

SOLUTION:
- All doses converted to integer nanomolar (nM)
- All times converted to integer minutes (min)
- Single canonicalization function: no manual key construction
- Hashable, frozen dataclass: safe for dict keys

CONTRACT:
Two semantically identical conditions MUST collapse to the same canonical key.
No floats escape this module.

RESOLUTION CONSTANTS:
- DOSE_RESOLUTION_NM = 1 (1 nanomolar)
- TIME_RESOLUTION_MIN = 1 (1 minute)

ROUNDING SEMANTICS:
- Uses Python's built-in round() (banker's rounding / round-half-to-even)
- Deterministic across platforms and runs
- Example: 0.5 → 0, 1.5 → 2, 2.5 → 2
- If you need round-half-up, use Decimal.quantize() instead

Example:
    dose=1.000 µM → 1000 nM
    dose=1.001 µM → 1001 nM (distinct)
    dose=1.0005 µM → 1000 nM (banker's rounding)
    dose=1.0009 µM → 1001 nM

After this module, aggregation races are impossible.
"""

from dataclasses import dataclass
from typing import Optional

# Resolution constants: define minimum distinguishable differences
DOSE_RESOLUTION_NM: int = 1   # 1 nanomolar = 0.001 µM
TIME_RESOLUTION_MIN: int = 1  # 1 minute = 0.0167 hours


@dataclass(frozen=True)
class CanonicalCondition:
    """
    Immutable canonical condition key for aggregation.

    All experimental conditions collapse to this representation.
    Used as dictionary keys for grouping replicates.

    Fields are intentionally minimal and non-redundant:
    - cell_line: str (e.g., "A549")
    - compound_id: str (e.g., "tunicamycin", "DMSO")
    - dose_nM: int (integer nanomolar, no floats)
    - time_min: int (integer minutes, no floats)
    - assay: str (e.g., "cell_painting", "ldh_cytotoxicity")
    - position_class: Optional[str] (e.g., "edge", "center", None)

    Frozen and hashable → safe for dict keys.
    """

    cell_line: str
    compound_id: str
    dose_nM: int
    time_min: int
    assay: str
    position_class: Optional[str] = None

    def __post_init__(self):
        """Validate canonical fields."""
        # Doses and times must be non-negative integers
        if self.dose_nM < 0:
            raise ValueError(f"dose_nM must be non-negative, got {self.dose_nM}")
        if self.time_min < 0:
            raise ValueError(f"time_min must be non-negative, got {self.time_min}")

        # Ensure integer types (catch accidental floats)
        if not isinstance(self.dose_nM, int):
            raise TypeError(f"dose_nM must be int, got {type(self.dose_nM)}")
        if not isinstance(self.time_min, int):
            raise TypeError(f"time_min must be int, got {type(self.time_min)}")

    def to_dict(self):
        """Serialize to dict for logging/audit."""
        return {
            "cell_line": self.cell_line,
            "compound_id": self.compound_id,
            "dose_nM": self.dose_nM,
            "time_min": self.time_min,
            "assay": self.assay,
            "position_class": self.position_class,
        }

    def __str__(self):
        """Human-readable representation."""
        dose_uM = self.dose_nM / 1000.0
        time_h = self.time_min / 60.0
        pos = f"/{self.position_class}" if self.position_class else ""
        return (
            f"{self.cell_line}/{self.compound_id}@{dose_uM:.3f}µM/"
            f"{time_h:.1f}h/{self.assay}{pos}"
        )


def canonical_dose_uM(dose_uM: float) -> int:
    """
    Convert dose from micromolar (µM) to integer nanomolar (nM).

    Uses DOSE_RESOLUTION_NM for quantization (currently 1 nM).
    Rounding: Python's round() (banker's rounding / round-half-to-even).

    Args:
        dose_uM: Dose in micromolar (float, must be finite and non-negative)

    Returns:
        Dose in nanomolar (int), quantized to DOSE_RESOLUTION_NM

    Raises:
        ValueError: If dose is negative, NaN, or infinite

    Examples:
        1.000 µM → 1000 nM
        1.001 µM → 1001 nM
        1.0005 µM → 1000 nM (banker's rounding)
        1.0015 µM → 1002 nM (banker's rounding)
        0.0 µM → 0 nM
    """
    # Validation: reject invalid inputs
    if dose_uM < 0:
        raise ValueError(f"Dose must be non-negative, got {dose_uM} µM")

    import math
    if not math.isfinite(dose_uM):
        raise ValueError(f"Dose must be finite, got {dose_uM} µM")

    # Convert µM → nM, quantize to resolution
    dose_nM_raw = dose_uM * 1000.0
    dose_nM_quantized = round(dose_nM_raw / DOSE_RESOLUTION_NM) * DOSE_RESOLUTION_NM

    return int(dose_nM_quantized)


def canonical_time_h(time_h: float) -> int:
    """
    Convert time from hours (h) to integer minutes (min).

    Uses TIME_RESOLUTION_MIN for quantization (currently 1 minute).
    Rounding: Python's round() (banker's rounding / round-half-to-even).

    Args:
        time_h: Time in hours (float, must be finite and non-negative)

    Returns:
        Time in minutes (int), quantized to TIME_RESOLUTION_MIN

    Raises:
        ValueError: If time is negative, NaN, or infinite

    Examples:
        24.0 h → 1440 min
        24.01 h → 1441 min
        12.0 h → 720 min
        0.0 h → 0 min
        0.00833 h (30 sec) → 0 min (rounds down)
    """
    # Validation: reject invalid inputs
    if time_h < 0:
        raise ValueError(f"Time must be non-negative, got {time_h} h")

    import math
    if not math.isfinite(time_h):
        raise ValueError(f"Time must be finite, got {time_h} h")

    # Convert h → min, quantize to resolution
    time_min_raw = time_h * 60.0
    time_min_quantized = round(time_min_raw / TIME_RESOLUTION_MIN) * TIME_RESOLUTION_MIN

    return int(time_min_quantized)


def canonical_condition_key(
    *,
    cell_line: str,
    compound_id: str,
    dose_uM: float,
    time_h: float,
    assay: str,
    position_class: Optional[str] = None,
) -> CanonicalCondition:
    """
    Create canonical condition key from raw experimental parameters.

    This is the ONLY function that should be used to create condition keys.
    All aggregation must go through this.

    Args:
        cell_line: Cell line identifier (e.g., "A549")
        compound_id: Compound identifier (e.g., "tunicamycin", "DMSO")
        dose_uM: Dose in micromolar (float)
        time_h: Time in hours (float)
        assay: Assay type (e.g., "cell_painting")
        position_class: Optional position class (e.g., "edge", "center")

    Returns:
        CanonicalCondition with integer dose/time representations

    Example:
        >>> canonical_condition_key(
        ...     cell_line="A549",
        ...     compound_id="DMSO",
        ...     dose_uM=1.000,
        ...     time_h=24.0,
        ...     assay="cell_painting",
        ...     position_class="center"
        ... )
        CanonicalCondition(
            cell_line='A549',
            compound_id='DMSO',
            dose_nM=1000,
            time_min=1440,
            assay='cell_painting',
            position_class='center'
        )
    """
    return CanonicalCondition(
        cell_line=cell_line,
        compound_id=compound_id,
        dose_nM=canonical_dose_uM(dose_uM),
        time_min=canonical_time_h(time_h),
        assay=assay,
        position_class=position_class,
    )


def are_conditions_equivalent(
    dose1_uM: float,
    time1_h: float,
    dose2_uM: float,
    time2_h: float,
) -> bool:
    """
    Check if two raw conditions are equivalent after canonicalization.

    Useful for detecting near-duplicates before they cause aggregation issues.

    Args:
        dose1_uM, dose2_uM: Doses in micromolar
        time1_h, time2_h: Times in hours

    Returns:
        True if conditions collapse to same canonical representation

    Example:
        >>> are_conditions_equivalent(1.000, 24.0, 1.001, 24.0)
        False  # 1000 nM vs 1001 nM
        >>> are_conditions_equivalent(1.0000, 24.0, 1.00001, 24.0)
        True  # Both round to 1000 nM
    """
    dose1_nM = canonical_dose_uM(dose1_uM)
    dose2_nM = canonical_dose_uM(dose2_uM)
    time1_min = canonical_time_h(time1_h)
    time2_min = canonical_time_h(time2_h)

    return dose1_nM == dose2_nM and time1_min == time2_min
