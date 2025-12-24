"""
Assay Parameter Centralization

This module defines tunable assay constants that were previously scattered
as magic numbers. These are **confessed parameters** - design choices for
plausible realism, not derived from first principles or calibrated from data.

📖 **Documentation**: See docs/ASSUMPTIONS_AND_BOUNDARIES.md for:
- What changing these values affects
- Why these defaults were chosen
- Calibration strategies if validating against real data
- Enforced invariants vs. confessed parameters

Design principle: Enforce functional forms and bounds, not exact values.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AssayParams:
    """
    Centralized assay measurement parameters.

    These constants shape what the agent observes but are not
    claimed to be biologically accurate. They serve epistemic goals:
    preventing oracles, creating plausible measurement artifacts,
    and forcing robust inference.

    All parameters include validation bounds to prevent nonsense values.
    """

    # Cell Painting: Dead cell signal floor
    # Purpose: Prevents dead-cell dropout from being a perfect viability oracle
    # Formula: signal_intensity = CP_DEAD_SIGNAL_FLOOR + (1 - CP_DEAD_SIGNAL_FLOOR) * viability
    # Rationale: Dead cells retain some fluorescence (membrane fragments, debris)
    CP_DEAD_SIGNAL_FLOOR: float = 0.3  # 30% residual signal

    # LDH Viability: Death amplification cap
    # Purpose: Prevents LDH signal explosion near 100% death
    # Formula: amp = min(death_fraction / (1 - death_fraction), LDH_DEATH_AMPLIFICATION_CAP)
    # Rationale: Assay saturates at high death; cap prevents numerical instability
    LDH_DEATH_AMPLIFICATION_CAP: float = 10.0  # 10× maximum

    # LDH Viability: ATP signal floor
    # Purpose: Basal ATP from non-mitochondrial sources
    # Formula: atp_signal = max(ATP_SIGNAL_FLOOR, 1 - coeff * mito_dysfunction)
    # Rationale: Glycolysis provides ~30% of ATP even with mito failure
    ATP_SIGNAL_FLOOR: float = 0.3  # 30% basal ATP

    # Cell Painting: Segmentation yield loss coefficient
    # Purpose: Models how debris/dead cells reduce segmentation success
    # Formula: yield = 1.0 - SEGMENTATION_C_BASE * debris_load
    # Rationale: At 100% debris, lose ~80% of segmentable cells
    SEGMENTATION_C_BASE: float = 0.8  # 80% yield loss at full debris

    def __post_init__(self):
        """
        Validate parameters on construction.

        Enforces:
        - Floors must be in (0, 1) exclusive (0 = perfect oracle, 1 = no signal)
        - Caps must be > 1 (otherwise not actually capping)
        - Coefficients must be in reasonable ranges

        Raises:
            ValueError: If any parameter violates bounds
        """
        errors = []

        # Signal floors: must prevent oracles but allow measurement
        if not (0.0 < self.CP_DEAD_SIGNAL_FLOOR < 1.0):
            errors.append(
                f"CP_DEAD_SIGNAL_FLOOR must be in (0, 1), got {self.CP_DEAD_SIGNAL_FLOOR}. "
                "Zero would create viability oracle; one would create no-signal regime."
            )

        if not (0.0 < self.ATP_SIGNAL_FLOOR < 1.0):
            errors.append(
                f"ATP_SIGNAL_FLOOR must be in (0, 1), got {self.ATP_SIGNAL_FLOOR}. "
                "Zero would create mito dysfunction oracle; one would saturate signal."
            )

        # Amplification cap: must actually cap (> 1)
        if not (1.0 < self.LDH_DEATH_AMPLIFICATION_CAP < 100.0):
            errors.append(
                f"LDH_DEATH_AMPLIFICATION_CAP must be in (1, 100), got {self.LDH_DEATH_AMPLIFICATION_CAP}. "
                "Must be > 1 to cap amplification; < 100 to remain realistic."
            )

        # Segmentation coefficient: reasonable range for yield loss
        if not (0.0 <= self.SEGMENTATION_C_BASE <= 2.0):
            errors.append(
                f"SEGMENTATION_C_BASE must be in [0, 2], got {self.SEGMENTATION_C_BASE}. "
                "Zero = no debris effect; 2 = 200% loss (max plausible with amplification)."
            )

        if errors:
            raise ValueError(
                "AssayParams validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )


# Default instance used throughout codebase
# Override by constructing new AssayParams(...) with different values
DEFAULT_ASSAY_PARAMS = AssayParams()
