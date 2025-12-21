"""
Canonical assay types.

This enum is the single source of truth for assay identities.
All legacy string variants must be normalized through from_string().
"""

from enum import Enum
from typing import Optional


class AssayType(Enum):
    """Canonical assay types with display names and normalization.

    Each member has:
    - Canonical internal name (enum value)
    - Display name for human-readable output
    - Normalization map via from_string() to handle legacy variants
    """

    # High-content imaging
    CELL_PAINTING = "cell_painting"

    # Scalar viability/toxicity
    LDH_CYTOTOXICITY = "ldh_cytotoxicity"

    # Single-cell transcriptomics
    SCRNA_SEQ = "scrna_seq"

    # Additional scalar readouts (used in run_context)
    ATP = "atp"
    UPR = "upr"
    TRAFFICKING = "trafficking"

    @property
    def display_name(self) -> str:
        """Human-readable display name."""
        _DISPLAY_NAMES = {
            AssayType.CELL_PAINTING: "Cell Painting",
            AssayType.LDH_CYTOTOXICITY: "LDH Cytotoxicity",
            AssayType.SCRNA_SEQ: "scRNA-seq",
            AssayType.ATP: "ATP",
            AssayType.UPR: "UPR",
            AssayType.TRAFFICKING: "Trafficking",
        }
        return _DISPLAY_NAMES[self]

    @property
    def method_name(self) -> str:
        """Method name in BiologicalVirtualMachine (e.g., 'cell_painting_assay')."""
        _METHOD_NAMES = {
            AssayType.CELL_PAINTING: "cell_painting_assay",
            AssayType.LDH_CYTOTOXICITY: "ldh_cytotoxicity_assay",
            AssayType.SCRNA_SEQ: "scrna_seq_assay",
            # Scalar assays don't have dedicated methods yet
            AssayType.ATP: "atp_assay",
            AssayType.UPR: "upr_assay",
            AssayType.TRAFFICKING: "trafficking_assay",
        }
        return _METHOD_NAMES[self]

    @classmethod
    def from_string(cls, s: str) -> "AssayType":
        """Normalize legacy string variants to canonical AssayType.

        This is the ONLY place where string normalization happens.
        All legacy code must go through this function.

        Args:
            s: Assay string (any legacy variant)

        Returns:
            Canonical AssayType

        Raises:
            ValueError: If string doesn't match any known variant

        Normalization map (case-insensitive):
        - "cell_painting", "cellpainting", "cell_paint" → CELL_PAINTING
        - "ldh_cytotoxicity", "ldh", "LDH" → LDH_CYTOTOXICITY
        - "scrna_seq", "scrna", "scRNA" → SCRNA_SEQ
        - "atp", "ATP" → ATP
        - "upr", "UPR" → UPR
        - "trafficking", "TRAFFICKING" → TRAFFICKING
        """
        # Normalize to lowercase for comparison
        s_lower = s.lower().strip()

        # Normalization table
        _NORMALIZATION_MAP = {
            # Cell Painting variants
            "cell_painting": cls.CELL_PAINTING,
            "cellpainting": cls.CELL_PAINTING,
            "cell_paint": cls.CELL_PAINTING,
            # LDH variants
            "ldh_cytotoxicity": cls.LDH_CYTOTOXICITY,
            "ldh": cls.LDH_CYTOTOXICITY,
            # scRNA-seq variants
            "scrna_seq": cls.SCRNA_SEQ,
            "scrna": cls.SCRNA_SEQ,
            "scrna-seq": cls.SCRNA_SEQ,
            # Scalar assays (case-insensitive)
            "atp": cls.ATP,
            "upr": cls.UPR,
            "trafficking": cls.TRAFFICKING,
        }

        if s_lower in _NORMALIZATION_MAP:
            return _NORMALIZATION_MAP[s_lower]

        # If not found, raise with helpful error
        valid_variants = list(_NORMALIZATION_MAP.keys())
        raise ValueError(
            f"Unknown assay string: '{s}'. "
            f"Valid variants (case-insensitive): {valid_variants}"
        )

    @classmethod
    def try_from_string(cls, s: str) -> Optional["AssayType"]:
        """Try to normalize string, return None if invalid.

        Use this when you want to handle unknown assays gracefully.
        """
        try:
            return cls.from_string(s)
        except ValueError:
            return None

    def __str__(self) -> str:
        """String representation uses display name."""
        return self.display_name

    def __repr__(self) -> str:
        """Repr shows enum member name."""
        return f"AssayType.{self.name}"
